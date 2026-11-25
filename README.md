# SL departure board (DIY)

A small LED departure board for Stockholm's metro, built from a Raspberry Pi and a
64×32 RGB LED matrix. It shows the next trains from **Sandsborg** on the green line
(line 18), only in the direction **towards the city** (Gullmarsplan / T-Centralen),
in orange-yellow text like SL's platform signs.

```
18 Alvik          4 min
18 Hässelby s    14 min     <- long names scroll
```

## Features

- Live departures from SL's open Transport API (no API key needed)
- Only metro trains in one direction, filtered with the API's `direction_code`
- Two rows like SL's platform signs: line number, destination and minutes left,
  e.g. "7 min" (or "Nu")
- A custom pixel font in the style of SL's signs (proportional letters, large
  rounded lowercase, real descenders), drawn by hand in `tools/make_sl_font.py`
- Long destination names scroll smoothly
- Data is fetched every 30 seconds, while the screen is redrawn 20 times per second
  so the countdown stays accurate
- If the API can't be reached, the last known departures stay on screen and a tiny
  red mark appears in the bottom-right corner. The program never crashes on errors.
- Night mode: the screen turns off (or dims) between configurable times
- A clock is shown when there are no departures
- Runs in an emulator on a Mac/PC, so you can develop without the hardware

## Project layout

| File | What it does |
|------|--------------|
| `config.py` | All settings: station, direction, colors, brightness, night mode, GPIO options |
| `sl_api.py` | Fetches and filters departures. Knows nothing about the screen. |
| `display.py` | Draws on the LED panel, or on the emulator when not on a Pi |
| `main.py` | Main loop: fetch, handle errors, night mode, redraw |
| `tests/` | pytest tests using a saved API response (no network needed) |
| `fonts/` | BDF bitmap fonts (the SL-style font is generated, see below) |
| `tools/make_sl_font.py` | The SL-style font, drawn as text; run it to regenerate the font file |
| `sl-skylt.service` | systemd service that starts the board at boot |
| `emulator_config.json` | Settings for the emulator on the Mac |

## Hardware

- Raspberry Pi 3B with Raspberry Pi OS Lite (64-bit)
- Waveshare RGB-Matrix-P4-64x32 (HUB75 connector, 64×32 pixels, 1/16 scan)
- Female-to-female jumper wires (no adapter board / HAT)
- Separate 5 V / 4 A power supply for the panel
- Micro-USB power supply for the Pi

### Wiring

The panel is wired directly to the Pi's GPIO header. This is the library's
`regular` hardware mapping. The full reference, with pictures, is in
[hzeller's wiring.md](https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/wiring.md).

For a single panel (chain 1) you need these connections. "Pin" means the
**physical pin number** on the Pi's 40-pin header:

| HUB75 input | Pi pin | GPIO |
|-------------|-------:|-----:|
| R1          | 23     | 11 |
| G1          | 13     | 27 |
| B1          | 26     | 7  |
| R2          | 24     | 8  |
| G2          | 21     | 9  |
| B2          | 19     | 10 |
| A           | 15     | 22 |
| B           | 16     | 23 |
| C           | 18     | 24 |
| D           | 22     | 25 |
| CLK         | 11     | 17 |
| LAT / STB   | 7      | 4  |
| OE          | 12     | 18 |
| GND         | 6      | -  |

(The panel is 1/16 scan, so the `E` line is not used.)

Power the panel from the separate 5 V supply through its own power connector.
**Do not** power the panel from the Pi's 5 V pins: it can draw several amps.
Do connect the panel's ground to the Pi's ground (the GND wire above).

## Running on the Mac (emulator)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Then open <http://localhost:8888> in a browser to see the board. The code detects
that it isn't running on a Raspberry Pi and uses
[RGBMatrixEmulator](https://github.com/ty-porter/RGBMatrixEmulator) automatically.
You can force a choice with an environment variable:

```bash
SL_EMULATOR=1 python main.py   # always emulator
SL_EMULATOR=0 python main.py   # always the real panel
```

Other useful commands:

```bash
python sl_api.py                    # print upcoming departures in the terminal
python sl_api.py search Sandsborg   # look up the site id of a station
pytest                              # run the tests
```

## Installing on the Raspberry Pi

All commands are run on the Pi over SSH. The paths assume the user `pi`; if your
user has another name, change `/home/pi` here and in `sl-skylt.service`.

### 1. Turn off the onboard sound

The Pi's onboard sound uses the same hardware timer as the LED library, and the
library refuses to start while it is loaded.

```bash
sudo sed -i 's/^dtparam=audio=on/dtparam=audio=off/' /boot/firmware/config.txt
echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf
sudo update-initramfs -u
sudo reboot
```

After the reboot, `lsmod | grep snd_bcm2835` should print nothing.

### 2. Install system packages

```bash
sudo apt update
sudo apt install -y git python3-dev python3-venv cython3 build-essential
```

### 3. Get the code and create a virtual environment

```bash
cd ~
git clone <your-repo-url> tunnelbana
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
cd ~/tunnelbana
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install ~/rpi-rgb-led-matrix   # builds the rgbmatrix Python bindings
```

(The emulator is skipped automatically on the Pi, see `requirements.txt`.)
If the build of the bindings fails, see the
[Python bindings README](https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python).

### 4. Test it by hand

```bash
sudo .venv/bin/python main.py
```

Stop with `Ctrl+C`. If the picture flickers or looks garbled, try another
`GPIO_SLOWDOWN` value in `config.py` (1–4). If it is too bright, lower `BRIGHTNESS`.

### 5. Start automatically at boot

```bash
sudo cp sl-skylt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sl-skylt
```

Useful commands:

```bash
systemctl status sl-skylt       # is it running?
journalctl -u sl-skylt -f       # follow the log
sudo systemctl restart sl-skylt # restart after changing config.py
```

## Configuration

Everything is in `config.py`. The most common changes:

- **Another station:** run `python sl_api.py search <name>`, put the id in `SITE_ID`.
- **Direction:** `DIRECTION_CODE` is `1` or `2`. Run `python sl_api.py` and check the
  destinations to see which one is which for your station.
- **Night mode:** `NIGHT_START`, `NIGHT_END`, and `NIGHT_BRIGHTNESS` (0 = off).
- **Colors and brightness:** `TEXT_COLOR`, `BRIGHTNESS`.
- **Number of rows:** `NUM_ROWS` (2 like SL's signs; 3 also fits on the panel).

## Changing the font

The SL-style font is drawn as text in `tools/make_sl_font.py`, where every `#` is
one LED. To change a letter, edit its drawing and regenerate the font:

```bash
python tools/make_sl_font.py
```

## How the direction filter was chosen

The API returns a `direction_code` (1 or 2) for each departure. At Sandsborg the real
response had code `1` for trains to *Alvik* (line direction *Hässelby strand*), and
code `2` for trains to *Farsta strand*. So `1` means towards the city. The code
filters on this number rather than on destination names, because trains towards the
city can end at different stations.

## Data source

Departures come from [SL Transport API](https://www.trafiklab.se/api/our-apis/sl/transport/)
(`https://transport.integration.sl.se/v1`).
