#!/usr/bin/env python3
"""Example usage of YouTube Upload Agent."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from youtube_upload_agent import YouTubeUploadAgent


async def example_login():
    """Example: Login to YouTube and save session."""
    print("🔐 Example: Login to YouTube")
    
    agent = YouTubeUploadAgent(headless=False)
    result = await agent.login_to_youtube()
    
    print(f"Result: {result}")
    return result['success']


async def example_upload():
    """Example: Upload videos with file dialog."""
    print("📤 Example: Upload videos")
    
    agent = YouTubeUploadAgent(headless=False)
    result = await agent.upload_videos()
    
    print(f"Result: {result}")
    return result['success']


async def example_upload_specific_files():
    """Example: Upload specific video files."""
    print("📁 Example: Upload specific files")
    
    # Example file paths (replace with your actual video files)
    video_files = [
        "/path/to/your/video1.mp4",
        "/path/to/your/video2.mp4"
    ]
    
    # Check if files exist
    existing_files = [f for f in video_files if Path(f).exists()]
    
    if not existing_files:
        print("❌ No video files found. Please update the file paths in the example.")
        return False
    
    agent = YouTubeUploadAgent(headless=False)
    result = await agent.upload_videos(video_files=existing_files)
    
    print(f"Result: {result}")
    return result['success']


async def main():
    """Main example function."""
    logging.basicConfig(level=logging.INFO)
    
    print("🎥 YouTube Upload Agent Examples")
    print("=" * 50)
    
    examples = {
        "1": ("Login to YouTube", example_login),
        "2": ("Upload videos (file dialog)", example_upload),
        "3": ("Upload specific files", example_upload_specific_files),
    }
    
    print("Available examples:")
    for key, (description, _) in examples.items():
        print(f"{key}. {description}")
    
    choice = input("\nEnter example number (1-3): ").strip()
    
    if choice in examples:
        description, example_func = examples[choice]
        print(f"\n🚀 Running: {description}")
        print("-" * 30)
        
        try:
            success = await example_func()
            if success:
                print("\n✅ Example completed successfully!")
            else:
                print("\n❌ Example failed!")
        except Exception as e:
            print(f"\n💥 Example error: {e}")
            logging.error(f"Example error: {e}", exc_info=True)
    else:
        print("❌ Invalid choice")


if __name__ == "__main__":
    asyncio.run(main()) 