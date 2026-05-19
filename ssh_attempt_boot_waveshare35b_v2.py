import time
import paramiko

HOST = "videopi.local"
USER = "maarten"
PASS = " "


def connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)
    return ssh


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 40) -> str:
    print(f"\n=== {cmd} ===")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    return out


def sudo(ssh: paramiko.SSHClient, cmd: str, timeout: int = 40) -> str:
    return run(ssh, f"echo '{PASS}' | sudo -S bash -lc \"{cmd}\"", timeout=timeout)


def main() -> None:
    ssh = connect()
    print("Connected. Preparing boot overlay switch attempt.")

    # Ensure overlay file exists in firmware overlays folder.
    run(ssh, "ls -la /home/maarten/LCD-show/waveshare35b-v2-overlay.dtb")
    sudo(
        ssh,
        "cp /home/maarten/LCD-show/waveshare35b-v2-overlay.dtb /boot/firmware/overlays/waveshare35b-v2.dtbo",
    )
    run(ssh, "ls -la /boot/firmware/overlays/waveshare35b-v2.dtbo")

    # Backup config and read current config.
    sudo(ssh, "cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_waveshare_test.bak")
    config_now = run(ssh, "cat /boot/firmware/config.txt")

    # Build test config:
    # - remove fbtft overlay line(s)
    # - keep dtparam=spi=on
    # - add waveshare35b-v2 overlay in [all]
    lines = config_now.splitlines()
    filtered = []
    for line in lines:
        s = line.strip()
        if s.startswith("dtoverlay=fbtft"):
            continue
        if s.startswith("dtoverlay=mipi-dbi-spi"):
            continue
        filtered.append(line)

    text = "\n".join(filtered).rstrip() + "\n"
    if "dtparam=spi=on" not in text:
        text += "dtparam=spi=on\n"
    if "dtoverlay=waveshare35b-v2" not in text:
        text += "dtoverlay=waveshare35b-v2:rotate=90\n"

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/config.txt.waveshare_test", "w") as fh:
        fh.write(text)
    sftp.close()

    sudo(ssh, "cp /tmp/config.txt.waveshare_test /boot/firmware/config.txt")
    run(ssh, "tail -40 /boot/firmware/config.txt")

    # Reboot
    print("\nRebooting now...")
    try:
        sudo(ssh, "reboot", timeout=5)
    except Exception:
        pass
    ssh.close()

    # Reconnect loop
    time.sleep(25)
    re = None
    for i in range(18):
        try:
            print(f"Reconnect attempt {i + 1}/18...")
            re = connect()
            print("Reconnected.")
            break
        except Exception as exc:
            print(f"Not ready yet: {exc}")
            time.sleep(5)

    if re is None:
        print("Failed to reconnect after reboot.")
        return

    # Post-reboot diagnostics
    run(re, "uname -a")
    run(re, "ls -la /dev/fb* 2>/dev/null || echo NO_FB")
    run(re, "ls -la /dev/spi* 2>/dev/null || echo NO_SPI")
    run(re, "for f in /sys/class/graphics/fb*; do echo \"== $f ==\"; cat $f/name 2>/dev/null; cat $f/virtual_size 2>/dev/null; done")
    run(re, "dmesg | grep -Ei 'waveshare|ili9486|fbtft|spi0.0|spi0.1|ads7846|fb[0-9]|panel' | tail -80")
    run(re, "cat /sys/bus/spi/devices/spi0.0/modalias 2>/dev/null || true")
    run(re, "cat /sys/bus/spi/devices/spi0.1/modalias 2>/dev/null || true")
    run(re, "python3 -c \"f=open('/dev/fb0','wb'); f.write(b'\\x00\\xf8'*(480*320)); f.close()\" 2>/dev/null || true")
    run(re, "dd if=/dev/urandom of=/dev/fb0 bs=307200 count=1 2>&1 || true")
    run(re, "cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true")

    re.close()


if __name__ == "__main__":
    main()
