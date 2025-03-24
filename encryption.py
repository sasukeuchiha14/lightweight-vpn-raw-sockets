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

def load_key(local=False):
    """Load the encryption key"""
    try:
        path = DEFAULT_KEY_PATH if local else os.path.expanduser("~/.vpn_key")
        with open(path, 'rb') as f:
            key_data = f.read()
            
        # Check if it's a hex string or binary
        if len(key_data) == 64:  # Hex string would be 64 chars for 32 bytes
            try:
                # Try to decode as hex string
                return bytes.fromhex(key_data.decode('utf-8'))
            except:
                pass
                
        return key_data
    except FileNotFoundError:
        # Generate a new key if none exists
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
