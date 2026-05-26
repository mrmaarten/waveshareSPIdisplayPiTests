# HyperPixel RTSP: GPU Output Test Plan

Goal: test whether `ffmpeg` can send the RTSP stream to Raspberry Pi's MMAL video output (`vout_rpi`) instead of converting/scaling frames on the CPU and writing `bgra` pixels to `/dev/fb0`.

Result: successful on 2026-05-26. The HyperPixel showed a good live video feed through `vout_rpi`, and `ffmpeg` CPU dropped from the previous framebuffer-path observation of about `85%` to roughly `20-32%` during the GPU-output test.

---

## Why test this?

The current production command is:

```bash
ffmpeg ... \
  -c:v h264_mmal \
  -i "$RTSP_URL" \
  -vf scale=800:480 -pix_fmt bgra \
  -f fbdev /dev/fb0
```

That already uses the GPU for H.264 decode, but the Pi still does these parts on CPU:

- scale camera video from `640x360` to `800x480`
- convert camera YUV frames to framebuffer `bgra`
- copy every frame into `/dev/fb0`

The Pi's `ffmpeg` build also exposes:

```text
vout_rpi  Rpi (mmal) video output device
```

If `vout_rpi` works with the HyperPixel DPI display, the GPU/display pipeline may handle presentation, scaling, and colorspace conversion more efficiently.

On this Pi, it does work: fullscreen `vout_rpi` displayed correctly on the HyperPixel.

---

## Current Known Sizes

Camera stream:

```text
codec: h264
size: 640x360
pixel format: yuvj420p
average frame rate: 15 fps
```

HyperPixel framebuffer:

```text
size: 800x480
pixel format: 32-bit BGRA-style framebuffer
device: /dev/fb0
```

The current `scale=800:480` fills the screen, but it stretches the 16:9 camera image to the 5:3 screen.

---

## Test Workflow

Yes: stop the normal stream first, then run a one-off command, then look at the screen.

The normal `hyperpixel-rtsp-display.service` owns the current stream. Stop it before testing so two `ffmpeg` processes do not fight over display output. Also stop the touch power service during the test so a tap cannot restart the production stream in the background.

### 1. SSH into the Pi

From the PC:

```bash
ssh pi@raspberrypi.local
```

### 2. Stop the production stream and touch controller

```bash
sudo systemctl stop hyperpixel-rtsp-display.service
sudo systemctl stop hyperpixel-touch-display-power.service
```

Keep the backlight on:

```bash
sudo python3 -c "from rpi_backlight import Backlight; Backlight().power = True"
```

### 3. Run the GPU-output test

This sources the existing root-only RTSP config, so the camera password does not need to be typed into the shell.

```bash
sudo bash -lc '. /etc/default/hyperpixel-rtsp; exec ffmpeg -hide_banner -loglevel warning \
  -rtsp_transport tcp -stimeout 5000000 \
  -fflags +nobuffer+genpts -flags low_delay \
  -use_wallclock_as_timestamps 1 \
  -c:v h264_mmal \
  -probesize 32 -analyzeduration 0 \
  -i "$RTSP_URL" \
  -an \
  -f vout_rpi -fullscreen 1 -'
```

This is the tested production candidate. A first run without generated timestamps also displayed video, but it repeatedly logged `non monotonically increasing dts` warnings. Adding `-fflags +nobuffer+genpts` and `-use_wallclock_as_timestamps 1` reduced the log noise to a single observed DTS warning while keeping CPU low.

What to check visually:

- Does live camera video appear on the HyperPixel?
- Is it full screen?
- Is the aspect ratio acceptable?
- Are colors correct?
- Is latency similar, better, or worse than the framebuffer version?
- Does touch/backlight still behave normally after restoring services?

Stop the manual test with `Ctrl+C`.

### 4. If fullscreen does not work, try a forced 800x480 window

```bash
sudo bash -lc '. /etc/default/hyperpixel-rtsp; exec ffmpeg -hide_banner -loglevel warning \
  -rtsp_transport tcp -stimeout 5000000 \
  -c:v h264_mmal \
  -fflags nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 \
  -i "$RTSP_URL" \
  -an \
  -f vout_rpi -window_size 800x480 -window_x 0 -window_y 0 -'
```

Stop with `Ctrl+C`.

### 5. If video appears behind/under console output, try a higher display layer

```bash
sudo bash -lc '. /etc/default/hyperpixel-rtsp; exec ffmpeg -hide_banner -loglevel warning \
  -rtsp_transport tcp -stimeout 5000000 \
  -c:v h264_mmal \
  -fflags nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 \
  -i "$RTSP_URL" \
  -an \
  -f vout_rpi -fullscreen 1 -display_layer 5 -'
```

Stop with `Ctrl+C`.

---

## Measure CPU During The Test

Open a second SSH session while the manual `ffmpeg` command is running:

```bash
ps -C ffmpeg -o pid,stat,pcpu,pmem,args
```

Compare against the current framebuffer pipeline, which was observed around `85%` CPU while running:

```text
ffmpeg ... -vf scale=800:480 -pix_fmt bgra -f fbdev /dev/fb0
```

Good outcome:

- HyperPixel shows live camera video.
- CPU is much lower than the framebuffer path.
- The command exits cleanly with `Ctrl+C`.

Observed outcome on 2026-05-26:

- HyperPixel showed good live video with fullscreen `vout_rpi`.
- `ffmpeg` remained running under system load checks.
- CPU was around `51%` immediately after startup, then settled around `24%`, then about `19.5%` after 23 seconds.
- Log contained the expected RTSP probing warning and one DTS warning with the generated-timestamp variant.

Bad outcome:

- Video does not appear on the HyperPixel.
- Video appears only on HDMI or nowhere.
- Colors/aspect/layering are wrong.
- CPU is not meaningfully lower.

If the bad outcome happens, keep the existing `/dev/fb0` production path.

---

## Restore Normal Production Mode

After testing:

```bash
sudo systemctl start hyperpixel-touch-display-power.service
sudo systemctl start hyperpixel-rtsp-display.service
```

Check:

```bash
systemctl is-active hyperpixel-touch-display-power.service hyperpixel-rtsp-display.service
pgrep -af 'ffmpeg.*rtsp' || echo "no ffmpeg"
```

Expected when restored and screen is on:

```text
active
active
ffmpeg ... -c:v h264_mmal ... -f vout_rpi -fullscreen 1 -
```

If restore behaves strangely, re-run the production installer from the repo root on the PC:

```bash
python ssh_install_touch_rtsp_power.py
```

---

## Decision Criteria

Switch to `vout_rpi` only if all of these are true:

- It displays correctly on the HyperPixel, not just HDMI.
- It can run full-screen or in an acceptable centered/aspect-correct layout.
- CPU usage is clearly lower than the current `fbdev` path.
- Starting/stopping it from systemd behaves reliably.
- Touch power toggling can be adjusted cleanly for the new output path.

If any of these fail, the current framebuffer approach is slower but known-good.

Decision: switch the production installer to `vout_rpi`. Keep the old framebuffer approach in git history as the fallback if later testing finds a systemd, touch power, or boot reliability problem.
