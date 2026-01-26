import torch
import librosa
import numpy as np
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor
import logging

# --- CONFIGURATION ---
# CHANGED: We now point to the online Repo ID instead of a local folder.
MODEL_PATH = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
EXPECTED_SAMPLE_RATE = 16000

# Setup cleaner logging for production feel
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealHer-AI")

print(f"⏳ Loading AI Brain from: {MODEL_PATH}")
print("   (Note: First run will take a moment to download the model)")

try:
    # 1. Load Feature Extractor (Sound Only)
    # This downloads the configuration from Hugging Face automatically
    feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(MODEL_PATH)
    
    # 2. Load the Classification Model
    # This downloads the 1.2GB weights from Hugging Face automatically
    model = Wav2Vec2ForSequenceClassification.from_pretrained(MODEL_PATH)
    
    logger.info("✅ AI Model Loaded Successfully! System is ready.")

except OSError as e:
    logger.error(f"❌ CRITICAL: Could not connect to Hugging Face or find model: {MODEL_PATH}.")
    logger.error(f"Details: {e}")
    model = None
    feature_extractor = None
except Exception as e:
    logger.error(f"❌ CRITICAL: Unknown AI Error: {e}")
    model = None
    feature_extractor = None

def analyze_audio(file_path: str):
    """
    Production-ready audio analysis.
    Returns: Dictionary with 'gender', 'confidence', and 'raw_scores'.
    """
    # 1. Safety Check: Is the model actually loaded?
    if not model or not feature_extractor:
        logger.error("Attempted analysis with no model loaded.")
        return {"error": "AI Service Unavailable. Contact Admin."}

    try:
        # 2. Load Audio & Resample
        # 'sr=16000' is mandatory. If the user uploads 44.1kHz, this fixes it instantly.
        audio_input, sample_rate = librosa.load(file_path, sr=EXPECTED_SAMPLE_RATE)

        # 3. Pre-processing (The "Ears")
        # converts raw sound into the tensor format the model expects
        inputs = feature_extractor(
            audio_input, 
            sampling_rate=EXPECTED_SAMPLE_RATE, 
            return_tensors="pt", 
            padding=True
        )

        # 4. Prediction (The "Brain")
        # Disable gradient calculation for speed & memory
        with torch.no_grad(): 
            logits = model(inputs.input_values).logits

        # 5. Math: Convert Logits to Probabilities (0.0 to 1.0)
        scores = torch.softmax(logits, dim=1).detach().cpu().numpy()[0]
        
        # 6. Label Extraction
        # The model config contains the map: {0: 'female', 1: 'male', ...}
        id2label = model.config.id2label
        predicted_id = torch.argmax(logits, dim=1).item()
        predicted_label = id2label[predicted_id]
        confidence = float(scores[predicted_id])

        # 7. Return Clean Data
        return {
            "gender": predicted_label,      # e.g., "female"
            "confidence": round(confidence, 4), # e.g., 0.9845
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Analysis Failed for file {file_path}: {e}")
        return {"error": "Audio processing failed. File might be corrupt.", "details": str(e)}