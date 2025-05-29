import os
import subprocess
import tempfile
import shutil
import logging
import datetime
from pathlib import Path
from typing import Optional
from .subtitle_generator import SubtitleGenerator

logger = logging.getLogger(__name__)

class ShortsCreator:
    """Creates TikTok/YouTube style short videos from gameplay compilations."""
    
    def __init__(self, output_dir: str = "exported_videos"):
        self.output_dir = Path(output_dir)
        self.shorts_dir = self.output_dir / "shorts"
        self.shorts_dir.mkdir(exist_ok=True)
        self.subtitle_generator = SubtitleGenerator()
    
    def create_short_from_compilation(self, video_path: str, no_webcam: bool = False, add_subtitles: bool = False) -> Optional[str]:
        """
        Create a shorts-style video from a kill compilation.
        
        Args:
            video_path: Path to the compilation video
            no_webcam: If True, create video without webcam overlay
            add_subtitles: If True, add subtitles to the video
            
        Returns:
            Path to created short video or None if failed
        """
        if not os.path.exists(video_path):
            logger.error(f"Source video not found: {video_path}")
            return None
        
        # Generate output path
        video_name = Path(video_path).stem
        # Remove the .mp4 extension if present and preserve the custom title
        if video_name.endswith("_kills_compilation"):
            video_name = video_name.replace("_kills_compilation", "")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.shorts_dir / f"{video_name}_short_{timestamp}.mp4"
        
        logger.info(f"Creating short from: {Path(video_path).name}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Get source video dimensions
                src_width = int(subprocess.check_output([
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width", "-of", "csv=p=0", video_path
                ]).decode().strip())
                
                src_height = int(subprocess.check_output([
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=height", "-of", "csv=p=0", video_path
                ]).decode().strip())
                
                logger.info(f"Source video dimensions: {src_width}x{src_height}")
            except Exception as e:
                logger.error(f"Error getting video dimensions: {str(e)}")
                src_width, src_height = 1920, 1080
            
            # TikTok preferred dimensions
            output_width = 1080
            output_height = 1920
            
            # Create blurred background
            blurred_bg = os.path.join(temp_dir, "blurred_bg.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", video_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5",
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-an",
                blurred_bg
            ], check=True)
            
            # Extract webcam if not no_webcam mode
            webcam_path = os.path.join(temp_dir, "webcam.mp4")
            if not no_webcam:
                # Updated webcam coordinates based on new layout:
                # 23px from left, 1862px from right, 23px from top, 1038px from bottom
                # For 2560x1440 source: right edge = 2560 - 1862 = 698px, bottom edge = 1440 - 1038 = 402px
                x, y = 23, 23
                width = 698 - 23  # 675px wide
                height = 402 - 23  # 379px tall
                
                # Adjust for actual source dimensions
                x = max(0, min(x, src_width - 1))
                y = max(0, min(y, src_height - 1))
                width = max(1, min(width, src_width - x))
                height = max(1, min(height, src_height - y))
                
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", video_path,
                    "-vf", f"crop={width}:{height}:{x}:{y}",
                    "-c:v", "h264_nvenc", "-preset", "p4", "-an",
                    webcam_path
                ], check=True)
            
            # Extract killfeed
            killfeed_path = os.path.join(temp_dir, "killfeed.mp4")
            kf_x, kf_y = 2069, 78
            kf_width, kf_height = 475, 201
            
            # Adjust for actual source dimensions
            kf_x = max(0, min(kf_x, src_width - 1))
            kf_y = max(0, min(kf_y, src_height - 1))
            kf_width = max(1, min(kf_width, src_width - kf_x))
            kf_height = max(1, min(kf_height, src_height - kf_y))
            
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", video_path,
                "-vf", f"crop={kf_width}:{kf_height}:{kf_x}:{kf_y}",
                "-c:v", "h264_nvenc", "-preset", "p4", "-an",
                killfeed_path
            ], check=True)
            
            # Create gameplay video without zoom
            gameplay_path = os.path.join(temp_dir, "gameplay.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", video_path,
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-c:a", "copy",
                gameplay_path
            ], check=True)
            
            # Build filter complex
            if no_webcam:
                gameplay_height = int(output_height * 0.85)  # Increased to reduce blur area
                top_bar_height = int((output_height - gameplay_height) / 2)
                
                filter_complex = [
                    f"[1:v]scale=-1:{gameplay_height}:force_original_aspect_ratio=1[gameplay_base]",
                    f"[2:v]scale={output_width}*0.45:-1,format=rgba,colorchannelmixer=aa=0.6[killfeed_scaled]",
                    f"[gameplay_base][killfeed_scaled]overlay=x=(W-w)/2:y=0[gameplay_with_killfeed]",
                    f"[0:v][gameplay_with_killfeed]overlay=x=(W-w)/2:y={top_bar_height}[v]"
                ]
                
                ffmpeg_command = [
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", blurred_bg,
                    "-i", gameplay_path,
                    "-i", killfeed_path,
                    "-filter_complex", ";".join(filter_complex),
                    "-map", "[v]", "-map", "1:a",
                    "-c:v", "h264_nvenc", "-preset", "p4",
                    "-b:v", "30M",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-s", f"{output_width}x{output_height}",
                    str(output_path)
                ]
            else:
                webcam_height = round(output_height / 3)
                # Make gameplay larger to reduce blur area - use 85% of remaining space
                remaining_height = output_height - webcam_height
                gameplay_area_height = int(remaining_height * 0.85)
                
                filter_complex = [
                    f"[1:v]scale={output_width}:{webcam_height}[webcam_scaled]",
                    f"[2:v]scale={output_width}:{gameplay_area_height}:force_original_aspect_ratio=increase,crop={output_width}:{gameplay_area_height}[gameplay_base]",
                    f"[3:v]scale={output_width}*0.45:-1,format=rgba,colorchannelmixer=aa=0.6[killfeed_scaled]",
                    f"[gameplay_base][killfeed_scaled]overlay=x=W-w-20:y=20[gameplay_with_killfeed]",
                    f"[0:v][webcam_scaled]overlay=x=0:y=0[bg_plus_webcam]",
                    f"[bg_plus_webcam][gameplay_with_killfeed]overlay=x=0:y={webcam_height}[v]"
                ]
                
                ffmpeg_command = [
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", blurred_bg,
                    "-i", webcam_path,
                    "-i", gameplay_path,
                    "-i", killfeed_path,
                    "-filter_complex", ";".join(filter_complex),
                    "-map", "[v]", "-map", "2:a",
                    "-c:v", "h264_nvenc", "-preset", "p4",
                    "-b:v", "30M",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-s", f"{output_width}x{output_height}",
                    str(output_path)
                ]
            
            try:
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"✓ Created short: {output_path}")
                
                # Add subtitles if requested
                if add_subtitles:
                    logger.info(f"Adding subtitles to short video: {output_path}")
                    final_output = self._add_subtitles_to_video(str(output_path))
                    if final_output and final_output != str(output_path):
                        logger.info(f"✓ Subtitles added successfully: {Path(final_output).name}")
                    else:
                        logger.warning("Subtitle generation failed or returned original video")
                    return final_output if final_output else str(output_path)
                else:
                    logger.info("Subtitles not requested for this short video")
                
                return str(output_path)
            except subprocess.CalledProcessError as e:
                logger.error(f"Error creating short: {str(e)}")
                return None
            except Exception as e:
                logger.error(f"Unexpected error creating short: {str(e)}")
                return None
    
    def _add_subtitles_to_video(self, video_path: str) -> Optional[str]:
        """Add subtitles to the video using NVIDIA Parakeet TDT 0.6B V2."""
        try:
            logger.info(f"Starting subtitle generation for: {video_path}")
            video_name = Path(video_path).stem
            final_video = self.shorts_dir / f"{video_name}_with_subtitles.mp4"
            
            logger.info(f"Target subtitle video path: {final_video}")
            
            # Generate subtitles with GPU-accelerated overlay
            logger.info("Calling subtitle_generator.generate_subtitles...")
            subtitle_result = self.subtitle_generator.generate_subtitles(video_path, str(final_video))
            
            if subtitle_result:
                logger.info(f"✓ Subtitle generation successful, removing original video: {video_path}")
                # Remove original video
                os.unlink(video_path)
                logger.info(f"✓ Subtitle video created: {final_video}")
                return str(final_video)
            else:
                logger.warning("Failed to generate subtitles, returning original video")
                return video_path
                
        except Exception as e:
            logger.error(f"Error adding subtitles: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return video_path 