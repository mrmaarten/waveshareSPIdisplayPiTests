import paramiko

HOST = "videopi.local"
USER = "maarten"
PASS = " "


def safe_print(prefix: str, text: str) -> None:
    try:
        print(f"{prefix}{text}")
    except UnicodeEncodeError:
        print((prefix + text).encode("ascii", errors="replace").decode("ascii"))


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
            safe_print("", out)
        if err:
            safe_print("STDERR: ", err)
        return out

    def sudo(cmd: str, timeout: int = 40) -> str:
        return run(f"echo '{PASS}' | sudo -S bash -lc \"{cmd}\"", timeout=timeout)

    # Fix config overlay line to a single rotate param.
    cfg = run("cat /boot/firmware/config.txt")
    lines = cfg.splitlines()
    new_lines = []
    for line in lines:
        s = line.strip()
        if s.startswith("dtoverlay=waveshare35b-v2"):
            new_lines.append("dtoverlay=waveshare35b-v2:rotate=90")
        else:
            new_lines.append(line)
    fixed_cfg = "\n".join(new_lines) + "\n"

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/config.txt.finalfix", "w") as f:
        f.write(fixed_cfg)
    sftp.close()

    sudo("cp /boot/firmware/config.txt /boot/firmware/config.txt.pre_finalfix.bak")
    sudo("cp /tmp/config.txt.finalfix /boot/firmware/config.txt")
    run("tail -30 /boot/firmware/config.txt")

    # Ensure CLI target and no display manager auto-start.
    sudo("systemctl disable display-manager || true")
    sudo("systemctl set-default multi-user.target")
    run("systemctl get-default")
    run("systemctl is-enabled display-manager 2>/dev/null || true")
    run("systemctl is-active display-manager 2>/dev/null || true")

    # Ensure boot console text is visible.
    cmdline = run("cat /boot/firmware/cmdline.txt")
    for tok in ("quiet", "splash"):
        cmdline = cmdline.replace(tok, "")
    cmdline = " ".join(cmdline.split())
    if "fbcon=map:1" not in cmdline:
        cmdline += " fbcon=map:1"

    sftp = ssh.open_sftp()
    with sftp.open("/tmp/cmdline.finalfix", "w") as f:
        f.write(cmdline + "\n")
    sftp.close()

    sudo("cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.pre_finalfix.bak")
    sudo("cp /tmp/cmdline.finalfix /boot/firmware/cmdline.txt")
    run("cat /boot/firmware/cmdline.txt")

    # Quick live frame test.
    sudo("python3 - <<'PY'\n"
         "f=open('/dev/fb0','wb')\n"
         "f.write(b'\\x00\\xf8'*(480*320))\n"
         "f.close()\n"
         "PY")
    run("cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx 2>/dev/null || true")

    print("\nAll fixes applied. Reboot to validate.")
    ssh.close()


if __name__ == "__main__":
    main()
