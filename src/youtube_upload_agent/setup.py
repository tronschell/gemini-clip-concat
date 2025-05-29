#!/usr/bin/env python3
"""Setup script for YouTube Upload Agent."""

import os
import subprocess
import sys
from pathlib import Path


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        print(f"Error output: {e.stderr}")
        return False


def check_env_file():
    """Check if .env file exists and has required variables."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("⚠️  .env file not found")
        print("Creating .env file template...")
        
        env_content = """# Google API Key for Gemini Flash 2.0
# Get your API key from: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_google_api_key_here
"""
        env_file.write_text(env_content)
        print("✅ Created .env file template")
        print("📝 Please edit .env and add your Google API key")
        return False
    
    # Check if API key is set
    env_content = env_file.read_text()
    if "your_google_api_key_here" in env_content:
        print("⚠️  Please update your GOOGLE_API_KEY in .env file")
        return False
    
    print("✅ .env file looks good")
    return True


def main():
    """Main setup function."""
    print("🎥 YouTube Upload Agent Setup")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("❌ Python 3.9 or higher is required for google-genai")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Install dependencies
    commands = [
        ("pip install browser-use playwright langchain-google-genai python-dotenv", 
         "Installing Python dependencies"),
        ("playwright install chromium", 
         "Installing Playwright browser"),
    ]
    
    for command, description in commands:
        if not run_command(command, description):
            print(f"❌ Setup failed at: {description}")
            return False
    
    # Check .env file
    env_ok = check_env_file()
    
    print("\n" + "=" * 50)
    if env_ok:
        print("🎉 Setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Run: python src/youtube_upload_agent/cli.py")
        print("2. Choose option 1 to login to YouTube")
        print("3. Choose option 2 to upload videos")
    else:
        print("⚠️  Setup completed with warnings")
        print("\n📋 Next steps:")
        print("1. Edit .env file and add your Google API key")
        print("2. Get API key from: https://aistudio.google.com/app/apikey")
        print("3. Run: python src/youtube_upload_agent/cli.py")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 