# Default rules for the Reactive Pipeline
# Each rule maps a finding (port/service) to a set of recommended tools.

RULES = [
    {
        "port": 80,
        "service_names": ["http", "http-alt", "http-proxy"],
        "tools": [
            {
                "tool_name": "Nikto",
                "label": "Nikto Web Scan",
                "reason": "Port 80 is open (HTTP).",
                "params": {"target": "http://{ip}:{port}"}
            },
            {
                "tool_name": "Gobuster",
                "label": "Gobuster Directory Bruteforce",
                "reason": "Port 80 is open. Find hidden directories.",
                "params": {
                    "mode": "dir",
                    "target": "http://{ip}:{port}",
                    "wordlist": "/usr/share/wordlists/dirb/common.txt" # Default, user should verify
                }
            }
        ]
    },
    {
        "port": 443,
        "service_names": ["https", "ssl/http", "http"],
        "tools": [
            {
                "tool_name": "Nikto",
                "label": "Nikto SSL Web Scan",
                "reason": "Port 443 is open (HTTPS).",
                "params": {"target": "https://{ip}:{port}"}
            },
            {
                "tool_name": "Gobuster",
                "label": "Gobuster Directory Bruteforce (SSL)",
                "reason": "Port 443 is open.",
                "params": {
                    "mode": "dir",
                    "target": "https://{ip}:{port}",
                    "wordlist": "/usr/share/wordlists/dirb/common.txt"
                }
            }
        ]
    },
    {
        "port": 8080,
        "service_names": ["http", "http-alt", "http-proxy"],
        "tools": [
            {
                "tool_name": "Nikto",
                "label": "Nikto Web Scan (Port 8080)",
                "reason": "Port 8080 is often an alternative HTTP port.",
                "params": {"target": "http://{ip}:{port}"}
            }
        ]
    },
    {
        "port": 445,
        "service_names": ["microsoft-ds", "netbios-ssn"],
        "tools": [
            {
                "tool_name": "Nmap",
                "label": "Nmap SMB Enum Scripts",
                "reason": "SMB Port 445 is open. Check for vulnerabilities (e.g., EternalBlue).",
                "params": {
                    # This requires advanced param mapping in ui_nmap, but for now we can simulate "Extra Args"
                    "scan_type": "-sC -sV -p 445 --script=smb-vuln*",
                    "target": "{ip}"
                }
            }
        ]
    },
    {
        "port": 3306,
        "service_names": ["mysql"],
        "tools": [
             {
                "tool_name": "Nmap",
                "label": "Nmap MySQL Scripts",
                "reason": "MySQL Port 3306 is open.",
                "params": {
                    "scan_type": "-sV -p 3306 --script=mysql-info,mysql-enum,mysql-users,mysql-empty-password",
                    "target": "{ip}"
                }
            }
        ]
    },
    {
        "port": 22,
        "service_names": ["ssh"],
        "tools": [
             {
                "tool_name": "Methodology",
                "label": "Hydra SSH Brute (Generic)",
                "reason": "SSH is open. Consider brute-forcing if authorized.",
                "params": {
                    "note": "Hydra not yet fully integrated in UI, but this signals intent."
                }
            }
        ]
    }
]
