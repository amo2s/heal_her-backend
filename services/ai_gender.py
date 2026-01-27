import requests
import os
import logging
import json
import time

# --- CONFIGURATION ---
# We use the Inference API URL for the exact same model
API_URL = "https://api-inference.huggingface.co/models/alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealHer-AI-Cloud")

# Load your existing keys from environment variables
raw_keys = [
    os.getenv("HUGGINGFACE_API_KEY"),
    os.getenv("HUGGINGFACE_API_KEY_1"),
    os.getenv("HUGGINGFACE_API_KEY_2")
]
# Clean up keys (remove empty ones and whitespace)
HF_KEYS = [k.strip() for k in raw_keys if k]

if not HF_KEYS:
    logger.error("⚠️ CRITICAL: No HUGGINGFACE_API_KEY found! Voice verification will fail.")

def analyze_audio(file_path: str):
    """
    Serverless Analysis: Sends audio to Hugging Face API.
    Returns: {'gender': 'female', 'confidence': 0.98, 'status': 'success'}
    """
    if not HF_KEYS:
        return {"error": "Server misconfiguration: No AI Keys."}

    # 1. Read the audio file from disk
    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except Exception as e:
        return {"error": f"Could not read file: {str(e)}"}

    # 2. Try Keys (Failover System)
    last_error = None
    
    for key in HF_KEYS:
        headers = {"Authorization": f"Bearer {key}"}
        
        try:
            logger.info(f"☁️ Sending audio to AI Cloud...")
            response = requests.post(API_URL, headers=headers, data=data)
            
            # Case A: Model is Loading (503 Error)
            # Hugging Face puts free models to sleep. We must wait for it to wake up.
            if response.status_code == 503:
                error_data = response.json()
                estimated_time = error_data.get("estimated_time", 20)
                logger.info(f"💤 AI is sleeping. Waking up... (Wait {estimated_time}s)")
                
                # Wait for the model to load
                time.sleep(estimated_time)
                
                # Retry the request with the same key
                logger.info("🔄 Retrying request...")
                response = requests.post(API_URL, headers=headers, data=data)

            # Check for other errors
            if response.status_code != 200:
                logger.warning(f"⚠️ API Error {response.status_code}: {response.text}")
                continue # Try next key

            # Case B: Success
            result = response.json()
            
            # The API returns a list of dicts: 
            # [{'label': 'female', 'score': 0.99}, {'label': 'male', 'score': 0.01}]
            
            # Sort by score (highest confidence first)
            top_result = sorted(result, key=lambda x: x['score'], reverse=True)[0]
            
            predicted_label = top_result['label'] # 'female' or 'male'
            confidence = top_result['score']
            
            return {
                "gender": predicted_label.lower(),
                "confidence": round(confidence, 4),
                "status": "success"
            }

        except Exception as e:
            last_error = e
            logger.error(f"❌ Key failed: {e}")
            continue

    # If all keys fail
    return {"error": "AI Cloud busy or unreachable.", "details": str(last_error)}