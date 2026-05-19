import paramiko

HOST = "videopi.local"
USER = "maarten"
PASS = " "


def main() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)

    def run(cmd: str, timeout: int = 40) -> str:
        print(f"\n=== {cmd} ===")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        if out:
            print(out)
        if err:
            print(f"STDERR: {err}")
        return out

    def sudo(cmd: str, timeout: int = 40) -> str:
        return run(f"echo '{PASS}' | sudo -S bash -lc \"{cmd}\"", timeout=timeout)

    # Snapshot current state.
    run("uname -a")
    run("systemctl is-active display-manager || true")
    run("ps -ef | grep -E 'labwc|wayfire|wayland|Xorg' | grep -v grep || true")
    run("cat /sys/class/graphics/fb0/rotate 2>/dev/null || true")
    run("cat /boot/firmware/config.txt | tail -40")

    # 1) Fix rotation back to 90.
    cfg = run("cat /boot/firmware/config.txt")
    cfg2 = cfg.replace("dtoverlay=waveshare35b-v2:rotate=270", "dtoverlay=waveshare35b-v2:rotate=90")
    cfg2 = cfg2.replace("dtoverlay=waveshare35b-v2", "dtoverlay=waveshare35b-v2:rotate=90")
    if cfg2 != cfg:
        sftp = ssh.open_sftp()
        with sftp.open("/tmp/config.txt.rotate90", "w") as f:
            f.write(cfg2)
        sftp.close()
        sudo("cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_rotate90_fix.bak")
        sudo("cp /tmp/config.txt.rotate90 /boot/firmware/config.txt")
        run("tail -30 /boot/firmware/config.txt")

    # 2) Prevent blank-after-boot by running CLI target instead of desktop session.
    #    This keeps framebuffer console visible on the SPI LCD.
    sudo("systemctl stop display-manager || true")
    sudo("systemctl disable display-manager || true")
    sudo("systemctl set-default multi-user.target")

    # Also remove quiet splash to make console text visible.
    cmdline = run("cat /boot/firmware/cmdline.txt")
    new_cmdline = cmdline.replace("quiet", "").replace("splash", "")
    # normalize spaces
    new_cmdline = " ".join(new_cmdline.split())
    if "fbcon=map:1" not in new_cmdline:
        new_cmdline += " fbcon=map:1"
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/cmdline.fixed", "w") as f:
        f.write(new_cmdline + "\n")
    sftp.close()
    sudo("cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.pre_lcd_fix.bak")
    sudo("cp /tmp/cmdline.fixed /boot/firmware/cmdline.txt")
    run("cat /boot/firmware/cmdline.txt")

    # Show immediate test frame now.
    sudo("python3 - <<'PY'\n"
         "f=open('/dev/fb0','wb')\n"
         "f.write(b'\\x00\\xf8'*(480*320))\n"
         "f.close()\n"
         "PY")

    run("cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true")
    print("\nDone. Reboot required for rotation/default-target/cmdline changes.")
    ssh.close()


if __name__ == "__main__":
    main()
