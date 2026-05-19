import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('videopi.local', username='maarten', password=' ', timeout=10)

def run(cmd):
    print(f'>>> {cmd}')
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print(f'STDERR: {err.strip()}')
    print()
    return out.strip()

def sudo(cmd):
    return run(f'echo " " | sudo -S {cmd} 2>&1')

# Step 1: Restore from backup
print("Restoring from backup...")
sudo('cp /boot/firmware/config.txt.bak /boot/firmware/config.txt')

# Step 2: Verify restored
print("Verifying restore:")
run('tail -10 /boot/firmware/config.txt')

# Step 3: Write a Python script ON the Pi to modify config.txt
modify_script = r'''
import re

with open('/boot/firmware/config.txt', 'r') as f:
    content = f.read()

# Remove the old mipi-dbi-spi overlay lines
lines = content.split('\n')
new_lines = []
skip_lines = {
    'dtoverlay=mipi-dbi-spi,spi0-0,speed=32000000,write-only',
    'dtparam=width=480,height=320',
    'dtparam=reset-gpio=27,dc-gpio=25',
    'dtparam=backlight-gpio=24',
}
seen_all = False
for line in lines:
    stripped = line.strip()
    if stripped in skip_lines:
        continue
    # Remove duplicate [all]
    if stripped == '[all]':
        if seen_all:
            continue
        seen_all = True
    new_lines.append(line)

content = '\n'.join(new_lines)

# Remove trailing whitespace/newlines and add fbtft overlay
content = content.rstrip()
content += '\ndtoverlay=fbtft,spi0-0,ili9486,dc_pin=25,reset_pin=27,led_pin=24,speed=16000000,rotate=90,fps=30\n'

with open('/boot/firmware/config.txt', 'w') as f:
    f.write(content)

print('Config updated successfully')
'''

# Write the modify script to the Pi
sftp = ssh.open_sftp()
with sftp.open('/tmp/modify_config.py', 'w') as f:
    f.write(modify_script)
sftp.close()

# Run it with sudo
sudo('python3 /tmp/modify_config.py')

# Verify
print("=" * 60)
print("Final config.txt (last 20 lines):")
print("=" * 60)
run('tail -20 /boot/firmware/config.txt')

ssh.close()
