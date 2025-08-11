# Redboar

<p align="center">
  <img src="icon.png" alt="Redboar icon" width="120" />
</p>

Redboar is a Linux-first, Python 3/Tkinter GUI that consolidates popular pentesting tools into a single interface. It features a modern, themeable UI (Glass/Brutalist/Neubrutalist), per‑tool command builders, and an AI Assistant with offline planning or ChatGPT integration.

## Supported Tools
- Gobuster
- Nmap
- SQLMap
- Nikto
- John the Ripper

## Key Features
- Command builders per tool with live Preview and one‑click Copy
- Start/Stop scans with progress indicator; robust process cleanup on Linux
- Color‑coded output with a searchable “Output” section
- Export results as Text or HTML
- Profiles: save/load your favorite settings; state auto‑restores on launch
- AI Assistant tab:
  - Local engine (offline) for heuristic planning
  - ChatGPT engine (optional) with `REDBOAR_OPENAI_API_KEY`
  - Plans steps; you review and apply to tool tabs before running

## Requirements
- Linux with Python 3 and Tkinter
  - Debian/Ubuntu/Kali:
    ```bash
    sudo apt update && sudo apt install -y python3 python3-tk
    ```
- Recommended tools (app will offer to auto‑install on Kali/apt):
  ```bash
  sudo apt install -y gobuster nmap sqlmap nikto perl john
  ```

## Run
Clone this repository and run:

```bash
python3 main_app.py
```

If you’re in WSL without WSLg, you need an X server (e.g., VcXsrv) and DISPLAY configured.

Optional debug logging:

```bash
REDBOAR_DEBUG=1 python3 main_app.py
```

## Using the App
1) Theme and layout
   - View → select theme: Glass, Brutalist, or Neubrutalist
2) Tools
   - Choose a tool tab; fill inputs (target, wordlist, options)
   - Review “Command → Preview”; Copy if needed
   - Start Scan / Stop Scan; view colored output; search within output
   - Export Text/HTML; Save/Load Profiles from menu
3) AI Assistant
   - Engine: Local (offline) or ChatGPT (set key in‑app)
   - Enter a goal and scope; Plan Steps; select and Run Selected to populate tabs
   - Review commands and Start when ready

Profiles and state are stored under:
- `~/.config/redboar/state.json` (auto‑restore)
- `~/.config/redboar/profiles.json` (menu → Profiles)
- Runs/AI logs: `~/.config/redboar/runs.jsonl`, `~/.config/redboar/ai_runs.jsonl`

## AI Assistant
- Engine selector: Local (offline) or ChatGPT (requires `REDBOAR_OPENAI_API_KEY`)
- Enter a goal (e.g., “enumerate services on 127.0.0.1”), set scope/time budget
- Click “Plan Steps”, select items, then “Run Selected” to populate tool tabs
- Review Command Preview in the tool tab and click Start

## Safe Local Testing
- Nmap: target `127.0.0.1` with defaults
- Gobuster/Nikto: run a local web server `python3 -m http.server 8000` and target `http://127.0.0.1:8000`
- SQLMap/John: use local vulnerable labs or known test hashes only

## Running Tests
This project includes simple unit tests that do not require network access or tool installs.

Run all tests

```bash
python3 -m unittest discover -s tests -v
```

You should see all tests passing.

## Disclaimer
Use Redboar responsibly and only against systems you are authorized to test.

