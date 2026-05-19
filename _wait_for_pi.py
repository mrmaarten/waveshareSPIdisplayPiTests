import time
from pi_stream_common import connect, HOST

def main():
    print(f"Waiting for {HOST} to come back online...")
    for _ in range(30):
        try:
            ssh = connect()
            print("Pi is back online!")
            ssh.close()
            return
        except Exception:
            print(".", end="", flush=True)
            time.sleep(2)
    print("\nTimeout waiting for Pi.")

if __name__ == "__main__":
    main()
