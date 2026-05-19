"""Shared helpers for Pi video stream and display test scripts."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import paramiko

HOST = "videopi.local"
HOST_FALLBACK_IP = "192.168.0.22"
USER = "maarten"
PASS = ""
STREAM_PORT = 5000
WIDTH = 480
HEIGHT = 320
BACKLIGHT_GPIO = 24

# Corrects photo-negative colors when generic fbtft ili9486 init is wrong.
# Set False after switching to waveshare35b-v2 overlay (see ssh_fix_display_invert.py).
FFMPEG_NEGATE_COLORS = False
PIX_FMT = "rgb565le"


def pi_ffmpeg_vf(negate: bool | None = None) -> str:
    """Build Pi-side video filter: scale to panel size, optional color negate."""
    if negate is None:
        negate = FFMPEG_NEGATE_COLORS
    vf = f"scale={WIDTH}:{HEIGHT}"
    if negate:
        vf += ",negate"
    return vf


SCRIPT_DIR = Path(__file__).resolve().parent
TEST_VIDEO = SCRIPT_DIR / "test2.mp4"


def find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    # Winget Gyan.FFmpeg common install location
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    if local.is_dir():
        for candidate in local.glob("Gyan.FFmpeg*/ffmpeg*/bin/ffmpeg.exe"):
            if candidate.is_file():
                return str(candidate)
    raise FileNotFoundError(
        "ffmpeg not found on PATH. Install with: winget install Gyan.FFmpeg"
    )


def connect(host: str | None = None) -> paramiko.SSHClient:
    candidates: list[str] = []
    if host:
        candidates.append(host)
    candidates.append(HOST)
    if HOST_FALLBACK_IP not in candidates:
        candidates.append(HOST_FALLBACK_IP)
    try:
        ip = resolve_pi_host()
        if ip not in candidates:
            candidates.append(ip)
    except Exception:
        pass

    last_error: Exception | None = None
    for target in candidates:
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(target, username=USER, password=PASS, timeout=15)
            if target != HOST:
                print(f"SSH connected via {target}")
            return client
        except Exception as exc:
            last_error = exc
    raise last_error or OSError("SSH connect failed")


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[str, str, int]:
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(err.rstrip())
    return out, err, code


def sudo(ssh: paramiko.SSHClient, cmd: str, timeout: int = 120) -> tuple[str, str, int]:
    escaped = cmd.replace("\\", "\\\\").replace('"', '\\"')
    return run(ssh, f'echo "{PASS}" | sudo -S bash -lc "{escaped}"', timeout=timeout)


def ensure_ffmpeg_on_pi(ssh: paramiko.SSHClient) -> None:
    _, _, code = run(ssh, "command -v ffmpeg")
    if code == 0:
        print("ffmpeg already installed on Pi.")
        return
    print("Installing ffmpeg on Pi (may take a few minutes)...")
    sudo(
        ssh,
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg",
        timeout=600,
    )


def ensure_vlc_on_pi(ssh: paramiko.SSHClient) -> None:
    _, _, code = run(ssh, "command -v cvlc")
    if code == 0:
        run(ssh, "cvlc --version 2>/dev/null | head -1 || true")
        print("VLC (cvlc) already installed on Pi.")
        return
    print("Installing VLC on Pi (may take a few minutes)...")
    sudo(
        ssh,
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq vlc",
        timeout=600,
    )
    run(ssh, "command -v cvlc && cvlc --version 2>/dev/null | head -1 || echo cvlc_missing")


def prepare_framebuffer(ssh: paramiko.SSHClient) -> None:
    sudo(ssh, "systemctl stop display-manager 2>/dev/null || true")
    sudo(ssh, "chmod 666 /dev/fb0 2>/dev/null || true")
    run(ssh, "test -c /dev/fb0 && echo fb0_ok || echo fb0_missing")


def kill_pi_stream_processes(ssh: paramiko.SSHClient) -> None:
    sudo(ssh, "pkill -f 'ffmpeg.*tcp://' 2>/dev/null || true")
    sudo(ssh, "pkill -f 'ffmpeg.*fbdev' 2>/dev/null || true")
    sudo(ssh, "pkill -f 'vlc.*tcp://' 2>/dev/null || true")
    sudo(ssh, "pkill -f 'vlc.*udp://' 2>/dev/null || true")
    sudo(ssh, "pkill -x vlc 2>/dev/null || true")
    sudo(ssh, "pkill -x cvlc 2>/dev/null || true")
    time.sleep(0.5)


def get_pc_lan_ip(pi_host: str = HOST) -> str:
    """Return this PC's LAN IP as seen when connecting to the Pi."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect((pi_host, STREAM_PORT))
        return sock.getsockname()[0]
    finally:
        sock.close()


def pi_listener_cmd(negate: bool | None = None) -> str:
    return (
        f"ffmpeg -hide_banner -loglevel warning "
        f"-i tcp://0.0.0.0:{STREAM_PORT}?listen=1 "
        f"-vf {pi_ffmpeg_vf(negate)} -pix_fmt {PIX_FMT} "
        f"-f fbdev /dev/fb0"
    )


def pi_vlc_client_cmd(server_ip: str, inverted: bool = False) -> str:
    """cvlc TCP client -> SPI framebuffer (VLC cannot listen on tcp:// reliably)."""
    parts = [
        "env FRAMEBUFFER=/dev/fb0",
        "cvlc --intf dummy --no-video-title-show --no-osd --no-audio",
        f"--network-caching=400 --width={WIDTH} --height={HEIGHT}",
        "-V fb --fbdev=/dev/fb0 --no-fb-tty --fb-chroma=RV16",
    ]
    if inverted:
        parts.append("--video-filter=invert")
    parts.append(f"tcp://{server_ip}:{STREAM_PORT}")
    return " ".join(parts)


def pi_client_cmd(server_ip: str, negate: bool | None = None) -> str:
    return (
        f"ffmpeg -hide_banner -loglevel warning "
        f"-i tcp://{server_ip}:{STREAM_PORT} "
        f"-vf {pi_ffmpeg_vf(negate)} -pix_fmt {PIX_FMT} "
        f"-f fbdev /dev/fb0"
    )


def resolve_negate_colors(
    invert: bool,
    no_invert: bool,
    inverted: bool = False,
) -> bool | None:
    """Map CLI flags to pi_ffmpeg_vf negate argument (None = use FFMPEG_NEGATE_COLORS)."""
    if no_invert and (invert or inverted):
        raise ValueError("--no-invert cannot be combined with --invert or --inverted")
    if invert or inverted:
        return True
    if no_invert:
        return False
    return None


def pc_push_cmd(ffmpeg: str, video: Path, target_host: str | None = None) -> list[str]:
    if target_host is None:
        target_host = resolve_pi_host()
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-stream_loop",
        "-1",
        "-re",
        "-i",
        str(video),
        "-vf",
        f"scale={WIDTH}:{HEIGHT}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "25",
        "-f",
        "mpegts",
        f"tcp://{target_host}:{STREAM_PORT}",
    ]


def pc_listen_cmd(ffmpeg: str, video: Path) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-stream_loop",
        "-1",
        "-re",
        "-i",
        str(video),
        "-vf",
        f"scale={WIDTH}:{HEIGHT}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        "25",
        "-f",
        "mpegts",
        f"tcp://0.0.0.0:{STREAM_PORT}?listen=1",
    ]


def start_pi_background_ffmpeg(ssh: paramiko.SSHClient, ffmpeg_cmd: str, log_name: str) -> None:
    start_pi_background_player(ssh, ffmpeg_cmd, log_name, label="ffmpeg")


def start_pi_background_player(
    ssh: paramiko.SSHClient,
    player_cmd: str,
    log_name: str,
    *,
    label: str = "player",
) -> None:
    kill_pi_stream_processes(ssh)
    bg = f"nohup {player_cmd} > /tmp/{log_name} 2>&1 & echo $!"
    out, _, _ = run(ssh, bg)
    pid = out.strip().splitlines()[-1] if out.strip() else "?"
    print(f"Pi {label} started (pid {pid}). Log: /tmp/{log_name}")


def tail_pi_log(ssh: paramiko.SSHClient, log_name: str, lines: int = 15) -> None:
    run(ssh, f"tail -n {lines} /tmp/{log_name} 2>/dev/null || true")


def run_local_ffmpeg(cmd: list[str]) -> subprocess.Popen:
    print("\n>>> " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    return subprocess.Popen(cmd)


def wait_for_pi_tcp_listener(ssh: paramiko.SSHClient, port: int = STREAM_PORT, timeout: float = 30.0) -> bool:
    """Wait until Pi ffmpeg is listening without opening a client connection (that breaks ffmpeg)."""
    deadline = time.time() + timeout
    pattern = f":{port}"
    while time.time() < deadline:
        out, _, code = run(ssh, f"ss -tln 2>/dev/null | grep '{pattern}' || true")
        if pattern in out and "LISTEN" in out:
            return True
        time.sleep(0.5)
    return False


def resolve_pi_host() -> str:
    """Prefer IPv4 address over .local hostname (avoids Windows/ffmpeg IPv6 issues)."""
    try:
        infos = socket.getaddrinfo(HOST, STREAM_PORT, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except OSError:
        pass
    return HOST


def assert_test_video() -> Path:
    if not TEST_VIDEO.is_file():
        raise FileNotFoundError(f"Test video not found: {TEST_VIDEO}")
    return TEST_VIDEO


def try_allow_windows_firewall_port(port: int = STREAM_PORT) -> bool:
    """Allow inbound TCP on port for Pi pull tests (may require admin)."""
    import subprocess as sp

    rule = f"AnalogVideoWall-PiStream-{port}"
    try:
        sp.run(
            [
                "netsh",
                "advfirewall",
                "firewall",
                "add",
                "rule",
                f"name={rule}",
                "dir=in",
                "action=allow",
                "protocol=TCP",
                f"localport={port}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        return True
    except FileNotFoundError:
        return False


def wait_for_local_tcp_listener(port: int = STREAM_PORT, timeout: float = 30.0) -> bool:
    """Wait for a local TCP listener without connecting (connecting breaks ffmpeg listen mode)."""
    import subprocess as sp

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            out = sp.check_output(["netstat", "-an"], text=True, errors="replace")
            if f"0.0.0.0:{port}" in out and "LISTENING" in out:
                return True
            if f"[::]:{port}" in out and "LISTENING" in out:
                return True
        except (sp.CalledProcessError, FileNotFoundError):
            pass
        time.sleep(0.5)
    return False
