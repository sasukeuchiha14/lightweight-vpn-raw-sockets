import subprocess
import re
import platform
import threading

class NetworkScanner:
    def __init__(self, log_callback=None):
        self.available_ips = []
        self.scanning = False
        self.log_callback = log_callback
    
    def log(self, message):
        """Send log message to callback if available"""
        if self.log_callback:
            self.log_callback(message)
    
    def scan_network(self):
        """Scan the network for available devices"""
        self.scanning = True
        self.available_ips = []
        self.log("Scanning network...")
        
        try:
            if platform.system() == "Windows":
                # Use arp command on Windows
                result = subprocess.check_output("arp -a", shell=True).decode('utf-8')
                
                # Also try to detect WSL interfaces on Windows
                try:
                    wsl_result = subprocess.check_output("ipconfig", shell=True).decode('utf-8')
                    # Look for WSL adapters in ipconfig output
                    if "WSL" in wsl_result or "vEthernet" in wsl_result:
                        self.log("Detected WSL - scanning for WSL IPs")
                        # Common WSL IP ranges
                        wsl_ranges = ["172."]
                        for range_prefix in wsl_ranges:
                            for i in range(16, 32):  # Common WSL subnet range
                                ip_pattern = f"{range_prefix}{i}\\."
                                if re.search(ip_pattern, wsl_result):
                                    self.log(f"Found potential WSL subnet: {range_prefix}{i}.*")
                except Exception as e:
                    self.log(f"WSL detection error: {str(e)}")
                    
            else:  # Linux/Mac
                # Try different commands on Linux
                try:
                    result = subprocess.check_output("ip neigh", shell=True).decode('utf-8')
                except:
                    try:
                        result = subprocess.check_output("arp -n", shell=True).decode('utf-8')
                    except:
                        result = ""
            
            # Parse IPs from result
            ip_pattern = r'\d+\.\d+\.\d+\.\d+'
            ips = re.findall(ip_pattern, result)
            
            # Add unique IPs and skip localhost
            for ip in ips:
                if ip not in self.available_ips and not ip.startswith("127."):
                    self.available_ips.append(ip)
            
            # Add common WSL IP if we're on Windows
            if platform.system() == "Windows":
                wsl_ips = ["172.31.62.1"]  # Add the specific WSL IP
                for ip in wsl_ips:
                    if ip not in self.available_ips:
                        self.available_ips.append(ip)
                        self.log(f"Added known WSL IP: {ip}")
            
            self.log(f"Found {len(self.available_ips)} devices on network")
        except Exception as e:
            self.log(f"Error scanning network: {str(e)}")
        
        self.scanning = False
        return self.available_ips
    
    def scan_async(self):
        """Start network scan in background thread"""
        thread = threading.Thread(target=self.scan_network, daemon=True)
        thread.start()
        return thread
    
    def validate_ip(self, ip):
        """Validate IP address format"""
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        return re.match(ip_pattern, ip) is not None