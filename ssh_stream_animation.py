import paramiko
import time

HOST = "videopi.local"
USER = "maarten"
PASS = " "
WIDTH = 480
HEIGHT = 320

def rgb565(r: int, g: int, b: int) -> bytes:
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return bytes((v & 0xFF, (v >> 8) & 0xFF))

def build_frame(offset_x: int) -> bytes:
    # A simple moving gradient bar
    buf = bytearray(WIDTH * HEIGHT * 2)
    idx = 0
    for y in range(HEIGHT):
        for x in range(WIDTH):
            val = (x + offset_x) % 255
            r = val
            g = 255 - val
            b = 128
            pix = rgb565(r, g, b)
            buf[idx] = pix[0]
            buf[idx + 1] = pix[1]
            idx += 2
    return bytes(buf)

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting...")
    ssh.connect(HOST, username=USER, password=PASS, timeout=10)
    print("Connected. Generating and streaming frames...")
    
    # Grant write access to /dev/fb0 temporarily so we don't need sudo for the pipe
    ssh.exec_command(f"echo '{PASS}' | sudo -S chmod 666 /dev/fb0")
    time.sleep(0.5) # Wait for chmod to take effect
    
    sftp = ssh.open_sftp()
    try:
        with sftp.open("/dev/fb0", "wb") as f:
            offset = 0
            frames = 50
            print(f"Streaming {frames} frames...")
            
            start_time = time.time()
            for i in range(frames):
                frame_data = build_frame(offset)
                # Ensure we write exactly at the start of the framebuffer each time
                f.seek(0)
                f.write(frame_data)
                offset += 15  # move the gradient
                
                if (i + 1) % 10 == 0:
                    print(f"Sent frame {i + 1}/{frames}")
                    
            elapsed = time.time() - start_time
            print(f"Finished! Sent {frames} frames in {elapsed:.2f} seconds ({frames/elapsed:.2f} FPS via SFTP)")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sftp.close()
        ssh.close()

if __name__ == "__main__":
    main()
