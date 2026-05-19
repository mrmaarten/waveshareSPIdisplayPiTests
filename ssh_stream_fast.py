import paramiko
import time
import socket
import sys

HOST = "videopi.local"
USER = "maarten"
PASS = " "
PORT = 9000
WIDTH = 480
HEIGHT = 320

def rgb565(r: int, g: int, b: int) -> bytes:
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return bytes((v & 0xFF, (v >> 8) & 0xFF))

def build_frame(offset_x: int) -> bytearray:
    buf = bytearray(WIDTH * HEIGHT * 2)
    idx = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            val = (x + offset_x * 5) % 255
            r = val
            g = 255 - val
            b = 128
            
            v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            buf[idx] = v & 0xFF
            buf[idx + 1] = (v >> 8) & 0xFF
            idx += 2
    return buf

def start_receiver(ssh):
    # Grant write access to /dev/fb0
    ssh.exec_command(f"echo '{PASS}' | sudo -S chmod 666 /dev/fb0")
    time.sleep(0.5)
    
    # Python script to run on the Pi
    receiver_script = """
import socket
import sys

PORT = 9000
FRAME_SIZE = 480 * 320 * 2

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('0.0.0.0', PORT))
sock.listen(1)

print("Listening on port 9000...")
try:
    with open('/dev/fb0', 'wb') as fb:
        while True:
            conn, addr = sock.accept()
            print("Connected by", addr)
            try:
                while True:
                    data = conn.recv(FRAME_SIZE)
                    if not data:
                        break
                    # We might not receive a full frame in one chunk, 
                    # but for raw writing to fb0, pushing chunks is fine.
                    # To keep it perfectly aligned, we should seek(0) after a full frame,
                    # but simple streaming works if the sender is consistent.
                    fb.write(data)
                    fb.flush()
            except Exception as e:
                print("Connection error:", e)
            finally:
                conn.close()
                fb.seek(0)
except KeyboardInterrupt:
    pass
finally:
    sock.close()
"""
    # Upload and run it
    sftp = ssh.open_sftp()
    with sftp.open("/tmp/recv_fb0.py", "w") as f:
        f.write(receiver_script)
    sftp.close()
    
    # Kill any existing python receiver
    ssh.exec_command("pkill -f recv_fb0.py")
    time.sleep(0.5)
    
    # Start the receiver in the background
    print("Starting python receiver on Pi...")
    ssh.exec_command("nohup python3 /tmp/recv_fb0.py > /tmp/recv.log 2>&1 &")
    time.sleep(1) 

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting via SSH...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)
    
    start_receiver(ssh)
    
    print("Connecting to raw TCP stream...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((HOST, PORT))
    except Exception as e:
        print(f"Failed to connect to TCP port: {e}")
        ssh.close()
        return

    print("Connected! Streaming animation at target 20 FPS (Press Ctrl+C to stop)")
    
    target_fps = 20
    frame_time = 1.0 / target_fps
    
    try:
        offset = 0
        frames = 0
        start_time = time.time()
        last_report = start_time
        
        while True:
            loop_start = time.time()
            
            # Generate frame
            frame_data = build_frame(offset)
            
            # Send frame
            sock.sendall(frame_data)
            
            frames += 1
            offset += 1
            
            # Report FPS every second
            now = time.time()
            if now - last_report >= 1.0:
                print(f"Streaming at {frames / (now - last_report):.1f} FPS")
                frames = 0
                last_report = now
                
            # Sleep to maintain target FPS
            elapsed = time.time() - loop_start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
    except KeyboardInterrupt:
        print("\nStopping stream...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sock.close()
        ssh.exec_command("pkill -f recv_fb0.py")
        ssh.close()

if __name__ == "__main__":
    main()
