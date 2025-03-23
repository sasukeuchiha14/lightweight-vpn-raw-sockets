import os
import platform

def copy_to_clipboard(text):
    """Cross-platform clipboard copy function"""
    try:
        # Try using tkinter for clipboard (works on most platforms)
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Hide the window
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()  # Required for clipboard to work
        root.destroy()
        return True
    except:
        # Fall back to system-specific methods
        try:
            if platform.system() == "Windows":
                import subprocess
                subprocess.run(['clip'], input=text.encode('utf-8'), check=True)
            elif platform.system() == "Darwin":  # macOS
                import subprocess
                subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
            elif platform.system() == "Linux":
                import subprocess
                subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode('utf-8'), check=True)
            else:
                return False
            return True
        except:
            return False

class KeyManager:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
    
    def log(self, message):
        """Send log message to callback if available"""
        if self.log_callback:
            self.log_callback(message)
    
    def handle_key_management(self, option, key_text, generate_key, load_key, save_key):
        """Handle different key management operations"""
        if option == "new":
            generate_key(local=True)  # Save in current directory for easy sharing
            key_text = load_key().hex()
            self.log("Generated new encryption key")
            log_file_path = os.path.join(os.getcwd(), "vpn_key.txt")
            self.log(f"Key saved to: {log_file_path}")
            return key_text, True  # Return key text and using_existing_key flag
        
        elif option == "existing" or option == "browse":
            # Use file dialog to select a key file
            uploaded_key = self.open_file_dialog()
            if uploaded_key:
                try:
                    save_key(uploaded_key, local=True)  # Save the selected key to the default location
                    self.log("Selected key loaded successfully")
                    return uploaded_key, True
                except Exception as e:
                    self.log(f"Error saving selected key: {str(e)}")
                    return key_text, False
            return key_text, False
        
        elif option == "upload":
            # Use the file dialog to upload a key
            uploaded_key = self.open_file_dialog()
            if uploaded_key:
                try:
                    save_key(uploaded_key, local=True)
                    self.log("Key file uploaded successfully")
                    log_file_path = os.path.join(os.getcwd(), "vpn_key.txt")
                    self.log(f"Key saved to: {log_file_path}")
                    return uploaded_key, True
                except Exception as e:
                    self.log(f"Error saving uploaded key: {str(e)}")
                    return key_text, False
            return key_text, False
        
        elif option == "manual":
            # Manual key entry (from text input)
            try:
                if len(key_text) == 64:  # 32 bytes = 64 hex chars
                    save_key(key_text, local=True)  # Save in current directory
                    self.log("Saved manually entered key")
                    log_file_path = os.path.join(os.getcwd(), "vpn_key.txt")
                    self.log(f"Key saved to: {log_file_path}")
                    return key_text, True
                else:
                    self.log("Invalid key length (must be 64 hex characters)")
                    return key_text, False
            except Exception as e:
                self.log(f"Error saving key: {str(e)}")
                return key_text, False
        
        return key_text, False

    def open_file_dialog(self):
        """Open a file dialog to select a key file"""
        try:
            import tkinter as tk
            from tkinter import filedialog
            
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            
            file_path = filedialog.askopenfilename(
                title="Select Key File",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            
            if file_path:
                try:
                    with open(file_path, 'rb') as f:
                        key_data = f.read()
                        
                    # Validate the key
                    if len(key_data) == 32:  # 256-bit key
                        return key_data.hex()
                    else:
                        # Try to interpret as hex string
                        try:
                            key_text = key_data.decode('utf-8').strip()
                            # Filter out non-hex characters
                            key_text = ''.join(c for c in key_text if c.lower() in "0123456789abcdef")
                            if len(key_text) == 64:  # 32 bytes = 64 hex chars
                                return key_text
                        except:
                            pass
                        
                        self.log(f"Invalid key file format. Key must be 32 bytes or 64 hex characters.")
                        return None
                except Exception as e:
                    self.log(f"Error reading key file: {str(e)}")
                    return None
            return None
        except Exception as e:
            self.log(f"Error opening file dialog: {str(e)}")
            return None