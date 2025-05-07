EXECUTABLE_PATHS = {
    'gobuster': ['/usr/bin/gobuster', '/snap/bin/gobuster', 'gobuster'],
    'nmap': ['/usr/bin/nmap', 'nmap'],
    'sqlmap': ['/usr/share/sqlmap/sqlmap.py', 'sqlmap.py', 'sqlmap'],
    'nikto': ['/usr/bin/nikto', '/opt/nikto/program/nikto.pl', 'nikto.pl', 'nikto'],
    'john': ['/usr/sbin/john', '/opt/john/run/john', 'john']
}

COMMON_PACKAGE_NAMES = {
    'gobuster': 'gobuster',
    'nmap': 'nmap',
    'sqlmap': 'sqlmap',
    'nikto': 'nikto',
    'john': 'johntheripper'
}

TOOL_DISPLAY_NAMES_MAP = {
    'gobuster': 'Gobuster',
    'nmap': 'Nmap',
    'sqlmap': 'SQLMap',
    'nikto': 'Nikto',
    'john': 'John the Ripper'
}
