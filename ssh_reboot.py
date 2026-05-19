import paramiko
import time

from env_config import PI_HOST, PI_PASS, PI_USER

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)

print("Rebooting...")
try:
    stdin, stdout, stderr = ssh.exec_command(f'echo "{PI_PASS}" | sudo -S reboot 2>&1', timeout=5)
    print(stdout.read().decode())
except:
    pass
ssh.close()
print("Reboot command sent. Waiting 30s for Pi to come back...")

time.sleep(30)

# Try to reconnect
for attempt in range(10):
    try:
        print(f"Connection attempt {attempt+1}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(PI_HOST, username=PI_USER, password=PI_PASS, timeout=10)
        print("Connected!")
        
        def run(cmd):
            print(f'>>> {cmd}')
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
            out = stdout.read().decode()
            err = stderr.read().decode()
            if out: print(out.strip())
            if err: print(f'STDERR: {err.strip()}')
            print()
            return out.strip()
        
        run('ls /dev/fb*')
        run('cat /sys/class/graphics/fb0/name')
        run('cat /sys/class/graphics/fb0/virtual_size')
        run('ls /sys/class/graphics/')
        run('dmesg | grep -E "fbtft|ili9486|fb|spi" | tail -20')
        run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')
        
        ssh.close()
        break
    except Exception as e:
        print(f"  Not ready yet: {e}")
        time.sleep(5)
