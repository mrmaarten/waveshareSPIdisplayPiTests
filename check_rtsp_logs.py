from pi_stream_common import connect, run
ssh = connect()
out, _, _ = run(ssh, "journalctl -u hyperpixel-rtsp-display.service -n 50 --no-pager")
print(out.strip())
