import paramiko

from env_config import PI_HOST, PI_PASS, PI_USER

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

commands = [
    # Check if modetest/libdrm-tests is available
    'which modetest 2>/dev/null || echo "modetest not found"',

    # Check fb0 details
    'fbset -fb /dev/fb0 2>/dev/null || echo "fbset not available"',

    # Check deferred IO settings
    'ls /sys/class/graphics/fb0/ 2>/dev/null',

    # Check what card1 exposes
    'ls /sys/class/drm/card1/',

    # Look at connector details
    'find /sys/class/drm/card1-SPI-1/ -type f -exec sh -c \'echo "--- {}:" && cat {} 2>/dev/null\' \\;',

    # Check if fb_defio is in use (dirty tracking for fbdev)
    'cat /sys/module/drm/parameters/fbdev_emulation 2>/dev/null || echo "param not found"',
    'cat /sys/module/drm_kms_helper/parameters/fbdev_emulation 2>/dev/null || echo "param not found"',

    # Check SPI speed and device
    'ls /sys/bus/spi/devices/',
    'cat /sys/bus/spi/devices/spi0.0/modalias 2>/dev/null',
    'cat /sys/bus/spi/devices/spi0.0/of_node/compatible 2>/dev/null',

    # Install and use modetest
    'dpkg -l | grep libdrm-tests 2>/dev/null || echo "libdrm-tests not installed"',
    
    # Try Python3 + PIL to write to fb
    'python3 -c "import struct; data = b\'\\xff\\x00\' * (480*320); open(\'/dev/fb0\',\'wb\').write(data)" 2>&1',
]

for cmd in commands:
    print(f'=== {cmd} ===')
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print(f'STDERR: {err.strip()}')
    print()

ssh.close()
