# Raspberry Pi LCD setup and debugging
_Exported on 5/17/2026 at 20:49:05 GMT+2 from Cursor (3.3.30)_

---

**User**

I am trying to make this screen work on a Raspberry pi 3b+. I am running bookworm or later. I am trying to get it working with overlays. but so far I am not seeing anything on the screen. The screens back light is on.  What would you do via ssh to get the screen working? How can we debug this?

---

**Cursor**

This is a very common SPI-based 3.5" LCD (ILI9486 driver, 320x480, SKU MPI3501). These screens are well-known but can be tricky on Bookworm because Raspberry Pi OS switched to KMS/DRM by default, which changed how these SPI displays work. Here's a systematic debugging approach via SSH:

## 1. Check What You're Working With

First, gather system info:

```bash
# OS version
cat /etc/os-release

# Kernel version
uname -a

# Check current boot config
cat /boot/firmware/config.txt

# Check if SPI is enabled
ls /dev/spi*

# Check loaded overlays and modules
dmesg | grep -i spi
dmesg | grep -i ili
dmesg | grep -i fb
dmesg | grep -i drm
```

> **Note:** On Bookworm the boot config moved from `/boot/config.txt` to `/boot/firmware/config.txt`. Make sure you're editing the right one.

## 2. Enable SPI and the Correct Overlay

In `/boot/firmware/config.txt`, you need:

```ini
# Make sure SPI is on
dtparam=spi=on

# For ILI9486-based MPI3501 screens, try this overlay:
dtoverlay=piscreen,speed=16000000,rotate=90
```

If `piscreen` doesn't work, alternatives to try (one at a time):

```ini
# Option B - generic ILI9486 via the ads7846 touch + piscreen2r
dtoverlay=piscreen2r,speed=16000000,rotate=90

# Option C - use the fbtft driver directly
dtoverlay=fbtft,spi0-0,ili9486,speed=16000000,bgr=1,fps=30,rotate=90,width=320,height=480
```

After editing, reboot: `sudo reboot`

## 3. The Bookworm KMS Problem

This is likely your main issue. Bookworm enables KMS by default, which means the console and desktop go to HDMI via the DRM driver, **not** to SPI framebuffer devices. Check this line in `config.txt`:

```ini
# You'll likely see this:
dtoverlay=vc4-kms-v3d
```

You have a few options:

### Option A: Switch to legacy framebuffer mode (simplest for SPI LCDs)

```ini
# Comment out or remove the KMS line:
#dtoverlay=vc4-kms-v3d

# Or switch to fkms (partial KMS, still allows fbcp to work):
dtoverlay=vc4-fkms-v3d
```

Then use `fbcp` (framebuffer copy) to mirror the primary display to the SPI framebuffer.

### Option B: Keep KMS and use fbcp-ili9341 (better performance)

```bash
sudo apt install cmake git
git clone https://github.com/juj/fbcp-ili9341.git
cd fbcp-ili9341
mkdir build && cd build
cmake -DSPI_BUS_CLOCK_DIVISOR=6 -DILI9486=ON -DGPIO_TFT_DATA_CONTROL=25 -DGPIO_TFT_RESET_PIN=27 -DSTATISTICS=0 -DDISPLAY_ROTATE_180_DEGREES=OFF ..
make -j
sudo ./fbcp-ili9341
```

The GPIO pins depend on your exact wiring — for the MPI3501 hat, typical pins are DC=25, RST=27, but verify with your hat's pinout.

## 4. Debugging Step by Step via SSH

```bash
# Step 1: Is the SPI device present?
ls -la /dev/spi*
# You should see /dev/spidev0.0 and /dev/spidev0.1

# Step 2: Is there a framebuffer device for the LCD?
ls -la /dev/fb*
# fb0 = HDMI, fb1 = SPI LCD (if overlay loaded correctly)

# Step 3: Check if the overlay loaded
dmesg | grep -i "ili9486\|fbtft\|piscreen\|fb1"
# Look for errors or successful probe messages

# Step 4: Check all loaded dtoverlays
sudo vcdbg log msg 2>&1 | grep -i overlay

# Step 5: If /dev/fb1 exists, test it directly!
# Fill screen with random data (you should see noise):
cat /dev/urandom > /dev/fb1
# Or fill with a color:
dd if=/dev/zero bs=1024 count=300 > /dev/fb1

# Step 6: If fb1 doesn't exist, check the kernel module
lsmod | grep fbtft
# If empty, try loading manually:
sudo modprobe fbtft_device name=piscreen speed=16000000 rotate=90
```

## 5. If /dev/fb1 Exists But Screen Is Blank

The overlay loaded but nothing is being sent to it. You need to either:

```bash
# Mirror fb0 to fb1 with fbcp
sudo apt install fbcp
sudo fbcp &

# Or redirect the console to fb1
con2fbmap 1 1
```

## 6. Common Gotcha: GPIO Pin Conflicts

Make sure nothing else is claiming the SPI0 pins (GPIO 7-11) or the DC/RST pins. Check:

```bash
# See GPIO state
raspi-gpio get
# Or
pinctrl get
```

## Summary / Most Likely Fix

Given you're on Bookworm with the backlight on but no image:

1. **Backlight on** = the screen has power (good)
2. **No image** = either the SPI overlay isn't loading, or KMS is directing all output to HDMI

The most common fix is:
1. Ensure `dtparam=spi=on` and `dtoverlay=piscreen,speed=16000000,rotate=90` are in `/boot/firmware/config.txt`
2. Comment out `dtoverlay=vc4-kms-v3d` (or switch to `vc4-fkms-v3d`)
3. Reboot
4. Check if `/dev/fb1` exists
5. If yes, run `fbcp` to mirror the display

Would you like me to look at any existing config files in your project, or help you draft the exact `config.txt` changes?

