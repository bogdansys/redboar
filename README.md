# Redboar

<p align="center">
  <img src="icon.png" alt="Redboar icon" width="120" />
</p>

Redboar is a Python 3, Tkinter-based GUI that consolidates several popular penetration testing tools into a single interface.

## Supported Tools
- Gobuster
- Nmap
- SQLMap
- Nikto
- John the Ripper

## Features
- Form-driven command builders with live preview and copy-to-clipboard.
- Start, stop, and monitor scans with an integrated progress bar.
- Color‑coded real‑time output highlighting status codes, open ports, vulnerable findings, and more.
- Export scan results to a file for later review.
- Automatic detection of tool executables with guidance when tools are missing.

## Requirements
- Python 3 with Tkinter (`python3-tk` on Debian/Ubuntu).
- The above tools installed and available in your `PATH`. Paths can be customised in `config.py`.

## Usage
Clone this repository and run:

```bash
python3 main_app.py
```

A tabbed interface opens for each tool. Fill in the required fields, review the generated command, then start the scan. Output appears in the log window and can be cleared or exported.

## Disclaimer
Use Redboar responsibly and only against systems you are authorised to test.

