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

# Record SPI bytes before
before = run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')

# Write solid RED to screen (RGB565: red = 0xF800, little-endian = 0x00 0xF8)
print("Writing solid RED to screen...")
run('python3 -c "f=open(\'/dev/fb0\',\'wb\'); f.write(b\'\\x00\\xf8\' * (480*320)); f.close()"')
time.sleep(2)

# Record SPI bytes after
after = run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')
try:
    diff = int(after) - int(before)
    print(f'>>> SPI bytes transferred: {diff} (expected ~307200 for one frame)')
    print()
except:
    pass

# Also write random noise to be very visible
print("Now writing random noise...")
before2 = run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')
run('dd if=/dev/urandom of=/dev/fb0 bs=307200 count=1 2>&1')
time.sleep(2)
after2 = run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx')
try:
    diff2 = int(after2) - int(before2)
    print(f'>>> SPI bytes transferred: {diff2} (expected ~307200 for one frame)')
except:
    pass

ssh.close()
print("\nDone! Check the screen - do you see red and then random noise?")
