
import unittest
import tkinter as tk
import sys
import os
import tempfile

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui import ui_nmap, ui_gobuster, ui_sqlmap, ui_nikto, ui_john
from ui import ui_nuclei, ui_searchsploit, ui_hydra

class TestTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tk.Tk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()

    def setUp(self):
        # Create a dummy wordlist for Gobuster check
        self.tmp_wordlist = tempfile.NamedTemporaryFile(delete=False)
        self.tmp_wordlist.close()
        
        class MockApp:
            def __init__(self, tmp_list_path):
                self.root = TestTools.root 
                
                # Nmap
                self.nmap_target_var = tk.StringVar(value="127.0.0.1")
                self.nmap_ports_var = tk.StringVar(value="")
                self.nmap_scan_type_vars = {'-sS': tk.BooleanVar(), '-sV': tk.BooleanVar(value=True)}
                self.nmap_ping_scan_var = tk.BooleanVar()
                self.nmap_no_ping_var = tk.BooleanVar()
                self.nmap_os_detect_var = tk.BooleanVar()
                self.nmap_version_detect_var = tk.BooleanVar()
                self.nmap_fast_scan_var = tk.BooleanVar()
                self.nmap_verbose_var = tk.BooleanVar()
                
                # Gobuster
                self.gobuster_modes = {'Directory/File': 'dir', 'DNS Subdomain': 'dns', 'Virtual Host': 'vhost'}
                self.gobuster_current_mode_var = tk.StringVar(value="Directory/File")
                self.gobuster_target_var = tk.StringVar(value="http://example.com")
                self.gobuster_wordlist_var = tk.StringVar(value=tmp_list_path)
                self.gobuster_threads_var = tk.StringVar(value="10")
                self.gobuster_extensions_var = tk.StringVar(value="")
                self.gobuster_status_codes_var = tk.StringVar(value="")
                
                # Nuclei 
                self.nuclei_target_var = tk.StringVar(value="http://test.com")
                self.nuclei_templates_var = tk.StringVar(value="")
                self.nuclei_severity_var = tk.StringVar(value="low")
                self.nuclei_rate_var = tk.StringVar(value="150")
                
                # SearchSploit 
                self.searchsploit_var = tk.StringVar(value="wordpress 5.0")
                self.searchsploit_strict_var = tk.BooleanVar()
                self.searchsploit_path_var = tk.BooleanVar()
                
                # Hydra 
                self.hydra_target_var = tk.StringVar(value="192.168.1.10")
                self.hydra_service_var = tk.StringVar(value="ssh")
                self.hydra_user_var = tk.StringVar(value="root")
                self.hydra_user_is_list = tk.BooleanVar(value=False)
                self.hydra_pass_var = tk.StringVar(value="password")
                self.hydra_pass_is_list = tk.BooleanVar(value=False)
                
        self.app = MockApp(self.tmp_wordlist.name)

    def tearDown(self):
        if os.path.exists(self.tmp_wordlist.name):
            os.remove(self.tmp_wordlist.name)

    def test_nmap_command(self):
        cmd = ui_nmap.build_command(self.app)
        self.assertIn('127.0.0.1', cmd)
        self.assertIn('-sV', cmd) 

    def test_gobuster_command(self):
        cmd = ui_gobuster.build_command(self.app)
        self.assertIn('dir', cmd)
        self.assertIn('http://example.com', cmd)
        self.assertIn(self.tmp_wordlist.name, cmd)
        
    def test_nuclei_command(self):
        cmd = ui_nuclei.build_command(self.app)
        self.assertIn('-u', cmd)
        self.assertIn('http://test.com', cmd)
        self.assertIn('-s', cmd)
        self.assertIn('low', cmd)
        
    def test_searchsploit_command(self):
        cmd = ui_searchsploit.build_command(self.app)
        # shlex splits "wordpress 5.0" -> ["wordpress", "5.0"]
        self.assertIn('wordpress', cmd)
        self.assertIn('5.0', cmd)
        self.assertNotIn('--strict', cmd)
        
    def test_hydra_command(self):
        cmd = ui_hydra.build_command(self.app)
        self.assertIn('hydra', cmd)
        self.assertIn('192.168.1.10', cmd)
        self.assertIn('ssh', cmd)
        self.assertIn('-l', cmd) 
        self.assertIn('root', cmd)
        self.assertIn('-p', cmd) 
        self.assertIn('password', cmd)

if __name__ == '__main__':
    unittest.main()
