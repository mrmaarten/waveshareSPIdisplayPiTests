import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('videopi.local', username='maarten', password=' ', timeout=10)

commands = [
    'uname -a',
    'cat /sys/class/graphics/fb0/name',
    'cat /sys/class/graphics/fb0/virtual_size',
    'ls /sys/class/graphics/',
    'ls /dev/fb*',
    'dmesg | grep -E "mipi|panel|fb|spi" | tail -20',
    'tail -30 /boot/firmware/config.txt',
    'ls -la /lib/firmware/panel.bin',
    'cat /proc/device-tree/model',
    'cat /sys/class/drm/card*/device/driver/module/refcnt 2>/dev/null; ls /sys/class/drm/',
    'ls /sys/class/backlight/',
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
