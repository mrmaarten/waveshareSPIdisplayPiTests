import paramiko

HOST = "videopi.local"
USER = "maarten"
PASS = " "


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)

    def run(cmd: str) -> str:
        print(f"\n=== {cmd} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=40)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err:
            print(f"STDERR: {err}")
        return out

    def sudo(cmd: str) -> str:
        return run(f"echo '{PASS}' | sudo -S bash -lc \"{cmd}\"")

    run("ls -la ~/LCD-show/waveshare35b-v2-overlay.dtb")
    sudo("cp /home/maarten/LCD-show/waveshare35b-v2-overlay.dtb /boot/firmware/overlays/waveshare35b-v2.dtbo")
    run("ls -la /boot/firmware/overlays/waveshare35b-v2.dtbo")

    # Inspect active overlays before runtime switch.
    sudo("dtoverlay -l")

    # Try removing known boot overlays by index (best effort).
    sudo("dtoverlay -r 0 || true")
    sudo("dtoverlay -r 1 || true")

    # Runtime load vendor overlay.
    sudo("dtoverlay waveshare35b-v2 || true")
    sudo("dtoverlay -l")

    run("ls -la /dev/fb*")
    run("for f in /sys/class/graphics/fb*; do echo \"== $f ==\"; cat $f/name 2>/dev/null; cat $f/virtual_size 2>/dev/null; done")
    run("dmesg | grep -Ei 'fbtft|ili9486|waveshare|fb[0-9]|spi0.0|spi0.1' | tail -60")

    # Write to each framebuffer to maximize chance of visible output.
    run("for fb in /dev/fb0 /dev/fb1; do if [ -e $fb ]; then echo \"Testing $fb\"; python3 -c \"f=open('$fb','wb'); f.write(b'\\x00\\xf8'*(480*320)); f.close()\"; fi; done")
    run("for fb in /dev/fb0 /dev/fb1; do if [ -e $fb ]; then dd if=/dev/urandom of=$fb bs=307200 count=1 2>&1; fi; done")

    run("cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true")
    run("cat /sys/bus/spi/devices/spi0.1/statistics/bytes_tx 2>/dev/null || true")

    ssh.close()


if __name__ == "__main__":
    main()
