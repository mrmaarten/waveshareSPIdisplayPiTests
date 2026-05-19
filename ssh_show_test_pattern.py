import paramiko

from env_config import PI_PASS
from pi_stream_common import connect

WIDTH = 480
HEIGHT = 320


def rgb565(r: int, g: int, b: int) -> bytes:
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return bytes((v & 0xFF, (v >> 8) & 0xFF))


def build_pattern() -> bytes:
    # 6 vertical bars + colored corners:
    # top-left red, top-right green, bottom-left blue, bottom-right white
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

            # Corner markers (30x30 blocks).
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


def main() -> None:
    ssh = connect()

    pattern = build_pattern()
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/fb_pattern.bin", "wb") as f:
        f.write(pattern)
    sftp.close()

    cmds = [
        f"echo '{PI_PASS}' | sudo -S systemctl stop display-manager",
        f"echo '{PI_PASS}' | sudo -S sh -c 'cat /tmp/fb_pattern.bin > /dev/fb0'",
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
