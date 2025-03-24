import pygame
import sys
import threading
import os
import platform
import re
import time
import socket
import subprocess

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
        
        # Add refresh timer for UI updates
        self.last_ui_refresh = 0
        self.ui_refresh_interval = 0.5  # seconds
    
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
    
    # Update handle_vpn_message to strictly limit log history
    def handle_vpn_message(self, message, msg_type="info"):
        """Handle messages from the VPN module with improved log management"""
        current_time = time.strftime("%H:%M:%S")
        
        if msg_type == "message":
            # Track as packet received
            self.packets_received += 1
            self.bytes_transferred += len(message)
            
            # More detailed log for easier debugging
            if "TEST_PACKET" in message or "test packet" in message.lower():
                # Make test packets more visible in logs
                log_entry = f"[{current_time}] 📦 Test packet received: {len(message)} bytes"
            elif "KEY_VERIFICATION" in message:
                log_entry = f"[{current_time}] 🔑 Key verification packet received: {len(message)} bytes"
            else:
                log_entry = f"[{current_time}] 📥 Packet received: {len(message)} bytes"
            
            # Add to transfer logs
            self.transfer_logs.append(log_entry)
            
            # Print to console for easier debugging
            print(f"RECEIVED: {log_entry}")
            
            # Limit log history
            while len(self.transfer_logs) > 10:
                self.transfer_logs.pop(0)
    
        elif msg_type == "decryption_failed":
            # Log decryption failures but don't count as received packets
            log_entry = f"[{current_time}] ❌ Decryption failed - keys may not match!"
            self.transfer_logs.append(log_entry)
            print(f"ERROR: {log_entry}")
            
            # Show popup about potential key mismatch
            self.ui.show_popup("Decryption failed - keys may not match!", 3.0)
            
            # Limit log history
            while len(self.transfer_logs) > 10:
                self.transfer_logs.pop(0)
                
        elif msg_type == "packet_sent":
            # Track as packet sent
            self.packets_sent += 1
            self.bytes_transferred += len(message)
            
            # More detailed log
            if "TEST_PACKET" in message or "test packet" in message.lower():
                log_entry = f"[{current_time}] 📤 Test packet sent: {len(message)} bytes"
            else:
                log_entry = f"[{current_time}] 📤 Packet sent: {len(message)} bytes"
            
            # Add to transfer logs
            self.transfer_logs.append(log_entry)
            
            # Print to console for easier debugging
            print(f"SENT: {log_entry}")
            
            # Limit log history
            while len(self.transfer_logs) > 10:
                self.transfer_logs.pop(0)
                
        else:
            # Regular info/error logs
            self.log_messages.append(message)
            
            # Print to console for easier debugging
            print(f"LOG: {message}")
            
            # Limit general log history
            while len(self.log_messages) > 15:
                self.log_messages.pop(0)
    
    # Update the start_vpn_thread method to include key checks
    def start_vpn_thread(self):
        """Start VPN in a separate thread with improved stability and key checks"""
        try:
            # Verify we can load the key before connecting
            try:
                from encryption import load_key
                key = load_key()
                if len(key) != 32:  # Must be 32 bytes (256 bits)
                    self.log_message(f"Warning: Key size is {len(key)} bytes, expected 32 bytes")
                    self.ui.show_popup("Warning: Encryption key may be invalid", 3.0)
            except Exception as key_error:
                self.log_message(f"Error loading encryption key: {str(key_error)}")
                self.ui.show_popup("Error loading encryption key", 3.0)
                return
                
            # First make sure any previous VPN is stopped
            stop_vpn()
            
            # Short delay to ensure cleanup
            time.sleep(0.5)
            
            # Reset connection statistics
            self.packets_sent = 0
            self.packets_received = 0
            self.bytes_transferred = 0
            self.connection_time = 0
            self.connection_start_time = 0
            
            # Start new VPN connection
            if self.connection_type == "send":
                self.log_message(f"Starting VPN sender to {self.entered_ip}")
                threading.Thread(target=self.vpn_sender_wrapper, args=(self.entered_ip,), daemon=True).start()
            else:  # receive
                self.log_message("Starting VPN receiver")
                threading.Thread(target=self.vpn_receiver_wrapper, daemon=True).start()
            
            self.vpn_active = True
            self.transfer_logs.append("VPN connection initialized")
            
            # Log key fingerprint for reference
            self.check_key_compatibility()
            
        except Exception as e:
            self.log_message(f"Error starting VPN: {str(e)}")
            self.vpn_active = False
    
    # Improve VPN sender wrapper to prevent disconnection
    def vpn_sender_wrapper(self, ip):
        """Wrapper for vpn_sender with improved error handling and reconnection"""
        try:
            # Log connection attempt
            self.log_message(f"Connecting to VPN target: {ip}")
            
            # Run vpn_sender and handle any errors
            vpn_sender(ip)
            
            # If we reach here normally, the connection ended gracefully
            self.log_message("VPN sender connection ended")
        except ConnectionRefusedError:
            self.log_message(f"Connection refused by {ip}. Is the receiver running?")
            self.vpn_active = False
        except ConnectionResetError:
            self.log_message("Connection reset by peer. Remote host disconnected.")
            self.vpn_active = False
        except socket.timeout:
            self.log_message("Connection timed out")
            self.vpn_active = False
        except Exception as e:
            self.log_message(f"VPN sender error: {str(e)}")
            # Don't set vpn_active to False immediately to allow for retries
            
            # Try to recover if still active
            if self.vpn_active:
                self.log_message("Attempting to reconnect...")
                time.sleep(2)  # Wait before reconnecting
                try:
                    vpn_sender(ip)
                except Exception as e2:
                    self.log_message(f"Reconnection failed: {str(e2)}")
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
    
    # Update the draw_config_screen method to add connection test for both modes
    def draw_config_screen(self):
        """Draw the VPN configuration screen"""
        self.ui.draw_button("Back", self.back_button)
        
        title_text = "Sender Configuration" if self.connection_type == "send" else "Receiver Configuration"
        title_surf = self.fonts['title'].render(title_text, True, BLACK)
        self.screen.blit(title_surf, (self.WIDTH//2 - title_surf.get_width()//2, 30))
        
        # Show connecting IP address (for sender) or listening status (for receiver)
        if self.connection_type == "send":
            ip_text = f"Target IP: {self.entered_ip}"
        else:
            # Get and display your own IP
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                ip_text = f"Listening on: {local_ip}:8989"
            except:
                ip_text = "Listening on: localhost:8989"
                
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
        
        # Add a port test button for both sender and receiver
        port_test_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 50, 200, 40)
        if self.connection_type == "send":
            self.ui.draw_button("Test Connection", port_test_button, BLUE)
        else:
            self.ui.draw_button("Test Listening Port", port_test_button, BLUE)
    
    # Update the draw_connected_screen method to only show test packet button in send mode
    def draw_connected_screen(self):
        """Draw the connected VPN screen"""
        # Wider disconnect button
        disconnect_button = pygame.Rect(20, 20, 150, 40)
        self.ui.draw_button("Disconnect", disconnect_button, RED)
        
        # Draw VPN toggle circle - SHIFTED RIGHT FOR BETTER TEXT LAYOUT
        circle_center = (200, 200)  # Moved from 150 to 200 for more space
        circle_color = GREEN if self.vpn_active else RED
        self.ui.draw_circle_button(circle_center, 50, circle_color)
        
        # Status text
        status_text = "VPN ACTIVE" if self.vpn_active else "VPN INACTIVE"
        status_surf = self.fonts['normal'].render(status_text, True, BLACK)
        self.screen.blit(status_surf, (circle_center[0] - status_surf.get_width()//2, circle_center[1] + 60))
        
        # Show connected IP with adjusted positioning
        if self.connection_type == "send":
            ip_text = f"Connected to: {self.entered_ip}"
        else:
            ip_text = "Listening for connections"
        
        ip_surf = self.fonts['normal'].render(ip_text, True, BLACK)
        
        # Make sure the text is fully visible within screen bounds
        text_x = circle_center[0] - ip_surf.get_width()//2
        # Ensure text doesn't go beyond left margin
        if text_x < 30:
            text_x = 30
        self.screen.blit(ip_surf, (text_x, circle_center[1] + 90))
        
        # Rest of the method remains unchanged
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
            f"Data transferred: {bytes_str}",
            f"VPN Port: {8989}"  # Show the VPN port being used
        ]
        
        y_offset = stats_area.y + 50
        for stat in stats:
            stat_surf = self.fonts['small'].render(stat, True, BLACK)
            self.screen.blit(stat_surf, (stats_area.x + 20, y_offset))
            y_offset += 30
        
        # Add test packet button ONLY in send mode
        if self.connection_type == "send":
            test_packet_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 80, 200, 50)
            self.ui.draw_button("Send Test Packet", test_packet_button, 
                             GREEN if self.vpn_active else GRAY)
        
        # Add key verification button
        verify_key_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 130, 200, 40)
        self.ui.draw_button("Verify Encryption Key", verify_key_button, BLUE if self.vpn_active else GRAY)
        
        # Draw packet transfer logs with improved visual cues
        log_area = pygame.Rect(50, self.HEIGHT - 200, self.WIDTH - 100, 100)
        pygame.draw.rect(self.screen, LIGHT_GRAY, log_area, border_radius=5)
        
        log_title = self.fonts['normal'].render("Packet Transfer Log", True, BLACK)
        self.screen.blit(log_title, (log_area.x + 10, log_area.y + 5))
        
        # Add indicator if there are more logs than shown and show count
        if len(self.transfer_logs) > 5:
            more_logs_text = f"(+{len(self.transfer_logs) - 5} more logs)"
            more_logs_surf = self.fonts['small'].render(more_logs_text, True, DARK_GRAY)
            self.screen.blit(more_logs_surf, (log_area.x + log_area.width - more_logs_surf.get_width() - 15, log_area.y + 10))
        
        # Display the most recent logs - use reversed to have newest at the top
        y_offset = log_area.y + 40
        # Make a copy and select the last 5 entries to display (most recent)
        display_logs = list(self.transfer_logs[-5:])
        # Ensure these are shown in reverse order (newest at the top) - optional
        # display_logs.reverse()  # Uncomment if you want newest at top
        
        for log in display_logs:
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
    
    # Update handle_config_screen_events to add the port test for both modes
    def handle_config_screen_events(self, event):
        """Handle events for the configuration screen"""
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.back_button.collidepoint(event.pos):
                self.current_state = self.STATE_IP_ENTRY
                self.using_existing_key = False
            
            # Test Connection button - for both sender and receiver
            port_test_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 50, 200, 40)
            if port_test_button.collidepoint(event.pos):
                if self.connection_type == "send":
                    # Test connection to remote server for sender
                    threading.Thread(
                        target=self.test_port_connection,
                        args=(self.entered_ip, 8989),
                        daemon=True
                    ).start()
                else:
                    # Test local listening port for receiver
                    threading.Thread(
                        target=self.test_listening_port,
                        args=(8989,),
                        daemon=True
                    ).start()
                    
            # Now handle the key management buttons
            if self.connection_type == "send":
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
    
    # Update the handle_connected_screen_events method to fix test packet sending
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
            
            # Test packet button - ONLY check in send mode
            if self.connection_type == "send":
                test_packet_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 80, 200, 50)
                if test_packet_button.collidepoint(event.pos) and self.vpn_active:
                    try:
                        # Create a more distinctive test packet
                        test_data = f"EXPLICIT_TEST_PACKET_{time.time()}"
                        self.log_message(f"Sending test packet: {test_data}")
                        
                        # Use direct method from vpn module for more reliable sending
                        from vpn import active_connections
                        
                        # Get the correct connection from active connections
                        connection_id = f"{self.entered_ip}:8989"  # Hardcoded port for now
                        if connection_id in active_connections:
                            sock = active_connections[connection_id]
                            from vpn import send_message
                            send_result = send_message(sock, test_data)
                            if send_result:
                                self.log_message("Test packet sent directly to connection")
                                self.ui.show_popup("Test packet sent", 2.0)
                            else:
                                self.log_message("Failed to send test packet directly")
                                self.ui.show_popup("Failed to send test packet", 2.0)
                        else:
                            # Fall back to queue if direct connection not found
                            self.log_message("No active connection found, queueing test packet")
                            queue_message(test_data)
                            self.ui.show_popup("Test packet queued for sending", 2.0)
                    except Exception as e:
                        self.log_message(f"Error sending test packet: {str(e)}")
                        self.ui.show_popup(f"Error: {str(e)}", 2.0)
            
            # Then update handle_connected_screen_events to add logic for this button
            verify_key_button = pygame.Rect(self.WIDTH//2 - 100, self.HEIGHT - 130, 200, 40)
            if verify_key_button.collidepoint(event.pos) and self.vpn_active:
                self.verify_vpn_keys()
    
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
    
    # Add this function to your VPNApplication class
    def test_port_connection(self, ip, port):
        """Test if a port is open on the target IP with popup feedback"""
        self.log_message(f"Testing connection to {ip}:{port}...")
        self.ui.show_popup(f"Testing connection to {ip}...", 1.0)
        
        # Run ping test to check basic connectivity
        ping_success = self.ping_test(ip)
        
        if not ping_success:
            self.log_message(f"❌ Cannot reach host {ip} (ping failed)")
            self.ui.show_popup(f"IP Unreachable: Cannot reach {ip}", 3.0)
            return False
            
        # If ping successful, test the specific port
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(3)
            result = test_socket.connect_ex((ip, port))
            test_socket.close()
            
            if result == 0:
                self.log_message(f"✅ Host reachable and Port {port} is OPEN on {ip}")
                self.ui.show_popup(f"Connection successful to {ip}:{port}", 3.0)
                return True
            else:
                self.log_message(f"⚠️ Host reachable but Port {port} is CLOSED on {ip} (Error code: {result})")
                self.ui.show_popup(f"Port {port} is closed on {ip}", 3.0)
                return False
        except Exception as e:
            self.log_message(f"❌ Error testing port: {str(e)}")
            self.ui.show_popup(f"Connection error: {str(e)}", 3.0)
            return False

    def ping_test(self, host, count=2):
        """Test if host is reachable using ping"""
        try:
            self.log_message(f"Pinging {host}...")
            
            # Different ping command based on platform
            if platform.system().lower() == "windows":
                command = ["ping", "-n", str(count), "-w", "1000", host]
            else:
                command = ["ping", "-c", str(count), "-W", "1", host]
                
            # Run the ping command
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
            output = stdout.decode()
            
            # Check for successful pings
            if platform.system().lower() == "windows":
                success = "TTL=" in output
            else:
                success = "bytes from" in output
                
            packet_loss = "100% packet loss" in output or "100% loss" in output
            
            if success and not packet_loss:
                self.log_message("✅ Ping successful")
                return True
            else:
                self.log_message(f"❌ Ping failed: {packet_loss}")
                return False
                
        except Exception as e:
            self.log_message(f"❌ Ping error: {str(e)}")
            return False
    
    # Add this method to test listening port for receiver mode
    def test_listening_port(self, port):
        """Test if the listening port is available and working"""
        self.log_message(f"Testing if port {port} is available for listening...")
        self.ui.show_popup(f"Testing port {port}...", 1.0)
        
        try:
            # Try to create a test socket and bind to the port
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            
            # Enable address reuse to avoid "port in use" errors
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                test_socket.bind(('0.0.0.0', port))
                test_socket.listen(1)
                
                # Port is available for listening
                self.log_message(f"✅ Port {port} is available for listening")
                
                # Get my IP address for display
                try:
                    hostname = socket.gethostname()
                    local_ip = socket.gethostbyname(hostname)
                    self.ui.show_popup(f"Listening successful on {local_ip}:{port}", 3.0)
                except:
                    self.ui.show_popup(f"Listening successful on port {port}", 3.0)
                
                result = True
            except OSError as e:
                if "in use" in str(e).lower() or "being used" in str(e).lower():
                    # The port is in use - could be our own VPN or another app
                    self.log_message(f"⚠️ Port {port} is already in use - may be your VPN receiver")
                    self.ui.show_popup(f"Port {port} already in use - VPN may be running", 3.0)
                    # This might not be an error if our VPN is already running
                    result = "in_use"
                else:
                    self.log_message(f"❌ Port binding error: {str(e)}")
                    self.ui.show_popup(f"Port error: {str(e)}", 3.0)
                    result = False
        except Exception as e:
            self.log_message(f"❌ Error testing listening port: {str(e)}")
            self.ui.show_popup(f"Test error: {str(e)}", 3.0)
            result = False
        finally:
            try:
                test_socket.close()
            except:
                pass
            
        return result
    
    # Update the verify_vpn_keys method
    def verify_vpn_keys(self):
        """Verifies that both sides are using the same encryption key by sending a test packet"""
        if not self.vpn_active:
            self.ui.show_popup("VPN must be active to verify keys", 2.0)
            return False
            
        # First check and display our key fingerprint
        self.check_key_compatibility()
        
        try:
            # Generate a simple test string with current timestamp
            test_data = f"KEY_VERIFICATION_TEST_{time.time()}"
            self.log_message(f"Sending key verification packet: {test_data}")
            
            # Show instructions for key verification
            if self.connection_type == "send":
                # Use direct send method to verify connection
                from vpn import active_connections, send_message
                
                # Get the connection
                connection_id = f"{self.entered_ip}:8989"
                if connection_id in active_connections:
                    sock = active_connections[connection_id]
                    if send_message(sock, test_data):
                        self.ui.show_popup("Verification packet sent - match fingerprints with receiver", 3.0)
                        return True
                    else:
                        self.ui.show_popup("Failed to send verification packet", 2.0)
                        return False
                else:
                    self.ui.show_popup("No active connection found", 2.0)
                    return False
            else:
                # For receiver, we can only wait for incoming packets
                self.ui.show_popup("Compare key fingerprint with sender's", 3.0)
                return True
                
        except Exception as e:
            self.log_message(f"Key verification error: {str(e)}")
            self.ui.show_popup(f"Verification error: {str(e)}", 2.0)
            return False
    
    def check_key_compatibility(self):
        """Verify if sender and receiver are using the same encryption key"""
        try:
            # Get key info for debugging
            from encryption import load_key
            key = load_key()
            key_hex = key.hex()
            
            # Log key fingerprint (first and last 4 bytes only - for security)
            key_fingerprint = f"{key_hex[:8]}...{key_hex[-8:]}"
            self.log_message(f"Using encryption key with fingerprint: {key_fingerprint}")
            
            # Add key fingerprint to status display
            self.transfer_logs.append(f"Key fingerprint: {key_fingerprint}")
            
            # Show popup with key info
            self.ui.show_popup(f"Key fingerprint: {key_fingerprint}", 4.0)
            return True
        except Exception as e:
            self.log_message(f"Error checking key: {str(e)}")
            self.ui.show_popup("Error retrieving key info", 3.0)
            return False
    
    # Add a method to show key mismatch help
    def show_key_mismatch_help(self):
        """Show instructions for fixing a key mismatch"""
        self.log_message("Detected potential key mismatch between sender and receiver")
        
        help_text = [
            "If you're seeing decryption errors:",
            "1. Both sender and receiver must use the same exact key",
            "2. Generate a new key on sender and use 'Copy' button",
            "3. On receiver, click 'Paste' to use the exact same key",
            "4. Reconnect both sides after ensuring keys match"
        ]
        
        for line in help_text:
            self.log_message(line)
        
        self.ui.show_popup("See log for key mismatch help", 3.0)
    
    # Update the run method to draw popups
    def run(self):
        """Main application loop"""
        running = True
        clock = pygame.time.Clock()
        
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
            
            # Regular UI update
            pygame.display.flip()
            
            # Force refresh the screen every interval to ensure logs are updated
            current_time = time.time()
            if current_time - self.last_ui_refresh >= self.ui_refresh_interval:
                pygame.display.update()
                self.last_ui_refresh = current_time
                
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
                    
            # Limit frame rate to save CPU
            clock.tick(30)
        
        pygame.quit()
        stop_vpn()

if __name__ == "__main__":
    app = VPNApplication()
    app.run()