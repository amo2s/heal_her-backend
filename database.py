import os
import socket  # <--- NEW IMPORT
from supabase import create_client, Client
from dotenv import load_dotenv

# --- NETWORK FIX ---
# Increase default timeout to 60 seconds to handle slow public Wi-Fi (Library/Cafe)
# This prevents the "SSL Handshake Timed Out" error.
socket.setdefaulttimeout(60)

# Load environment variables from .env file
load_dotenv()

# Get keys securely
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_ANON_KEY")

# Safety Check: Stop the server immediately if keys are missing
if not url or not key:
    raise ValueError("❌ API Keys missing! Check your .env file for SUPABASE_URL and SUPABASE_ANON_KEY.")

# THE FIX: Ensure the URL always has a trailing slash for the Storage SDK
if not url.endswith("/"):
    url += "/"

# Initialize Supabase once
supabase: Client = create_client(url, key)