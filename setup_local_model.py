#!/usr/bin/env python3
"""
Setup script for local model configuration.
Helps configure the environment for local LLaMA model usage.
"""

import os
import shutil
from pathlib import Path

def setup_environment():
    """Setup environment file for local model."""
    print("🔧 Setting up environment for local model...")
    
    env_example = Path("env.example")
    env_file = Path(".env")
    
    if not env_file.exists():
        if env_example.exists():
            shutil.copy(env_example, env_file)
            print(f"✅ Created .env file from {env_example}")
        else:
            print("❌ env.example not found!")
            return False
    else:
        print("✅ .env file already exists")
    
    return True

def check_model_file():
    """Check if the LLaMA model file exists."""
    print("\n📁 Checking for LLaMA model file...")
    
    model_path = Path("llama.cpp/models/llama-3.1-8b-q4.gguf")
    
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"✅ Model file found: {model_path}")
        print(f"   Size: {size_mb:.1f} MB")
        return True
    else:
        print(f"❌ Model file not found: {model_path}")
        print("\nTo use this chatbot with local models, you need:")
        print("1. A quantized LLaMA model (GGUF format)")
        print("2. Place it in: llama.cpp/models/llama-3.1-8b-q4.gguf")
        print("\nYou can download models from:")
        print("- Hugging Face: https://huggingface.co/models?library=gguf")
        print("- TheBloke's quantized models")
        return False

def check_dependencies():
    """Check if required dependencies are installed."""
    print("\n📦 Checking dependencies...")
    
    required_packages = [
        "llama-cpp-python",
        "sentence-transformers",
        "langchain",
        "chromadb",
        "vanna"
    ]
    
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def create_directories():
    """Create necessary directories."""
    print("\n📂 Creating directories...")
    
    directories = [
        "data/documents",
        "data/vector_db", 
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ {directory}")
    
    return True

def main():
    """Main setup function."""
    print("🚀 Local Model Setup for Hybrid Chatbot")
    print("=" * 50)
    
    steps = [
        ("Environment Setup", setup_environment),
        ("Model File Check", check_model_file),
        ("Dependencies Check", check_dependencies),
        ("Directory Creation", create_directories)
    ]
    
    all_passed = True
    
    for step_name, step_func in steps:
        print(f"\n{step_name}:")
        print("-" * 30)
        
        try:
            result = step_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ Error in {step_name}: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    print("📊 SETUP SUMMARY")
    print("=" * 50)
    
    if all_passed:
        print("✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your database credentials")
        print("2. Run: python test_local_setup.py")
        print("3. Run: python scripts/train_vanna.py")
        print("4. Run: python scripts/setup_rag.py")
        print("5. Run: python main.py")
    else:
        print("❌ Setup incomplete. Please address the issues above.")
        print("\nCommon solutions:")
        print("- Install dependencies: pip install -r requirements.txt")
        print("- Download a LLaMA model and place it in llama.cpp/models/")
        print("- Ensure you have sufficient RAM (8GB+ for 8B models)")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)


