# Redboar Framework 2.0

<p align="center">
  <img src="icon.png" alt="Redboar icon" width="120" />
</p>

Redboar is a massive exploitation framework, fully open-source and Linux-first, designed to unify and extend the capabilities of tools like Nmap, Gobuster, SQLMap, Nikto, and John into a seamless offensive workflow. It provides advanced command builders with live previews, reusable profiles, and automated exports, while its integrated AI assistant can strategize attack paths, analyze logs, and triage vulnerabilities.

## 🚀 Key Features

### 🖥️ Workspace & Dashboard
- **Project Management**: Create and switch between projects (`.db` backed).
- **Mission Control Dashboard**: Live stats on hosts, services, and vulnerabilities.
- **Top Ports Chart**: Visual breakdown of your target's attack surface.
- **Integrated Notes**: Persistent, project-specific scratchpad.

### 🛠️ The Arsenal (Supported Tools)
Redboar wraps the industry's best tools with a unified UI:
- **Network**: `Nmap` (Auto-parsing to DB)
- **Web**: `Gobuster` (Dir/DNS/Vhost), `Nikto`, `SQLMap`
- **Vulnerability**: `Nuclei` (Template-based scanning)
- **Exploitation**: `SearchSploit` (ExploitDB), `Hydra` (Bruteforce), `RevShell` (One-liner generator)
- **Cracking**: `John the Ripper`

### 🧠 AI Analyst 2.0
- **Planning**: Generates attack plans based on your goal (Offline or OpenAI).
- **Log Analysis**: One-click "Analyze Output" to explain errors or findings.
- **Triage**: "Triage Findings" scans your DB and suggests high-priority targets.
- **Smart Context**: Aware of your current project's scope.

### 📊 Reporting & Visualization
- **Network Graph**: Interactive node-link diagram of hosts and services.
- **HTML Reports**: Professional, client-ready reports with Executive Summaries and Host/Service details.
- **Text/HTML Exports**: Quick export of raw tool output.

## 📦 Requirements
- Linux (Debian/Ubuntu/Kali recommended)
- Python 3 + Tkinter
- External tools installed (Nmap, Gobuster, etc.)

### Installation
1.  **Clone the repo:**
    ```bash
    git clone https://github.com/yourusername/redboar.git
    cd redboar
    ```
2.  **Install Python dependencies:**
    ```bash
    sudo apt update && sudo apt install -y python3 python3-tk
    ```
3.  **Install Core Tools (Kali/Debian):**
    ```bash
    sudo apt install -y gobuster nmap sqlmap nikto perl john hydra exploitdb nuclei
    ```

## 🏃 Run
```bash
python3 main_app.py
```
*Optional: Set `REDBOAR_DEBUG=1` for verbose logging.*

## 🎮 Workflow
1.  **Start a Project**: `Project > New Project...`
2.  **Scan**: Go to **Nmap**, run a scan. Results are auto-saved to the DB.
3.  **Visualize**: Check the **Dashboard** for stats or **Network Graph** for topology.
4.  **Enumerate**: Use **Gobuster** or **Nuclei** on discovered ports.
5.  **Analyze**: Use **AI Assistant** to interpret results or suggest exploits.
6.  **Report**: `Project > Generate Report (HTML)...` to finalize.

## ⚙️ Configuration
State and profiles are stored in `~/.config/redboar/`:
- `state.json`: Auto-restores last used tool settings.
- `runs.jsonl`: Audit log of all executed commands.
- `redboar.db`: SQLite database for project data.

## ⚠️ Disclaimer
**Use Redboar responsibly.** This tool is for educational purposes and authorized security testing only. Assessing targets without permission is illegal.
