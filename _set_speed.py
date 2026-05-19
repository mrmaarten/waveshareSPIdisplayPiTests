import paramiko
from pi_stream_common import connect, sudo, run
import time

def main():
    ssh = connect()
    print("--- Updating config.txt ---")
    
    # Remove existing speed parameter if any, then append the new speed
    sed_cmd = (
        "sed -i 's/dtoverlay=waveshare35b-v2:rotate=90.*/dtoverlay=waveshare35b-v2:rotate=90,speed=32000000/' "
        "/boot/firmware/config.txt"
    )
    sudo(ssh, sed_cmd)
    
    print("--- Verifying config.txt ---")
    run(ssh, "cat /boot/firmware/config.txt | grep waveshare35b-v2")
    
    print("--- Rebooting Pi ---")
    sudo(ssh, "reboot")
    ssh.close()

if __name__ == "__main__":
    main()
