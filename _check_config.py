import paramiko
from pi_stream_common import connect, run

def main():
    ssh = connect()
    print("--- Current config.txt ---")
    run(ssh, "cat /boot/firmware/config.txt | grep -E '^dtparam|^dtoverlay'")
    ssh.close()

if __name__ == "__main__":
    main()
