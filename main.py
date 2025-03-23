import pygame
import sys
import threading
import os
import platform
import re
import time

# Import our modules
from ui_components import UIComponents, WHITE, BLACK, GREEN, BLUE, RED, DARK_GREEN, LIGHT_GRAY, GRAY, DARK_GRAY
from utils import copy_to_clipboard, KeyManager
from vpn import vpn_sender, vpn_receiver, set_message_callback, queue_message, stop_vpn
from encryption import generate_key, load_key, save_key

class VPNApplication:
    def __init__(self):
        # Initialize Pygame
        pygame.init()
        
        # Screen settings
        self.WIDTH, self.HEIGHT = 900, 600
        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Lightweight VPN")
        
        # Fonts
        self.fonts = {
            'normal': pygame.font.Font(None, 36),
            'small': pygame.font.Font(None, 24),
            'title': pygame.font.Font(None, 48)
        }
        
        # Initialize UI components
        self.ui = UIComponents(self.screen, self.fonts)
        
        # Initialize key manager
        self.key_manager = KeyManager(self.log_message)
        
        # States
        self.STATE_IP_ENTRY = "ip_entry"
        self.STATE_CONFIG = "config"
        self.STATE_CONNECTED = "connected"
        self.current_state = self.STATE_IP_ENTRY
        
        # VPN status
        self.vpn_active = False
        self.connection_type = None  # "send" or "receive"
        self.entered_ip = ""
        self.log_messages = []
        self.transfer_logs = []  # For packet transfer information
        self.key_text = ""
        self.using_existing_key = False
        
        # Text inputs
        self.active_input = "ip"  # Start with IP input active
        
        # Stats
        self.packets_sent = 0
        self.packets_received = 0
        self.bytes_transferred = 0
        self.connection_time = 0
        self.connection_start_time = 0
        
        # Copy button state flag
        self.copy_button_clicked = False
        self.copy_button_timer = 0
        
        # Set up button rectangles
        self.setup_buttons()
        
        # Set message callback
        set_message_callback(self.handle_vpn_message)
    
    # Update the setup_buttons method
    def setup_buttons(self):
        """Initialize all button rectangles"""
        # Main buttons
        self.back_button = pygame.Rect(20, 20, 150, 40)  # Widened disconnect button
        
        # Connection buttons
        self.send_button = pygame.Rect(self.WIDTH//2 - 200, self.HEIGHT - 150, 180, 50)
        self.receive_button = pygame.Rect(self.WIDTH//2 + 20, self.HEIGHT - 150, 180, 50)
        
        # VPN toggle
        self.toggle_vpn_button = pygame.Rect(100, 150, 100, 100)
        
        # Key management
        self.new_key_button = pygame.Rect(self.WIDTH//2 - 250, 300, 220, 50)
        self.existing_key_button = pygame.Rect(self.WIDTH//2 + 30, 300, 220, 50)
        self.upload_key_button = pygame.Rect(self.WIDTH//2 + 30, 370, 220, 50)
        self.copy_key_button = pygame.Rect(self.WIDTH//2 + 310, 200, 80, 40)
        
        # IP input
        self.ip_input_box = pygame.Rect(self.WIDTH//2 - 150, self.HEIGHT//2 - 50, 300, 40)
    
    def log_message(self, message):
        """Add a message to the log"""
        self.log_messages.append(message)
    
    def handle_vpn_message(self, message, msg_type="info"):
        """Handle messages from the VPN module"""
        if msg_type == "message":
            # Track as packet transfer
            self.packets_received += 1
            self.bytes_transferred += len(message)
            self.transfer_logs.append(f"Packet received: {len(message)} bytes")
            # Keep only the last 20 transfer logs
            if len(self.transfer_logs) > 20:
                self.transfer_logs.pop(0)
        elif msg_type == "packet_sent":
            self.packets_sent += 1
            self.bytes_transferred += len(message)
            self.transfer_logs.append(f"Packet sent: {len(message)} bytes")
            # Keep only the last 20 transfer logs
            if len(self.transfer_logs) > 20:
                self.transfer_logs.pop(0)
        else:
            self.log_messages.append(message)
    
    # Fix the start_vpn_thread method to be more robust
    def start_vpn_thread(self):
        """Start VPN in a separate thread"""
        try:
            # First make sure any previous VPN is stopped
            stop_vpn()
            
            # Short delay to ensure cleanup
            time.sleep(0.5)
            
            # Start new VPN connection
            if self.connection_type == "send":
                self.log_message(f"Starting VPN sender to {self.entered_ip}")
                threading.Thread(target=self.vpn_sender_wrapper, args=(self.entered_ip,), daemon=True).start()
            else:  # receive
                self.log_message("Starting VPN receiver")
                threading.Thread(target=self.vpn_receiver_wrapper, daemon=True).start()
            
            self.vpn_active = True
            
            # Queue a connection successful message after a brief delay
            def send_initial_packet():
                time.sleep(1)
                if self.vpn_active:
                    queue_message("VPN connection established")
            
            threading.Thread(target=send_initial_packet, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"Error starting VPN: {str(e)}")
            self.vpn_active = False
    
    def vpn_sender_wrapper(self, ip):
        """Wrapper for vpn_sender with error handling"""
        try:
            vpn_sender(ip)
        except Exception as e:
            self.log_message(f"VPN sender error: {str(e)}")
            self.vpn_active = False
    
    def vpn_receiver_wrapper(self):
        """Wrapper for vpn_receiver with error handling"""
        try:
            vpn_receiver()
        except Exception as e:
            self.log_message(f"VPN receiver error: {str(e)}")
            self.vpn_active = False
    
    def validate_ip(self, ip):
        """Validate IP address format"""
        ip_pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
        return re.match(ip_pattern, ip) is not None
    
    def draw_ip_entry_screen(self):
        """Draw the IP entry screen"""
        title_surf = self.fonts['title'].render("Lightweight VPN", True, BLACK)
        self.screen.blit(title_surf, (self.WIDTH//2 - title_surf.get_width()//2, 30))
        
        # IP entry instructions
        instruction_text = "Enter the IP address to connect to:"
        instruction_surf = self.fonts['normal'].render(instruction_text, True, BLACK)
        self.screen.blit(instruction_surf, (self.WIDTH//2 - instruction_surf.get_width()//2, self.HEIGHT//2 - 100))
        
        # Draw IP input box with cursor
        self.ui.draw_input_box(self.ip_input_box, self.entered_ip, self.active_input == "ip")
        
        # Draw connection type buttons
        if self.entered_ip and self.validate_ip(self.entered_ip):
            self.ui.draw_button("Send Mode", self.send_button)
            self.ui.draw_button("Receive Mode", self.receive_button)
    
    def draw_config_screen(self):
        """Draw the VPN configuration screen"""
        self.ui.draw_button("Back", self.back_button)
        
        title_text = "Sender Configuration" if self.connection_type == "send" else "Receiver Configuration"
        title_surf = self.fonts['title'].render(title_text, True, BLACK)
        self.screen.blit(title_surf, (self.WIDTH//2 - title_surf.get_width()//2, 30))
        
        # Show connecting IP address
        ip_text = f"IP: {self.entered_ip}"
        ip_surf = self.fonts['normal'].render(ip_text, True, BLACK)
        self.screen.blit(ip_surf, (self.WIDTH//2 - ip_surf.get_width()//2, 80))
        
        if self.connection_type == "send":
            self.ui.draw_button("Generate New Key", self.new_key_button)
            self.ui.draw_button("Select Existing Key", self.existing_key_button)
        else:  # receive mode
            self.ui.draw_button("Enter Key", self.new_key_button)
            self.ui.draw_button("Upload Key File", self.upload_key_button)
        
        # Draw key text area if key is being shown/entered
        if self.using_existing_key or self.active_input == "key":
            key_area = pygame.Rect(self.WIDTH//2 - 300, 200, 600, 80)
            pygame.draw.rect(self.screen, WHITE, key_area, border_radius=5)
            pygame.draw.rect(self.screen, BLACK, key_area, 2, border_radius=5)
            
            key_title = self.fonts['normal'].render("Encryption Key:", True, BLACK)
            self.screen.blit(key_title, (key_area.x + 10, key_area.y - 30))
            
            # Display the key (could be truncated if too long)
            key_display = self.fonts['small'].render(self.key_text[:60] + "..." if len(self.key_text) > 60 else self.key_text, True, BLACK)
            self.screen.blit(key_display, (key_area.x + 10, key_area.y + 20))
            
            # Button differs based on mode - Copy for Send, Paste for Receive
            if self.connection_type == "send":
                self.ui.draw_button("Copy", self.copy_key_button, DARK_GREEN if not self.copy_button_clicked else GREEN, 
                                  WHITE, button_id="copy_key")
            else:
                self.ui.draw_button("Paste", self.copy_key_button, BLUE, WHITE)
            
            # Connect button
            connect_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 100, 200, 50)
            self.ui.draw_button("Connect", connect_button, GREEN)
    
    # Update the draw_connected_screen method
    def draw_connected_screen(self):
        """Draw the connected VPN screen"""
        # Wider disconnect button
        disconnect_button = pygame.Rect(20, 20, 150, 40)
        self.ui.draw_button("Disconnect", disconnect_button, RED)
        
        # Draw VPN toggle circle
        circle_center = (150, 200)
        circle_color = GREEN if self.vpn_active else RED
        self.ui.draw_circle_button(circle_center, 50, circle_color)
        
        status_text = "VPN ACTIVE" if self.vpn_active else "VPN INACTIVE"
        status_surf = self.fonts['normal'].render(status_text, True, BLACK)
        self.screen.blit(status_surf, (circle_center[0] - status_surf.get_width()//2, circle_center[1] + 60))
        
        # Show connected IP
        ip_text = f"Connected to: {self.entered_ip}" if self.connection_type == "send" else "Listening for connections"
        ip_surf = self.fonts['normal'].render(ip_text, True, BLACK)
        self.screen.blit(ip_surf, (circle_center[0] - ip_surf.get_width()//2, circle_center[1] + 90))
        
        # Update connection time
        if self.vpn_active:
            if self.connection_start_time == 0:
                self.connection_start_time = time.time()
            self.connection_time = time.time() - self.connection_start_time
        else:
            self.connection_start_time = 0
        
        # Draw packet statistics
        stats_area = pygame.Rect(self.WIDTH//2 + 50, 100, self.WIDTH//2 - 100, 200)
        pygame.draw.rect(self.screen, LIGHT_GRAY, stats_area, border_radius=5)
        pygame.draw.rect(self.screen, BLACK, stats_area, 2, border_radius=5)
        
        stats_title = self.fonts['normal'].render("VPN Statistics", True, BLACK)
        self.screen.blit(stats_title, (stats_area.x + 10, stats_area.y + 10))
        
        # Format connection time as mm:ss
        minutes = int(self.connection_time // 60)
        seconds = int(self.connection_time % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        # Format bytes transferred in appropriate units
        if self.bytes_transferred < 1024:
            bytes_str = f"{self.bytes_transferred} B"
        elif self.bytes_transferred < 1024*1024:
            bytes_str = f"{self.bytes_transferred/1024:.2f} KB"
        else:
            bytes_str = f"{self.bytes_transferred/(1024*1024):.2f} MB"
        
        # Display stats
        stats = [
            f"Connection time: {time_str}",
            f"Packets sent: {self.packets_sent}",
            f"Packets received: {self.packets_received}",
            f"Data transferred: {bytes_str}"
        ]
        
        y_offset = stats_area.y + 50
        for stat in stats:
            stat_surf = self.fonts['small'].render(stat, True, BLACK)
            self.screen.blit(stat_surf, (stats_area.x + 20, y_offset))
            y_offset += 30
        
        # Add test packet button
        test_packet_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 80, 200, 50)
        self.ui.draw_button("Send Test Packet", test_packet_button, 
                         GREEN if self.vpn_active else GRAY)
        
        # Draw packet transfer logs
        log_area = pygame.Rect(50, self.HEIGHT - 200, self.WIDTH - 100, 100)
        pygame.draw.rect(self.screen, LIGHT_GRAY, log_area, border_radius=5)
        
        log_title = self.fonts['normal'].render("Packet Transfer Log", True, BLACK)
        self.screen.blit(log_title, (log_area.x + 10, log_area.y + 5))
        
        y_offset = log_area.y + 40
        for log in self.transfer_logs[-5:]:  # Show only last 5 logs
            log_surf = self.fonts['small'].render(log, True, DARK_GRAY)
            self.screen.blit(log_surf, (log_area.x + 15, y_offset))
            y_offset += 20
    
    def handle_ip_entry_events(self, event):
        """Handle events for the IP entry screen"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Activate IP input when clicked
            if self.ip_input_box.collidepoint(event.pos):
                self.active_input = "ip"
            
            # Check connection type buttons if IP is valid
            if self.entered_ip and self.validate_ip(self.entered_ip):
                if self.send_button.collidepoint(event.pos):
                    self.connection_type = "send"
                    self.current_state = self.STATE_CONFIG
                elif self.receive_button.collidepoint(event.pos):
                    self.connection_type = "receive"
                    self.current_state = self.STATE_CONFIG
    
    def handle_config_screen_events(self, event):
        """Handle events for the configuration screen"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.back_button.collidepoint(event.pos):
                self.current_state = self.STATE_IP_ENTRY
                self.using_existing_key = False
            
            elif self.connection_type == "send":
                if self.new_key_button.collidepoint(event.pos):
                    # Generate a new key and show popup
                    self.key_text, self.using_existing_key = self.key_manager.handle_key_management(
                        "new", self.key_text, generate_key, load_key, save_key)
                    if self.using_existing_key:
                        self.ui.show_popup("New key generated and saved to vpn_key.txt")
                elif self.existing_key_button.collidepoint(event.pos):
                    # Use file dialog to select existing key
                    self.key_text, self.using_existing_key = self.key_manager.handle_key_management(
                        "browse", self.key_text, generate_key, load_key, save_key)
                    if self.using_existing_key:
                        self.ui.show_popup("Key loaded successfully")
            else:  # receive mode
                if self.new_key_button.collidepoint(event.pos):
                    # Activate a text input for the key
                    self.active_input = "key"
                    self.key_text = ""
                elif self.upload_key_button.collidepoint(event.pos):
                    # Use file dialog
                    previous_key = self.key_text
                    self.key_text, self.using_existing_key = self.key_manager.handle_key_management(
                        "upload", self.key_text, generate_key, load_key, save_key)
                    if self.using_existing_key and self.key_text != previous_key:
                        self.ui.show_popup("Key file uploaded successfully")
            
            # Check for connect button if key is selected
            if self.using_existing_key or self.active_input == "key":
                connect_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 100, 200, 50)
                if connect_button.collidepoint(event.pos):
                    if self.active_input == "key":
                        previous_status = self.using_existing_key
                        self.key_text, self.using_existing_key = self.key_manager.handle_key_management(
                            "manual", self.key_text, generate_key, load_key, save_key)
                        if self.using_existing_key and not previous_status:
                            self.ui.show_popup("Key saved successfully")
                    if self.using_existing_key:  # Only connect if we have a valid key
                        self.current_state = self.STATE_CONNECTED
                        self.start_vpn_thread()
            
            # Copy/Paste key button based on mode
            if self.copy_key_button.collidepoint(event.pos) and (self.using_existing_key or self.active_input == "key"):
                if self.connection_type == "send":
                    # Copy key to clipboard
                    if copy_to_clipboard(self.key_text):
                        self.ui.show_popup("Key copied to clipboard")
                        # Change button to checkmark for 2 seconds
                        self.copy_button_clicked = True
                        self.copy_button_timer = time.time()
                        self.ui.set_copy_button_state("copy_key", True)
                    else:
                        self.ui.show_popup("Failed to copy key to clipboard")
                else:
                    # Paste key from clipboard in receive mode
                    clipboard_text = self.get_clipboard_text()
                    if clipboard_text:
                        # Filter out non-hex characters
                        hex_chars = ''.join(c for c in clipboard_text if c.lower() in "0123456789abcdef")
                        if hex_chars:
                            self.key_text = hex_chars
                            self.ui.show_popup("Key pasted from clipboard")
                        else:
                            self.ui.show_popup("No valid key found in clipboard")
    
    def handle_connected_screen_events(self, event):
        """Handle events for the connected screen"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.back_button.collidepoint(event.pos):
                try:
                    # Proper cleanup sequence
                    if self.vpn_active:
                        stop_vpn()
                        self.vpn_active = False
                        self.transfer_logs.append("VPN connection stopped")
                    self.current_state = self.STATE_CONFIG
                except Exception as e:
                    self.log_message(f"Error disconnecting: {str(e)}")
            
            # Toggle VPN
            toggle_rect = pygame.Rect(100, 150, 100, 100)
            if toggle_rect.collidepoint(event.pos):
                try:
                    self.vpn_active = not self.vpn_active
                    if self.vpn_active:
                        self.start_vpn_thread()
                        self.transfer_logs.append("VPN connection started")
                    else:
                        stop_vpn()
                        self.log_message("VPN stopped")
                        self.transfer_logs.append("VPN connection stopped")
                except Exception as e:
                    self.log_message(f"Error toggling VPN: {str(e)}")
            
            # Add a new Test Packet button
            test_packet_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 80, 200, 50)
            if test_packet_button.collidepoint(event.pos) and self.vpn_active:
                try:
                    # Send a test packet
                    test_data = f"Test packet: {time.time()}"
                    queue_message(test_data)
                    self.log_message("Test packet queued for sending")
                except Exception as e:
                    self.log_message(f"Error sending test packet: {str(e)}")
    
    # Update the handle_key_events method to remove chat references
    def handle_key_events(self, event):
        """Handle keyboard events"""
        if event.key == pygame.K_ESCAPE:
            try:
                if self.current_state == self.STATE_CONNECTED:
                    if self.vpn_active:
                        stop_vpn()
                    self.vpn_active = False
                    self.current_state = self.STATE_CONFIG
                elif self.current_state == self.STATE_CONFIG:
                    self.current_state = self.STATE_IP_ENTRY
            except Exception as e:
                self.log_message(f"Error disconnecting: {str(e)}")
        
        # Handle Ctrl+V for paste
        ctrl_pressed = pygame.key.get_mods() & pygame.KMOD_CTRL
        
        if self.active_input == "ip" and self.current_state == self.STATE_IP_ENTRY:
            if event.key == pygame.K_RETURN:
                if self.validate_ip(self.entered_ip):
                    self.log_message(f"IP entered: {self.entered_ip}")
                else:
                    self.log_message("Invalid IP format. Use: xxx.xxx.xxx.xxx")
            elif event.key == pygame.K_BACKSPACE:
                self.entered_ip = self.entered_ip[:-1]
            elif ctrl_pressed and event.key == pygame.K_v:
                # Paste IP from clipboard
                clipboard_text = self.get_clipboard_text()
                if clipboard_text and self.validate_ip(clipboard_text):
                    self.entered_ip = clipboard_text
                    self.log_message(f"Pasted IP: {self.entered_ip}")
                else:
                    self.log_message("Invalid IP in clipboard")
            else:
                # Only allow numbers and periods for IP
                if event.unicode in "0123456789.":
                    self.entered_ip += event.unicode
        
        elif self.active_input == "key" and self.current_state == self.STATE_CONFIG:
            if event.key == pygame.K_RETURN:
                # Save the entered key
                self.key_text, self.using_existing_key = self.key_manager.handle_key_management(
                    "manual", self.key_text, generate_key, load_key, save_key)
            elif event.key == pygame.K_BACKSPACE:
                self.key_text = self.key_text[:-1]
            elif ctrl_pressed and event.key == pygame.K_v:
                # Paste key from clipboard
                clipboard_text = self.get_clipboard_text()
                if clipboard_text:
                    # Filter out non-hex characters
                    hex_chars = ''.join(c for c in clipboard_text if c.lower() in "0123456789abcdef")
                    if hex_chars:
                        self.key_text = hex_chars
                        self.log_message("Pasted encryption key")
                        self.ui.show_popup("Key pasted from clipboard")
                    else:
                        self.log_message("Clipboard doesn't contain valid hex characters")
                        self.ui.show_popup("No valid key found in clipboard")
            else:
                # Only allow hex characters (0-9, a-f)
                if event.unicode.lower() in "0123456789abcdef":
                    self.key_text += event.unicode.lower()

    # Add this helper method to get text from clipboard
    def get_clipboard_text(self):
        """Get text from clipboard"""
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()  # Hide the window
            clipboard_text = root.clipboard_get()
            root.destroy()
            return clipboard_text
        except:
            # Fall back to system-specific methods
            try:
                if platform.system() == "Windows":
                    import subprocess
                    p = subprocess.Popen(['powershell.exe', '-command', 'Get-Clipboard'], 
                                        stdout=subprocess.PIPE)
                    return p.communicate()[0].decode().strip()
                elif platform.system() == "Darwin":  # macOS
                    import subprocess
                    p = subprocess.Popen(['pbpaste'], stdout=subprocess.PIPE)
                    return p.communicate()[0].decode().strip()
                elif platform.system() == "Linux":
                    import subprocess
                    p = subprocess.Popen(['xclip', '-selection', 'clipboard', '-o'], 
                                        stdout=subprocess.PIPE)
                    return p.communicate()[0].decode().strip()
            except:
                self.log_message("Unable to access clipboard")
                return ""
    
    # Update the run method to draw popups
    def run(self):
        """Main application loop"""
        running = True
        
        while running:
            self.screen.fill(WHITE)
            
            # Draw different screens based on current state
            if self.current_state == self.STATE_IP_ENTRY:
                self.draw_ip_entry_screen()
            elif self.current_state == self.STATE_CONFIG:
                self.draw_config_screen()
            elif self.current_state == self.STATE_CONNECTED:
                self.draw_connected_screen()
            
            # Reset copy button after 2 seconds
            if self.copy_button_clicked and time.time() - self.copy_button_timer > 2:
                self.copy_button_clicked = False
                self.ui.set_copy_button_state("copy_key", False)
            
            # Draw any active popup notification
            self.ui.draw_popup()
            
            pygame.display.flip()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if self.current_state == self.STATE_IP_ENTRY:
                        self.handle_ip_entry_events(event)
                    elif self.current_state == self.STATE_CONFIG:
                        self.handle_config_screen_events(event)
                    elif self.current_state == self.STATE_CONNECTED:
                        self.handle_connected_screen_events(event)
                
                elif event.type == pygame.KEYDOWN:
                    self.handle_key_events(event)
        
        pygame.quit()
        stop_vpn()

if __name__ == "__main__":
    app = VPNApplication()
    app.run()