import paramiko
import time
import socket
import sys

HOST = "videopi.local"
USER = "maarten"
PASS = " "
WIDTH = 480
HEIGHT = 320

def run_cmd(ssh, cmd):
    print(f"=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err and " " not in err and "sudo" not in err:
        err_safe = err.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
        print(f"STDERR: {err_safe}")
    return out

def run_sudo_cmd(ssh, cmd):
    return run_cmd(ssh, f"echo '{PASS}' | sudo -S {cmd}")

def wait_for_ssh(host, port=22, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.close()
            return True
        except (socket.timeout, socket.error, ConnectionRefusedError):
            time.sleep(2)
    return False

def rgb565(r: int, g: int, b: int) -> bytes:
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return bytes((v & 0xFF, (v >> 8) & 0xFF))

def build_pattern() -> bytes:
    bar_colors = [
        (255, 0, 0),      # red
        (0, 255, 0),      # green
        (0, 0, 255),      # blue
        (255, 255, 0),    # yellow
        (255, 0, 255),    # magenta
        (0, 255, 255),    # cyan
    ]
    bar_w = WIDTH // len(bar_colors)
    buf = bytearray(WIDTH * HEIGHT * 2)
    idx = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            bar = min(x // bar_w, len(bar_colors) - 1)
            r, g, b = bar_colors[bar]
            if x < 30 and y < 30:
                r, g, b = (255, 0, 0)
            elif x >= WIDTH - 30 and y < 30:
                r, g, b = (0, 255, 0)
            elif x < 30 and y >= HEIGHT - 30:
                r, g, b = (0, 0, 255)
            elif x >= WIDTH - 30 and y >= HEIGHT - 30:
                r, g, b = (255, 255, 255)
            pix = rgb565(r, g, b)
            buf[idx] = pix[0]
            buf[idx + 1] = pix[1]
            idx += 2
    return bytes(buf)

def connect():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)
    print("Connected.")
    return ssh

def diagnose(ssh):
    print("\n--- DIAGNOSTICS ---")
    run_cmd(ssh, "cat /boot/firmware/config.txt | grep -E '^dtoverlay|^dtparam|^enable_uart'")
    run_cmd(ssh, "cat /boot/firmware/cmdline.txt")
    run_cmd(ssh, "cat /sys/class/graphics/fb0/blank 2>/dev/null || echo 'No fb0'")
    run_cmd(ssh, "cat /sys/class/graphics/fb0/name 2>/dev/null || echo 'No fb0'")
    run_cmd(ssh, "systemctl get-default")
    run_cmd(ssh, "systemctl is-active display-manager || true")
    run_cmd(ssh, "cat /sys/module/kernel/parameters/consoleblank 2>/dev/null || true")
    run_cmd(ssh, "dmesg | grep -i fb_ili9486 | tail -n 5")

def fix_cmdline(ssh):
    print("\n--- FIX CMDLINE ---")
    cmdline = run_cmd(ssh, "cat /boot/firmware/cmdline.txt")
    if "consoleblank=0" not in cmdline:
        print("Adding consoleblank=0 to cmdline.txt")
        run_sudo_cmd(ssh, "cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.bak")
        new_cmdline = cmdline.strip() + " consoleblank=0"
        run_sudo_cmd(ssh, f"sh -c 'echo \"{new_cmdline}\" > /boot/firmware/cmdline.txt'")
    else:
        print("consoleblank=0 already in cmdline.txt")

def setup_service(ssh):
    print("\n--- SETUP SYSTEMD SERVICE ---")
    service_content = """[Unit]
Description=Unblank SPI LCD framebuffer
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo 0 > /sys/class/graphics/fb0/blank'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
    # Upload service file
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/lcd-unblank.service", "w") as f:
        f.write(service_content)
    sftp.close()

    run_sudo_cmd(ssh, "mv /tmp/lcd-unblank.service /etc/systemd/system/lcd-unblank.service")
    run_sudo_cmd(ssh, "chown root:root /etc/systemd/system/lcd-unblank.service")
    run_sudo_cmd(ssh, "chmod 644 /etc/systemd/system/lcd-unblank.service")
    
    run_sudo_cmd(ssh, "systemctl daemon-reload")
    run_sudo_cmd(ssh, "systemctl enable lcd-unblank.service")
    run_sudo_cmd(ssh, "systemctl start lcd-unblank.service")

def write_test_pattern(ssh):
    print("\n--- WRITE TEST PATTERN ---")
    pattern = build_pattern()
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/fb_pattern.bin", "wb") as f:
        f.write(pattern)
    sftp.close()
    run_sudo_cmd(ssh, "sh -c 'cat /tmp/fb_pattern.bin > /dev/fb0'")
    run_cmd(ssh, "cat /sys/class/graphics/fb0/blank")

def main():
    ssh = connect()
    
    # Step 1: Diagnose
    diagnose(ssh)
    
    # Step 2: Fix cmdline
    fix_cmdline(ssh)
    
    # Step 3: Create systemd service
    setup_service(ssh)
    
    print("\n--- REBOOTING ---")
    try:
        run_sudo_cmd(ssh, "reboot")
    except Exception as e:
        print(f"Reboot command issued (exception expected: {e})")
    ssh.close()
    
    print("Waiting 10s before checking ping...")
    time.sleep(10)
    print("Waiting for Pi to boot (SSH port open)...")
    if wait_for_ssh(HOST):
        print("SSH is back! Waiting another 15s for full boot...")
        time.sleep(15)
        
        # Reconnect
        ssh2 = connect()
        print("\n--- VERIFY AFTER REBOOT ---")
        run_cmd(ssh2, "cat /sys/class/graphics/fb0/blank")
        run_cmd(ssh2, "cat /sys/module/kernel/parameters/consoleblank 2>/dev/null || true")
        run_cmd(ssh2, "systemctl status lcd-unblank.service")
        
        write_test_pattern(ssh2)
        ssh2.close()
        
        print("\nSUCCESS: Verification complete.")
    else:
        print("\nTIMEOUT waiting for Pi to come back online.")

if __name__ == "__main__":
    main()
