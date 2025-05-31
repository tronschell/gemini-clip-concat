import logging
from collections import deque
from typing import List, Dict, Any, Callable, Optional
from pathlib import Path

from .config import Config

logger = logging.getLogger(__name__)

class VideoQueue:
    """Manages video processing tasks in LIFO order for deferred processing."""
    
    def __init__(self, config: Config):
        """
        Initialize the video queue.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.queue = deque()  # LIFO queue using deque
        self.logger = logging.getLogger(__name__)
    
    def add_video(self, video_path: str, game_name: str) -> int:
        """
        Add a video to the processing queue.
        
        Args:
            video_path: Path to the video file to queue
            game_name: Name of the currently running game
            
        Returns:
            Position in queue (1-based index)
        """
        try:
            video_name = Path(video_path).name
            
            # Add to the end of deque (LIFO - last in, first out)
            self.queue.append(video_path)
            position = len(self.queue)
            
            self.logger.info(f"📋 Video queued: {video_name} (position {position}) - {game_name} is running")
            self.logger.info(f"📋 Queue status: {position} video(s) waiting for {game_name} to close")
            
            return position
            
        except Exception as e:
            self.logger.error(f"📋 Error adding video to queue: {str(e)}")
            raise
    
    def process_all_queued(self, processor_callback: Callable[[str], Optional[str]]) -> List[str]:
        """
        Process all queued videos in LIFO order.
        
        Args:
            processor_callback: Function to call for processing each video
            
        Returns:
            List of successful compilation paths
        """
        if not self.queue:
            self.logger.info("📋 No videos in queue to process")
            return []
        
        queue_size = len(self.queue)
        self.logger.info(f"📋 Processing {queue_size} queued video(s) in LIFO order...")
        
        results = []
        processed_count = 0
        
        try:
            # Process in LIFO order (pop from right end)
            while self.queue:
                video_path = self.queue.pop()  # LIFO - last in, first out
                processed_count += 1
                
                try:
                    video_name = Path(video_path).name
                    self.logger.info(f"📋 Processing queued video {processed_count}/{queue_size}: {video_name}")
                    
                    result = processor_callback(video_path)
                    if result:
                        results.append(result)
                        self.logger.info(f"✓ Successfully processed queued video: {video_name}")
                    else:
                        self.logger.warning(f"📋 No compilation created for queued video: {video_name}")
                        
                except Exception as e:
                    video_name = Path(video_path).name if video_path else "unknown"
                    self.logger.error(f"📋 Error processing queued video {video_name}: {str(e)}")
                    continue
            
            self.logger.info(f"📋 Completed processing queue: {len(results)}/{queue_size} videos successful")
            return results
            
        except Exception as e:
            self.logger.error(f"📋 Error processing video queue: {str(e)}")
            return results
    
    def get_queue_status(self) -> Dict[str, Any]:
        """
        Get current queue status information.
        
        Returns:
            Dictionary with queue size and video list
        """
        try:
            video_names = [Path(video_path).name for video_path in self.queue]
            
            return {
                "queue_size": len(self.queue),
                "videos": list(self.queue),  # Full paths
                "video_names": video_names,  # Just filenames
                "is_empty": len(self.queue) == 0
            }
            
        except Exception as e:
            self.logger.error(f"📋 Error getting queue status: {str(e)}")
            return {
                "queue_size": 0,
                "videos": [],
                "video_names": [],
                "is_empty": True
            }
    
    def clear_queue(self) -> int:
        """
        Clear all queued videos.
        
        Returns:
            Number of videos that were cleared
        """
        try:
            cleared_count = len(self.queue)
            
            if cleared_count > 0:
                self.queue.clear()
                self.logger.info(f"📋 Cleared {cleared_count} video(s) from queue")
            else:
                self.logger.info("📋 Queue was already empty")
                
            return cleared_count
            
        except Exception as e:
            self.logger.error(f"📋 Error clearing queue: {str(e)}")
            return 0 