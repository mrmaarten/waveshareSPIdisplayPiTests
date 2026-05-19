import time
import paramiko

from env_config import PI_HOST, PI_PASS, PI_USER

HOST = PI_HOST
USER = PI_USER
PASS = PI_PASS
WIDTH = 480
HEIGHT = 320


def rgb565(r: int, g: int, b: int) -> bytes:
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return bytes((v & 0xFF, (v >> 8) & 0xFF))


def quadrants() -> bytes:
    # TL red, TR green, BL blue, BR white
    data = bytearray(WIDTH * HEIGHT * 2)
    i = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if x < WIDTH // 2 and y < HEIGHT // 2:
                p = rgb565(255, 0, 0)
            elif x >= WIDTH // 2 and y < HEIGHT // 2:
                p = rgb565(0, 255, 0)
            elif x < WIDTH // 2 and y >= HEIGHT // 2:
                p = rgb565(0, 0, 255)
            else:
                p = rgb565(255, 255, 255)
            data[i] = p[0]
            data[i + 1] = p[1]
            i += 2
    return bytes(data)


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
    cfg = run(c, "cat /boot/firmware/config.txt")
    cfg2 = cfg.replace("dtoverlay=waveshare35b-v2:rotate=90", "dtoverlay=waveshare35b-v2:rotate=270")
    if cfg2 == cfg and "dtoverlay=waveshare35b-v2" in cfg:
        cfg2 = cfg.replace("dtoverlay=waveshare35b-v2", "dtoverlay=waveshare35b-v2:rotate=270")

    sftp = c.open_sftp()
    with sftp.open("/tmp/config.txt.rotate270", "w") as f:
        f.write(cfg2)
    with sftp.open("/tmp/fb_quadrants.bin", "wb") as f:
        f.write(quadrants())
    sftp.close()

    sudo(c, "cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_rotate270_test.bak")
    sudo(c, "cp /tmp/config.txt.rotate270 /boot/firmware/config.txt")
    run(c, "tail -25 /boot/firmware/config.txt")

    print("\nRebooting...")
    try:
        sudo(c, "reboot", timeout=5)
    except Exception:
        pass
    c.close()

    time.sleep(25)
    c2 = None
    for n in range(18):
        try:
            print(f"Reconnect attempt {n + 1}/18...")
            c2 = connect()
            print("Reconnected.")
            break
        except Exception as exc:
            print(f"Not ready: {exc}")
            time.sleep(5)

    if c2 is None:
        print("Could not reconnect after reboot.")
        return

    sudo(c2, "systemctl stop display-manager || true")
    run(c2, "cat /sys/class/graphics/fb0/rotate")
    run(c2, "dmesg | grep -Ei 'fbtft|ili9486|rotate|spi0.0|fb0' | tail -30")
    sudo(c2, "cat /tmp/fb_quadrants.bin > /dev/fb0")
    run(c2, "cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true")
    c2.close()


if __name__ == "__main__":
    main()
