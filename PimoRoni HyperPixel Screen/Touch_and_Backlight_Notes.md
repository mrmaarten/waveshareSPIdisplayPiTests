# HyperPixel: Touch & Backlight — What We Tried

Notes from getting the Pimoroni HyperPixel 3.5" working on **Raspberry Pi OS Legacy (32-bit Buster, CLI)** with PC-pushed video and backlight control.

---

## Final working solution (confirmed)

### Touch — tap screen to toggle backlight (CLI)

| Item | Detail |
|------|--------|
| **Install (from PC, repo root)** | `python ssh_install_touch_toggle.py` |
| **Pi service** | `hyperpixel-backlight-touch.service` (enabled on boot) |
| **Pi script** | `/home/pi/hyperpixel_backlight_touch.py` |
| **How it works** | Python 3 reads touch directly over **I2C bus 11** @ `0x5c` + GPIO interrupt (pin 27). No desktop, no `uinput`, no `evdev`. Toggles `rpi_backlight` on each tap (0.5s debounce). |
| **Status** | **Success** — tapping the screen turns the backlight on/off in CLI. |

**Check after reboot:**

```bash
ssh pi@raspberrypi.local "systemctl is-active hyperpixel-backlight-touch.service"
# → active

ssh pi@raspberrypi.local "journalctl -u hyperpixel-backlight-touch.service -n 5 --no-pager"
```

**Repo file:** [`ssh_install_touch_toggle.py`](../ssh_install_touch_toggle.py)

---

### Backlight — without touch (from PC)

| Method | Command / action |
|--------|------------------|
| **While streaming** | Run `python ssh_stream_hyperpixel.py` on Windows → press **`1`** (on) or **`2`** (off) |
| **SSH anytime** | `sudo python3 -c "from rpi_backlight import Backlight; Backlight().power = True"` (or `False`) |

**Repo file:** [`ssh_stream_hyperpixel.py`](../ssh_stream_hyperpixel.py)

---

### Video on screen (from PC)

```bash
python ssh_stream_hyperpixel.py
```

800×480, pixel format `bgra` → Pi `ffmpeg` → `/dev/fb0`. More detail in the sections below.

---

## Hardware / OS context

- Pi hostname: `raspberrypi.local` (see repo `.env` for SSH credentials)
- Display: original HyperPixel 3.5" (800×480), `dtoverlay=hyperpixel` + `dtoverlay=hyperpixel-gpio-backlight`
- Touch controller on I2C address `0x5c` (visible on **bus 11** as `/dev/i2c-11`, not bus 3)
- Backlight: `rpi_backlight` (kernel `hyperpixel-gpio-backlight` overlay)

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

**Status:** **Success** — confirmed working during video loop tests.

**Repo files:** [`ssh_stream_hyperpixel.py`](../ssh_stream_hyperpixel.py), shared helpers in [`pi_stream_common.py`](../pi_stream_common.py).

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

### 3. Video stream to framebuffer (separate from backlight)

PC pushes H.264 over TCP; Pi `ffmpeg` writes to `/dev/fb0`.

**HyperPixel-specific settings** (in `ssh_stream_hyperpixel.py`):

- Resolution: `800×480`
- Pixel format: `bgra` (Pi `fbdev` rejected `rgb565le`)

**Status:** **Success** for video; does not control backlight by itself.

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

See **[Final working solution](#final-working-solution-confirmed)** at the top for install and verification steps.

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
| [`ssh_stream_hyperpixel.py`](../ssh_stream_hyperpixel.py) | Stream test video to HyperPixel; keys **1** / **2** for backlight |
| [`ssh_install_touch_toggle.py`](../ssh_install_touch_toggle.py) | Install I2C touch-to-backlight service on the Pi |
| [`pi_stream_common.py`](../pi_stream_common.py) | SSH, ffmpeg, `sudo`, shared constants (default 480×320 is for Waveshare; HyperPixel overrides in stream script) |
| [`Setup_Guide.md`](Setup_Guide.md) | Original flash/driver/omxplayer/touch guide (Goodix + `touchtoggle` — see table #1) |

---

## Summary

Same as **[Final working solution](#final-working-solution-confirmed)** above. If touch stops after an OS or HyperPixel reinstall, re-run `python ssh_install_touch_toggle.py` and check `journalctl -u hyperpixel-backlight-touch.service`.
