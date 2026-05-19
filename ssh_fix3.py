import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('videopi.local', username='maarten', password=' ', timeout=10)

def run(cmd):
    print(f'=== {cmd} ===')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print(f'STDERR: {err.strip()}')
    print()
    return out.strip()

# Record SPI bytes before a framebuffer write
before = run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')

# Write a solid red screen (RGB565 red = 0xF800)
run('python3 -c "import sys; sys.stdout.buffer.write(b\'\\x00\\xf8\' * (480*320))" > /dev/fb0 2>&1')
time.sleep(2)

# Record SPI bytes after
after = run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')

try:
    diff = int(after) - int(before)
    print(f'>>> SPI bytes transferred during fb write: {diff}')
    print(f'>>> Expected for one full frame (480*320*2): {480*320*2}')
    print()
except:
    pass

# Check fbtft availability
run('modinfo fbtft 2>&1 | head -5')
run('modinfo fb_ili9486 2>&1 | head -5')
run('ls /boot/firmware/overlays/ | grep fbtft')

# Clone LCD-show if not present and check for .dtbo files
run('test -d ~/LCD-show || git clone https://github.com/waveshare/LCD-show.git ~/LCD-show 2>&1 | tail -3')
run('find ~/LCD-show -name "*35*" -o -name "*ili9486*" 2>/dev/null | head -20')

# Check if the ILI9486 is actually a 16-bit bus width chip (Waveshare uses shift registers)
# This would explain why panel-mipi-dbi (8-bit DBI Type C) doesn't work
run('cat ~/panel-mipi-dbi/ili9486.txt')

# Check kernel log for any SPI errors
run('dmesg | grep -i "spi\\|error" | grep -iv "usb\\|mmc\\|eth" | tail -15')

ssh.close()
