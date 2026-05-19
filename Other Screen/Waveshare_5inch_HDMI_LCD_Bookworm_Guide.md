# Waveshare 5-inch HDMI LCD (V2.02) Guide for Raspberry Pi Bookworm

## Overview
This screen is a **Waveshare 5-inch HDMI LCD (V2.02)** (or a direct, identical clone of it). It features an 800x480 resolution and a resistive touch screen. 

*   **Video:** It receives the video signal through the U-shaped HDMI bridge connector linking the Pi's HDMI port to the screen's HDMI port.
*   **Touch & Power:** The 40-pin GPIO header is used to draw power (5V/GND) for the display backlight and to route the SPI pins for the touch controller (which is an `ads7846` / `XPT2046` compatible resistive touch chip).

## Compatibility with 64-bit Bookworm (and beyond)
**Yes, it is compatible, but with some modern caveats.** 

Because Raspberry Pi OS "Bookworm" (and beyond) switched from the older X11 windowing system to **Wayland/Wayfire** and uses **KMS** (Kernel Mode Setting) for video drivers, the old manufacturer installation scripts (like the common `LCD-show` script found on GitHub) are mostly broken or deprecated on modern 64-bit OS versions. 

Here is how it interacts with the modern overlay system:

### 1. Video (HDMI)
In the past, you would force the 800x480 resolution using `hdmi_cvt` and `hdmi_group` in `/boot/config.txt`. On Bookworm, KMS often ignores these settings. 
Instead, to force the custom resolution, you typically need to append a video parameter to the single line inside `/boot/firmware/cmdline.txt`. 

Append the following to the end of the line (do not create a new line):
```text
video=HDMI-A-1:800x480M@60D
```

### 2. Touch (Device Tree Overlay)
The touch functionality fully supports the modern overlay system. You do not need third-party drivers. The Linux kernel has built-in support for this touch controller via the `ads7846` overlay. 

You enable it by adding a line like this to your `/boot/firmware/config.txt`:
```ini
dtparam=spi=on
dtoverlay=ads7846,cs=1,penirq=25,penirq_pull=2,speed=50000,keep_vref_on=1,swapxy=0,pmax=255,xohms=150,xmin=200,xmax=3900,ymin=200,ymax=3900
```
*(Note: `swapxy`, `xmin`, `xmax`, etc., are the parameters that dictate the orientation and edge boundaries of the touch).*

### 3. The "Gotcha": Touch Calibration on Bookworm
If the touch orientation is upside down or misaligned compared to the screen, this is where Bookworm makes things tricky:
*   Old tutorials will tell you to use `xinput_calibrator` and edit an X11 file (`99-calibration.conf`). **This will not work on Bookworm** because it uses Wayland instead of X11.
*   To calibrate touch on Bookworm, you have two options:
    1.  **The modern way:** Use `udev` rules and calculate a `LIBINPUT_CALIBRATION_MATRIX` to flip/rotate the touch input at the system level. 
    2.  **The easy fallback:** Use `sudo raspi-config` -> `Advanced Options` -> `Wayland` and switch the backend back to **X11**. Once you are back on X11, all the old tutorials, calibration tools, and manufacturer driver scripts for this screen will work perfectly again.

## Hardware Pinout & Power Control

The screen uses a 26-pin female header that plugs into the first 26 pins of the Raspberry Pi's 40-pin GPIO header. However, it only actively uses 11 specific pins. If you want to wire it manually (e.g., using jumper wires to intercept the 5V line with a relay), here is the exact pinout:

### Power & Ground (Required)
*   **Pin 2 & 4 (5V):** Main power for the screen and backlight.
*   **Pin 6, 9, 14, 20, 25 (GND):** Ground connections. (It is recommended to connect all of them for stable power).

### Touch Controller (SPI Interface)
These pins are required for the `ads7846` resistive touch chip to communicate with the Pi:
*   **Pin 19 (GPIO 10 / SPI0_MOSI):** `TP_SI` (Touch Panel SPI Data Input)
*   **Pin 21 (GPIO 9 / SPI0_MISO):** `TP_SO` (Touch Panel SPI Data Output)
*   **Pin 22 (GPIO 25):** `TP_IRQ` (Touch Panel Interrupt)
*   **Pin 23 (GPIO 11 / SPI0_SCLK):** `TP_SCK` (Touch Panel SPI Clock)
*   **Pin 24 (GPIO 8 / SPI0_CE0):** `TP_CS` (Touch Panel Chip Select)

### Unused Pins
The following pins within the 26-pin footprint are completely unused by the screen (NC) and are free for other components (like relays, buttons, or sensors):
*   Pins 1 & 17 (3.3V)
*   Pins 3 & 5 (I2C)
*   Pins 7, 8, 10, 11, 12, 13, 15, 16, 18, 26
*   *All pins from 27 to 40 on the Pi are also completely exposed and free to use.*

### Turning Off the Screen (Relay Setup)
The Raspberry Pi cannot turn off its physical 5V pins via software. If you stop the video stream, the screen's backlight will remain on. To physically cut power to the screen using a script:
1.  Run a wire from **Pin 2** (and optionally Pin 4) on the Pi to the input of a 5V relay module or MOSFET.
2.  Run a wire from the output of the relay to the 5V pins on the screen's header.
3.  Connect the ground and touch pins directly as listed above.
4.  Use one of the free GPIO pins (e.g., Pin 11 / GPIO 17) to control the relay from your code.

