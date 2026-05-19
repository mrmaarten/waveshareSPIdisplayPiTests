import paramiko
import time

from env_config import PI_HOST, PI_PASS, PI_USER

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

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
    return run(f'echo "{PI_PASS}" | sudo -S bash -c \'{cmd}\' 2>&1')

# Step 1: Read current config.txt
print("=" * 60)
print("STEP 1: Reading current config.txt")
print("=" * 60)
current = run('cat /boot/firmware/config.txt')

# Step 2: Build new config.txt
# Replace the mipi-dbi-spi lines with fbtft + ili9486
print("=" * 60)
print("STEP 2: Writing new config.txt")
print("=" * 60)

new_config = current

# Remove the old mipi-dbi-spi overlay lines
lines_to_remove = [
    'dtoverlay=mipi-dbi-spi,spi0-0,speed=32000000,write-only',
    'dtparam=width=480,height=320',
    'dtparam=reset-gpio=27,dc-gpio=25',
    'dtparam=backlight-gpio=24',
]
for line in lines_to_remove:
    new_config = new_config.replace(line, '')

# Remove any double blank lines that result
while '\n\n\n' in new_config:
    new_config = new_config.replace('\n\n\n', '\n\n')

# Remove duplicate [all] if present
new_config = new_config.replace('[all]\n[all]', '[all]')

# Add fbtft overlay at the end
# Using ili9486 controller with Waveshare 3.5B pinout
# dc_pin=25, reset_pin=27, led_pin=24 (backlight)
# speed=16000000 (16MHz - safe for Pi 3B+)
fbtft_config = """dtoverlay=fbtft,spi0-0,ili9486,dc_pin=25,reset_pin=27,led_pin=24,speed=16000000,rotate=90,fps=30
"""

if 'fbtft' not in new_config:
    new_config = new_config.rstrip() + '\n' + fbtft_config

print("New config.txt tail:")
print('\n'.join(new_config.strip().split('\n')[-15:]))
print()

# Write the new config
sudo(f'cp /boot/firmware/config.txt /boot/firmware/config.txt.bak')
print("Backed up config.txt to config.txt.bak")

# Write new config via heredoc
escaped = new_config.replace("'", "'\\''")
sudo(f"cat > /boot/firmware/config.txt << 'ENDOFCONFIG'\n{new_config}\nENDOFCONFIG")

# Verify it was written
print("=" * 60)
print("STEP 3: Verifying new config.txt")
print("=" * 60)
run('tail -20 /boot/firmware/config.txt')

ssh.close()
print("\nDone! Config updated. Ready to reboot.")
