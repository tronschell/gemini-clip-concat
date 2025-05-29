import os
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

class VideoConcatenator:
    """Utility for concatenating multiple video files."""
    
    def __init__(self):
        pass
    
    async def concatenate_videos(self, video_paths: List[str], output_path: Optional[str] = None) -> Optional[str]:
        """
        Concatenate multiple video files into a single video.
        
        Args:
            video_paths: List of video file paths in the order to concatenate
            output_path: Optional output path. If None, generates a timestamped filename
            
        Returns:
            Path to the concatenated video file, or None if failed
        """
        if not video_paths or len(video_paths) < 2:
            logger.error("Need at least 2 videos to concatenate")
            return None
        
        # Validate all input files exist
        for video_path in video_paths:
            if not os.path.exists(video_path):
                logger.error(f"Video file not found: {video_path}")
                return None
        
        # Generate output path if not provided
        if output_path is None:
            export_dir = Path("exported_videos")
            export_dir.mkdir(exist_ok=True)
            
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = export_dir / f"concatenated_{timestamp}.mp4"
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create temporary file list for ffmpeg
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_filelist:
            for video_file in video_paths:
                abs_video_path = os.path.abspath(video_file)
                # Use forward slashes for ffmpeg compatibility
                safe_path = abs_video_path.replace("\\", "/")
                tmp_filelist.write(f"file '{safe_path}'\n")
            filelist_path = tmp_filelist.name
        
        try:
            # Build ffmpeg command for concatenation
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", filelist_path,
                "-c", "copy",
                str(output_path)
            ]
            
            logger.info(f"Concatenating {len(video_paths)} videos into {output_path}")
            
            # Execute ffmpeg command
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg concatenation failed. Return code: {process.returncode}")
                logger.error(f"FFmpeg stderr: {stderr.decode(errors='ignore') if stderr else 'N/A'}")
                if output_path.exists():
                    output_path.unlink()
                return None
            
            logger.info(f"Successfully concatenated videos into {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error during video concatenation: {str(e)}")
            if output_path.exists():
                output_path.unlink()
            return None
        finally:
            # Clean up temporary file list
            if os.path.exists(filelist_path):
                os.unlink(filelist_path)
    
    async def concatenate_and_process(self, video_paths: List[str], create_shorts: bool = True) -> List[str]:
        """
        Concatenate videos and create both regular compilation and shorts.
        
        Args:
            video_paths: List of video file paths in the order to concatenate
            create_shorts: Whether to create shorts version
            
        Returns:
            List of created video file paths
        """
        results = []
        
        # First concatenate the videos
        concatenated_path = await self.concatenate_videos(video_paths)
        if not concatenated_path:
            logger.error("Failed to concatenate videos")
            return results
        
        results.append(concatenated_path)
        logger.info(f"Created concatenated video: {Path(concatenated_path).name}")
        
        # Create shorts version if requested
        if create_shorts:
            try:
                from .shorts_creator import ShortsCreator
                from .config import Config
                
                config = Config()
                shorts_creator = ShortsCreator()
                
                logger.info("Creating shorts version from concatenated video...")
                short_path = shorts_creator.create_short_from_compilation(
                    concatenated_path,
                    no_webcam=config.shorts_no_webcam,
                    add_subtitles=config.shorts_add_subtitles
                )
                
                if short_path:
                    results.append(short_path)
                    logger.info(f"Created shorts video: {Path(short_path).name}")
                else:
                    logger.warning("Failed to create shorts video")
                    
            except Exception as e:
                logger.error(f"Error creating shorts: {str(e)}")
        
        return results 