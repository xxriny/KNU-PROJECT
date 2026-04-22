import os
import sys

def setup():
    print("Setting up Prompt Compressor (Phase 3)...")
    
    # 1. Install dependencies
    try:
        import llmlingua
        print("llmlingua already installed.")
    except ImportError:
        print("Installing llmlingua and dependencies...")
        os.system(f"{sys.executable} -m pip install llmlingua torch transformers accelerate")

    # 2. Pre-download the model
    print("Downloading LLMLingua-2 model (this may take a while)...")
    try:
        from llmlingua import PromptCompressor
        # This will trigger the download if not already present
        PromptCompressor(
            model_name="microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank",
            use_llmlingua2=True
        )
        print("Model downloaded and verified.")
    except Exception as e:
        print(f"Error during model setup: {e}")
        sys.exit(1)

    print("\nPhase 3 setup complete! LLMLingua-2 is ready to use.")

if __name__ == "__main__":
    setup()
