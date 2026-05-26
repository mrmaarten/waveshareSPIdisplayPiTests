# Setup Guide: Tapo Camera Stream on Pimoroni HyperPixel 3.5" (CLI Mode)

## Project Summary
The goal is to repurpose an original (discontinued) Pimoroni HyperPixel 3.5" display to show a live RTSP video stream from a Tapo security camera. The setup runs in a lightweight, headless CLI environment (no desktop GUI). The screen's capacitive touch controller toggles both the camera stream and the backlight with a simple tap.

**Important Note:** The original HyperPixel 3.5" is incompatible with modern 64-bit Raspberry Pi OS versions (Bullseye, Bookworm) due to changes in the graphics stack (Wayland/KMS). This guide relies on the **Legacy 32-bit OS (Buster)** to ensure the display and touch drivers work flawlessly.

## Current Automated Install

The repo now contains the final installer for this setup:

```bash
./.venv/bin/python ssh_install_touch_rtsp_power.py
```

Run it from the repo root on this machine. It reads Pi SSH and RTSP camera settings from `.env`, installs/updates the Pi services, and starts the screen in the desired production mode:

- `hyperpixel-rtsp-display.service` pulls the RTSP stream with `ffmpeg`, decodes H.264 with `h264_mmal`, and presents it through Raspberry Pi MMAL video output with `vout_rpi`.
- `hyperpixel-touch-display-power.service` listens to the HyperPixel touch controller and toggles both the stream service and the backlight together.
- Boot policy is screen on, backlight on, and camera stream running.
- Tap policy is display off/on with the stream stopped while the display is off.

The older `/dev/fb0` framebuffer path worked, but it spent CPU on scaling, colorspace conversion, and framebuffer copies. The tested `vout_rpi` path displayed correctly on the HyperPixel and reduced observed `ffmpeg` CPU from about `85%` to roughly `20-32%`.

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

## Step 4: Configure `.env`

On the computer running this repo, copy `.env.example` to `.env` and fill in the Pi SSH credentials plus the Tapo RTSP camera settings:

```env
PI_HOST=raspberrypi.local
PI_USER=pi
PI_PASS=raspberry

RTSP_HOST=192.168.0.190
RTSP_PORT=554
RTSP_PATH=/stream2
RTSP_USER=Camera
RTSP_PASS=your_camera_password_here
```

The installer percent-encodes special characters in the camera username/password before writing `/etc/default/hyperpixel-rtsp` on the Pi. Do not hand-edit the RTSP URL on the Pi unless you are debugging.

---

## Step 5: Install Video + Touch Power Services

Run the production installer from the repo root:

```bash
./.venv/bin/python ssh_install_touch_rtsp_power.py
```

This deploys:

- `hyperpixel-rtsp-display.service`: pulls RTSP with `ffmpeg`, uses `h264_mmal` for GPU H.264 decode, and outputs fullscreen through Raspberry Pi MMAL video output with `vout_rpi`.
- `hyperpixel-touch-display-power.service`: reads the HyperPixel touch controller directly over I2C and toggles both the RTSP service and the backlight.

Boot behavior:

- Backlight on.
- Camera stream running.
- Video presented by `vout_rpi`, not by CPU scaling/converting/copying into `/dev/fb0`.

Tap behavior:

- First tap stops `hyperpixel-rtsp-display.service`, writes the soft-yellow idle framebuffer, and turns the backlight off.
- Second tap writes the idle framebuffer, turns the backlight on, restarts the RTSP service, and the live camera feed appears after reconnect.

Use `--no-start` only when you want to update files and enable services for boot without restarting the current stream:

```bash
./.venv/bin/python ssh_install_touch_rtsp_power.py --no-start
```

---

## Step 6: Verify

Check service state:

```bash
ssh pi@raspberrypi.local "systemctl is-active hyperpixel-touch-display-power.service hyperpixel-rtsp-display.service"
ssh pi@raspberrypi.local "systemctl is-enabled hyperpixel-touch-display-power.service hyperpixel-rtsp-display.service"
```

Expected:

```text
active
active
enabled
enabled
```

Check that the installed display command uses GPU/MMAL output:

```bash
ssh pi@raspberrypi.local "grep -E 'h264_mmal|vout_rpi|genpts|use_wallclock' /usr/local/bin/hyperpixel_rtsp_display.sh"
```

Expected markers:

```text
-fflags +nobuffer+genpts -flags low_delay
-use_wallclock_as_timestamps 1
-c:v h264_mmal
-f vout_rpi -fullscreen 1 -
```

Check current ffmpeg CPU without printing the RTSP URL:

```bash
ssh pi@raspberrypi.local "ps -C ffmpeg -o pid,etime,stat,pcpu,pmem,comm"
```

The successful May 2026 test showed the old framebuffer path around `85%` CPU, while the `vout_rpi` production path settled around `20%`.

---

## Legacy Notes

The original plan used `omxplayer` and an `evdev` Goodix touch script. That did not become the final setup:

- `omxplayer` is not used by the current installer.
- The Goodix/`evdev` touch approach was unreliable on this HyperPixel setup.
- The working touch service reads the controller directly over I2C.
- The working video service uses `ffmpeg` with `h264_mmal` decode and `vout_rpi` presentation.

See `Touch_and_Backlight_Notes.md` for the full attempt history and `GPU_Output_Test_Plan.md` for the GPU-output experiment.

## Conclusion

Your Raspberry Pi now starts the Tapo camera stream on boot, presents it efficiently through the GPU/MMAL display path, and uses a single tap to turn both the stream and backlight off or back on.