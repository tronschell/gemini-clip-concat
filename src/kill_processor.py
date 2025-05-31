import os
import asyncio
import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from utils.config import Config
from utils.video_analysis import analyze_video
from utils.video_processor import VideoProcessor
from utils.file_watcher import FileWatcher
from utils.logging_config import setup_logging
from utils.delete_files import FileDeleter
from utils.file_selector import FileSelector
from utils.process_monitor import GameProcessMonitor
from utils.video_queue import VideoQueue
from utils.token_counter import export_token_data_to_csv, append_token_data_to_csv, log_token_summary

logger = logging.getLogger(__name__)

class KillProcessor:
    """Main processor for analyzing videos and creating kill compilations."""
    
    def __init__(self):
        self.config = Config()
        self.video_processor = VideoProcessor(output_dir="exported_videos")
        self.processed_videos: set = set()
        self.process_monitor: Optional[GameProcessMonitor] = None
        self.video_queue = VideoQueue(self.config)
        
        # Token tracking for watch mode
        self.watch_mode_start_time: Optional[datetime] = None
        self.watch_mode_csv_path: Optional[str] = None
        self.watch_mode_token_data: List[Dict[str, Any]] = []
        
        # Setup logging
        setup_logging()
        
        # Ensure output directories exist
        Path("exported_metadata").mkdir(exist_ok=True)
        Path("exported_videos").mkdir(exist_ok=True)
    
    def _on_game_start(self, process_name: str, game_type: str):
        """
        Callback for when a game process starts.
        
        Args:
            process_name: Name of the game process that started
            game_type: Type of game detected
        """
        logger.info(f"🎮 Game started: {process_name} (type: {game_type})")
        if self.config.queue_when_gaming:
            logger.info("📋 Video queueing enabled - new videos will be queued until game closes")
    
    def _on_game_stop(self, process_name: str):
        """
        Callback for when a game process stops.
        
        Args:
            process_name: Name of the game process that stopped
        """
        logger.info(f"🎮 Game stopped: {process_name}")
        
        if self.config.queue_when_gaming:
            # Process all queued videos when game stops
            queue_status = self.video_queue.get_queue_status()
            if not queue_status["is_empty"]:
                logger.info(f"📋 Processing {queue_status['queue_size']} queued video(s) now that {process_name} has closed")
                try:
                    # Use the method without queue logic to avoid recursion
                    processed_videos = self.video_queue.process_all_queued(self._process_video_without_queue)
                    if processed_videos:
                        logger.info(f"✓ Successfully processed {len(processed_videos)} queued video(s)")
                    else:
                        logger.info("📋 No videos were successfully processed from queue")
                except Exception as e:
                    logger.error(f"📋 Error processing queued videos: {str(e)}")
            else:
                logger.info("📋 No videos in queue to process")
    
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
        token_usage = None
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
            
            # Retry logic for zero highlights with temperature escalation
            max_retries = self.config.max_zero_highlight_retries
            retry_count = 0
            highlights = None
            current_temperature = self.config.temperature
            
            while retry_count <= max_retries:
                try:
                    # Analyze video using kills prompt with current temperature
                    highlights, token_usage = await analyze_video(
                        video_path=video_path,
                        output_file="exported_metadata/kills.json",
                        temperature=current_temperature
                    )
                    
                    # Add timestamp and game type to token usage
                    if token_usage:
                        token_usage["timestamp"] = datetime.now().isoformat()
                        token_usage["game_type"] = self.config.game_type
                        token_usage["cached_tokens"] = token_usage.get("cached_tokens", 0)
                    
                    # If we got highlights, break out of retry loop
                    if highlights:
                        if current_temperature > self.config.temperature:
                            logger.info(f"✓ Found {len(highlights)} highlight(s) in {Path(video_path).name} with increased temperature: {current_temperature:.1f}")
                        break
                        
                    # If no highlights and we have retries left
                    if retry_count < max_retries:
                        retry_count += 1
                        # Increase temperature by 0.1 for next attempt
                        current_temperature += 0.1
                        logger.info(f"No highlights found in {Path(video_path).name}, retrying ({retry_count}/{max_retries}) with increased temperature: {current_temperature:.1f}")
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    else:
                        logger.info(f"No highlights found in {Path(video_path).name} after {max_retries} retries")
                        
                except Exception as e:
                    logger.error(f"Error analyzing video {video_path} (attempt {retry_count + 1}): {str(e)}")
                    if retry_count < max_retries:
                        retry_count += 1
                        # Also increase temperature on error retries
                        current_temperature += 0.1
                        logger.info(f"Retrying with increased temperature: {current_temperature:.1f}")
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    else:
                        raise
            
            # Handle token tracking for watch mode
            if token_usage and self.watch_mode_csv_path:
                try:
                    # Log token costs for watch mode
                    cost = token_usage.get("cost", 0.0)
                    total_tokens = token_usage.get("total_tokens", 0)
                    logger.info(f"💰 Token cost for {Path(video_path).name}: ${cost:.4f} ({total_tokens:,} tokens)")
                    
                    # Append to CSV and in-memory tracking
                    append_token_data_to_csv(token_usage, self.watch_mode_csv_path)
                    self.watch_mode_token_data.append(token_usage)
                except Exception as e:
                    logger.error(f"Failed to track tokens for watch mode: {str(e)}")
            
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
            
            # Track failed processing for watch mode
            if self.watch_mode_csv_path:
                error_token_data = {
                    "video": video_path,
                    "status": "error",
                    "model_name": self.config.model_name,
                    "game_type": self.config.game_type,
                    "thinking_mode": True,  # We use thinking mode
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cached_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
                
                try:
                    append_token_data_to_csv(error_token_data, self.watch_mode_csv_path)
                    self.watch_mode_token_data.append(error_token_data)
                except Exception as csv_error:
                    logger.error(f"Failed to log error token data: {str(csv_error)}")
            
            return None
    
    def process_single_video_sync(self, video_path: str) -> Optional[str]:
        """Synchronous wrapper for process_single_video."""
        
        # Check if we should queue the video instead of processing immediately
        if (self.config.queue_when_gaming and 
            self.process_monitor and 
            self.process_monitor.current_game_type):
            
            # Get the current game name for logging
            running_games = self.process_monitor.get_running_game_processes()
            game_name = "Unknown Game"
            if running_games:
                # Get the first running game name
                game_process = next(iter(running_games.keys()))
                game_name = game_process.replace('.exe', '').replace('_', ' ').title()
            
            # Queue the video instead of processing
            try:
                position = self.video_queue.add_video(video_path, game_name)
                return None  # Return None to indicate video was queued, not processed
            except Exception as e:
                logger.error(f"📋 Failed to queue video {Path(video_path).name}: {str(e)}")
                # Fall through to normal processing if queueing fails
        
        # Normal processing logic
        return self._process_video_without_queue(video_path)
    
    def _process_video_without_queue(self, video_path: str) -> Optional[str]:
        """Process a video without any queue logic - used for both normal processing and queue processing."""
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
        
        # Initialize token tracking for watch mode
        self.watch_mode_start_time = datetime.now()
        self.watch_mode_token_data = []
        
        # Create CSV file for watch mode token tracking
        try:
            csv_filename = f"token_costs_watch_{self.watch_mode_start_time.strftime('%Y%m%d_%H%M%S')}.csv"
            self.watch_mode_csv_path = str(Path("exported_metadata") / csv_filename)
            
            # Create empty CSV with headers
            export_token_data_to_csv([], "watch", self.watch_mode_start_time)
            logger.info(f"📊 Token tracking initialized for watch mode: {csv_filename}")
        except Exception as e:
            logger.error(f"Failed to initialize token tracking CSV: {str(e)}")
            self.watch_mode_csv_path = None
        
        # Initialize and start process monitor for automatic game detection
        try:
            self.process_monitor = GameProcessMonitor(
                self.config, 
                check_interval=3.0,
                on_game_start=self._on_game_start,
                on_game_stop=self._on_game_stop
            )
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
            process_callback=self._process_single_video_with_token_tracking,
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
            
            # Log final token summary for watch mode
            if self.watch_mode_token_data:
                logger.info("📊 Watch mode completed - generating final token summary")
                log_token_summary(self.watch_mode_token_data)
    
    def _process_single_video_with_token_tracking(self, video_path: str) -> Optional[str]:
        """
        Process a single video with token tracking for watch mode.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            Path to the created compilation video or None if no kills found
        """
        try:
            # Process the video normally
            result = self.process_single_video_sync(video_path)
            
            # Note: Token tracking is handled in the async methods called by process_single_video_sync
            return result
            
        except Exception as e:
            logger.error(f"Error processing video with token tracking {video_path}: {str(e)}")
            
            # Track failed processing
            if self.watch_mode_csv_path:
                error_token_data = {
                    "video": video_path,
                    "status": "error",
                    "model_name": self.config.model_name,
                    "game_type": self.config.game_type,
                    "thinking_mode": True,  # We use thinking mode
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "cached_tokens": 0,
                    "total_tokens": 0,
                    "cost": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
                
                try:
                    append_token_data_to_csv(error_token_data, self.watch_mode_csv_path)
                    self.watch_mode_token_data.append(error_token_data)
                except Exception as csv_error:
                    logger.error(f"Failed to log error token data: {str(csv_error)}")
            
            return None
    
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
        select_mode_token_data = []
        select_mode_start_time = datetime.now()
        
        try:
            while True:
                batch_results, batch_token_data = self._process_single_batch_with_tokens(file_selector)
                
                if batch_results:
                    all_results.extend(batch_results)
                
                if batch_token_data:
                    select_mode_token_data.extend(batch_token_data)
                
                # Ask if user wants to process more videos
                if not file_selector.confirm_continue_processing():
                    break
            
            # Export token data to CSV for select mode
            if select_mode_token_data:
                try:
                    csv_path = export_token_data_to_csv(select_mode_token_data, "select", select_mode_start_time)
                    logger.info(f"📊 Token usage data exported to: {Path(csv_path).name}")
                    
                    # Log summary
                    log_token_summary(select_mode_token_data)
                except Exception as e:
                    logger.error(f"Failed to export token data for select mode: {str(e)}")
            
            return all_results
            
        except Exception as e:
            logger.error(f"Error in manual video selection loop: {str(e)}")
            file_selector.show_error("Error", f"An error occurred: {str(e)}")
            return all_results
        finally:
            file_selector.cleanup()
    
    def _process_single_batch_with_tokens(self, file_selector) -> tuple[List[str], List[Dict[str, Any]]]:
        """
        Process a single batch of selected videos with token tracking.
        
        Args:
            file_selector: FileSelector instance to use for dialogs
            
        Returns:
            Tuple of (compilation paths, token usage data)
        """
        results = []
        token_data = []
        
        # Open file selection dialog
        selected_files = file_selector.select_video_files(
            title="Select Videos to Analyze for Kills"
        )
        
        if not selected_files:
            logger.info("No files selected")
            file_selector.show_info("No Selection", "No video files were selected.")
            return [], []
        
        logger.info(f"User selected {len(selected_files)} video file(s)")
        
        # Show prompt type selection dialog
        prompt_types = file_selector.select_prompt_types(selected_files)
        
        if not prompt_types:
            logger.info("No prompt types selected or dialog cancelled")
            file_selector.show_info("No Selection", "No prompt types were selected.")
            return [], []
        
        # Process each selected file
        videos_to_reanalyze = []
        videos_to_use_existing = []
        video_game_type_pairs = []
        
        for video_path in selected_files:
            game_type = prompt_types.get(video_path, self.config.game_type)
            
            # Check if video was already analyzed
            if self.is_video_already_analyzed(video_path):
                # Ask for confirmation to re-analyze
                if file_selector.confirm_reanalysis(video_path):
                    logger.info(f"User confirmed re-analysis for {Path(video_path).name}")
                    # Remove existing analysis before re-analyzing
                    if self.remove_video_from_analysis(video_path):
                        videos_to_reanalyze.append(video_path)
                        video_game_type_pairs.append((video_path, game_type))
                    else:
                        logger.error(f"Failed to remove existing analysis for {Path(video_path).name}")
                else:
                    logger.info(f"User chose to use existing analysis for {Path(video_path).name}")
                    videos_to_use_existing.append(video_path)
            else:
                # Video not analyzed before, add to re-analysis list
                videos_to_reanalyze.append(video_path)
                video_game_type_pairs.append((video_path, game_type))
        
        # Process videos that need re-analysis with their specific game types
        if video_game_type_pairs:
            logger.info(f"Re-analyzing {len(video_game_type_pairs)} video(s) with custom game types")
            reanalysis_results, reanalysis_tokens = asyncio.run(self.process_multiple_videos_with_game_types_and_tokens(video_game_type_pairs))
            results.extend(reanalysis_results)
            token_data.extend(reanalysis_tokens)
        
        # Process videos using existing analysis (no token cost for these)
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
                        
                        # Add token data entry for existing analysis (no cost)
                        existing_token_data = {
                            "video": video_path,
                            "status": "existing_analysis",
                            "model_name": self.config.model_name,
                            "game_type": prompt_types.get(video_path, self.config.game_type),
                            "thinking_mode": False,  # No thinking mode used for existing analysis
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "cached_tokens": 0,
                            "total_tokens": 0,
                            "cost": 0.0,
                            "timestamp": datetime.now().isoformat()
                        }
                        token_data.append(existing_token_data)
                    else:
                        logger.error(f"Failed to create compilation from existing analysis for {Path(video_path).name}")
                else:
                    logger.warning(f"No existing highlights found for {Path(video_path).name}")
        
        if not results:
            logger.info("No videos were processed successfully")
            file_selector.show_info("No Processing", "No videos were processed successfully.")
            return [], token_data
        
        # Show completion message for this batch
        success_count = len(results)
        total_cost = sum(data.get("cost", 0.0) for data in token_data)
        message = f"Successfully processed {success_count} video(s) in this batch!\n\nCompilations saved to: exported_videos/"
        if total_cost > 0:
            message += f"\n\nToken cost for this batch: ${total_cost:.4f}"
        if self.config.make_short:
            message += "\n\nShorts will be created automatically."
        file_selector.show_info("Batch Complete", message)
        
        # Clean up uploaded files after processing
        if results:
            self.cleanup_uploaded_files()
        
        return results, token_data

    def _process_single_batch(self, file_selector) -> List[str]:
        """
        Process a single batch of selected videos (legacy method).
        
        Args:
            file_selector: FileSelector instance to use for dialogs
            
        Returns:
            List of paths to created compilation videos for this batch
        """
        results, _ = self._process_single_batch_with_tokens(file_selector)
        return results

    def process_selected_videos(self) -> List[str]:
        """
        Legacy method for backward compatibility.
        Calls the new looping version.
        """
        return self.process_selected_videos_loop()

    async def process_single_video_with_game_type(self, video_path: str, game_type: str) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """
        Process a single video to find kills and create compilation using a specific game type.
        
        Args:
            video_path: Path to the video file
            game_type: Game type to use for analysis
            
        Returns:
            Tuple of (compilation path or None, token usage data or None)
        """
        token_usage = None
        try:
            # Skip if already processed (unless reprocessing is enabled)
            if not self.config.reprocess_analyzed_videos and video_path in self.processed_videos:
                logger.info(f"Skipping already processed video: {Path(video_path).name}")
                return None, None
            
            # Check if video was already analyzed in kills.json
            if not self.config.reprocess_analyzed_videos and self.is_video_already_analyzed(video_path):
                logger.info(f"Skipping already analyzed video: {Path(video_path).name}")
                self.processed_videos.add(video_path)
                return None, None
            
            logger.info(f"Processing video: {Path(video_path).name} with game type: {game_type}")
            
            # Retry logic for zero highlights with temperature escalation
            max_retries = self.config.max_zero_highlight_retries
            retry_count = 0
            highlights = None
            current_temperature = self.config.temperature
            
            while retry_count <= max_retries:
                try:
                    # Analyze video using specified game type with current temperature
                    highlights, token_usage = await analyze_video(
                        video_path=video_path,
                        output_file="exported_metadata/kills.json",
                        game_type=game_type,
                        temperature=current_temperature
                    )
                    
                    # Add timestamp and game type to token usage
                    if token_usage:
                        token_usage["timestamp"] = datetime.now().isoformat()
                        token_usage["game_type"] = game_type
                        token_usage["cached_tokens"] = token_usage.get("cached_tokens", 0)
                    
                    # If we got highlights, break out of retry loop
                    if highlights:
                        if current_temperature > self.config.temperature:
                            logger.info(f"✓ Found {len(highlights)} highlight(s) in {Path(video_path).name} with increased temperature: {current_temperature:.1f}")
                        break
                        
                    # If no highlights and we have retries left
                    if retry_count < max_retries:
                        retry_count += 1
                        # Increase temperature by 0.1 for next attempt
                        current_temperature += 0.1
                        logger.info(f"No highlights found in {Path(video_path).name}, retrying ({retry_count}/{max_retries}) with increased temperature: {current_temperature:.1f}")
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    else:
                        logger.info(f"No highlights found in {Path(video_path).name} after {max_retries} retries")
                        
                except Exception as e:
                    logger.error(f"Error analyzing video {video_path} (attempt {retry_count + 1}): {str(e)}")
                    if retry_count < max_retries:
                        retry_count += 1
                        # Also increase temperature on error retries
                        current_temperature += 0.1
                        logger.info(f"Retrying with increased temperature: {current_temperature:.1f}")
                        await asyncio.sleep(self.config.retry_delay_seconds)
                    else:
                        raise
            
            if not highlights:
                logger.info(f"No kills found in {Path(video_path).name}")
                self.processed_videos.add(video_path)
                return None, token_usage
            
            logger.info(f"Found {len(highlights)} kill(s) in {Path(video_path).name}")
            
            # Process video to create compilation
            compilation_path = self.video_processor.process_video_highlights(video_path, highlights)
            
            if compilation_path:
                logger.info(f"✓ Created kill compilation: {Path(compilation_path).name}")
                self.processed_videos.add(video_path)
                return compilation_path, token_usage
            else:
                logger.error(f"Failed to create compilation for {Path(video_path).name}")
                return None, token_usage
                
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
            
            # Create error token data
            error_token_data = {
                "video": video_path,
                "status": "error",
                "model_name": self.config.model_name,
                "game_type": game_type,
                "thinking_mode": True,  # We use thinking mode
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
                "cost": 0.0,
                "timestamp": datetime.now().isoformat()
            }
            
            return None, error_token_data

    async def process_multiple_videos_with_game_types_and_tokens(self, video_game_type_pairs: List[tuple]) -> tuple[List[str], List[Dict[str, Any]]]:
        """
        Process multiple videos with their respective game types concurrently and collect token data.
        
        Args:
            video_game_type_pairs: List of tuples containing (video_path, game_type)
            
        Returns:
            Tuple of (compilation paths, token usage data)
        """
        if not video_game_type_pairs:
            logger.warning("No videos to process")
            return [], []
        
        logger.info(f"Processing {len(video_game_type_pairs)} video(s) with custom game types")
        
        # Process videos in batches based on config
        batch_size = self.config.batch_size
        results = []
        token_data = []
        
        for i in range(0, len(video_game_type_pairs), batch_size):
            batch = video_game_type_pairs[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} videos)")
            
            # Process batch concurrently
            batch_results = await asyncio.gather(
                *(self.process_single_video_with_game_type(video_path, game_type) 
                  for video_path, game_type in batch),
                return_exceptions=True
            )
            
            # Filter successful results and collect token data
            for result in batch_results:
                if isinstance(result, tuple) and len(result) == 2:
                    compilation_path, token_usage = result
                    if compilation_path:  # Successful compilation
                        results.append(compilation_path)
                    if token_usage:  # Token data available
                        token_data.append(token_usage)
                elif isinstance(result, Exception):
                    logger.error(f"Batch processing error: {str(result)}")
        
        logger.info(f"✓ Successfully processed {len(results)} video(s)")
        
        # Clean up uploaded files after batch processing
        if results:  # Only cleanup if we processed any videos
            self.cleanup_uploaded_files()
        
        return results, token_data

    async def process_multiple_videos_with_game_types(self, video_game_type_pairs: List[tuple]) -> List[str]:
        """
        Process multiple videos with their respective game types concurrently (legacy method).
        
        Args:
            video_game_type_pairs: List of tuples containing (video_path, game_type)
            
        Returns:
            List of paths to created compilation videos
        """
        results, _ = await self.process_multiple_videos_with_game_types_and_tokens(video_game_type_pairs)
        return results 