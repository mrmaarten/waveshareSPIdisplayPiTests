import time
import paramiko

from env_config import PI_HOST, PI_PASS, PI_USER

HOST = PI_HOST
USER = PI_USER
PASS = PI_PASS


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=10)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 40) -> str:
    print(f"\n=== {cmd} ===")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    return out


def sudo(c: paramiko.SSHClient, cmd: str, timeout: int = 40) -> str:
    return run(c, f"echo '{PASS}' | sudo -S bash -lc \"{cmd}\"", timeout=timeout)


def main() -> None:
    c = connect()
    sudo(c, "cp /boot/firmware/config.txt.pre_final_display_tune.bak /boot/firmware/config.txt")
    run(c, "tail -30 /boot/firmware/config.txt")
    run(c, "cat /boot/firmware/cmdline.txt")

    print("\nRebooting to restore known-good LCD state...")
    try:
        sudo(c, "reboot", timeout=5)
    except Exception:
        pass
    c.close()

    time.sleep(25)
    c2 = None
    for i in range(20):
        try:
            print(f"Reconnect attempt {i + 1}/20...")
            c2 = connect()
            print("Reconnected.")
            break
        except Exception as exc:
            print(f"Not ready: {exc}")
            time.sleep(4)

    if c2 is None:
        print("Could not reconnect.")
        return

    run(c2, "ls -la /dev/fb* 2>/dev/null || echo NO_FB")
    run(c2, "cat /sys/class/graphics/fb0/name 2>/dev/null || true")
    run(c2, "cat /sys/class/graphics/fb0/rotate 2>/dev/null || true")
    run(c2, "dmesg | grep -Ei 'fbtft|ili9486|spi0.0|fb0|waveshare|ads7846' | tail -60")
    c2.close()


if __name__ == "__main__":
    main()
