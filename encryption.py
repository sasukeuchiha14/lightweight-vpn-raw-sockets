import os
import random
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
import platform

# Constants
KEY_SIZE = 32  # 256 bits
KEY_FILE = "vpn_key.txt"

def get_key_path(local=False):
    """Get the path for the key file
    
    Args:
        local: If True, save in the current directory instead of the system location
    """
    if local:
        # Save in the current directory
        return os.path.join(os.getcwd(), KEY_FILE)
    
    # Otherwise use platform-specific paths
    if platform.system() == "Windows":
        key_dir = os.path.join(os.getenv("APPDATA"), "LightweightVPN")
    else:  # Linux/Mac
        key_dir = os.path.join(os.path.expanduser("~"), ".lightweight_vpn")
    
    # Ensure directory exists
    if not os.path.exists(key_dir):
        os.makedirs(key_dir)
    
    return os.path.join(key_dir, KEY_FILE)

def generate_key(local=True):
    """Generate a new random encryption key and save it to file
    
    Args:
        local: If True, save in the current directory for easy sharing
    """
    key = os.urandom(KEY_SIZE)  # Generate random 256-bit key
    
    # Save key to file
    key_path = get_key_path(local)
    with open(key_path, "wb") as f:
        f.write(key)
    
    return key

def load_key():
    """Load the encryption key from file or generate a new one"""
    key_path = get_key_path()
    
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            key = f.read()
        return key
    else:
        # No key exists, generate and save a new one
        return generate_key()

def save_key(key_data, local=True):
    """Save a given key to the key file
    
    Args:
        key_data: The key data (hex string or bytes)
        local: If True, save in the current directory for easy sharing
    """
    # Convert from hex string if needed
    if isinstance(key_data, str):
        key_data = binascii.unhexlify(key_data)
    
    key_path = get_key_path(local)
    with open(key_path, "wb") as f:
        f.write(key_data)

def encrypt_message(message):
    """Encrypt a message using the VPN key"""
    # Convert string to bytes if needed
    if isinstance(message, str):
        message = message.encode('utf-8')
    
    # Load the key
    key = load_key()
    
    # Generate a random IV (initialization vector)
    iv = os.urandom(16)
    
    # Create AES cipher
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # Pad and encrypt the message
    padded_message = pad(message, AES.block_size)
    encrypted_message = cipher.encrypt(padded_message)
    
    # Prepend the IV to the encrypted message
    return iv + encrypted_message

def decrypt_message(encrypted_data):
    """Decrypt a message using the VPN key"""
    # Load the key
    key = load_key()
    
    # Extract the IV (first 16 bytes)
    iv = encrypted_data[:16]
    encrypted_message = encrypted_data[16:]
    
    # Create AES cipher
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # Decrypt and unpad the message
    decrypted_message = unpad(cipher.decrypt(encrypted_message), AES.block_size)
    
    # Return as string
    return decrypted_message.decode('utf-8')

# Run a test
if __name__ == "__main__":
    test_data = "Hello, Secure World!"
    
    # Generate a new key
    # generate_key()
    
    print("\n🔐 Encrypting Message...")
    encrypted = encrypt_message(test_data)
    print("Encrypted:", encrypted.hex())

    print("\n🔓 Decrypting Message...")
    decrypted = decrypt_message(encrypted)
    print("Decrypted:", decrypted)
