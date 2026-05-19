import paramiko
import time

from env_config import PI_HOST, PI_PASS, PI_USER

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

def run(cmd):
    print(f'=== {cmd} ===')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print(f'STDERR: {err.strip()}')
    print()
    return out.strip()

# Force a test pattern via modetest on the SPI panel
# Connector 34, CRTC 37, mode 480x320
run('modetest -M panel-mipi-dbi -s 34@37:480x320 -d 2>&1 | head -20')
time.sleep(2)

# Record SPI bytes before and after a framebuffer write
run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')
run('dd if=/dev/urandom of=/dev/fb0 bs=307200 count=1 2>&1')
time.sleep(1)
run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')

# Check what Waveshare LCD-show has available
run('ls ~/LCD-show/*.dtb 2>/dev/null; ls ~/LCD-show/*.dtbo 2>/dev/null; echo "---"; ls ~/LCD-show/waveshare35* 2>/dev/null || echo "LCD-show not cloned yet"')

# Check if fbtft is available as a kernel module
run('modinfo fbtft 2>&1 | head -5')
run('modinfo fb_ili9486 2>&1 | head -5')

# Check available fbtft overlays
run('ls /boot/firmware/overlays/ | grep fbtft 2>/dev/null || echo "no fbtft overlays"')

# Check piscreen or other generic SPI fb overlays
run('ls /boot/firmware/overlays/ | grep -E "piscreen|pitft|sainsmart|tinylcd" 2>/dev/null || echo "none found"')

ssh.close()
