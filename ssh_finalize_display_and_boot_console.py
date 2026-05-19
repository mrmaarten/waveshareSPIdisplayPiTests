import time
import paramiko

HOST = "videopi.local"
USER = "maarten"
PASS = " "
WIDTH = 480
HEIGHT = 320


def rgb565(r: int, g: int, b: int) -> bytes:
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return bytes((v & 0xFF, (v >> 8) & 0xFF))


def quadrants() -> bytes:
    data = bytearray(WIDTH * HEIGHT * 2)
    i = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if x < WIDTH // 2 and y < HEIGHT // 2:
                p = rgb565(255, 0, 0)       # TL red
            elif x >= WIDTH // 2 and y < HEIGHT // 2:
                p = rgb565(0, 255, 0)       # TR green
            elif x < WIDTH // 2 and y >= HEIGHT // 2:
                p = rgb565(0, 0, 255)       # BL blue
            else:
                p = rgb565(255, 255, 255)   # BR white
            data[i] = p[0]
            data[i + 1] = p[1]
            i += 2
    return bytes(data)


def connect() -> paramiko.SSHClient:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=10)
    return c


def run(c: paramiko.SSHClient, cmd: str, timeout: int = 45) -> str:
    print(f"\n=== {cmd} ===")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    if out:
        print(out)
    if err:
        print(f"STDERR: {err}")
    return out


def sudo(c: paramiko.SSHClient, cmd: str, timeout: int = 45) -> str:
    return run(c, f"echo '{PASS}' | sudo -S bash -lc \"{cmd}\"", timeout=timeout)


def main() -> None:
    c = connect()
    print("Connected. Applying final config pass.")

    cfg = run(c, "cat /boot/firmware/config.txt")
    cmdline = run(c, "cat /boot/firmware/cmdline.txt")

    # Backup before editing.
    sudo(c, "cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_final_display_tune.bak")
    sudo(c, "cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.pre_final_display_tune.bak")

    # Build new config:
    # - remove current SPI display overlay lines
    # - add explicit fbtft ili9486 line with rotate=270
    filtered = []
    for line in cfg.splitlines():
        s = line.strip()
        if s.startswith("dtoverlay=waveshare35b-v2"):
            continue
        if s.startswith("dtoverlay=fbtft"):
            continue
        if s.startswith("dtoverlay=mipi-dbi-spi"):
            continue
        filtered.append(line)
    new_cfg = "\n".join(filtered).rstrip() + "\n"
    if "dtparam=spi=on" not in new_cfg:
        new_cfg += "dtparam=spi=on\n"
    new_cfg += (
        "dtoverlay=fbtft,spi0-0,ili9486,regwidth=16,buswidth=8,"
        "dc_pin=25,reset_pin=27,led_pin=24,speed=16000000,rotate=270,fps=30\n"
    )

    # Remove quiet/splash but keep console and desktop.
    new_cmdline = cmdline.replace(" quiet", "").replace(" splash", "")
    # Normalize accidental double spaces.
    while "  " in new_cmdline:
        new_cmdline = new_cmdline.replace("  ", " ")
    new_cmdline = new_cmdline.strip() + "\n"

    sftp = c.open_sftp()
    with sftp.open("/tmp/config.txt.final", "w") as f:
        f.write(new_cfg)
    with sftp.open("/tmp/cmdline.txt.final", "w") as f:
        f.write(new_cmdline)
    with sftp.open("/tmp/fb_quadrants.bin", "wb") as f:
        f.write(quadrants())
    sftp.close()

    sudo(c, "cp /tmp/config.txt.final /boot/firmware/config.txt")
    sudo(c, "cp /tmp/cmdline.txt.final /boot/firmware/cmdline.txt")

    run(c, "tail -30 /boot/firmware/config.txt")
    run(c, "cat /boot/firmware/cmdline.txt")

    print("\nRebooting...")
    try:
        sudo(c, "reboot", timeout=5)
    except Exception:
        pass
    c.close()

    # Reconnect loop.
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
        print("Could not reconnect after reboot.")
        return

    # Confirm booted config and draw test image.
    run(c2, "cat /boot/firmware/cmdline.txt")
    run(c2, "ls -la /dev/fb* 2>/dev/null || echo NO_FB")
    run(c2, "cat /sys/class/graphics/fb0/name 2>/dev/null || true")
    run(c2, "cat /sys/class/graphics/fb0/rotate 2>/dev/null || true")
    run(c2, "dmesg | grep -Ei 'fbtft|ili9486|spi0.0|fb0|waveshare' | tail -40")

    sudo(c2, "systemctl stop display-manager || true")
    sudo(c2, "cat /tmp/fb_quadrants.bin > /dev/fb0")
    run(c2, "cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true")

    c2.close()


if __name__ == "__main__":
    main()
