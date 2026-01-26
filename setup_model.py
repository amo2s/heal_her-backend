import os
from huggingface_hub import snapshot_download

# --- CONFIGURATION ---
REPO_ID = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"
LOCAL_DIR = "./model_cache"

def download_model():
    print(f"🚀 Starting download for: {REPO_ID}")
    print("📦 Size: ~1.26GB. This supports resume functionality.")

    try:
        path = snapshot_download(
            repo_id=REPO_ID,
            local_dir=LOCAL_DIR,
            local_dir_use_symlinks=False,  # Downloads actual files, not symlinks
            resume_download=True,          # key: allows resuming interrupted downloads
            etag_timeout=6000              # 10 minute timeout for bad connections
        )
        print(f"\n✅ Download Complete! Model saved to: {os.path.abspath(path)}")
        print("👉 You can now run your FastAPI server.")

    except Exception as e:
        print(f"\n❌ Download Error: {e}")
        print("💡 Tip: Your internet might have dropped. Run this script again to resume.")

if __name__ == "__main__":
    download_model()