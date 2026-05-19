# Setup Guide: Tapo Camera Stream on Pimoroni HyperPixel 3.5" (CLI Mode)

## Project Summary
The goal is to repurpose an original (discontinued) Pimoroni HyperPixel 3.5" display to show a live RTSP video stream from a Tapo security camera. The setup will run in a lightweight, headless CLI environment (no desktop GUI) to save resources. Additionally, the screen's capacitive touch capabilities will be used to toggle the backlight on and off with a simple tap.

**Important Note:** The original HyperPixel 3.5" is incompatible with modern 64-bit Raspberry Pi OS versions (Bullseye, Bookworm) due to changes in the graphics stack (Wayland/KMS). This guide relies on the **Legacy 32-bit OS (Buster)** to ensure the display and touch drivers work flawlessly.

---

## Step 1: Flashing the SD Card

1. Download and install the [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Insert your MicroSD card into your computer.
3. Open Raspberry Pi Imager:
   * Click **Choose Device** and select your Raspberry Pi model.
   * Click **Choose OS** -> **Raspberry Pi OS (Other)** -> **Raspberry Pi OS (Legacy, 32-bit) Lite**. *(This is the Buster-based CLI-only version).*
   * Click **Choose Storage** and select your MicroSD card.
4. Click **Next** and you will be prompted to apply OS customization settings. Click **Edit Settings**:
   * **General:** Set your hostname, username, and password. Configure your Wi-Fi credentials.
   * **Services:** Enable SSH (use password authentication or provide your public key).
5. Save the settings and click **Yes** to write to the SD card.

---

## Step 2: Hardware Assembly & Initial Boot

1. Carefully align the HyperPixel 3.5" screen with the 40-pin GPIO header on your Raspberry Pi and press it down firmly.
2. Insert the flashed MicroSD card and power on the Raspberry Pi.
3. Wait a minute or two for the Pi to boot and connect to your Wi-Fi network.
4. Find the Pi's IP address (via your router's admin panel or a tool like `ping` or `nmap`) and SSH into it from your computer:
   ```bash
   ssh username@your-pi-ip
   ```

---

## Step 3: Installing the HyperPixel Drivers

Once logged in via SSH, run the official Pimoroni legacy install script:

1. Execute the following command:
   ```bash
   curl https://get.pimoroni.com/hyperpixel | bash
   ```
2. Follow the on-screen prompts. The script will automatically configure `/boot/config.txt` for DPI mode 6 and install the necessary `hyperpixel-init` scripts.
3. Once the installation finishes, reboot the Pi:
   ```bash
   sudo reboot
   ```
4. After rebooting, the screen should light up and display the Raspberry Pi terminal console.

*(Optional) Disable Console Blanking:*
To stop the terminal from going to sleep on its own after 10 minutes:
1. Edit the boot command line: `sudo nano /boot/cmdline.txt`
2. Add `consoleblank=0` to the end of the line (ensure it stays on a single line).
3. Save and exit (Ctrl+X, Y, Enter).

---

## Step 4: Setting up the Video Stream

We will use `omxplayer`, a hardware-accelerated video player designed specifically for the Raspberry Pi's legacy graphics stack.

1. Install `omxplayer`:
   ```bash
   sudo apt update
   sudo apt install omxplayer
   ```
2. Test your Tapo camera stream. You will need to enable RTSP streaming in the Tapo app (Camera Settings -> Advanced Settings -> Camera Account) and set a username and password.
   ```bash
   omxplayer --avdict rtsp_transport:tcp "rtsp://tapo_user:tapo_pass@<TAPO_IP_ADDRESS>:554/stream1"
   ```
   *If the stream plays successfully on the screen, press `Ctrl+C` in your SSH terminal to stop it.*

3. **Create a Systemd Service to run the stream on boot:**
   ```bash
   sudo nano /etc/systemd/system/tapostream.service
   ```
   Add the following content:
   ```ini
   [Unit]
   Description=Tapo Camera RTSP Stream
   After=network.target

   [Service]
   Type=simple
   User=pi
   ExecStart=/usr/bin/omxplayer --avdict rtsp_transport:tcp "rtsp://tapo_user:tapo_pass@<TAPO_IP_ADDRESS>:554/stream1"
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```
4. Enable and start the service:
   ```bash
   sudo systemctl enable tapostream.service
   sudo systemctl start tapostream.service
   ```

---

## Step 5: Setting up Touch-to-Toggle

We will use a Python script to listen for touch events and toggle the backlight.

1. Install the required Python libraries:
   ```bash
   sudo apt install python3-pip
   sudo pip3 install evdev rpi_backlight
   ```

2. Create the Python script:
   ```bash
   nano ~/touch_toggle.py
   ```
   Add the following code:
   ```python
   import evdev
   import time
   from rpi_backlight import Backlight

   # Initialize backlight control
   backlight = Backlight()

   # Find the Goodix touch screen device
   touch_device = None
   devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
   for device in devices:
       if "Goodix" in device.name or "gt911" in device.name.lower():
           touch_device = device
           break

   if touch_device is None:
       print("Touch screen not found!")
       exit(1)

   print(f"Listening for touches on {touch_device.name}...")

   # Variables to handle debounce
   last_toggle_time = 0
   debounce_delay = 0.5  # half a second

   # Listen for events
   try:
       for event in touch_device.read_loop():
           # EV_KEY type with code 330 (BTN_TOUCH) indicates a touch
           if event.type == evdev.ecodes.EV_KEY and event.code == evdev.ecodes.BTN_TOUCH and event.value == 1:
               current_time = time.time()
               if current_time - last_toggle_time > debounce_delay:
                   # Toggle the backlight
                   backlight.power = not backlight.power
                   last_toggle_time = current_time
   except KeyboardInterrupt:
       pass
   ```

3. **Create a Systemd Service for the touch script:**
   ```bash
   sudo nano /etc/systemd/system/touchtoggle.service
   ```
   Add the following content:
   ```ini
   [Unit]
   Description=HyperPixel Touch to Toggle Backlight
   After=multi-user.target

   [Service]
   Type=simple
   User=root
   ExecStart=/usr/bin/python3 /home/pi/touch_toggle.py
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
   *(Note: Ensure the `ExecStart` path matches where you saved the script, e.g., `/home/yourusername/touch_toggle.py`)*

4. Enable and start the touch service:
   ```bash
   sudo systemctl enable touchtoggle.service
   sudo systemctl start touchtoggle.service
   ```

## Conclusion
Your Raspberry Pi will now automatically start the Tapo camera stream on boot. Whenever you tap the screen, the Python script will detect the input and toggle the backlight power, allowing you to easily turn the display off at night and wake it up when needed!