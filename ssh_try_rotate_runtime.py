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


def quadrant_pattern() -> bytes:
    # TL=red, TR=green, BL=blue, BR=white
    buf = bytearray(WIDTH * HEIGHT * 2)
    idx = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if x < WIDTH // 2 and y < HEIGHT // 2:
                pix = rgb565(255, 0, 0)
            elif x >= WIDTH // 2 and y < HEIGHT // 2:
                pix = rgb565(0, 255, 0)
            elif x < WIDTH // 2 and y >= HEIGHT // 2:
                pix = rgb565(0, 0, 255)
            else:
                pix = rgb565(255, 255, 255)
            buf[idx] = pix[0]
            buf[idx + 1] = pix[1]
            idx += 2
    return bytes(buf)


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)

    pattern = quadrant_pattern()
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/fb_quadrants.bin", "wb") as f:
        f.write(pattern)
    sftp.close()

    cmds = [
        "cat /sys/class/graphics/fb0/rotate",
        f"echo '{PASS}' | sudo -S sh -c 'echo 270 > /sys/class/graphics/fb0/rotate'",
        "cat /sys/class/graphics/fb0/rotate",
        f"echo '{PASS}' | sudo -S sh -c 'cat /tmp/fb_quadrants.bin > /dev/fb0'",
        "cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true",
    ]

    for cmd in cmds:
        print(f"=== {cmd} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err:
            print(f"STDERR: {err}")

    ssh.close()


if __name__ == "__main__":
    main()
