from pi_stream_common import connect, run

ssh = connect()
print("=== CPU & Uptime ===")
out, _, _ = run(ssh, "top -bn1 | head -n 3")
print(out.strip())

print("\n=== Temperature ===")
out, _, _ = run(ssh, "vcgencmd measure_temp")
print(out.strip())

print("\n=== FFMPEG Processes ===")
out, _, _ = run(ssh, "pgrep -af ffmpeg || echo 'No ffmpeg processes running'")
print(out.strip())

print("\n=== Service Status ===")
out, _, _ = run(ssh, "systemctl is-active hyperpixel-touch-display-power.service hyperpixel-rtsp-display.service hyperpixel-backlight-touch.service")
print(out.strip())

print("\n=== Touch Service Logs ===")
out, _, _ = run(ssh, "journalctl -u hyperpixel-touch-display-power.service -n 20 --no-pager")
print(out.strip())
