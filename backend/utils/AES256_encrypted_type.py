from sqlalchemy.types import TypeDecorator, TEXT
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

from dotenv import load_dotenv
load_dotenv()

KEY_HEX = os.environ.get("DB_ENCRYPTION_KEY_HEX") 
if KEY_HEX:
    aesgcm = AESGCM(bytes.fromhex(KEY_HEX))
else:
    raise RuntimeError("DB encryption key not found")
    
class EncryptedString(TypeDecorator):
    """
    AES-256-GCM Encryption Type.
    Storage Format (Base64): [Nonce (12 bytes) + Ciphertext + AuthTag]
    """
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypts data using AES-256-GCM"""
        if not value:
            return
        
        data = value.encode('utf-8')
        
        # Generate unique Nonce (12 bytes is standard for GCM)
        nonce = os.urandom(12)
        
        # Encrypt
        ciphertext = aesgcm.encrypt(nonce, data, None)
        
        # Storage: Combine Nonce + Ciphertext; 
        combined = nonce + ciphertext
        
        # encode Base64
        return base64.b64encode(combined).decode('utf-8')

    def process_result_value(self, value, dialect):
        """Decrypts data using AES-256-GCM"""
        if not value:
            return
        
        try:

            encrypted_data = base64.b64decode(value)
            
            # Spliit to nonce (First 12 bytes) and ciphertext
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            original_data = aesgcm.decrypt(nonce, ciphertext, None)
            
            return original_data.decode('utf-8')
        
        except Exception as e:
            return "[Decryption Error]"
        
# Instructions when updating
# Load 32-byte (256-bit) key from environment
# Run `import os; os.urandom(32).hex()` to generate one for .env
# Example .env: ENCRYPTION_KEY_HEX=0123456789abcdef... (64 hex chars)

# Testing
# data = "Sensitive Information"
# encrypted = EncryptedString().process_bind_param(data, None)
# print(encrypted)
# decrypted = EncryptedString().process_result_value(encrypted, None)
# print(decrypted)