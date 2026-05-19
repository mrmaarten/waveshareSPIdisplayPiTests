"""
Fix photo-negative colors on Waveshare 3.5\" SPI display.

Switches /boot/firmware/config.txt from generic fbtft ili9486 to the
Waveshare waveshare35b-v2 overlay (correct ILI9486 init), reboots, and
draws the quadrant test pattern.

Usage:
  python ssh_fix_display_invert.py
  python ssh_fix_display_invert.py --overlay fbtft-bgr   # fallback: add bgr to fbtft
"""

from __future__ import annotations

import argparse
import time

from env_config import PI_USER
from pi_stream_common import HOST_FALLBACK_IP, connect, run, sudo


WAVESHARE_OVERLAY_SRC = f"/home/{PI_USER}/LCD-show/waveshare35c-overlay.dtb"
WAVESHARE_OVERLAY_DST = "/boot/firmware/overlays/waveshare35c.dtbo"
ROTATE = 90


def build_config_waveshare(current: str) -> str:
    filtered: list[str] = []
    for line in current.splitlines():
        s = line.strip()
        if s.startswith("dtoverlay=fbtft"):
            continue
        if s.startswith("dtoverlay=mipi-dbi-spi"):
            continue
        if s.startswith("dtoverlay=waveshare35c"):
            continue
        filtered.append(line)

    text = "\n".join(filtered).rstrip() + "\n"
    if "dtparam=spi=on" not in text:
        text += "dtparam=spi=on\n"
    text += f"dtoverlay=waveshare35c:rotate={ROTATE}\n"
    return text


def build_config_fbtft_bgr(current: str) -> str:
    filtered: list[str] = []
    for line in current.splitlines():
        s = line.strip()
        if s.startswith("dtoverlay=waveshare35c"):
            continue
        if s.startswith("dtoverlay=mipi-dbi-spi"):
            continue
        if s.startswith("dtoverlay=fbtft"):
            continue
        filtered.append(line)

    text = "\n".join(filtered).rstrip() + "\n"
    if "dtparam=spi=on" not in text:
        text += "dtparam=spi=on\n"
    text += (
        "dtoverlay=fbtft,spi0-0,ili9486,regwidth=16,buswidth=8,"
        f"dc_pin=25,reset_pin=27,led_pin=24,speed=16000000,rotate={ROTATE},fps=30,bgr\n"
    )
    return text


def reconnect(max_attempts: int = 20, delay: float = 4.0):
    time.sleep(25)
    for i in range(max_attempts):
        print(f"Reconnect attempt {i + 1}/{max_attempts}...")
        for host in (None, HOST_FALLBACK_IP):
            try:
                return connect(host)
            except Exception as exc:
                print(f"  {host or 'default'}: {exc}")
        time.sleep(delay)
    return None


def draw_test_pattern() -> None:
    import subprocess
    import sys
    from pathlib import Path

    pattern_script = Path(__file__).resolve().parent / "ssh_show_test_pattern.py"
    print("\nDrawing quadrant test pattern on /dev/fb0...")
    subprocess.run([sys.executable, str(pattern_script)], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix inverted Waveshare display colors")
    parser.add_argument(
        "--overlay",
        choices=("waveshare", "fbtft-bgr"),
        default="waveshare",
        help="waveshare=waveshare35b-v2 overlay (default); fbtft-bgr=add bgr to fbtft line",
    )
    parser.add_argument("--no-reboot", action="store_true", help="Patch config only, do not reboot")
    parser.add_argument("--no-pattern", action="store_true", help="Skip test pattern after reboot")
    args = parser.parse_args()

    ssh = connect()
    print("Connected.")

    if args.overlay == "waveshare":
        run(ssh, f"test -f {WAVESHARE_OVERLAY_SRC} && echo overlay_src_ok || echo overlay_src_missing")
        sudo(
            ssh,
            f"cp {WAVESHARE_OVERLAY_SRC} {WAVESHARE_OVERLAY_DST}",
        )
        run(ssh, f"ls -la {WAVESHARE_OVERLAY_DST}")

    sudo(ssh, "cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_invert_fix.bak")
    _, _, _ = run(ssh, "cat /boot/firmware/config.txt")
    stdin, stdout, _ = ssh.exec_command("cat /boot/firmware/config.txt")
    current = stdout.read().decode("utf-8", errors="replace")

    if args.overlay == "waveshare":
        new_cfg = build_config_waveshare(current)
        print(f"\nApplying waveshare35c:rotate={ROTATE} overlay.")
    else:
        new_cfg = build_config_fbtft_bgr(current)
        print("\nApplying fbtft ili9486 with bgr flag.")

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/config.txt.invert_fix", "w") as fh:
        fh.write(new_cfg)
    sftp.close()

    sudo(ssh, "cp /tmp/config.txt.invert_fix /boot/firmware/config.txt")
    run(ssh, "tail -25 /boot/firmware/config.txt")

    if args.no_reboot:
        print("\nConfig updated. Reboot the Pi to apply: sudo reboot")
        ssh.close()
        return

    print("\nRebooting Pi...")
    try:
        sudo(ssh, "reboot", timeout=5)
    except Exception:
        pass
    ssh.close()

    ssh2 = reconnect()
    if ssh2 is None:
        print("Could not reconnect after reboot.")
        return

    run(ssh2, "cat /sys/class/graphics/fb0/name 2>/dev/null || true")
    run(ssh2, "cat /sys/class/graphics/fb0/rotate 2>/dev/null || true")
    run(ssh2, "dmesg | grep -Ei 'waveshare|ili9486|fbtft|spi0.0|fb0' | tail -30")
    ssh2.close()

    if not args.no_pattern:
        draw_test_pattern()

    print(
        "\nDone. Check the screen: console should not be photo-negative; "
        "test pattern corners should be red/green/blue/white."
    )
    print(
        "If colors are correct, set FFMPEG_NEGATE_COLORS = False in pi_stream_common.py "
        "and re-run video stream."
    )


if __name__ == "__main__":
    main()
