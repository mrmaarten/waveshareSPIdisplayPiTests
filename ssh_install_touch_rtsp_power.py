"""
Install HyperPixel touch + RTSP unified power toggle on the Pi.

Boot: camera stream ON, backlight ON (same as split install).
Tap: toggles backlight AND starts/stops hyperpixel-rtsp-display.service together.

Disables hyperpixel-backlight-touch.service (legacy backlight-only touch).
Keeps hyperpixel-rtsp-display.service enabled on boot.

Credentials from repo .env (RTSP_*). Pi SSH from PI_*.

Usage (from repo root):
  python ssh_install_touch_rtsp_power.py
  python ssh_install_touch_rtsp_power.py --no-start
"""

from __future__ import annotations

import argparse
import shlex

from env_config import PI_HOST
from pi_stream_common import USER, connect, ensure_ffmpeg_on_pi, run, sudo
from ssh_install_rtsp_display import deploy as deploy_rtsp, enable_and_start as enable_rtsp
from ssh_install_touch_toggle import (
    disable_old_touchtoggle,
    ensure_dependencies,
    deploy_uinput_boot_fix,
    restore_hyperpixel_touch_if_patched,
    sudo_quiet,
    upload_text,
)

TOUCH_DISPLAY_POWER_SCRIPT = '''\
#!/usr/bin/env python3
"""HyperPixel I2C touch -> backlight + RTSP stream together (power save)."""
import subprocess
import time

import RPi.GPIO as gpio
import smbus
from rpi_backlight import Backlight

RTSP_UNIT = "hyperpixel-rtsp-display.service"
INT = 27
ADDR = 0x5c
DEBOUNCE_SEC = 0.5
BOOT_SYNC_RETRIES = 10
BOOT_SYNC_DELAY_SEC = 1.0
WIDTH = 800
HEIGHT = 480
# BGRA soft yellow — RGB ~(255, 242, 210)
IDLE_PIXEL = bytes((210, 242, 255, 255))
RTSP_STOP_WAIT_SEC = 3.0
RTSP_STOP_POLL_SEC = 0.1

backlight = Backlight()
display_on = True


def rtsp_active() -> bool:
    return (
        subprocess.run(
            ["systemctl", "is-active", "--quiet", RTSP_UNIT],
            check=False,
        ).returncode
        == 0
    )


def set_rtsp(active: bool) -> None:
    action = "start" if active else "stop"
    subprocess.run(["systemctl", action, RTSP_UNIT], check=False)


def fill_framebuffer_idle() -> None:
    frame = IDLE_PIXEL * (WIDTH * HEIGHT)
    with open("/dev/fb0", "wb") as fb:
        fb.write(frame)


def wait_rtsp_stopped() -> None:
    deadline = time.monotonic() + RTSP_STOP_WAIT_SEC
    while time.monotonic() < deadline:
        if not rtsp_active():
            return
        time.sleep(RTSP_STOP_POLL_SEC)


def set_display_on(on: bool) -> None:
    global display_on
    display_on = on
    if on:
        fill_framebuffer_idle()
        backlight.power = True
        set_rtsp(True)
    else:
        set_rtsp(False)
        wait_rtsp_stopped()
        fill_framebuffer_idle()
        backlight.power = False
    state = "ON" if on else "OFF"
    print(f"Display {state} (backlight + {RTSP_UNIT})")


def sync_display_on_at_boot() -> None:
    """Boot policy: screen on + stream running."""
    global display_on
    display_on = True
    backlight.power = True
    for attempt in range(BOOT_SYNC_RETRIES):
        if rtsp_active():
            print("Boot sync: RTSP display active.")
            return
        subprocess.run(["systemctl", "start", RTSP_UNIT], check=False)
        time.sleep(BOOT_SYNC_DELAY_SEC)
    print(
        "Warning: RTSP service not active after boot sync "
        f"({BOOT_SYNC_RETRIES} attempts)"
    )


def open_touch_bus():
    for bus_no in (11, 3, 1, 0):
        try:
            return smbus.SMBus(bus_no)
        except FileNotFoundError:
            continue
    raise RuntimeError("No I2C bus found for HyperPixel touch (tried 11, 3, 1, 0)")


bus = open_touch_bus()
bus.write_byte_data(ADDR, 0x6E, 0b00001110)

gpio.setmode(gpio.BCM)
gpio.setwarnings(False)
gpio.setup(INT, gpio.IN)

touch_active = False
last_toggle_time = 0.0

sync_display_on_at_boot()
print("HyperPixel touch display power listener running (I2C).")


def touch_pressed():
    data = bus.read_i2c_block_data(ADDR, 0x40, 8)
    x1 = data[0] | (data[4] << 8)
    y1 = data[1] | (data[5] << 8)
    return bool(x1 and y1)


while True:
    try:
        if gpio.input(INT):
            if touch_pressed():
                if not touch_active:
                    now = time.time()
                    if now - last_toggle_time >= DEBOUNCE_SEC:
                        set_display_on(not display_on)
                        last_toggle_time = now
                    touch_active = True
            else:
                touch_active = False
        else:
            touch_active = False
    except IOError:
        touch_active = False
    time.sleep(0.003)
'''

TOUCH_DISPLAY_POWER_UNIT = """\
[Unit]
Description=HyperPixel touch toggles backlight and RTSP display (power save)
After=network-online.target hyperpixel-init.service
Wants=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 {script_path}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

POWER_SERVICE = "hyperpixel-touch-display-power.service"
LEGACY_TOUCH_SERVICE = "hyperpixel-backlight-touch.service"


def deploy_touch_display_power(ssh, script_path: str) -> None:
    print(f"Writing {script_path}...")
    upload_text(ssh, "/tmp/hyperpixel_touch_display_power.py", TOUCH_DISPLAY_POWER_SCRIPT)
    run(ssh, f"mv /tmp/hyperpixel_touch_display_power.py {script_path}")
    run(ssh, f"chmod 755 {script_path}")

    unit_path = f"/etc/systemd/system/{POWER_SERVICE}"
    unit_content = TOUCH_DISPLAY_POWER_UNIT.format(script_path=script_path)
    upload_text(ssh, f"/tmp/{POWER_SERVICE}", unit_content)
    sudo_quiet(ssh, f"mv /tmp/{POWER_SERVICE} {unit_path}")
    sudo_quiet(ssh, f"chown root:root {unit_path}")
    sudo_quiet(ssh, f"chmod 644 {unit_path}")


def disable_legacy_backlight_touch(ssh) -> None:
    print(f"Disabling {LEGACY_TOUCH_SERVICE}...")
    sudo_quiet(ssh, f"systemctl stop {LEGACY_TOUCH_SERVICE} 2>/dev/null || true")
    sudo_quiet(ssh, f"systemctl disable {LEGACY_TOUCH_SERVICE} 2>/dev/null || true")


def enable_power_touch_service(ssh) -> None:
    print(f"Enabling {POWER_SERVICE}...")
    sudo_quiet(ssh, "systemctl daemon-reload")
    sudo_quiet(ssh, f"systemctl enable {POWER_SERVICE}")
    sudo_quiet(ssh, f"systemctl restart {POWER_SERVICE}")
    out, _, code = run(ssh, f"systemctl is-active {POWER_SERVICE}")
    if code != 0 or "active" not in out:
        run(ssh, f"journalctl -u {POWER_SERVICE} -n 25 --no-pager")
        raise RuntimeError(f"{POWER_SERVICE} failed to start")
    print(f"{POWER_SERVICE} is active.")
    run(ssh, f"journalctl -u {POWER_SERVICE} -n 5 --no-pager")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install Pi RTSP + touch unified power toggle (boot on, tap off/on)"
    )
    parser.add_argument(
        "--no-start",
        action="store_true",
        help="Install and enable RTSP for boot only; do not restart RTSP now",
    )
    args = parser.parse_args()

    script_path = f"/home/{USER}/hyperpixel_touch_display_power.py"
    ssh = connect()
    print("SSH connected.")
    try:
        ensure_dependencies(ssh)
        deploy_uinput_boot_fix(ssh)
        ensure_ffmpeg_on_pi(ssh)
        deploy_rtsp(ssh)
        disable_legacy_backlight_touch(ssh)
        restore_hyperpixel_touch_if_patched(ssh)
        disable_old_touchtoggle(ssh)
        deploy_touch_display_power(ssh, script_path)
        enable_rtsp(ssh, start_now=not args.no_start)
        enable_power_touch_service(ssh)
        print("\nDone.")
        print("  Boot: RTSP on + backlight on")
        print("  Tap: toggles backlight and RTSP stream together")
        print(f"  Service: {POWER_SERVICE}")
        print(f"  Legacy touch disabled: {LEGACY_TOUCH_SERVICE}")
        print(f"\nCheck: ssh {USER}@{shlex.quote(PI_HOST)}")
        print(f"  systemctl status {POWER_SERVICE} hyperpixel-rtsp-display.service")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
