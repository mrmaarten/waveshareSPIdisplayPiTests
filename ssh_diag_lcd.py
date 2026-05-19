import paramiko
import sys

from env_config import PI_HOST, PI_PASS, PI_USER

HOST = PI_HOST
USER = PI_USER
PASS = PI_PASS

commands = [
    ("Active overlays", "sudo dtoverlay -l 2>&1"),
    ("SPI devices", "ls -la /dev/spi* 2>/dev/null || echo NO_SPI"),
    ("Framebuffers", "ls -la /dev/fb* 2>/dev/null || echo NO_FB"),
    ("DRI devices", "ls -la /dev/dri/* 2>/dev/null || echo NO_DRI"),
    ("Graphics class", "ls -la /sys/class/graphics/"),
    ("FB0 name", "cat /sys/class/graphics/fb0/name 2>/dev/null || echo N/A"),
    ("FB0 size", "cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo N/A"),
    ("FB1 name", "cat /sys/class/graphics/fb1/name 2>/dev/null || echo N/A"),
    ("FB1 size", "cat /sys/class/graphics/fb1/virtual_size 2>/dev/null || echo N/A"),
    ("Panel.bin", "ls -la /lib/firmware/panel.bin 2>/dev/null || echo NOT_FOUND"),
    ("DMESG display", 'dmesg | grep -Ei "mipi|panel|ili|fb|drm|spi|gpio|fbtft" | tail -40'),
    ("Backlight class", "ls /sys/class/backlight/ 2>/dev/null || echo EMPTY"),
    ("Loaded modules", 'lsmod | grep -Ei "spi|drm|fb|mipi|panel|fbtft" || echo NONE'),
    ("ili9486.txt contents", "cat ~/panel-mipi-dbi/ili9486.txt 2>/dev/null || echo NOT_FOUND"),
    ("SPI debug", "ls -la /sys/bus/spi/devices/ 2>/dev/null"),
    ("SPI device details", "cat /sys/bus/spi/devices/spi0.0/modalias 2>/dev/null || echo N/A"),
]

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    print(f"Connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PASS, timeout=10)
    print("Connected!\n")

    for label, cmd in commands:
        print(f"--- {label} ---")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err and "sudo" not in err.lower():
            print(f"  [stderr] {err}")
        print()

except Exception as e:
    print(f"Connection failed: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    client.close()
