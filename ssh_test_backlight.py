"""
Toggle Waveshare SPI display backlight (GPIO 24) off then on via SSH.

Usage:
  python ssh_test_backlight.py [--off-seconds 3]
"""

from __future__ import annotations

import argparse
import time

from pi_stream_common import BACKLIGHT_GPIO, connect, run, sudo


def try_pinctrl(ssh, gpio: int, level: str) -> bool:
    """level: 'dl' (off) or 'dh' (on)"""
    _, err, code = run(ssh, f"pinctrl set {gpio} op {level}")
    return code == 0


def try_sysfs(ssh, gpio: int, value: int) -> bool:
    sudo(ssh, f"sh -c 'echo {gpio} > /sys/class/gpio/export 2>/dev/null || true'")
    sudo(ssh, f"sh -c 'echo out > /sys/class/gpio/gpio{gpio}/direction'")
    _, _, code = sudo(ssh, f"sh -c 'echo {value} > /sys/class/gpio/gpio{gpio}/value'")
    return code == 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Test Waveshare backlight on GPIO 24")
    parser.add_argument(
        "--off-seconds",
        type=float,
        default=3.0,
        help="Seconds to keep backlight off before turning on (default: 3)",
    )
    args = parser.parse_args()

    gpio = BACKLIGHT_GPIO
    ssh = connect()
    print(f"Connected. Testing backlight on GPIO {gpio}.\n")

    method = None

    print("=== Backlight OFF ===")
    if try_pinctrl(ssh, gpio, "dl"):
        method = "pinctrl"
        print("Used pinctrl (output low). Screen should be dark.")
    elif try_sysfs(ssh, gpio, 0):
        method = "sysfs"
        print("Used sysfs GPIO (value 0). Screen should be dark.")
    else:
        print("Failed to turn backlight off with pinctrl and sysfs.")
        ssh.close()
        return

    print(f"Waiting {args.off_seconds}s...")
    time.sleep(args.off_seconds)

    print("\n=== Backlight ON ===")
    if method == "pinctrl":
        ok = try_pinctrl(ssh, gpio, "dh")
    else:
        ok = try_sysfs(ssh, gpio, 1)

    if ok:
        print("Backlight ON. Screen should be visible again.")
    else:
        print("Failed to turn backlight back on.")

    run(ssh, f"pinctrl get {gpio} 2>/dev/null || cat /sys/class/gpio/gpio{gpio}/value 2>/dev/null || true")
    ssh.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
