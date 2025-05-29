"""YouTube Upload Agent using Browser Use and Gemini Flash 2.0."""

import os
import logging
import asyncio
from pathlib import Path
from typing import List, Optional
from tkinter import filedialog, messagebox
import tkinter as tk

from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Controller, ActionResult
from dotenv import load_dotenv

from .browser_manager import BrowserManager

# Load environment variables with proper encoding handling
try:
    load_dotenv(encoding='utf-8')
except UnicodeDecodeError:
    try:
        load_dotenv(encoding='utf-16')
    except:
        # If .env file has issues, continue without it
        pass

logger = logging.getLogger(__name__)


class YouTubeUploadAgent:
    """Agent for uploading videos to YouTube using Browser Use."""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser_manager = BrowserManager()
        self.controller = Controller()
        self._setup_llm()
        self._setup_custom_actions()
        logger.info("Initialized YouTube Upload Agent with Gemini Flash 2.0")
        
    def _setup_llm(self):
        """Setup Gemini Flash 2.0 LLM using LangChain integration."""
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key or api_key == "your_google_api_key_here":
            print("\n❌ Google API Key not configured!")
            print("📝 Please follow these steps:")
            print("1. Go to: https://aistudio.google.com/app/apikey")
            print("2. Sign in with your Google account")
            print("3. Click 'Create API Key'")
            print("4. Copy the generated API key")
            print("5. Edit the .env file and replace 'your_google_api_key_here' with your actual API key")
            print("6. Save the .env file and run the agent again")
            print("\n💡 The .env file should look like:")
            print("GOOGLE_API_KEY=AIzaSyD...your_actual_api_key_here...")
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        # Use LangChain's ChatGoogleGenerativeAI for proper Browser Use integration
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.0-flash',
            temperature=0.0,
            google_api_key=api_key
        )
        logger.info("Initialized Gemini Flash 2.0 via LangChain")
        
    def _setup_custom_actions(self):
        """Setup custom actions for file handling."""
        
        @self.controller.action('Get selected video file paths')
        def get_video_file_paths() -> ActionResult:
            """Return the paths of selected video files for upload."""
            # This will be populated when upload_videos is called
            if hasattr(self, '_selected_video_files'):
                file_info = []
                for file_path in self._selected_video_files:
                    file_path_obj = Path(file_path)
                    size_mb = file_path_obj.stat().st_size / (1024 * 1024)
                    file_info.append(f"{file_path_obj.name} ({size_mb:.1f} MB) - {file_path}")
                
                result = f"Selected video files:\n" + "\n".join(file_info)
                return ActionResult(
                    extracted_content=result,
                    include_in_memory=True,
                    data={"file_paths": self._selected_video_files}
                )
            else:
                return ActionResult(extracted_content="No video files selected yet")
        
        @self.controller.action('Upload file to current page')
        def upload_file_to_page(file_path: str) -> ActionResult:
            """Provide file path for upload to the current page."""
            try:
                if Path(file_path).exists():
                    return ActionResult(
                        extracted_content=f"File ready for upload: {Path(file_path).name}",
                        include_in_memory=True,
                        data={"upload_file_path": file_path}
                    )
                else:
                    return ActionResult(extracted_content=f"File not found: {file_path}")
            except Exception as e:
                return ActionResult(extracted_content=f"Error accessing file: {e}")
    
    async def upload_videos(self, video_files: Optional[List[str]] = None) -> dict:
        """Upload videos to YouTube."""
        try:
            # First, let user select videos via native file explorer
            if not video_files:
                print("📁 Opening file explorer to select videos...")
                video_files = self._select_video_files_native()
                
                if not video_files:
                    return {
                        "success": False,
                        "message": "No videos selected",
                        "details": "User cancelled file selection"
                    }
                
                print(f"✅ Selected {len(video_files)} video(s):")
                for i, file_path in enumerate(video_files, 1):
                    file_size = Path(file_path).stat().st_size / (1024 * 1024)
                    print(f"   {i}. {Path(file_path).name} ({file_size:.1f} MB)")
            
            # Store selected files for custom actions
            self._selected_video_files = video_files
            
            browser_session = self.browser_manager.create_browser_session(self.headless)
            
            # Create file list for the agent with full paths
            file_details = []
            for file_path in video_files:
                file_details.append({
                    "path": file_path,
                    "name": Path(file_path).name,
                    "size_mb": Path(file_path).stat().st_size / (1024 * 1024)
                })
            
            task = f"""
            Upload the following video files to YouTube Studio:
            
            Selected Videos ({len(file_details)} files):
            {chr(10).join([f"- {file['name']} ({file['size_mb']:.1f} MB) at: {file['path']}" for file in file_details])}
            
            Instructions:
            1. Navigate to YouTube Studio (https://studio.youtube.com)
            2. If not logged in, wait for user to log in manually
            3. For EACH video file (upload one at a time):
               a. Click on 'CREATE' button (or '+' icon) 
               b. Click on 'Upload videos'
               c. In the file upload area, either:
                  - Drag and drop the video file from the file path
                  - Click "SELECT FILES" and navigate to the file location
                  - Use the file path: {file_details[0]['path'] if file_details else 'N/A'}
               d. Wait for upload to start and show progress
               e. While uploading, fill in video details:
                  - Title: Use the filename without extension as title
                  - Visibility: For first video, set to 'Public'. For subsequent videos, schedule them:
                    • Video 2+: Schedule 2 hours apart, rounded to next hour
                    • Example: If uploading at 15:45, schedule as:
                      - First video: Public (immediate)
                      - Second video: Scheduled for 18:00
                      - Third video: Scheduled for 20:00
                      And so on...
               f. Click 'Publish' when ready
               g. Wait for processing to complete before starting next video
            
            4. Repeat step 3 for each remaining video file
            5. After all uploads complete, provide a summary with:
               - Total number of videos uploaded successfully
               - Any errors or issues encountered
               - Video URLs or IDs if available
            
            Important Notes:
            - Handle each video upload sequentially (one at a time)
            - Wait for each upload to fully complete before starting the next
            - If any upload fails, note the error and continue with remaining videos
            - Use the 'Get selected video file paths' action if you need the file paths
            """
            
            agent = Agent(
                task=task,
                llm=self.llm,
                browser_session=browser_session,
                controller=self.controller,
            )
            
            logger.info(f"Starting YouTube upload process for {len(video_files)} videos")
            result = await agent.run()
            
            return {
                "success": True,
                "message": f"Upload process completed for {len(video_files)} videos",
                "details": result.extracted_content if hasattr(result, 'extracted_content') else str(result),
                "uploaded_files": [Path(f).name for f in video_files]
            }
            
        except Exception as e:
            logger.error(f"Error during upload: {e}")
            return {
                "success": False,
                "message": f"Upload failed: {e}",
                "details": None
            }
        finally:
            self.browser_manager.cleanup()
    
    def _select_video_files_native(self) -> List[str]:
        """Open native file explorer to select video files."""
        try:
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            root.lift()      # Bring to front
            root.attributes('-topmost', True)  # Keep on top
            
            file_paths = filedialog.askopenfilenames(
                title="Select video files to upload to YouTube",
                filetypes=[
                    ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.3gp *.ogv"),
                    ("MP4 files", "*.mp4"),
                    ("AVI files", "*.avi"),
                    ("MOV files", "*.mov"),
                    ("All files", "*.*")
                ],
                multiple=True
            )
            
            root.destroy()
            return list(file_paths) if file_paths else []
            
        except Exception as e:
            logger.error(f"Error selecting files: {e}")
            print(f"❌ Error opening file dialog: {e}")
            return []
    
    async def login_to_youtube(self) -> dict:
        """Helper method to login to YouTube and save session."""
        try:
            browser_session = self.browser_manager.create_browser_session(headless=False)
            
            task = """
            Navigate to YouTube Studio (https://studio.youtube.com) and help the user log in:
            1. Go to https://studio.youtube.com
            2. If not logged in, click on 'Sign in' 
            3. Wait for user to complete the login process manually, do not fill in any fields or click anything until the user logs in
            4. Once logged in and you can see the YouTube Studio dashboard, confirm login success
            5. The browser session will be saved for future use
            """
            
            agent = Agent(
                task=task,
                llm=self.llm,
                browser_session=browser_session,
            )
            
            logger.info("Starting YouTube login process")
            result = await agent.run()
            
            return {
                "success": True,
                "message": "Login completed and session saved",
                "details": result.extracted_content if hasattr(result, 'extracted_content') else str(result)
            }
            
        except Exception as e:
            logger.error(f"Error during login: {e}")
            return {
                "success": False,
                "message": f"Login failed: {e}",
                "details": None
            }


async def main():
    """Main function for testing the agent."""
    logging.basicConfig(level=logging.INFO)
    
    agent = YouTubeUploadAgent(headless=False)
    
    print("YouTube Upload Agent")
    print("1. Login to YouTube (first time setup)")
    print("2. Upload videos")
    
    choice = input("Enter your choice (1 or 2): ").strip()
    
    if choice == "1":
        result = await agent.login_to_youtube()
        print(f"Login result: {result}")
    elif choice == "2":
        result = await agent.upload_videos()
        print(f"Upload result: {result}")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main()) 