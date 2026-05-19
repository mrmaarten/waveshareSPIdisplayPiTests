"""Revert config.txt to pre_invert_fix.bak (waveshare35b-v2, working display)."""
from pi_stream_common import connect, run, sudo

ssh = connect()
print("=== Current config tail ===")
run(ssh, "tail -5 /boot/firmware/config.txt")
print("\n=== Backup we're reverting to ===")
run(ssh, "tail -5 /boot/firmware/config.txt.pre_invert_fix.bak")
print("\n=== Restoring pre_invert_fix.bak ===")
sudo(ssh, "cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_revert.bak")
sudo(ssh, "cp /boot/firmware/config.txt.pre_invert_fix.bak /boot/firmware/config.txt")
run(ssh, "tail -10 /boot/firmware/config.txt")
print("\n=== cmdline.txt ===")
run(ssh, "cat /boot/firmware/cmdline.txt")
print("\nRebooting...")
try:
    sudo(ssh, "reboot", timeout=5)
except Exception:
    pass
ssh.close()

import time
time.sleep(30)

for i in range(20):
    print(f"Reconnect {i+1}/20...")
    try:
        ssh2 = connect()
        print("Connected!")
        run(ssh2, "cat /sys/class/graphics/fb0/name 2>/dev/null || echo fb0_missing")
        run(ssh2, "dmesg | grep -Ei 'fbtft|ili9486|fb0|fbcon|spi0' | tail -15")
        run(ssh2, "tail -5 /boot/firmware/config.txt")
        ssh2.close()
        break
    except Exception as e:
        print(f"  {e}")
        time.sleep(4)
