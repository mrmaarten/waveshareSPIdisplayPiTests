# HyperPixel: Touch, Backlight & Camera — What We Tried

Notes from getting the Pimoroni HyperPixel 3.5" working on **Raspberry Pi OS Legacy (32-bit Buster, CLI)**.

**Current goal (achieved):** On boot, the Pi shows an **RTSP camera feed** on the display. **Tap the screen** to turn the backlight and stream **off together** (power save), or back **on**. No PC required after install.

---

## Production — unified touch + RTSP power toggle (recommended)

One install deploys RTSP + a touch listener that toggles **backlight and stream together**.

| Service | Role | Boot |
|---------|------|------|
| `hyperpixel-rtsp-display.service` | `ffmpeg` RTSP → 800×480 `bgra` → `/dev/fb0` | **Enabled** — starts on boot |
| `hyperpixel-touch-display-power.service` | I2C touch → backlight + `systemctl start/stop` RTSP | **Enabled** — syncs display on at start |
| `hyperpixel-backlight-touch.service` | Legacy backlight-only touch | **Disabled** by power installer (not removed) |

```
  [Camera RTSP] ──network──► Pi ffmpeg ──► /dev/fb0
         ▲                           │
         │              systemctl start/stop
         └──────── [Finger tap] ──I2C──► hyperpixel_touch_display_power.py
                                        └──► rpi_backlight on/off
```

**Boot:** stream **on**, backlight **on** (same as before). **First tap:** both **off** (stops ffmpeg, dims panel). **Second tap:** both **on**.

**One-time install from PC (repo root):**

1. Copy [`.env.example`](../.env.example) → `.env` and set Pi SSH + camera credentials.
2. Install unified power mode:

   ```bash
   python ssh_install_touch_rtsp_power.py
   ```

   Use `--no-start` to update config/units without restarting RTSP immediately.

On macOS, if `paramiko` is missing: `python3 -m venv .venv && .venv/bin/pip install paramiko` then use `.venv/bin/python` for the commands above.

**Example `.env` (camera section):**

```env
RTSP_HOST=192.168.0.190
RTSP_PORT=554
RTSP_PATH=/stream2
RTSP_USER=Camera
RTSP_PASS=your_password_here
```

Equivalent stream URL: `rtsp://Camera@192.168.0.190:554/stream2` (user/password are stored separately; special characters in the password are **percent-encoded** on the Pi, e.g. `@` → `%40`).

**Verify after reboot:**

```bash
ssh pi@raspberrypi.local "systemctl is-active hyperpixel-rtsp-display.service hyperpixel-touch-display-power.service"
# both → active

ssh pi@raspberrypi.local "systemctl is-enabled hyperpixel-backlight-touch.service"
# → disabled

ssh pi@raspberrypi.local "pgrep -af 'ffmpeg.*rtsp' || echo 'no ffmpeg (display off)'"
ssh pi@raspberrypi.local "journalctl -u hyperpixel-touch-display-power.service -n 10 --no-pager"
```

**Manual test:** camera visible → tap → backlight off and no `ffmpeg` → tap → stream returns.

**Change camera or password:** Edit `.env` on PC, run `python ssh_install_touch_rtsp_power.py` again.

**Repo files:** [`ssh_install_touch_rtsp_power.py`](../ssh_install_touch_rtsp_power.py), [`env_config.py`](../env_config.py).

**Pi script:** `/home/pi/hyperpixel_touch_display_power.py`

### Rollback to legacy (backlight-only touch)

```bash
sudo systemctl disable --now hyperpixel-touch-display-power.service
sudo systemctl enable --now hyperpixel-backlight-touch.service
sudo systemctl enable --now hyperpixel-rtsp-display.service
```

Or from PC: `python ssh_install_touch_toggle.py` then `python ssh_install_rtsp_display.py` (do not re-run power installer).

---

## Legacy — split camera + backlight touch (superseded)

Two independent systemd services (stream always on; tap only dims panel):

| Service | Role |
|---------|------|
| `hyperpixel-rtsp-display.service` | RTSP → framebuffer |
| `hyperpixel-backlight-touch.service` | I2C touch → `rpi_backlight` only |

```
  [Camera RTSP] ──network──► Pi ffmpeg ──► /dev/fb0 (HyperPixel image)
                                    ▲
  [Finger tap] ──I2C 0x5c──► hyperpixel_backlight_touch.py ──► backlight on/off
```

**Install (legacy):**

```bash
python ssh_install_touch_toggle.py
python ssh_install_rtsp_display.py
```

**Verify (legacy):**

```bash
ssh pi@raspberrypi.local "systemctl is-active hyperpixel-rtsp-display.service hyperpixel-backlight-touch.service"
```

**Repo files:** [`ssh_install_rtsp_display.py`](../ssh_install_rtsp_display.py), [`ssh_install_touch_toggle.py`](../ssh_install_touch_toggle.py).

---

### RTSP camera on boot (detail)

| Item | Detail |
|------|--------|
| **Configure** | Repo `.env`: `RTSP_HOST`, `RTSP_PORT`, `RTSP_PATH`, `RTSP_USER`, `RTSP_PASS` |
| **Install** | `python ssh_install_rtsp_display.py` (use `--no-start` to enable on boot without starting now) |
| **Pi service** | `hyperpixel-rtsp-display.service` — `After=network-online.target`, `Restart=always` / `RestartSec=5` |
| **Pi config** | `/etc/default/hyperpixel-rtsp` (root, mode `600`) — `RTSP_URL`, `WIDTH=800`, `HEIGHT=480`, `PIX_FMT=bgra` |
| **Pi script** | `/usr/local/bin/hyperpixel_rtsp_display.sh` |
| **ffmpeg** | `-rtsp_transport tcp -stimeout 5000000` → scale → `bgra` → `-f fbdev /dev/fb0` (no audio) |
| **Drop recovery** | Buster `ffmpeg` has no `-reconnect`; systemd restarts the service if ffmpeg exits |
| **Touch (legacy)** | `hyperpixel-backlight-touch.service` — backlight only; see unified installer above |

**Status:** **Success** — stream runs on boot. With power installer, tap stops/starts stream + backlight.

**Troubleshooting:**

| Symptom | Check |
|---------|--------|
| Black screen, service `active` | Camera reachable from Pi: `ping 192.168.0.190`; credentials in `.env`; re-run install after `.env` change |
| Service crash-loop | `journalctl -u hyperpixel-rtsp-display.service -f` — auth errors, wrong path, or ffmpeg option not supported |
| `Option reconnect not found` | Old script on Pi — re-run `ssh_install_rtsp_display.py` (reconnect flags removed for Buster) |
| Harmless log spam | `[fbdev] non monotonically increasing dts` — known with RTSP → fbdev; video can still display |
| Change camera URL | Edit `.env` on PC, run `python ssh_install_touch_rtsp_power.py` (or legacy `ssh_install_rtsp_display.py`) |

**Stop / disable stream only:**

```bash
sudo systemctl stop hyperpixel-rtsp-display.service
sudo systemctl disable hyperpixel-rtsp-display.service
```

---

### Touch — tap screen to toggle backlight only (legacy CLI)

| Item | Detail |
|------|--------|
| **Install** | `python ssh_install_touch_toggle.py` (superseded by `ssh_install_touch_rtsp_power.py`) |
| **Pi service** | `hyperpixel-backlight-touch.service` (enabled on boot) |
| **Pi script** | `/home/pi/hyperpixel_backlight_touch.py` |
| **How it works** | Python 3: **I2C bus 11** @ `0x5c` + GPIO interrupt (pin 27). No desktop, no `uinput`, no `evdev`. Toggles `rpi_backlight` per tap (0.5s debounce). |
| **Status** | **Success** — works with RTSP video on screen |

**Repo file:** [`ssh_install_touch_toggle.py`](../ssh_install_touch_toggle.py)

---

### Backlight — without touch (optional)

| Method | Command / action |
|--------|------------------|
| **SSH anytime** | `sudo python3 -c "from rpi_backlight import Backlight; Backlight().power = True"` (or `False`) |
| **While PC streaming** | `python ssh_stream_hyperpixel.py` → **`1`** (on) / **`2`** (off) |

**Repo file:** [`ssh_stream_hyperpixel.py`](../ssh_stream_hyperpixel.py)

---

### Video on screen from PC (dev / test only)

Not needed for normal use once RTSP boot display is installed.

```bash
python ssh_stream_hyperpixel.py
```

PC pushes H.264 over TCP; Pi `ffmpeg` → `/dev/fb0`. Same panel settings: **800×480**, **`bgra`**.

---

## Hardware / OS context

- Pi hostname: `raspberrypi.local` (see repo `.env` for `PI_HOST`, `PI_USER`, `PI_PASS`)
- Display: original HyperPixel 3.5" (800×480), `dtoverlay=hyperpixel` + `dtoverlay=hyperpixel-gpio-backlight`
- Touch controller on I2C address `0x5c` (visible on **bus 11** as `/dev/i2c-11`, not bus 3)
- Backlight: `rpi_backlight` (kernel `hyperpixel-gpio-backlight` overlay)
- Camera: RTSP on LAN (e.g. `rtsp://USER@HOST:554/stream2`)

---

## Backlight on/off without touch (working)

These methods **do work** on this setup.

### 1. PC keyboard while streaming (`ssh_stream_hyperpixel.py`)

While `python ssh_stream_hyperpixel.py` is running on Windows, keys send SSH commands to the Pi:

| Key | Action |
|-----|--------|
| `1` | Screen **ON** |
| `2` | Screen **OFF** |
| `q` | Stop stream and exit |

**How it works:** Each key runs on the Pi (as root via `sudo`):

```bash
python3 -c "from rpi_backlight import Backlight; Backlight().power = True"   # or False
```

**Prerequisites:** `rpi_backlight` installed for Python 3 (`pip3 install rpi_backlight`). The stream script calls `ensure_rpi_backlight()` on startup if missing.

**Status:** **Success** — confirmed during PC loop tests; superseded by touch + RTSP for daily use.

**Repo files:** [`ssh_stream_hyperpixel.py`](../ssh_stream_hyperpixel.py), [`pi_stream_common.py`](../pi_stream_common.py).

---

### 2. Manual SSH one-liner (any time)

From your PC:

```bash
ssh pi@raspberrypi.local
```

Then:

```bash
# ON
sudo python3 -c "from rpi_backlight import Backlight; Backlight().power = True"

# OFF
sudo python3 -c "from rpi_backlight import Backlight; Backlight().power = False"
```

**Status:** **Success** — same mechanism as the keyboard controls above.

---

### 3. Video to framebuffer — PC push vs Pi RTSP

| Mode | How | When |
|------|-----|------|
| **Pi RTSP (production)** | `hyperpixel-rtsp-display.service` | Boot, no PC |
| **PC TCP push** | `ssh_stream_hyperpixel.py` | Development, test patterns |

**HyperPixel ffmpeg settings** (both paths):

- Resolution: `800×480`
- Pixel format: `bgra` (Pi `fbdev` rejected `rgb565le`)

**Status:** **Success** for both; backlight is separate (touch or SSH).

---

## Touch-to-toggle backlight — attempts and outcomes

Touch **can** work in CLI (no desktop). It does not need X11. The failures below were implementation/boot issues, not “CLI doesn’t support touch.”

| # | Approach | What it did | Result | Why |
|---|----------|-------------|--------|-----|
| 1 | **[Setup_Guide.md](Setup_Guide.md) plan** — `touch_toggle.py` + `touchtoggle.service` | `evdev` loop on input device named **Goodix** / **gt911**; toggle `Backlight().power` on `BTN_TOUCH` | **Failed** | On this Pi the touch stack does not expose a Goodix-named node. Service logged `Touch screen not found!` and exited. |
| 2 | **`ssh_install_touch_toggle.py` (v1)** — same Goodix matching, deployed via SSH | Wrote `/home/pi/touch_toggle.py`, enabled `touchtoggle.service` | **Failed** | Same as #1 after deploy. |
| 3 | **Widen device search** — match **Touchscreen**, `BTN_TOUCH` capability, wait up to 60s for device | Updated `touch_toggle.py`; service `After=hyperpixel-touch.service` | **Failed** | Found `/dev/input/event7` (`Touchscreen`) but `read_loop()` immediately raised `OSError: [Errno 19] No such device`. Virtual input node is unstable when Pimoroni’s daemon misbehaves. |
| 4 | **Install `rpi_backlight` on Pi** | `apt` / `pip3 install rpi_backlight` for Python 3 | **Success** (dependency only) | Required for keyboard/SSH backlight; did not fix touch by itself. |
| 5 | **Patch `/usr/bin/hyperpixel-touch`** — call `toggle_backlight()` on first finger press (Python 3 subprocess) | Injected into Pimoroni’s I2C touch daemon | **Failed** (touch) | Pimoroni service exits before main loop: `"/dev/uinput" cannot be opened for writing"`. No touch processing runs; patch never executes. |
| 6 | **`/dev/uinput` boot fix** — `tmpfiles.d` mode `0666`, systemd `ExecStartPre` for `hyperpixel-touch` | Persist permissions, restart daemon | **Partial** | `chmod` helps manual starts; **`hyperpixel-touch.service` still fails** on boot (forking + uinput timing). Not reliable for touch. |
| 7 | **Standalone I2C listener** — `hyperpixel_backlight_touch.py` + `hyperpixel-backlight-touch.service` | Python 3: GPIO interrupt + `smbus` @ `0x5c`, no `uinput` | **Failed first** | Used `SMBus(3)`; this Pi only has **`/dev/i2c-11`** → `FileNotFoundError`. |
| 8 | **I2C bus auto-detect** — try buses `11, 3, 1, 0` | Same script, `open_touch_bus()` | **Success** | Service stays **active**; touch on bus 11. **Confirmed:** tap toggles backlight on/off in CLI. |
| 9 | **Restore stock `hyperpixel-touch`** | Removed backlight patch to avoid double-toggle if Pimoroni daemon ever runs | **N/A** | Avoids duplicate toggles; Pimoroni daemon still not healthy on boot. |
| 10 | **Disable `touchtoggle.service`** | Stopped conflicting evdev listener | **Success** (cleanup) | Prevents crash-looping service from old attempts. |
| 11 | **RTSP boot display** — `hyperpixel-rtsp-display.service` + `.env` deploy | Pi pulls camera RTSP to fb0; touch service unchanged | **Success** | Legacy split layout: camera on boot + tap for backlight only. |
| 12 | **Unified power toggle** — `hyperpixel-touch-display-power.service` | Tap toggles backlight + `systemctl start/stop` RTSP | **Success** | Recommended: boot on; tap off/on saves Pi + panel power. |

See **[Production — unified touch + RTSP power toggle](#production--unified-touch--rtsp-power-toggle-recommended)** for install and verification.

---

## Pimoroni `hyperpixel-touch.service` (reference)

Installed by `curl https://get.pimoroni.com/hyperpixel | bash`.

| Item | Detail |
|------|--------|
| Role | Reads touch over I2C/GPIO, exposes a virtual **Touchscreen** via `uinput` |
| Typical failure | Exits if `/dev/uinput` cannot be opened; journal: `Failed with result 'exit-code'` |
| Impact | No `Touchscreen` in `evdev` list → approaches #1–#3 cannot work |
| Backlight | Not required for our I2C-only listener (#8) |

---

## Quick reference — scripts in repo

| Script | Purpose |
|--------|---------|
| [`ssh_install_touch_rtsp_power.py`](../ssh_install_touch_rtsp_power.py) | **Production:** RTSP on boot + tap toggles stream and backlight together |
| [`ssh_install_rtsp_display.py`](../ssh_install_rtsp_display.py) | Legacy: RTSP camera → HyperPixel on boot only |
| [`ssh_install_touch_toggle.py`](../ssh_install_touch_toggle.py) | Legacy: I2C touch-to-backlight only |
| [`ssh_stream_hyperpixel.py`](../ssh_stream_hyperpixel.py) | Dev: stream `test.mp4` from PC; keys **1** / **2** for backlight |
| [`pi_stream_common.py`](../pi_stream_common.py) | SSH, ffmpeg, `sudo`, shared helpers |
| [`env_config.py`](../env_config.py) | Loads `.env` (`PI_*`, `RTSP_*`) |
| [`.env.example`](../.env.example) | Template for Pi SSH + RTSP credentials |
| [`Setup_Guide.md`](Setup_Guide.md) | Original flash/driver/omxplayer/touch guide (Goodix + `touchtoggle` — see table #1) |

---

## Summary

| What you want | What to use |
|---------------|-------------|
| Camera on boot; tap off/on stream + backlight | `python ssh_install_touch_rtsp_power.py` |
| Camera on screen only (legacy) | `ssh_install_rtsp_display.py` |
| Tap backlight only, stream always on (legacy) | `ssh_install_touch_toggle.py` |
| Change camera or password | Edit `.env`, re-run `ssh_install_touch_rtsp_power.py` |
| Test video from PC | `ssh_stream_hyperpixel.py` |

If something breaks after an OS or HyperPixel reinstall:

```bash
python ssh_install_touch_rtsp_power.py
```

Check:

```bash
journalctl -u hyperpixel-touch-display-power.service -n 30 --no-pager
journalctl -u hyperpixel-rtsp-display.service -n 30 --no-pager
```

Both `hyperpixel-touch-display-power.service` and `hyperpixel-rtsp-display.service` should be `active` after reboot (until you tap display off).
