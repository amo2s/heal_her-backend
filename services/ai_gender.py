import torch
import librosa
import numpy as np
import os
import logging
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor

# --- CONFIGURATION ---
# 1. The Online Address (Where to download from)
REPO_ID = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"

# 2. The Local Address (Where to save it on your 16GB Server)
# We will save it in a folder named 'model_cache' right next to this script
CACHE_DIR = os.path.join(os.getcwd(), "model_cache")

EXPECTED_SAMPLE_RATE = 16000

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealHer-Local-AI")

print(f"🧠 AI System Initializing...")
print(f"📂 Model Storage: {CACHE_DIR}")

# --- GLOBAL MODEL LOADER ---
# We load this ONCE when the server starts. 
# It stays in your 16GB RAM for instant predictions.
try:
    logger.info("⏳ Checking for model files...")
    
    # 1. Load the "Ears" (Feature Extractor)
    # The 'cache_dir' parameter tells it: "Check this folder. If empty, download from Hugging Face."
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
        REPO_ID, 
        cache_dir=CACHE_DIR
    )

    # 2. Load the "Brain" (Classification Model)
    logger.info("⏳ Loading 1.2GB AI Brain (This might take time on first run)...")
    model = Wav2Vec2ForSequenceClassification.from_pretrained(
        REPO_ID, 
        cache_dir=CACHE_DIR
    )
    
    logger.info("✅ AI Model Loaded Successfully! Running locally on server.")

except Exception as e:
    logger.error(f"❌ CRITICAL AI LOAD ERROR: {e}")
    # We don't crash the app, but verification will fail until fixed.
    model = None
    feature_extractor = None


def analyze_audio(file_path: str):
    """
    Local High-Performance Analysis.
    Uses your server's RAM and CPU. No API limits.
    """
    # 1. Safety Check
    if not model or not feature_extractor:
        return {"error": "AI Model failed to load at startup. Check server logs."}

    try:
        # 2. Load Audio & Resample
        # Librosa uses ffmpeg (ensure static_ffmpeg is working in main.py)
        audio_input, sample_rate = librosa.load(file_path, sr=EXPECTED_SAMPLE_RATE)

        # 3. Pre-processing
        inputs = feature_extractor(
            audio_input, 
            sampling_rate=EXPECTED_SAMPLE_RATE, 
            return_tensors="pt", 
            padding=True
        )

        # 4. Prediction (Inference)
        with torch.no_grad(): 
            logits = model(inputs.input_values).logits

        # 5. Math: Logits -> Probabilities
        scores = torch.softmax(logits, dim=1).detach().cpu().numpy()[0]
        
        # 6. Extract Result
        id2label = model.config.id2label
        predicted_id = torch.argmax(logits, dim=1).item()
        predicted_label = id2label[predicted_id]
        confidence = float(scores[predicted_id])

        return {
            "gender": predicted_label.lower(),      # 'female' or 'male'
            "confidence": round(confidence, 4),     # 0.9845
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Analysis Failed for {file_path}: {e}")
        return {"error": "Audio processing failed.", "details": str(e)}