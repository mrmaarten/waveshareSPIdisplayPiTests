import paramiko
import time
import shlex

HOST = "videopi.local"
USER = "maarten"
PASS = " "


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)

    def run(cmd: str, sudo: bool = False, timeout: int = 30) -> str:
        print(f"\n=== {cmd} ===")
        full_cmd = cmd
        if sudo:
            full_cmd = f"echo {shlex.quote(PASS)} | sudo -S bash -lc {shlex.quote(cmd)}"
        stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err:
            print(f"STDERR: {err}")
        return out

    # Baseline state
    run("uname -a")
    run("cat /sys/class/graphics/fb0/name")
    run("cat /sys/class/graphics/fb0/virtual_size")
    run("cat /sys/class/graphics/fb0/blank")
    run("cat /sys/class/graphics/fb0/state")
    run("cat /sys/module/kernel/parameters/consoleblank")
    run("ls /sys/class/backlight/ || true")
    run("cat /sys/class/backlight/fb_ili9486/brightness 2>/dev/null || true")
    run("cat /sys/class/backlight/fb_ili9486/actual_brightness 2>/dev/null || true")
    before_bytes = run("cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx")

    # Runtime unblank attempts
    run("echo 0 > /sys/class/graphics/fb0/blank", sudo=True)
    run("echo 0 > /sys/module/kernel/parameters/consoleblank", sudo=True)
    run("cat /sys/class/graphics/fb0/blank")
    run("cat /sys/module/kernel/parameters/consoleblank")

    # Push obvious pixel patterns
    run(
        "python3 -c \"f=open('/dev/fb0','wb'); f.write(b'\\x00\\xf8' * (480*320)); f.close()\"",
        sudo=True,
    )
    time.sleep(2)
    run("dd if=/dev/urandom of=/dev/fb0 bs=307200 count=1 2>&1", sudo=True)
    time.sleep(2)

    after_bytes = run("cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx")
    run("cat /sys/class/graphics/fb0/blank")
    run("cat /sys/class/graphics/fb0/state")
    run("dmesg | grep -Ei 'ili9486|fbtft|fb0|spi0.0|panel|backlight' | tail -30")

    try:
        tx_diff = int(after_bytes) - int(before_bytes)
        print(f"\n>>> SPI bytes transferred during second attempt: {tx_diff}")
    except ValueError:
        print("\n>>> Could not calculate SPI byte delta.")

    ssh.close()


if __name__ == "__main__":
    main()
