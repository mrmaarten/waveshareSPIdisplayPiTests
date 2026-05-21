"""
Install HyperPixel RTSP camera display on the Pi (starts on boot).

Pulls RTSP on the Pi with ffmpeg -> /dev/fb0 (800x480 bgra).
For tap + stream together (power save), use ssh_install_touch_rtsp_power.py instead.
Touch-to-toggle backlight only (hyperpixel-backlight-touch.service) stays independent.

Credentials and camera host are read from repo .env:
  RTSP_HOST, RTSP_PORT, RTSP_PATH, RTSP_USER, RTSP_PASS

Usage (from repo root):
  python ssh_install_rtsp_display.py
  python ssh_install_rtsp_display.py --no-start   # install only, do not start now
"""

from __future__ import annotations

import argparse
import shlex
from urllib.parse import quote

from env_config import PI_HOST, RTSP_HOST, RTSP_PASS, RTSP_PATH, RTSP_PORT, RTSP_USER
from pi_stream_common import (
    USER,
    connect,
    ensure_ffmpeg_on_pi,
    kill_pi_stream_processes,
    prepare_framebuffer,
    run,
    sudo,
)

HP_WIDTH = 800
HP_HEIGHT = 480
HP_PIX_FMT = "bgra"

ENV_PATH = "/etc/default/hyperpixel-rtsp"
SCRIPT_PATH = "/usr/local/bin/hyperpixel_rtsp_display.sh"
UNIT_PATH = "/etc/systemd/system/hyperpixel-rtsp-display.service"

DISPLAY_SCRIPT = """\
#!/bin/bash
set -euo pipefail
. /etc/default/hyperpixel-rtsp
exec ffmpeg -hide_banner -loglevel warning \\
  -rtsp_transport tcp -stimeout 5000000 \\
  -c:v h264_mmal \\
  -fflags nobuffer -flags low_delay \\
  -probesize 32 -analyzeduration 0 \\
  -i "$RTSP_URL" \\
  -vf "scale=${WIDTH}:${HEIGHT}" -pix_fmt "${PIX_FMT}" -an \\
  -f fbdev /dev/fb0
"""

SYSTEMD_UNIT = """\
[Unit]
Description=HyperPixel RTSP camera to framebuffer
After=network-online.target hyperpixel-init.service
Wants=network-online.target

[Service]
Type=simple
User=root
EnvironmentFile=-/etc/default/hyperpixel-rtsp
ExecStartPre=-/bin/systemctl stop display-manager
ExecStartPre=-/bin/chmod 666 /dev/fb0
ExecStart={script_path}
Restart=always
RestartSec=5
KillMode=mixed

[Install]
WantedBy=multi-user.target
"""


def build_rtsp_url() -> str:
    if not RTSP_USER:
        raise ValueError("RTSP_USER is empty — set it in .env (e.g. RTSP_USER=Camera)")
    if not RTSP_PASS:
        raise ValueError("RTSP_PASS is empty — set it in .env")
    user = quote(RTSP_USER, safe="")
    password = quote(RTSP_PASS, safe="")
    path = RTSP_PATH if RTSP_PATH.startswith("/") else f"/{RTSP_PATH}"
    return f"rtsp://{user}:{password}@{RTSP_HOST}:{RTSP_PORT}{path}"


def env_file_content(rtsp_url: str) -> str:
    # Single-quoted values; URL is percent-encoded so no shell metacharacters.
    safe_url = rtsp_url.replace("'", "'\"'\"'")
    return (
        f"RTSP_URL='{safe_url}'\n"
        f"WIDTH={HP_WIDTH}\n"
        f"HEIGHT={HP_HEIGHT}\n"
        f"PIX_FMT={HP_PIX_FMT}\n"
    )


def upload_text(ssh, remote_path: str, content: str) -> None:
    sftp = ssh.open_sftp()
    try:
        with sftp.open(remote_path, "w") as remote_file:
            remote_file.write(content)
    finally:
        sftp.close()


def deploy(ssh) -> None:
    rtsp_url = build_rtsp_url()
    print(f"RTSP target: rtsp://{RTSP_USER}:***@{RTSP_HOST}:{RTSP_PORT}{RTSP_PATH}")

    upload_text(ssh, "/tmp/hyperpixel-rtsp.env", env_file_content(rtsp_url))
    sudo(ssh, f"mv /tmp/hyperpixel-rtsp.env {ENV_PATH}")
    sudo(ssh, f"chown root:root {ENV_PATH}")
    sudo(ssh, f"chmod 600 {ENV_PATH}")

    upload_text(ssh, "/tmp/hyperpixel_rtsp_display.sh", DISPLAY_SCRIPT)
    sudo(ssh, f"mv /tmp/hyperpixel_rtsp_display.sh {SCRIPT_PATH}")
    sudo(ssh, f"chown root:root {SCRIPT_PATH}")
    sudo(ssh, f"chmod 755 {SCRIPT_PATH}")

    unit = SYSTEMD_UNIT.format(script_path=SCRIPT_PATH)
    upload_text(ssh, "/tmp/hyperpixel-rtsp-display.service", unit)
    sudo(ssh, f"mv /tmp/hyperpixel-rtsp-display.service {UNIT_PATH}")
    sudo(ssh, f"chown root:root {UNIT_PATH}")
    sudo(ssh, f"chmod 644 {UNIT_PATH}")


def enable_and_start(ssh, start_now: bool) -> None:
    sudo(ssh, "systemctl daemon-reload")
    sudo(ssh, "systemctl enable hyperpixel-rtsp-display.service")
    if not start_now:
        print("Service enabled for boot (not started now).")
        return
    kill_pi_stream_processes(ssh)
    prepare_framebuffer(ssh)
    sudo(ssh, "systemctl restart hyperpixel-rtsp-display.service")
    run(ssh, "sleep 3")
    out, _, code = run(ssh, "systemctl is-active hyperpixel-rtsp-display.service")
    if code != 0 or "active" not in out:
        run(ssh, "journalctl -u hyperpixel-rtsp-display.service -n 30 --no-pager")
        raise RuntimeError("hyperpixel-rtsp-display.service failed to start")
    print("hyperpixel-rtsp-display.service is active.")
    run(ssh, "journalctl -u hyperpixel-rtsp-display.service -n 8 --no-pager")
    run(ssh, "pgrep -af 'ffmpeg.*rtsp' || true")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Pi RTSP -> HyperPixel fb0 on boot")
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Install and enable only; do not restart the service now",
    )
    args = parser.parse_args()

    ssh = connect()
    print("SSH connected.")
    try:
        ensure_ffmpeg_on_pi(ssh)
        deploy(ssh)
        enable_and_start(ssh, start_now=not args.no_start)
        print("\nDone.")
        print("  Boot: hyperpixel-rtsp-display.service (camera on screen)")
        print("  Touch: hyperpixel-backlight-touch.service (tap toggles backlight)")
        print(f"\nCheck: ssh {USER}@{shlex.quote(PI_HOST)}")
        print("  systemctl status hyperpixel-rtsp-display.service")
        print("  journalctl -u hyperpixel-rtsp-display.service -f")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
