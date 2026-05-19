"""
Simulate a Tapo-style camera: PC hosts MPEG-TS over TCP, Pi pulls and shows on fb0.

Usage:
  python ssh_receive_network_stream.py
  python ssh_receive_network_stream.py --invert

Press Ctrl+C to stop (stops Pi decoder and PC server).
"""

from __future__ import annotations

import argparse
import signal
import sys
import time

from pi_stream_common import (
    FFMPEG_NEGATE_COLORS,
    STREAM_PORT,
    assert_test_video,
    connect,
    ensure_ffmpeg_on_pi,
    find_ffmpeg,
    get_pc_lan_ip,
    kill_pi_stream_processes,
    pc_listen_cmd,
    pi_client_cmd,
    pi_ffmpeg_vf,
    prepare_framebuffer,
    resolve_negate_colors,
    run,
    run_local_ffmpeg,
    tail_pi_log,
    try_allow_windows_firewall_port,
    wait_for_local_tcp_listener,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="PC hosts stream; Pi pulls and shows on fb0")
    parser.add_argument("--invert", action="store_true", help="Negate colors on Pi receiver")
    parser.add_argument("--no-invert", action="store_true", help="Disable Pi color negation")
    args = parser.parse_args()
    try:
        negate = resolve_negate_colors(args.invert, args.no_invert, inverted=False)
    except ValueError as exc:
        parser.error(str(exc))

    video = assert_test_video()
    ffmpeg = find_ffmpeg()
    pc_ip = get_pc_lan_ip()
    print(f"Using ffmpeg: {ffmpeg}")
    print(f"Video: {video}")
    print(f"PC stream server: tcp://{pc_ip}:{STREAM_PORT}?listen=1")
    print(f"Pi will connect as client (like rtsp://camera/...)")
    invert_on = negate if negate is not None else FFMPEG_NEGATE_COLORS
    print(f"Pi color inversion: {'on' if invert_on else 'off'}")
    if not try_allow_windows_firewall_port():
        print(
            "Note: If the Pi cannot connect, allow inbound TCP port "
            f"{STREAM_PORT} in Windows Firewall (or run this script as Administrator)."
        )

    server = run_local_ffmpeg(pc_listen_cmd(ffmpeg, video))
    if not wait_for_local_tcp_listener(timeout=30):
        server.terminate()
        raise RuntimeError("PC ffmpeg failed to open TCP listen port 5000")

    ssh = connect()
    print("SSH connected.")

    try:
        ensure_ffmpeg_on_pi(ssh)
        prepare_framebuffer(ssh)
        kill_pi_stream_processes(ssh)

        client_cmd = pi_client_cmd(pc_ip, negate)
        print(f"Pi ffmpeg filter: {pi_ffmpeg_vf(negate)}")
        bg = f"nohup {client_cmd} > /tmp/ffmpeg_recv_pull.log 2>&1 & echo $!"
        out, _, _ = run(ssh, bg)
        pid = out.strip().splitlines()[-1] if out.strip() else "?"
        print(f"\nPi ffmpeg client started (pid {pid}).")
        print("Watch the Waveshare screen. Press Ctrl+C to stop.\n")

        def stop(_signum=None, _frame=None) -> None:
            print("\nStopping...")
            kill_pi_stream_processes(ssh)
            server.terminate()
            try:
                server.wait(timeout=5)
            except Exception:
                server.kill()
            tail_pi_log(ssh, "ffmpeg_recv_pull.log")
            ssh.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, stop)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, stop)

        try:
            while server.poll() is None:
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        stop()
    except Exception as exc:
        print(f"Error: {exc}")
        kill_pi_stream_processes(ssh)
        server.terminate()
        ssh.close()
        raise


if __name__ == "__main__":
    main()
