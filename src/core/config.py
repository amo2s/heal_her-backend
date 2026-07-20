from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    CENTRAL VAULT CONFIGURATION
    Handles all environment variables with strict validation.
    """

    # --- DATABASE & INFRASTRUCTURE ---
    DATABASE_URL: str 
    REDIS_URL: str

    # --- SUPABASE API (For SDK/Service Role) ---
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # --- AUTHENTICATION & SECURITY (DUAL-DOMAIN) ---
    ALGORITHM: str = "HS256"
    
    # Standard Dashboard Secret
    JWT_SECRET_KEY: str
    
    # THE EXTREMIST UPGRADE: Dedicated Management Secret
    MANAGEMENT_JWT_SECRET_KEY: str 
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Argon2 Ghost Protocol Hash
    # (Generate one using: pwd_context.hash("any_password"))
    DUMMY_PASSWORD_HASH: str

    # --- ENCRYPTION ENGINE (CRITICAL) ---
    # This key is used for Application-Level Encryption of chat logs.
    # It must be a 32-byte url-safe base64-encoded string.
    MESSAGE_ENCRYPTION_KEY: str

    # --- CRYPTOGRAPHIC SIGNATURE ENGINE ---
    SIGNING_CERT_PATH: str
    SIGNING_KEY_PATH: str
    SIGNING_KEY_PASSPHRASE: str

    # --- FRONTEND INTEGRATION ---
    # This must match the secret sent in the 'x-healher-handshake' header
    FRONTEND_HANDSHAKE_SECRET: str

    # --- EXTERNAL SERVICES ---
    # Secure webhook URL for the Google Apps Script email engine
    GOOGLE_MAILER_WEBHOOK_URL: str

    # --- APP CONFIGURATION ---
    DEBUG: bool = False
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        # We ignore extra fields so your .env can have dynamic AI keys 
        # (like COHERE_API_KEY_1) without needing to define every single one here.
        extra="ignore" 
    )

# Create the singleton instance to be used throughout the app
settings = Settings()