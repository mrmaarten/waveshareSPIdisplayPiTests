"""Check current Pi display state and list config backups."""
from pi_stream_common import connect, run, sudo

ssh = connect()
print("=== config.txt ===")
run(ssh, "cat /boot/firmware/config.txt")
print("\n=== cmdline.txt ===")
run(ssh, "cat /boot/firmware/cmdline.txt")
print("\n=== config backups ===")
run(ssh, "ls -lt /boot/firmware/config.txt* | head -10")
print("\n=== cmdline backups ===")
run(ssh, "ls -lt /boot/firmware/cmdline.txt* | head -10")
print("\n=== fb devices ===")
run(ssh, "ls /dev/fb* 2>/dev/null || echo no_fb")
run(ssh, "cat /sys/class/graphics/fb0/name 2>/dev/null || echo fb0_missing")
print("\n=== dmesg ===")
run(ssh, "dmesg | grep -Ei 'fbtft|ili9486|fb0|fbcon|spi0' | tail -20")
ssh.close()
