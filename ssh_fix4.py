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

# Look at Waveshare's config for the 35b-v2
run('cat ~/LCD-show/boot/config-35b-v2.txt-90')
print('---')
run('cat ~/LCD-show/boot/config-35b-v2.txt-270')

# Check the overlay file
run('ls -la ~/LCD-show/waveshare35b-v2-overlay.dtb')

# Check what the fbtft overlay accepts
run('dtoverlay -h fbtft')

# Also check if there are other 35b configs
run('ls ~/LCD-show/boot/ | grep 35b')

# Let's also look at what Waveshare's install script does
run('head -100 ~/LCD-show/LCD35B-V2-show')

ssh.close()
