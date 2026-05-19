import paramiko
import time

HOST = "videopi.local"
USER = "maarten"
PASS = " "

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting...")
ssh.connect(HOST, username=USER, password=PASS, timeout=10)

stdin, stdout, stderr = ssh.exec_command('cat /boot/firmware/cmdline.txt')
cmdline = stdout.read().decode().strip()
print(f"Old cmdline: {cmdline}")

if 'fbcon=map:1' in cmdline:
    cmdline = cmdline.replace('fbcon=map:1', 'fbcon=map:0')
    print(f"New cmdline: {cmdline}")
    cmd = f'echo "{PASS}" | sudo -S sh -c \'echo "{cmdline}" > /boot/firmware/cmdline.txt\''
    ssh.exec_command(cmd)
    time.sleep(1)

print("Rebooting...")
ssh.exec_command(f'echo "{PASS}" | sudo -S reboot')
ssh.close()
print("Done.")
