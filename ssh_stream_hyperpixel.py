"""
Stream test.mp4 in a loop from this PC to the Pi over TCP (MPEG-TS / H.264)
specifically tailored for the Pimoroni HyperPixel 3.5" (800x480).

Usage:
  python ssh_stream_hyperpixel.py
  
Controls:
  Press '1' to turn screen ON
  Press '2' to turn screen OFF
  Press 'q' to stop and exit
"""

from __future__ import annotations

import msvcrt
import signal
import sys
import time

import pi_stream_common

# Override resolutions and formats for HyperPixel
pi_stream_common.WIDTH = 800
pi_stream_common.HEIGHT = 480
pi_stream_common.FFMPEG_NEGATE_COLORS = False
pi_stream_common.PIX_FMT = "bgra"

from pi_stream_common import (
    STREAM_PORT,
    assert_test_video,
    connect,
    ensure_ffmpeg_on_pi,
    find_ffmpeg,
    kill_pi_stream_processes,
    pc_push_cmd,
    pi_ffmpeg_vf,
    pi_listener_cmd,
    prepare_framebuffer,
    resolve_pi_host,
    run_local_ffmpeg,
    start_pi_background_ffmpeg,
    tail_pi_log,
    wait_for_pi_tcp_listener,
    run,
    sudo
)

def ensure_rpi_backlight(ssh) -> None:
    _, _, code = run(ssh, 'python3 -c "import rpi_backlight"')
    if code == 0:
        return
    print("Installing python3-pip and rpi_backlight on Pi (may take a minute)...")
    sudo(ssh, "DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip && pip3 install rpi_backlight")

def main() -> None:
    video = assert_test_video()
    ffmpeg = find_ffmpeg()
    print(f"Using ffmpeg: {ffmpeg}")
    print(f"Video: {video}")
    pi_ip = resolve_pi_host()
    print(f"Pi: {pi_ip}")

    # No negate necessary for HyperPixel usually
    negate = False

    print(f"Pi receiver: ffmpeg (TCP :{STREAM_PORT} on Pi) to /dev/fb0")
    print(f"Resolution overridden to {pi_stream_common.WIDTH}x{pi_stream_common.HEIGHT}")

    log_name = "ffmpeg_recv_push.log"

    ssh = connect()
    print("SSH connected.")

    server_proc = None
    try:
        prepare_framebuffer(ssh)

        print(f"PC push target: tcp://{pi_ip}:{STREAM_PORT}")
        ensure_ffmpeg_on_pi(ssh)
        ensure_rpi_backlight(ssh)
        listener = pi_listener_cmd(negate)
        print(f"Pi ffmpeg filter: {pi_ffmpeg_vf(negate)}")
        start_pi_background_ffmpeg(ssh, listener, log_name)
        
        if not wait_for_pi_tcp_listener(ssh, timeout=25):
            tail_pi_log(ssh, log_name, lines=40)
            raise RuntimeError(
                f"Pi ffmpeg did not open TCP port {STREAM_PORT}. Check /tmp/{log_name} on Pi."
            )
        tail_pi_log(ssh, log_name, lines=10)
        
        cmd = pc_push_cmd(ffmpeg, video, pi_ip)
        # Suppress the ffmpeg lag warnings by changing the loglevel from warning to error
        if "-loglevel" in cmd and "warning" in cmd:
            cmd[cmd.index("warning")] = "error"

        server_proc = run_local_ffmpeg(cmd)

        print("\nStreaming to Pi. Watch the HyperPixel screen.")
        print("---------------------------------------")
        print("Controls:")
        print("  [1] Turn screen ON")
        print("  [2] Turn screen OFF")
        print("  [q] Quit")
        print("---------------------------------------\n")

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

        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                if key == '1':
                    print("Turning screen ON...")
                    # Using pi_stream_common sudo wrapper just in case permissions require it
                    sudo(ssh, 'python3 -c "from rpi_backlight import Backlight; Backlight().power = True"')
                elif key == '2':
                    print("Turning screen OFF...")
                    sudo(ssh, 'python3 -c "from rpi_backlight import Backlight; Backlight().power = False"')
                elif key == 'q':
                    print("Quit requested.")
                    break
            
            if server_proc.poll() is not None:
                print("Local ffmpeg process ended unexpectedly.")
                break
                
            time.sleep(0.1)

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
