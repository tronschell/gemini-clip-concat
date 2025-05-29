import os
import time
import logging
from pathlib import Path
from typing import Set, Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent

logger = logging.getLogger(__name__)

class VideoFileHandler(FileSystemEventHandler):
    """Handler for video file events."""
    
    def __init__(self, 
                 process_callback: Callable[[str], None],
                 supported_extensions: tuple = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'),
                 ignore_existing_files: Set[str] = None):
        super().__init__()
        self.process_callback = process_callback
        self.supported_extensions = supported_extensions
        self.processing_files: Set[str] = set()
        self.pending_files: Set[str] = set()  # Files waiting for stability
        self.ignored_files: Set[str] = ignore_existing_files or set()  # Files to ignore
        self.last_modified: dict = {}
        
    def is_video_file(self, file_path: str) -> bool:
        """Check if file is a supported video format."""
        return Path(file_path).suffix.lower() in self.supported_extensions
    
    def is_file_stable(self, file_path: str, stability_window: int = 2) -> bool:
        """
        Check if file has stopped being modified (file is stable).
        
        Args:
            file_path: Path to the file
            stability_window: Seconds to wait for file stability
            
        Returns:
            True if file is stable, False otherwise
        """
        try:
            current_mtime = os.path.getmtime(file_path)
            last_mtime = self.last_modified.get(file_path, 0)
            
            # If this is the first time we see this file, record the time and wait
            if file_path not in self.last_modified:
                self.last_modified[file_path] = current_mtime
                logger.debug(f"First time seeing file: {file_path}, waiting for stability")
                return False
            
            # If file has been modified since last check, update timestamp and wait
            if current_mtime != last_mtime:
                self.last_modified[file_path] = current_mtime
                logger.debug(f"File modified: {file_path}, waiting for stability")
                return False
                
            # Check if enough time has passed since last modification
            time_since_modification = time.time() - current_mtime
            is_stable = time_since_modification >= stability_window
            
            if is_stable:
                logger.debug(f"File is stable: {file_path}")
                # Clean up tracking for this file
                self.last_modified.pop(file_path, None)
            else:
                logger.debug(f"File not yet stable: {file_path}, {time_since_modification:.1f}s < {stability_window}s")
            
            return is_stable
            
        except OSError as e:
            logger.debug(f"Error checking file stability for {file_path}: {e}")
            return False
    
    def on_created(self, event):
        """Handle file creation events."""
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            logger.debug(f"File created event: {event.src_path}")
            self._handle_video_file(event.src_path)
    
    def on_modified(self, event):
        """Handle file modification events."""
        if isinstance(event, FileModifiedEvent) and not event.is_directory:
            logger.debug(f"File modified event: {event.src_path}")
            self._handle_video_file(event.src_path)
    
    def _handle_video_file(self, file_path: str):
        """Process a video file if it meets criteria."""
        logger.debug(f"Handling file: {file_path}")
        
        if not self.is_video_file(file_path):
            logger.debug(f"Not a video file: {file_path}")
            return
        
        # Ignore files that existed when watcher started
        if file_path in self.ignored_files:
            logger.debug(f"Ignoring existing file: {file_path}")
            return
        
        logger.debug(f"Video file detected: {file_path}")
        
        # Avoid processing the same file multiple times
        if file_path in self.processing_files:
            logger.debug(f"File already being processed: {file_path}")
            return
            
        # Avoid scheduling multiple stability checks for the same file
        if file_path in self.pending_files:
            logger.debug(f"File already pending stability check: {file_path}")
            return
        
        # Check if file is stable before processing
        if not self.is_file_stable(file_path):
            logger.debug(f"File not stable yet: {file_path}")
            # Add to pending set to prevent duplicate stability checks
            self.pending_files.add(file_path)
            
            # Schedule a retry after a short delay
            import threading
            def retry_after_delay():
                time.sleep(3)  # Wait a bit longer than stability window
                # Remove from pending before retry
                self.pending_files.discard(file_path)
                self._handle_video_file(file_path)
            
            threading.Thread(target=retry_after_delay, daemon=True).start()
            return
        
        # File is stable, proceed with processing
        self.processing_files.add(file_path)
        
        try:
            logger.info(f"New video detected: {Path(file_path).name}")
            self.process_callback(file_path)
        except Exception as e:
            logger.error(f"Error processing video {file_path}: {str(e)}")
        finally:
            # Remove from processing set after completion or error
            self.processing_files.discard(file_path)
            # Also clean up from pending set if it was there
            self.pending_files.discard(file_path)

class FileWatcher:
    """Watch directories for new video files and process them."""
    
    def __init__(self, 
                 watch_directory: str,
                 process_callback: Callable[[str], None],
                 polling_interval: float = 1.0):
        self.watch_directory = Path(watch_directory)
        self.process_callback = process_callback
        self.polling_interval = polling_interval
        self.observer: Optional[Observer] = None
        self.is_watching = False
        
        # Create watch directory if it doesn't exist
        self.watch_directory.mkdir(parents=True, exist_ok=True)
        
    def start_watching(self):
        """Start watching the directory for new video files."""
        if self.is_watching:
            logger.warning("File watcher is already running")
            return
        
        logger.info(f"Starting file watcher on: {self.watch_directory}")
        
        # Get existing video files to ignore
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        existing_files = set()
        
        for ext in video_extensions:
            for video_path in self.watch_directory.rglob(f"*{ext}"):
                existing_files.add(str(video_path))
            for video_path in self.watch_directory.rglob(f"*{ext.upper()}"):
                existing_files.add(str(video_path))
        
        if existing_files:
            logger.debug(f"Ignoring {len(existing_files)} existing files")
        
        # Create event handler with existing files to ignore
        event_handler = VideoFileHandler(self.process_callback, ignore_existing_files=existing_files)
        
        # Create and start observer
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.watch_directory), recursive=True)
        self.observer.start()
        self.is_watching = True
        
        logger.info("✓ File watcher started successfully")
    
    def stop_watching(self):
        """Stop watching the directory."""
        if not self.is_watching or not self.observer:
            return
        
        logger.info("Stopping file watcher...")
        self.observer.stop()
        self.observer.join()
        self.is_watching = False
        logger.info("✓ File watcher stopped")
    
    def watch_and_wait(self):
        """Start watching and wait indefinitely (blocking)."""
        self.start_watching()
        
        try:
            while self.is_watching:
                time.sleep(self.polling_interval)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.stop_watching()
    
    def process_existing_files(self):
        """Process any existing video files in the watch directory."""
        logger.info(f"Scanning for existing videos in: {self.watch_directory}")
        
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        existing_videos = []
        
        for ext in video_extensions:
            existing_videos.extend(self.watch_directory.rglob(f"*{ext}"))
            existing_videos.extend(self.watch_directory.rglob(f"*{ext.upper()}"))
        
        if existing_videos:
            logger.info(f"Found {len(existing_videos)} existing video(s)")
            for video_path in existing_videos:
                try:
                    self.process_callback(str(video_path))
                except Exception as e:
                    logger.error(f"Error processing existing video {video_path}: {str(e)}")
        else:
            logger.info("No existing videos found")
    
    def __enter__(self):
        """Context manager entry."""
        self.start_watching()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_watching() 