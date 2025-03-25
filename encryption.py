import os
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Constants
DEFAULT_KEY_PATH = "vpn_key.txt"

def generate_key(local=False):
    """Generate a random 256-bit key and save it"""
    key = os.urandom(32)  # 32 bytes = 256 bits
    save_path = DEFAULT_KEY_PATH if local else os.path.expanduser("~/.vpn_key")
    with open(save_path, 'wb') as f:
        f.write(key)
    return key

# Replace the existing load_key function with this version
def load_key(local=False, direct_key=None):
    """Load the encryption key with strict cross-platform compatibility"""
    # If direct key string is provided, use it instead of loading from file
    if direct_key:
        return normalize_key_string(direct_key)
        
    try:
        path = DEFAULT_KEY_PATH if local else os.path.expanduser("~/.vpn_key")
        
        # Read the key file
        with open(path, 'rb') as f:
            file_content = f.read()
        
        # First, try to interpret as binary (32 bytes)
        if len(file_content) == 32:
            return file_content
            
        # Next, try to interpret as hex string
        try:
            # Convert to string and clean
            text_content = file_content.decode('utf-8', errors='ignore').strip()
            return normalize_key_string(text_content)
        except Exception as e:
            print(f"Error normalizing key: {e}")
            
        # If we get here, try a last resort approach
        print("Using hash-based key normalization as fallback")
        return hashlib.sha256(file_content).digest()
        
    except FileNotFoundError:
        # Generate a new key if none exists
        print("Key file not found, generating new key")
        return generate_key(local)

def save_key(key_data, local=False):
    """Save a key from hex string or bytes"""
    save_path = DEFAULT_KEY_PATH if local else os.path.expanduser("~/.vpn_key")
    
    # Handle hex string
    if isinstance(key_data, str):
        # Convert hex string to bytes
        key_bytes = bytes.fromhex(key_data)
    else:
        # Already bytes
        key_bytes = key_data
        
    # Ensure key is 32 bytes (256 bits)
    if len(key_bytes) != 32:
        raise ValueError("Key must be exactly 32 bytes (256 bits)")
        
    with open(save_path, 'wb') as f:
        f.write(key_bytes)

def encrypt_data(data):
    """Encrypt data using the stored key"""
    key = load_key()
    
    # Generate a random IV
    iv = os.urandom(16)
    
    # Create an encryptor
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # PKCS7 padding
    padded_data = pad(data, AES.block_size)
    
    # Encrypt the data
    encrypted_data = cipher.encrypt(padded_data)
    
    # Return IV + encrypted data
    return iv + encrypted_data

def decrypt_data(encrypted_data):
    """Decrypt data using the stored key"""
    key = load_key()
    
    # Extract IV and ciphertext
    iv = encrypted_data[:16]
    ciphertext = encrypted_data[16:]
    
    # Create a decryptor
    cipher = AES.new(key, AES.MODE_CBC, iv)
    
    # Decrypt the data
    padded_data = cipher.decrypt(ciphertext)
    
    # Remove PKCS7 padding
    return unpad(padded_data, AES.block_size)

# Helper functions for encryption-based operations
def encrypt_message(message):
    """Encrypt a text message"""
    if isinstance(message, str):
        return encrypt_data(message.encode('utf-8'))
    return encrypt_data(message)

def decrypt_message(encrypted_message):
    """Decrypt a message to text"""
    decrypted_data = decrypt_data(encrypted_message)
    return decrypted_data.decode('utf-8')

# Add this function to encryption.py
def normalize_key_string(key_string):
    """
    Strictly normalize a key string to ensure cross-platform compatibility
    """
    # Remove all non-hex characters (spaces, newlines, etc.)
    clean_key = ''.join(c for c in key_string if c.lower() in '0123456789abcdef')
    
    # Ensure we have exactly 64 hex chars (32 bytes)
    if len(clean_key) >= 64:
        clean_key = clean_key[:64]  # Take only first 64 chars if longer
    else:
        # If shorter, it's an invalid key - but we'll pad with zeros to prevent errors
        print(f"WARNING: Key too short ({len(clean_key)} chars), padding with zeros")
        clean_key = clean_key.ljust(64, '0')
    
    # Convert hex string to bytes
    return bytes.fromhex(clean_key)

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
