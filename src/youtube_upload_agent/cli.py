#!/usr/bin/env python3
"""CLI for YouTube Upload Agent."""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from youtube_upload_agent import YouTubeUploadAgent


async def main():
    """Main CLI function."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🎥 YouTube Upload Agent")
    print("=" * 50)
    print("This agent will help you upload videos to YouTube using Browser Use.")
    print("Make sure you have GOOGLE_API_KEY set in your .env file.")
    print()
    
    try:
        agent = YouTubeUploadAgent(headless=False)
        
        print("Options:")
        print("1. Login to YouTube (first time setup)")
        print("2. Upload videos (select files via dialog)")
        print("3. Exit")
        print()
        
        while True:
            choice = input("Enter your choice (1-3): ").strip()
            
            if choice == "1":
                print("\n🔐 Starting YouTube login process...")
                print("The browser will open. Please log in to your YouTube account.")
                result = await agent.login_to_youtube()
                print(f"\n✅ Login result: {result['message']}")
                if not result['success']:
                    print(f"❌ Error: {result['details']}")
                
            elif choice == "2":
                print("\n📤 Starting video upload process...")
                print("A file dialog will open to select your videos.")
                result = await agent.upload_videos()
                print(f"\n✅ Upload result: {result['message']}")
                if not result['success']:
                    print(f"❌ Error: {result['details']}")
                else:
                    print(f"📋 Details: {result['details']}")
                
            elif choice == "3":
                print("\n👋 Goodbye!")
                break
                
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
            
            print("\n" + "=" * 50)
    
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logging.error(f"CLI error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main()) 