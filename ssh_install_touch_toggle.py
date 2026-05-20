"""
Install HyperPixel touch-to-toggle backlight on the Pi.

For tap + RTSP stream together (power save), use ssh_install_touch_rtsp_power.py instead.
Deploys a small I2C touch listener (works in CLI; does not need uinput/X11).
Also fixes hyperpixel-touch.service boot failure when /dev/uinput is not ready.

Usage:
  python ssh_install_touch_toggle.py
"""

from __future__ import annotations

from pi_stream_common import PASS, USER, connect, run, sudo

HP_TOUCH_PATH = "/usr/bin/hyperpixel-touch"
HP_TOUCH_BACKUP = "/usr/bin/hyperpixel-touch.bak"
PATCH_MARKER = "backlight-toggle-patch"

BACKLIGHT_TOUCH_SCRIPT = '''\
#!/usr/bin/env python3
"""HyperPixel I2C touch -> backlight toggle (CLI, no uinput/desktop)."""
import time

import RPi.GPIO as gpio
import smbus
from rpi_backlight import Backlight

INT = 27
ADDR = 0x5c
DEBOUNCE_SEC = 0.5

backlight = Backlight()


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

print("HyperPixel backlight touch listener running (I2C).")


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
                        backlight.power = not backlight.power
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

BACKLIGHT_TOUCH_UNIT = """\
[Unit]
Description=HyperPixel touch to toggle backlight (I2C)
After=hyperpixel-init.service multi-user.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 {script_path}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

UINPUT_TMPFILES = "f /dev/uinput 0666 root root -\n"

HYPERPIXEL_TOUCH_DROPIN = """\
[Service]
ExecStartPre=/sbin/modprobe uinput
ExecStartPre=/bin/sh -c 'chmod 666 /dev/uinput 2>/dev/null || true'
"""


def sudo_quiet(ssh, cmd: str, timeout: int = 120) -> int:
    escaped = cmd.replace("\\", "\\\\").replace('"', '\\"')
    full = f'echo "{PASS}" | sudo -S bash -lc "{escaped}"'
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(full, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    if out.strip():
        print(out.rstrip())
    return stdout.channel.recv_exit_status()


def upload_text(ssh, remote_path: str, content: str) -> None:
    sftp = ssh.open_sftp()
    try:
        with sftp.open(remote_path, "w") as remote_file:
            remote_file.write(content)
    finally:
        sftp.close()


def ensure_dependencies(ssh) -> None:
    _, _, code = run(ssh, 'python3 -c "import RPi.GPIO, smbus; from rpi_backlight import Backlight"')
    if code == 0:
        print("python3 GPIO/smbus/rpi_backlight OK.")
        return
    print("Installing python3 deps on Pi...")
    sudo(
        ssh,
        "DEBIAN_FRONTEND=noninteractive apt-get update -qq && "
        "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip python3-rpi.gpio python3-smbus && "
        "pip3 install rpi_backlight",
        timeout=600,
    )
    _, _, code = run(ssh, 'python3 -c "import RPi.GPIO, smbus; from rpi_backlight import Backlight"')
    if code != 0:
        raise RuntimeError("Failed to install touch/backlight dependencies on Pi.")


def deploy_uinput_boot_fix(ssh) -> None:
    print("Installing persistent /dev/uinput permissions for boot...")
    upload_text(ssh, "/tmp/uinput-perms.conf", UINPUT_TMPFILES)
    sudo_quiet(ssh, "mv /tmp/uinput-perms.conf /etc/tmpfiles.d/uinput-perms.conf")
    sudo_quiet(ssh, "systemd-tmpfiles --create /etc/tmpfiles.d/uinput-perms.conf")
    upload_text(ssh, "/tmp/hyperpixel-touch-override.conf", HYPERPIXEL_TOUCH_DROPIN)
    sudo_quiet(ssh, "mkdir -p /etc/systemd/system/hyperpixel-touch.service.d")
    sudo_quiet(
        ssh,
        "mv /tmp/hyperpixel-touch-override.conf "
        "/etc/systemd/system/hyperpixel-touch.service.d/override.conf",
    )


def deploy_backlight_touch_service(ssh, script_path: str) -> None:
    print(f"Writing {script_path}...")
    upload_text(ssh, "/tmp/hyperpixel_backlight_touch.py", BACKLIGHT_TOUCH_SCRIPT)
    run(ssh, f"mv /tmp/hyperpixel_backlight_touch.py {script_path}")
    run(ssh, f"chmod 755 {script_path}")

    unit_path = "/etc/systemd/system/hyperpixel-backlight-touch.service"
    unit_content = BACKLIGHT_TOUCH_UNIT.format(script_path=script_path)
    upload_text(ssh, "/tmp/hyperpixel-backlight-touch.service", unit_content)
    sudo_quiet(ssh, f"mv /tmp/hyperpixel-backlight-touch.service {unit_path}")
    sudo_quiet(ssh, f"chown root:root {unit_path}")
    sudo_quiet(ssh, f"chmod 644 {unit_path}")


def restore_hyperpixel_touch_if_patched(ssh) -> None:
    """Avoid double-toggle if an earlier install patched hyperpixel-touch."""
    out, _, _ = run(ssh, f"grep -c {PATCH_MARKER} {HP_TOUCH_PATH} 2>/dev/null || echo 0")
    if out.strip() == "0":
        return
    print("Restoring stock hyperpixel-touch (backlight handled by new service)...")
    sudo_quiet(ssh, f"test -f {HP_TOUCH_BACKUP} && cp {HP_TOUCH_BACKUP} {HP_TOUCH_PATH}")


def disable_old_touchtoggle(ssh) -> None:
    sudo_quiet(ssh, "systemctl stop touchtoggle.service 2>/dev/null || true")
    sudo_quiet(ssh, "systemctl disable touchtoggle.service 2>/dev/null || true")


def enable_services(ssh) -> None:
    print("Enabling hyperpixel-backlight-touch.service...")
    sudo_quiet(ssh, "systemctl daemon-reload")
    sudo_quiet(ssh, "systemctl enable hyperpixel-backlight-touch.service")
    sudo_quiet(ssh, "systemctl restart hyperpixel-backlight-touch.service")
    out, _, code = run(ssh, "systemctl is-active hyperpixel-backlight-touch.service")
    if code != 0 or "active" not in out:
        run(ssh, "journalctl -u hyperpixel-backlight-touch.service -n 25 --no-pager")
        raise RuntimeError("hyperpixel-backlight-touch.service failed to start")
    print("hyperpixel-backlight-touch.service is active.")

    sudo_quiet(ssh, "systemctl reset-failed hyperpixel-touch.service 2>/dev/null || true")
    sudo_quiet(ssh, "systemctl restart hyperpixel-touch.service 2>/dev/null || true")
    run(ssh, "systemctl is-active hyperpixel-backlight-touch.service")
    run(ssh, "journalctl -u hyperpixel-backlight-touch.service -n 5 --no-pager")


def main() -> None:
    script_path = f"/home/{USER}/hyperpixel_backlight_touch.py"
    ssh = connect()
    print("SSH connected.")
    try:
        ensure_dependencies(ssh)
        deploy_uinput_boot_fix(ssh)
        deploy_backlight_touch_service(ssh, script_path)
        restore_hyperpixel_touch_if_patched(ssh)
        disable_old_touchtoggle(ssh)
        enable_services(ssh)
        print("\nDone. Tap the HyperPixel screen to toggle the backlight.")
        print("Service: hyperpixel-backlight-touch.service (I2C, CLI-safe, starts on boot)")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
