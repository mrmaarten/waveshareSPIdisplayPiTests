import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('videopi.local', username='maarten', password=' ', timeout=10)

def run(cmd, sudo=False):
    print(f'=== {cmd} ===')
    if sudo:
        full_cmd = f'echo " " | sudo -S bash -c \'{cmd}\' 2>&1'
    else:
        full_cmd = cmd
    stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=30)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out: print(out.strip())
    if err: print(f'STDERR: {err.strip()}')
    print()
    return out.strip()

# Install modetest
run('sudo apt-get install -y libdrm-tests 2>&1 | tail -5', sudo=True)

# Check SPI transfer stats
run('cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || echo "no stats"')
run('cat /sys/bus/spi/devices/spi0.0/statistics/transfers 2>/dev/null || echo "no stats"')

# Use modetest to list connectors and CRTCs for card1
run('modetest -M panel-mipi-dbi -c 2>&1 | head -30')
run('modetest -M panel-mipi-dbi -p 2>&1 | head -30')

# Try modetest with test pattern on the SPI connector
# First get the connector and CRTC IDs
run('modetest -M panel-mipi-dbi -c 2>&1')

ssh.close()
