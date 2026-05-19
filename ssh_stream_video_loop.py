"""
Stream test.mp4 in a loop from this PC to the Pi over TCP (MPEG-TS / H.264).

Default: PC pushes, Pi ffmpeg listens on TCP :5000 -> /dev/fb0.

With --vlc: PC listens, Pi cvlc connects (VLC cannot bind tcp listen on this build).

Usage:
  python ssh_stream_video_loop.py
  python ssh_stream_video_loop.py --invert
  python ssh_stream_video_loop.py --vlc --inverted

Press Ctrl+C to stop.
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
    ensure_vlc_on_pi,
    find_ffmpeg,
    get_pc_lan_ip,
    kill_pi_stream_processes,
    pc_listen_cmd,
    pc_push_cmd,
    pi_ffmpeg_vf,
    pi_listener_cmd,
    pi_vlc_client_cmd,
    prepare_framebuffer,
    resolve_negate_colors,
    resolve_pi_host,
    run_local_ffmpeg,
    start_pi_background_ffmpeg,
    start_pi_background_player,
    tail_pi_log,
    try_allow_windows_firewall_port,
    wait_for_local_tcp_listener,
    wait_for_pi_tcp_listener,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream test2.mp4 to Pi framebuffer over TCP")
    parser.add_argument(
        "--vlc",
        action="store_true",
        help="Use cvlc on Pi (PC listens, Pi connects — required for VLC TCP)",
    )
    parser.add_argument(
        "--inverted",
        action="store_true",
        help="Invert colors on Pi (VLC: invert filter; ffmpeg: negate)",
    )
    parser.add_argument(
        "--invert",
        action="store_true",
        help="Same as --inverted (ffmpeg only)",
    )
    parser.add_argument(
        "--no-invert",
        action="store_true",
        help="Disable Pi color inversion (use with waveshare35 overlay)",
    )
    args = parser.parse_args()
    try:
        negate = resolve_negate_colors(args.invert, args.no_invert, inverted=args.inverted)
    except ValueError as exc:
        parser.error(str(exc))

    video = assert_test_video()
    ffmpeg = find_ffmpeg()
    print(f"Using ffmpeg: {ffmpeg}")
    print(f"Video: {video}")
    pi_ip = resolve_pi_host()
    print(f"Pi: {pi_ip}")

    if args.vlc:
        invert_on = args.inverted
        print("Pi receiver: VLC (cvlc), PC listen / Pi connect")
        print(f"Pi color inversion: {'on' if invert_on else 'off'}")
        log_name = "vlc_recv_pull.log"
    else:
        invert_on = negate if negate is not None else FFMPEG_NEGATE_COLORS
        print(f"Pi receiver: ffmpeg (TCP :{STREAM_PORT} on Pi)")
        print(f"Pi color inversion: {'on' if invert_on else 'off'}")
        log_name = "ffmpeg_recv_push.log"

    ssh = connect()
    print("SSH connected.")

    server_proc = None
    try:
        prepare_framebuffer(ssh)

        if args.vlc:
            if not try_allow_windows_firewall_port():
                print(
                    f"Note: allow inbound TCP {STREAM_PORT} in Windows Firewall "
                    "if the Pi cannot connect."
                )
            pc_ip = get_pc_lan_ip(pi_ip)
            print(f"PC stream server: tcp://{pc_ip}:{STREAM_PORT} (listen)")
            ensure_vlc_on_pi(ssh)
            server_proc = run_local_ffmpeg(pc_listen_cmd(ffmpeg, video))
            if not wait_for_local_tcp_listener(timeout=30):
                raise RuntimeError("PC ffmpeg did not open TCP listen port 5000")
            client = pi_vlc_client_cmd(pc_ip, inverted=args.inverted)
            print(f"Pi cvlc command: {client}")
            start_pi_background_player(ssh, client, log_name, label="cvlc")
            time.sleep(2)
            tail_pi_log(ssh, log_name, lines=20)
        else:
            print(f"PC push target: tcp://{pi_ip}:{STREAM_PORT}")
            ensure_ffmpeg_on_pi(ssh)
            listener = pi_listener_cmd(negate)
            print(f"Pi ffmpeg filter: {pi_ffmpeg_vf(negate)}")
            start_pi_background_ffmpeg(ssh, listener, log_name)
            if not wait_for_pi_tcp_listener(ssh, timeout=25):
                tail_pi_log(ssh, log_name, lines=40)
                raise RuntimeError(
                    f"Pi ffmpeg did not open TCP port {STREAM_PORT}. Check /tmp/{log_name} on Pi."
                )
            tail_pi_log(ssh, log_name, lines=10)
            server_proc = run_local_ffmpeg(pc_push_cmd(ffmpeg, video, pi_ip))

        print("\nStreaming to Pi. Watch the Waveshare screen. Press Ctrl+C to stop.\n")

        def stop(_signum=None, _frame=None) -> None:
            print("\nStopping...")
            if server_proc is not None:
                server_proc.terminate()
                try:
                    server_proc.wait(timeout=5)
                except Exception:
                    server_proc.kill()
            kill_pi_stream_processes(ssh)
            ssh.close()
            sys.exit(0)

        signal.signal(signal.SIGINT, stop)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, stop)

        server_proc.wait()
        stop()
    except Exception as exc:
        print(f"Error: {exc}")
        if server_proc is not None:
            server_proc.terminate()
        kill_pi_stream_processes(ssh)
        ssh.close()
        raise


if __name__ == "__main__":
    main()
