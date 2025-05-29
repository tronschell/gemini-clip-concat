import os
import asyncio
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from utils.config import Config
from utils.video_analysis import analyze_video
from utils.video_processor import VideoProcessor
from utils.file_watcher import FileWatcher
from utils.logging_config import setup_logging
from utils.delete_files import FileDeleter
from utils.file_selector import FileSelector
from utils.process_monitor import GameProcessMonitor

logger = logging.getLogger(__name__)

class KillProcessor:
    """Main processor for analyzing videos and creating kill compilations."""
    
    def __init__(self):
        self.config = Config()
        self.video_processor = VideoProcessor(output_dir="exported_videos")
        self.processed_videos: set = set()
        self.process_monitor: Optional[GameProcessMonitor] = None
        
        # Setup logging
        setup_logging()
        
        # Ensure output directories exist
        Path("exported_metadata").mkdir(exist_ok=True)
        Path("exported_videos").mkdir(exist_ok=True)
    
    def cleanup_uploaded_files(self) -> bool:
        """
        Clean up all uploaded files from Gemini's Files API.
        
        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            import dotenv
            dotenv.load_dotenv()
            api_key = os.getenv("GOOGLE_API_KEY")
            
            if not api_key:
                logger.warning("GOOGLE_API_KEY not found, skipping file cleanup")
                return False
            
            logger.info("Cleaning up uploaded files from Gemini Files API...")
            file_deleter = FileDeleter(api_key=api_key)
            file_deleter.delete_all_files()
            logger.info("✓ File cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"Error during file cleanup: {str(e)}")
            return False
    
    def is_video_already_analyzed(self, video_path: str, output_file: str = "exported_metadata/kills.json") -> bool:
        """
        Check if a video has already been analyzed by looking in the kills.json file.
        
        Args:
            video_path: Path to the video file to check
            output_file: Path to the JSON file containing previous analyses
            
        Returns:
            True if video was already analyzed, False otherwise
        """
        if not os.path.exists(output_file):
            return False
        
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
            
            # Check if any highlights exist for this video
            if "highlights" in data:
                video_filename = Path(video_path).name
                for highlight in data["highlights"]:
                    source_filename = Path(highlight.get("source_video", "")).name
                    if source_filename == video_filename:
                        logger.debug(f"Video {video_filename} already analyzed (found in {output_file})")
                        return True
                        
            return False
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error reading {output_file}: {e}")
            return False
    
    async def process_single_video(self, video_path: str) -> Optional[str]:
        """
        Process a single video to find kills and create compilation.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Path to the created compilation video or None if no kills found
        """
        try:
            # Skip if already processed (unless reprocessing is enabled)
            if not self.config.reprocess_analyzed_videos and video_path in self.processed_videos:
                logger.info(f"Skipping already processed video: {Path(video_path).name}")
                return None
            
            # Check if video was already analyzed in kills.json
            if not self.config.reprocess_analyzed_videos and self.is_video_already_analyzed(video_path):
                logger.info(f"Skipping already analyzed video: {Path(video_path).name}")
                self.processed_videos.add(video_path)
                return None
            
            logger.info(f"Processing video: {Path(video_path).name}")
            
            # Retry logic for zero highlights
            max_retries = self.config.max_zero_highlight_retries
            retry_count = 0
            highlights = None
            
            while retry_count <= max_retries:
                try:
                    # Analyze video using kills prompt
                    highlights, token_usage = await analyze_video(
                        video_path=video_path,
                        output_file="exported_metadata/kills.json"
                    )
                    
                    # If we got highlights, break out of retry loop
                    if highlights:
                        break
                        
                    # If no highlights and we have retries left
                    if retry_count < max_retries:
                        retry_count += 1
                        logger.info(f"No highlights found in {Path(video_path).name}, retrying ({retry_count}/{max_retries})")
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    else:
                        logger.info(f"No highlights found in {Path(video_path).name} after {max_retries} retries")
                        
                except Exception as e:
                    logger.error(f"Error analyzing video {video_path} (attempt {retry_count + 1}): {str(e)}")
                    if retry_count < max_retries:
                        retry_count += 1
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    else:
                        raise
            
            if not highlights:
                logger.info(f"No kills found in {Path(video_path).name}")
                self.processed_videos.add(video_path)
                return None
            
            logger.info(f"Found {len(highlights)} kill(s) in {Path(video_path).name}")
            
            # Process video to create compilation
            compilation_path = self.video_processor.process_video_highlights(video_path, highlights)
            
            if compilation_path:
                logger.info(f"✓ Created kill compilation: {Path(compilation_path).name}")
                self.processed_videos.add(video_path)
                return compilation_path
            else:
                logger.error(f"Failed to create compilation for {Path(video_path).name}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
            return None
    
    def process_single_video_sync(self, video_path: str) -> Optional[str]:
        """Synchronous wrapper for process_single_video."""
        result = asyncio.run(self.process_single_video(video_path))
        
        # Clean up uploaded files after single video processing
        if result:  # Only cleanup if processing was successful
            self.cleanup_uploaded_files()
            
        return result
    
    async def process_multiple_videos(self, video_paths: List[str]) -> List[str]:
        """
        Process multiple videos concurrently.
        
        Args:
            video_paths: List of paths to video files
            
        Returns:
            List of paths to created compilation videos
        """
        if not video_paths:
            logger.warning("No videos to process")
            return []
        
        logger.info(f"Processing {len(video_paths)} video(s)")
        
        # Process videos in batches based on config
        batch_size = self.config.batch_size
        results = []
        
        for i in range(0, len(video_paths), batch_size):
            batch = video_paths[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} videos)")
            
            # Process batch concurrently
            batch_results = await asyncio.gather(
                *(self.process_single_video(video_path) for video_path in batch),
                return_exceptions=True
            )
            
            # Filter successful results
            for result in batch_results:
                if isinstance(result, str):  # Successful compilation path
                    results.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Batch processing error: {str(result)}")
        
        logger.info(f"✓ Successfully processed {len(results)} video(s)")
        
        # Clean up uploaded files after batch processing
        if results:  # Only cleanup if we processed any videos
            self.cleanup_uploaded_files()
        
        return results
    
    def start_watching(self, watch_directory: Optional[str] = None, ignore_existing: bool = False):
        """
        Start watching a directory for new video files.
        
        Args:
            watch_directory: Directory to watch (uses config default if not provided)
            ignore_existing: If True, ignore existing files and only process new ones
        """
        if not watch_directory:
            watch_directory = self.config.watch_directory
        
        logger.info(f"Starting kill processor file watcher on: {watch_directory}")
        
        # Initialize and start process monitor for automatic game detection
        try:
            self.process_monitor = GameProcessMonitor(self.config, check_interval=3.0)
            self.process_monitor.start_monitoring()
            logger.info("🔍 Automatic game detection enabled - will switch configs based on running games")
        except Exception as e:
            logger.warning(f"Failed to start process monitor: {str(e)}")
            logger.warning("Continuing without automatic game detection")
            self.process_monitor = None
        
        # Log initial game type
        logger.info(f"🎮 Current game configuration: '{self.config.game_type}'")
        
        # Create file watcher
        watcher = FileWatcher(
            watch_directory=watch_directory,
            process_callback=self.process_single_video_sync,
            polling_interval=self.config.polling_interval_seconds
        )
        
        # Process existing files if enabled and not ignoring existing files
        if self.config.process_immediately and not ignore_existing:
            logger.info("Processing existing videos in watch directory...")
            watcher.process_existing_files()
        elif ignore_existing:
            logger.info("Ignoring existing files - only new files will be processed")
        
        # Start watching for new files
        logger.info("Watching for new video files... (Press Ctrl+C to stop)")
        
        try:
            watcher.watch_and_wait()
        finally:
            # Clean up process monitor when watch mode ends
            if self.process_monitor:
                self.process_monitor.stop_monitoring()
    
    def process_directory(self, directory_path: str) -> List[str]:
        """
        Process all video files in a directory.
        
        Args:
            directory_path: Path to directory containing videos
            
        Returns:
            List of paths to created compilation videos
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        # Find all video files
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')
        video_files = []
        
        for ext in video_extensions:
            video_files.extend(directory.rglob(f"*{ext}"))
            video_files.extend(directory.rglob(f"*{ext.upper()}"))
        
        if not video_files:
            logger.warning(f"No video files found in {directory_path}")
            return []
        
        logger.info(f"Found {len(video_files)} video file(s) in {directory_path}")
        
        # Convert to string paths
        video_paths = [str(video_file) for video_file in video_files]
        
        # Process videos
        results = asyncio.run(self.process_multiple_videos(video_paths))
        
        # Note: cleanup is already handled in process_multiple_videos
        return results
    
    def create_config_template(self, config_path: str = "config.json"):
        """Create a config template for kill processing."""
        template_config = {
            "batch_size": 5,
            "model_name": "gemini-2.5-flash-preview-04-17",
            "max_retries": 10,
            "retry_delay_seconds": 2,
            "min_highlight_duration_seconds": 5,
            "username": "your_username_here",
            "temperature": 1.0,
            "use_caching": True,
            "cache_ttl_seconds": 3600,
            "game_type": "kills",
            "max_zero_highlight_retries": 3,
            "make_short": False,
            "shorts": {
                "no_webcam": False,
                "add_subtitles": False
            },
            "folder_watcher": {
                "watch_directory": "./videos",
                "polling_interval_seconds": 2,
                "process_immediately": True,
                "reprocess_analyzed_videos": False
            }
        }
        
        import json
        with open(config_path, 'w') as f:
            json.dump(template_config, f, indent=2)
        
        logger.info(f"Created config template at: {config_path}")
        logger.info("Please update the 'username' field and adjust other settings as needed.")
    
    def get_existing_highlights(self, video_path: str, output_file: str = "exported_metadata/kills.json") -> List[Dict[str, Any]]:
        """
        Get existing highlights for a video from the JSON file.
        
        Args:
            video_path: Path to the video file
            output_file: Path to the JSON file containing previous analyses
            
        Returns:
            List of highlight dictionaries for the video
        """
        if not os.path.exists(output_file):
            return []
        
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
            
            if "highlights" in data:
                video_filename = Path(video_path).name
                video_highlights = []
                for highlight in data["highlights"]:
                    source_filename = Path(highlight.get("source_video", "")).name
                    if source_filename == video_filename:
                        video_highlights.append(highlight)
                return video_highlights
                        
            return []
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error reading {output_file}: {e}")
            return []
    
    def remove_video_from_analysis(self, video_path: str, output_file: str = "exported_metadata/kills.json") -> bool:
        """
        Remove all highlights for a specific video from the JSON file.
        
        Args:
            video_path: Path to the video file
            output_file: Path to the JSON file containing previous analyses
            
        Returns:
            True if removal was successful, False otherwise
        """
        if not os.path.exists(output_file):
            return True  # Nothing to remove
        
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
            
            if "highlights" in data:
                video_filename = Path(video_path).name
                original_count = len(data["highlights"])
                
                # Filter out highlights for this video
                data["highlights"] = [
                    highlight for highlight in data["highlights"]
                    if Path(highlight.get("source_video", "")).name != video_filename
                ]
                
                removed_count = original_count - len(data["highlights"])
                
                # Write back to file
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                if removed_count > 0:
                    logger.info(f"Removed {removed_count} highlight(s) for {video_filename} from {output_file}")
                
                return True
            
            return True
            
        except (json.JSONDecodeError, KeyError, IOError) as e:
            logger.error(f"Error removing video from analysis file {output_file}: {e}")
            return False
    
    def process_selected_videos_loop(self) -> List[str]:
        """
        Allow user to manually select videos and process them with re-analysis confirmation.
        Loops to allow processing multiple batches of videos.
        Creates both regular compilation and shorts.
        
        Returns:
            List of paths to all created compilation videos across all batches
        """
        file_selector = FileSelector()
        all_results = []
        
        try:
            while True:
                batch_results = self._process_single_batch(file_selector)
                
                if batch_results:
                    all_results.extend(batch_results)
                
                # Ask if user wants to process more videos
                if not file_selector.confirm_continue_processing():
                    break
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error in manual video selection loop: {str(e)}")
            file_selector.show_error("Error", f"An error occurred: {str(e)}")
            return all_results
        finally:
            file_selector.cleanup()
    
    def _process_single_batch(self, file_selector) -> List[str]:
        """
        Process a single batch of selected videos.
        
        Args:
            file_selector: FileSelector instance to use for dialogs
            
        Returns:
            List of paths to created compilation videos for this batch
        """
        results = []
        
        # Open file selection dialog
        selected_files = file_selector.select_video_files(
            title="Select Videos to Analyze for Kills"
        )
        
        if not selected_files:
            logger.info("No files selected")
            file_selector.show_info("No Selection", "No video files were selected.")
            return []
        
        logger.info(f"User selected {len(selected_files)} video file(s)")
        
        # Process each selected file
        videos_to_reanalyze = []
        videos_to_use_existing = []
        
        for video_path in selected_files:
            # Check if video was already analyzed
            if self.is_video_already_analyzed(video_path):
                # Ask for confirmation to re-analyze
                if file_selector.confirm_reanalysis(video_path):
                    logger.info(f"User confirmed re-analysis for {Path(video_path).name}")
                    # Remove existing analysis before re-analyzing
                    if self.remove_video_from_analysis(video_path):
                        videos_to_reanalyze.append(video_path)
                    else:
                        logger.error(f"Failed to remove existing analysis for {Path(video_path).name}")
                else:
                    logger.info(f"User chose to use existing analysis for {Path(video_path).name}")
                    videos_to_use_existing.append(video_path)
            else:
                # Video not analyzed before, add to re-analysis list
                videos_to_reanalyze.append(video_path)
        
        # Process videos that need re-analysis
        if videos_to_reanalyze:
            logger.info(f"Re-analyzing {len(videos_to_reanalyze)} video(s)")
            reanalysis_results = asyncio.run(self.process_multiple_videos(videos_to_reanalyze))
            results.extend(reanalysis_results)
        
        # Process videos using existing analysis
        if videos_to_use_existing:
            logger.info(f"Creating compilations from existing analysis for {len(videos_to_use_existing)} video(s)")
            for video_path in videos_to_use_existing:
                existing_highlights = self.get_existing_highlights(video_path)
                if existing_highlights:
                    logger.info(f"Found {len(existing_highlights)} existing highlight(s) for {Path(video_path).name}")
                    # Create compilation using existing highlights
                    compilation_path = self.video_processor.process_video_highlights(video_path, existing_highlights)
                    if compilation_path:
                        logger.info(f"✓ Created compilation from existing analysis: {Path(compilation_path).name}")
                        results.append(compilation_path)
                    else:
                        logger.error(f"Failed to create compilation from existing analysis for {Path(video_path).name}")
                else:
                    logger.warning(f"No existing highlights found for {Path(video_path).name}")
        
        if not results:
            logger.info("No videos were processed successfully")
            file_selector.show_info("No Processing", "No videos were processed successfully.")
            return []
        
        # Show completion message for this batch
        success_count = len(results)
        message = f"Successfully processed {success_count} video(s) in this batch!\n\nCompilations saved to: exported_videos/"
        if self.config.make_short:
            message += "\n\nShorts will be created automatically."
        file_selector.show_info("Batch Complete", message)
        
        # Clean up uploaded files after processing
        if results:
            self.cleanup_uploaded_files()
        
        return results
    
    def process_selected_videos(self) -> List[str]:
        """
        Legacy method for backward compatibility.
        Calls the new looping version.
        """
        return self.process_selected_videos_loop() 