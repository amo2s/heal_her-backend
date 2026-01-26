import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()

# 1. Load the Master Key
key = os.getenv("ENCRYPTION_KEY")

if not key:
    raise ValueError("❌ FATAL ERROR: ENCRYPTION_KEY not found in .env file!")

# 2. Create the Locksmith
cipher_suite = Fernet(key)

def encrypt_message(plain_text: str) -> str:
    """
    Locks the message.
    Input: "Hello"
    Output: "gAAAAABk..."
    """
    if not plain_text:
        return ""
    # Convert text to bytes -> Encrypt -> Convert back to string
    return cipher_suite.encrypt(plain_text.encode()).decode()

def decrypt_message(encrypted_text: str) -> str:
    """
    Unlocks the message.
    Crucial: If it fails to unlock (e.g., old plain text messages), 
    it just returns the original text safely.
    """
    if not encrypted_text:
        return ""
    
    try:
        # Try to unlock
        return cipher_suite.decrypt(encrypted_text.encode()).decode()
    except Exception:
        # If it fails, it means this message wasn't encrypted (Legacy Data)
        # So we just return it as is.
        return encrypted_text