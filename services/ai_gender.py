import torch
import librosa
import numpy as np
import os
import logging
import subprocess
from transformers import Wav2Vec2ForSequenceClassification, Wav2Vec2FeatureExtractor

# --- CONFIGURATION ---
REPO_ID = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
CACHE_DIR = os.path.join(os.getcwd(), "model_cache")
EXPECTED_SAMPLE_RATE = 16000

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealHer-Local-AI")

print(f"🧠 AI System Initializing...")
print(f"📂 Model Storage: {CACHE_DIR}")

# --- GLOBAL VARS (Lazy Loading to prevent Crash 137) ---
model = None
feature_extractor = None

def load_ai_model():
    """
    Loads the model only when needed. 
    This prevents the server from crashing during startup.
    """
    global model, feature_extractor
    
    if model is None:
        logger.info("⏳ Loading 1.2GB AI Brain (First Run)...")
        try:
            feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained(
                REPO_ID, 
                cache_dir=CACHE_DIR
            )
            model = Wav2Vec2ForSequenceClassification.from_pretrained(
                REPO_ID, 
                cache_dir=CACHE_DIR
            )
            logger.info("✅ AI Model Loaded Successfully!")
        except Exception as e:
            logger.error(f"❌ CRITICAL AI LOAD ERROR: {e}")
            return None, None
            
    return model, feature_extractor

# --- HELPER 1: AUDIO CLEANER ---
def convert_audio_to_16k(input_path):
    """
    Forces audio to 16kHz Mono using FFMPEG. 
    This prevents the 'Chipmunk' speed bug where 48k audio sounds like a female.
    """
    output_path = input_path.replace(".wav", "_clean.wav")
    
    # Simple ffmpeg command to normalize audio
    command = [
        "ffmpeg", "-y", 
        "-i", input_path, 
        "-ar", "16000",   # Force 16k Hz
        "-ac", "1",       # Force Mono
        output_path
    ]
    
    try:
        # Run ffmpeg silently
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_path
    except Exception as e:
        logger.warning(f"⚠️ FFMPEG Failed, using original file: {e}")
        return input_path

# --- HELPER 2: PHYSICS CHECK ---
def get_voice_pitch(audio_path):
    """
    Returns the average pitch (Hz) of the voice.
    Males: ~85-155Hz
    Females: ~165-255Hz
    """
    try:
        y, sr = librosa.load(audio_path, sr=None)
        # Pitch tracking
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        
        # Filter out background noise
        threshold = np.median(magnitudes)
        pitch_indexes = magnitudes > threshold
        pitch_values = pitches[pitch_indexes]
        
        # Filter strictly for human vocal range (80Hz - 300Hz)
        valid_pitches = pitch_values[(pitch_values > 80) & (pitch_values < 300)]
        
        if len(valid_pitches) == 0:
            return 0
            
        return float(np.mean(valid_pitches))
    except Exception:
        return 0

# --- MAIN ANALYSIS FUNCTION ---
def analyze_audio(file_path: str):
    """
    The Double-Lock Analysis:
    1. AI Model Check (Pattern Recognition)
    2. Physics Check (Pitch Frequency)
    """
    
    # 1. Clean the Audio (Fix Speed/Pitch bugs)
    clean_path = convert_audio_to_16k(file_path)
    
    # 2. Load Model
    curr_model, curr_extractor = load_ai_model()
    
    if not curr_model or not curr_extractor:
        return {"error": "AI Model unavailable."}

    try:
        # 3. AI Prediction
        audio_input, sample_rate = librosa.load(clean_path, sr=EXPECTED_SAMPLE_RATE)
        
        inputs = curr_extractor(
            audio_input, 
            sampling_rate=EXPECTED_SAMPLE_RATE, 
            return_tensors="pt", 
            padding=True
        )

        with torch.no_grad(): 
            logits = curr_model(inputs.input_values).logits

        scores = torch.softmax(logits, dim=1).detach().cpu().numpy()[0]
        
        # Extract Labels
        id2label = curr_model.config.id2label
        predicted_id = torch.argmax(logits, dim=1).item()
        ai_label = id2label[predicted_id].lower()
        ai_confidence = float(scores[predicted_id])

        # 4. PHYSICS CHECK (The Guardrail)
        pitch_hz = get_voice_pitch(clean_path)
        logger.info(f"🔍 Physics Check: Pitch is {pitch_hz:.2f} Hz")
        
        final_decision = ai_label
        final_confidence = ai_confidence

        # --- STRICT RULE ---
        # If AI thinks it's 'female', but the voice is deep (< 165Hz), 
        # we assume the AI made a mistake and BLOCK it.
        if ai_label == "female" and pitch_hz > 0 and pitch_hz < 165:
            logger.warning(f"🛡️ SECURITY OVERRIDE: Deep voice detected ({pitch_hz:.2f}Hz). Blocking as Male.")
            final_decision = "male"
            final_confidence = 1.0 # Physics doesn't lie
            
        return {
            "gender": final_decision,
            "confidence": round(final_confidence, 4),
            "pitch_hz": round(pitch_hz, 2),
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Analysis Failed for {file_path}: {e}")
        return {"error": "Audio processing failed.", "details": str(e)}
    finally:
        # Clean up the temporary clean file
        if clean_path != file_path and os.path.exists(clean_path):
            os.remove(clean_path)