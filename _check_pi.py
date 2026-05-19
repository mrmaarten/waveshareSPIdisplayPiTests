import paramiko
from pi_stream_common import connect, run

def main():
    ssh = connect()
    print("--- Netstat for port 5000 ---")
    run(ssh, "ss -tlnp | grep 5000")
    print("--- Processes ---")
    run(ssh, "ps aux | grep -E 'ffmpeg|vlc' | grep -v grep")
    ssh.close()

if __name__ == "__main__":
    main()
