import json
import os
import logging
from typing import Dict, Any, Literal

logger = logging.getLogger(__name__)

# Define valid game types for typing
GameType = Literal["cs2", "overwatch2", "the_finals", "league_of_legends", "custom", "kills", "splitgate2"]

class Config:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        # Adjust path to config.json, assuming it's in the parent directory of src
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
        try:
            with open(config_path, 'r') as f:
                self._config = json.load(f)
            logger.info("Successfully loaded configuration from config.json")
        except FileNotFoundError:
            logger.warning("config.json not found, using default values")
            self._config = {
                "batch_size": 25,
                "model_name": "gemini-2.5-flash-preview-04-17",
                "max_retries": 10,
                "retry_delay_seconds": 2,
                "min_highlight_duration_seconds": 10,
                "username": "i have no enemies",
                "temperature": 1.0,
                "use_caching": False,
                "cache_ttl_seconds": 3600,
                "game_type": "cs2",
                "max_zero_highlight_retries": 3,
                "make_short": False,
                "shorts": {
                    "no_webcam": False,
                    "add_subtitles": False
                },
                "folder_watcher": {
                    "watch_directory": "./videos",
                    "polling_interval_seconds": 30,
                    "process_immediately": True,
                    "reprocess_analyzed_videos": False
                }
            }
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing config.json: {e}")
            raise

    @property
    def batch_size(self) -> int:
        return self._config.get("batch_size", 25)

    @property
    def model_name(self) -> str:
        return self._config.get("model_name", "gemini-2.5-flash-preview-04-17")

    @property
    def max_retries(self) -> int:
        return self._config.get("max_retries", 10)

    @property
    def retry_delay_seconds(self) -> int:
        return self._config.get("retry_delay_seconds", 2)

    @property
    def min_highlight_duration_seconds(self) -> int:
        return self._config.get("min_highlight_duration_seconds", 10)

    @property
    def username(self) -> str:
        return self._config.get("username", "i have no enemies")
        
    @property
    def temperature(self) -> float:
        return self._config.get("temperature", 1.0)

    @property
    def use_caching(self) -> bool:
        return self._config.get("use_caching", True)

    @property
    def cache_ttl_seconds(self) -> int:
        return self._config.get("cache_ttl_seconds", 3600)
    
    @property
    def game_type(self) -> GameType:
        """
        Get the game type for prompt selection.
        
        Returns:
            The game type as a string (cs2, overwatch2, the_finals, league_of_legends, custom)
        """
        return self._config.get("game_type", "cs2") 
        
    @property
    def watch_directory(self) -> str:
        """Directory to watch for new video files"""
        watcher_config = self._config.get("folder_watcher", {})
        return watcher_config.get("watch_directory", "./videos")
        
    @property
    def polling_interval_seconds(self) -> int:
        """How often to check for new files in seconds"""
        watcher_config = self._config.get("folder_watcher", {})
        return watcher_config.get("polling_interval_seconds", 30)
        
    @property
    def process_immediately(self) -> bool:
        """Whether to process videos immediately when detected"""
        watcher_config = self._config.get("folder_watcher", {})
        return watcher_config.get("process_immediately", True)
        
    @property
    def reprocess_analyzed_videos(self) -> bool:
        """Whether to reprocess videos that have already been analyzed"""
        watcher_config = self._config.get("folder_watcher", {})
        return watcher_config.get("reprocess_analyzed_videos", False)
        
    @property
    def max_zero_highlight_retries(self) -> int:
        """Maximum number of retries when zero highlights are found"""
        return self._config.get("max_zero_highlight_retries", 3)
    
    @property
    def make_short(self) -> bool:
        """Whether to automatically create shorts from kill compilations."""
        return self._config.get("make_short", False)
    
    @property
    def shorts_no_webcam(self) -> bool:
        """Whether to create shorts without webcam overlay."""
        shorts_config = self._config.get("shorts", {})
        return shorts_config.get("no_webcam", False)
    
    @property
    def shorts_add_subtitles(self) -> bool:
        """Whether to add subtitles to shorts."""
        shorts_config = self._config.get("shorts", {})
        return shorts_config.get("add_subtitles", False)
    
    @property
    def shorts(self) -> Dict[str, Any]:
        """Get the shorts configuration dictionary."""
        return self._config.get("shorts", {
            "no_webcam": False,
            "add_subtitles": False
        })
    
    @property
    def queue_when_gaming(self) -> bool:
        """
        Whether to queue video processing when a game is running.
        
        When enabled, videos will be queued instead of processed immediately
        if a game process is detected. Queued videos are processed in LIFO
        order when the game closes.
        
        Returns:
            True if videos should be queued during gaming, False otherwise
        """
        return self._config.get("queue_when_gaming", False) 