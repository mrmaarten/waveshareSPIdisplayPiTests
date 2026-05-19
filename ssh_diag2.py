import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('videopi.local', username='maarten', password=' ', timeout=10)

commands = [
    # DRM connector status
    'cat /sys/class/drm/card1-SPI-1/status',
    'cat /sys/class/drm/card1-SPI-1/enabled',
    'cat /sys/class/drm/card1-SPI-1/modes',
    'cat /sys/class/drm/card1-SPI-1/dpms',

    # Check fbcon mapping
    'cat /sys/class/graphics/fbcon/cursor_blink',
    'cat /sys/class/vtconsole/vtcon0/bind 2>/dev/null',
    'cat /sys/class/vtconsole/vtcon1/bind 2>/dev/null',
    'cat /sys/class/vtconsole/vtcon0/name 2>/dev/null',
    'cat /sys/class/vtconsole/vtcon1/name 2>/dev/null',

    # Kernel command line
    'cat /proc/cmdline',

    # Check backlight state
    'cat /sys/class/backlight/backlight_gpio/brightness',
    'cat /sys/class/backlight/backlight_gpio/max_brightness',
    'cat /sys/class/backlight/backlight_gpio/bl_power',

    # Try to check if DRM thinks the display is enabled
    'sudo dmesg | grep -i "enable\|disable\|mode\|connect" | grep -i "drm\|panel\|spi" | tail -15',

    # Check if there's a display manager running
    'systemctl is-active display-manager 2>/dev/null || echo "no display manager"',
    'ps aux | grep -E "Xorg|wayland|weston|labwc|wayfire" | grep -v grep',

    # Write test pattern and check
    'dd if=/dev/urandom of=/dev/fb0 bs=4096 count=75 2>&1',
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
