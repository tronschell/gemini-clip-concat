"""Browser manager for persistent YouTube sessions."""

import os
import logging
from pathlib import Path
from browser_use import BrowserSession, BrowserProfile

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages browser sessions with persistent cookies for YouTube."""
    
    def __init__(self, profile_name: str = "youtube_uploader"):
        self.profile_name = profile_name
        self.profile_dir = Path.home() / ".config" / "browseruse" / "profiles" / profile_name
        self.cookies_file = self.profile_dir / "cookies.json"
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
    def create_browser_session(self, headless: bool = False) -> BrowserSession:
        """Create a browser session with persistent cookies."""
        browser_profile = BrowserProfile(
            headless=headless,
            user_data_dir=str(self.profile_dir),
            cookies_file=str(self.cookies_file) if self.cookies_file.exists() else None,
            viewport={"width": 1280, "height": 720},
            locale='en-US',
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            allowed_domains=['*.youtube.com', '*.google.com', '*.googleapis.com'],
            keep_alive=True,
            accept_downloads=True,
        )
        
        browser_session = BrowserSession(
            browser_profile=browser_profile,
            keep_alive=True,
        )
        
        logger.info(f"Created browser session with profile: {self.profile_name}")
        return browser_session
    
    def cleanup(self):
        """Clean up browser resources."""
        logger.info("Browser cleanup completed") 