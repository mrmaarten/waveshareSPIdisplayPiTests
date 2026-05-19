# Waveshare 3.5" SPI Display — Overlay & Driver Summary

## Hardware

| Component        | Detail                                      |
|------------------|---------------------------------------------|
| Display          | Waveshare 3.5" SPI LCD (SKU MPI3501)        |
| Controller IC    | ILI9486                                     |
| Resolution       | 480 x 320 (landscape)                       |
| Interface        | SPI (SPI0, chip-select 0)                   |
| Pixel format     | RGB565 little-endian (`rgb565le`)            |
| Raspberry Pi     | 3B+                                         |
| OS               | Raspberry Pi OS Bookworm (kernel 6.x)       |

## GPIO Pinout

| Function      | GPIO | Physical pin | Notes                          |
|---------------|------|--------------|--------------------------------|
| SPI MOSI      | 10   | 19           | Data to display                |
| SPI MISO      | 9    | 21           | Not used by display            |
| SPI SCLK      | 11   | 23           | SPI clock                      |
| SPI CE0       | 8    | 24           | Chip-select                    |
| DC (Data/Cmd) | 25   | 22           | Data / command select          |
| Reset         | 27   | 13           | Hardware reset                 |
| Backlight     | 24   | 18           | Active-high, toggleable        |

## Kernel Driver / Device-Tree Overlay

The display is driven by the in-kernel **fbtft** staging driver. A device-tree overlay tells the kernel which SPI controller chip, pinout and init sequence to use.

Two overlay options were tested during bring-up:

### Option A — Generic fbtft overlay (working, needs color negate workaround)

Added to `/boot/firmware/config.txt`:

```ini
dtparam=spi=on
dtoverlay=fbtft,spi0-0,ili9486,regwidth=16,buswidth=8,dc_pin=25,reset_pin=27,led_pin=24,speed=16000000,rotate=270,fps=30
```

This loads the `fbtft` module with the generic ILI9486 init sequence. It produces a working framebuffer (`/dev/fb0`) but the init registers differ slightly from the Waveshare panel, causing **inverted / photo-negative colors**. The streaming scripts compensate with an ffmpeg `negate` filter (`FFMPEG_NEGATE_COLORS = True` in `pi_stream_common.py`).

### Option B — waveshare35b-v2 overlay (correct colors)

```ini
dtparam=spi=on
dtoverlay=waveshare35b-v2:rotate=90
```

Requires the compiled overlay blob to be present at `/boot/firmware/overlays/waveshare35b-v2.dtbo` (copied from the Waveshare `LCD-show` repo on the Pi: `/home/maarten/LCD-show/waveshare35b-v2-overlay.dtb`). This overlay uses the vendor-correct ILI9486 init sequence so colors display correctly without negation.

## Bookworm-Specific Configuration

Raspberry Pi OS Bookworm enables KMS (`vc4-kms-v3d`) by default, which routes all display output to HDMI via DRM. For the SPI framebuffer to work as the primary display:

1. **KMS is left enabled** — the fbtft overlay still creates `/dev/fb0` for the SPI LCD.
2. **Boot console is redirected** to the SPI framebuffer via kernel command line:
   ```
   fbcon=map:1
   ```
   (appended to `/boot/firmware/cmdline.txt`)
3. **Desktop / display-manager is disabled** — the Pi boots to a text console:
   ```bash
   systemctl set-default multi-user.target
   systemctl disable display-manager
   ```
4. `quiet` and `splash` are removed from `cmdline.txt` so boot messages are visible on the LCD.

## Framebuffer Details

| Property         | Value                    |
|------------------|--------------------------|
| Device node      | `/dev/fb0`               |
| Name (sysfs)     | `fb_ili9486` or `waveshare35b-v2` (depending on overlay) |
| Size             | 480 x 320 x 2 = 307 200 bytes |
| Pixel format     | RGB565 little-endian     |
| SPI clock        | 16 MHz                   |
| Target FPS       | 30                       |
| Rotation         | 270° (fbtft) or 90° (waveshare35b-v2) — both produce the same landscape orientation |

Writing raw pixel data to the framebuffer is immediate:

```bash
# Random noise test
cat /dev/urandom > /dev/fb0

# Solid red (RGB565 0xF800 = bytes 0x00 0xF8)
python3 -c "f=open('/dev/fb0','wb'); f.write(b'\x00\xf8'*(480*320)); f.close()"
```

SPI throughput can be monitored via:

```bash
cat /sys/bus/spi/devices/spi0.0/statistics/bytes_tx
```

## Backlight Control

GPIO 24 drives the backlight (active-high). It can be toggled at runtime without touching the driver:

```bash
# Off
pinctrl set 24 op dl

# On
pinctrl set 24 op dh
```

The `ssh_test_backlight.py` script automates this via SSH.

## Video Streaming Pipeline

The project streams video from a Windows PC to the Pi's framebuffer over TCP using ffmpeg on both ends.

```
┌──────────┐   H.264/MPEG-TS    ┌──────────┐   raw RGB565   ┌──────────┐
│  PC      │ ──── TCP:5000 ───> │  Pi      │ ────────────── │  /dev/fb0│
│  ffmpeg  │                    │  ffmpeg  │                │  (SPI)   │
└──────────┘                    └──────────┘                └──────────┘
```

**PC side** (push mode — `ssh_stream_video_loop.py`):
- Reads `test.mp4`, loops, scales to 480x320, encodes H.264 ultrafast/zerolatency.
- Pushes MPEG-TS over `tcp://<pi-ip>:5000`.

**Pi side** (listener):
- `ffmpeg -i tcp://0.0.0.0:5000?listen=1 -vf scale=480:320[,negate] -pix_fmt rgb565le -f fbdev /dev/fb0`

An alternative **pull mode** (`ssh_receive_network_stream.py`) reverses the roles: PC listens, Pi connects — simulating a camera/RTSP-like topology.

## Script Inventory

| Script                                | Purpose                                              |
|---------------------------------------|------------------------------------------------------|
| `pi_stream_common.py`                 | Shared SSH/ffmpeg helpers, constants, stream commands |
| `ssh_stream_video_loop.py`            | PC-push video stream to Pi framebuffer               |
| `ssh_receive_network_stream.py`       | PC-listen / Pi-pull video stream                     |
| `ssh_show_test_pattern.py`            | Draw color-bar + corner-marker pattern on fb0        |
| `ssh_test_backlight.py`               | Toggle backlight GPIO on/off                         |
| `ssh_fix_display_invert.py`           | Switch overlay to fix inverted colors                |
| `ssh_switch_driver.py`               | Switch between mipi-dbi-spi and fbtft overlays       |
| `ssh_finalize_display_and_boot_console.py` | Set fbtft overlay, boot console, disable desktop |
| `ssh_finalize_blank_fix.py`           | Final waveshare35b-v2 overlay + fbcon + CLI boot     |
| `ssh_diag.py` / `ssh_diag2.py` / `ssh_diag3.py` / `ssh_diag_lcd.py` | Diagnostic info gathering |
| `ssh_reboot.py`                       | Simple SSH reboot                                    |
