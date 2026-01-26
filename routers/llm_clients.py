import os
import random
from dotenv import load_dotenv
from litellm import acompletion 

load_dotenv()

# === 1. Smart Key Loader ===
def get_key_pool(prefix):
    keys = []
    # Check the main key (e.g., MISTRAL_API_KEY)
    if os.getenv(prefix):
        keys.append(os.getenv(prefix).strip())
    
    # Check rotation keys (e.g., MISTRAL_API_KEY_1 to _20)
    for i in range(1, 21):
        k = os.getenv(f"{prefix}_{i}")
        if k:
            keys.append(k.strip())
            
    # Remove duplicates and empty strings
    return [k for k in list(set(keys)) if k]

# --- LOAD ALL KEYS INTO POOLS ---
MISTRAL_KEYS = get_key_pool("MISTRAL_API_KEY")
COHERE_KEYS = get_key_pool("COHERE_API_KEY")
GROQ_KEYS = get_key_pool("GROQ_API_KEY")
HUGGINGFACE_KEYS = get_key_pool("HUGGINGFACE_API_KEY")
DEEPSEEK_KEYS = get_key_pool("DEEPSEEK_API_KEY")

print(f"🔥 AI Engine Initialized in Global Rotation Mode:")
print(f"   - Tier 1 (Randomized): Mistral, Cohere, Groq")
print(f"   - Tier 2 (Backup): HuggingFace, DeepSeek")

# === 2. The True Load-Balanced Chat Function ===
async def chat_with_ai(messages: list, system_instruction: str = None):
    """
    Args:
        messages: The chat history.
        system_instruction: Optional 'Identity' override.
    """
    
    # --- 1. Prepare Messages ---
    final_messages = messages.copy()
    if system_instruction:
        final_messages.insert(0, {"role": "system", "content": system_instruction})

    # --- 2. Define The Providers (Tier 1) ---
    # We define the "Recipe" for each provider here
    tier_1_providers = [
        {
            "name": "Mistral",
            "model": "mistral/mistral-large-latest",
            "keys": MISTRAL_KEYS
        },
        {
            "name": "Cohere",
            "model": "command-r-08-2024",
            "keys": COHERE_KEYS
        },
        {
            "name": "Groq",
            "model": "groq/llama-3.3-70b-versatile",
            "keys": GROQ_KEYS
        }
    ]

    # --- 3. SHUFFLE THE PROVIDERS (The Magic) ---
    # This ensures that sometimes Groq is 1st, sometimes Mistral is 1st, etc.
    random.shuffle(tier_1_providers)

    # --- 4. Build the Execution List ---
    attempts = []

    # ADD TIER 1 (Randomized Order)
    for provider in tier_1_providers:
        # We also shuffle the keys WITHIN the provider for double randomness
        current_keys = provider["keys"].copy()
        random.shuffle(current_keys)
        
        for key in current_keys:
            attempts.append({
                "model": provider["model"],
                "api_key": key,
                "provider": provider["name"]
            })

    # ADD TIER 2 (Backups - Always at the end)
    # We shuffle their keys too, just in case
    hf_keys = HUGGINGFACE_KEYS.copy()
    random.shuffle(hf_keys)
    for key in hf_keys:
        attempts.append({
            "model": "huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
            "api_key": key,
            "provider": "HuggingFace"
        })

    ds_keys = DEEPSEEK_KEYS.copy()
    random.shuffle(ds_keys)
    for key in ds_keys:
        attempts.append({
            "model": "deepseek/deepseek-chat",
            "api_key": key,
            "provider": "DeepSeek"
        })

    # --- 5. Execute The Loop ---
    last_error = None
    
    for attempt in attempts:
        try:
            # Optional: Debug log to see who won the lottery this time
            # print(f"🎲 Rolling Dice... Selected: {attempt['provider']}")
            
            response = await acompletion(
                model=attempt["model"],
                messages=final_messages,
                api_key=attempt["api_key"],
                temperature=0.7, 
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"⚠️ {attempt['provider']} Key Failed: {e}")
            last_error = e
            continue 

    # --- 6. Total Failure ---
    print(f"❌ CRITICAL: ALL {len(attempts)} AI MODELS FAILED. Last error: {last_error}")
    return "I am currently experiencing high traffic on all neural pathways. Please give me a moment to reconnect."