import os
import subprocess
import tempfile
import logging
import shutil
import random
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path

from .config import Config
from .shorts_creator import ShortsCreator

logger = logging.getLogger(__name__)

class VideoProcessor:
    
    def __init__(self, output_dir: str = "exported_videos"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self._nvenc_available = None
        self.config = Config()
        self.shorts_creator = ShortsCreator(output_dir)
    
    def check_nvenc_availability(self) -> bool:
        """
        Check if NVENC (NVIDIA hardware encoding) is available.
        
        Returns:
            True if NVENC is available, False otherwise
        """
        if self._nvenc_available is not None:
            return self._nvenc_available
        
        try:
            # Test if h264_nvenc encoder is available
            cmd = ['ffmpeg', '-hide_banner', '-encoders']
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Check if h264_nvenc is in the output
            self._nvenc_available = 'h264_nvenc' in result.stdout
            
            if self._nvenc_available:
                logger.info("NVENC hardware acceleration available")
            else:
                logger.info("NVENC not available, will use CPU encoding")
                
        except subprocess.CalledProcessError:
            logger.warning("Could not check NVENC availability, defaulting to CPU encoding")
            self._nvenc_available = False
        
        return self._nvenc_available
    
    def merge_overlapping_clips(self, highlights: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge overlapping clips by combining minimum start and maximum end times.
        
        Args:
            highlights: List of highlight dicts with timestamp_start_seconds and timestamp_end_seconds
            
        Returns:
            List of merged highlight dicts
        """
        if not highlights:
            return []
        
        # Sort highlights by start time
        sorted_highlights = sorted(highlights, key=lambda x: x['timestamp_start_seconds'])
        
        merged = []
        current = sorted_highlights[0].copy()
        
        for highlight in sorted_highlights[1:]:
            # Check if current clip overlaps with next clip
            if highlight['timestamp_start_seconds'] <= current['timestamp_end_seconds']:
                # Merge clips: extend end time to maximum of both clips
                current['timestamp_end_seconds'] = max(
                    current['timestamp_end_seconds'],
                    highlight['timestamp_end_seconds']
                )
                logger.debug(f"Merged overlapping clips: {current['timestamp_start_seconds']}-{current['timestamp_end_seconds']}")
            else:
                # No overlap, add current to merged list and start new clip
                merged.append(current)
                current = highlight.copy()
        
        # Add the last clip
        merged.append(current)
        
        logger.info(f"Merged {len(highlights)} clips into {len(merged)} clips")
        return merged
    
    def create_compilation(self, video_path: str, highlights: List[Dict[str, Any]], output_filename: str) -> str:
        """
        Create video compilation directly using FFmpeg filter_complex.
        Extracts and concatenates all segments in a single pass.
        
        Args:
            video_path: Path to source video
            highlights: List of highlight dicts with start/end times
            output_filename: Name for the final compilation video
            
        Returns:
            Path to the compilation video file
        """
        if not highlights:
            raise ValueError("No highlights to process")
        
        output_path = self.output_dir / output_filename
        
        # Check if NVENC is available
        use_nvenc = self.check_nvenc_availability()
        
        # Build filter_complex for extracting segments
        filter_parts = []
        input_labels = []
        
        for i, highlight in enumerate(highlights):
            start_time = highlight['timestamp_start_seconds']
            end_time = highlight['timestamp_end_seconds']
            duration = end_time - start_time
            
            # Create trim filter for each segment
            filter_parts.append(f"[0:v]trim=start={start_time}:duration={duration},setpts=PTS-STARTPTS[v{i}]")
            filter_parts.append(f"[0:a]atrim=start={start_time}:duration={duration},asetpts=PTS-STARTPTS[a{i}]")
            input_labels.extend([f"[v{i}]", f"[a{i}]"])
        
        # Concatenate all segments
        video_inputs = "[v" + "][v".join(map(str, range(len(highlights)))) + "]"
        audio_inputs = "[a" + "][a".join(map(str, range(len(highlights)))) + "]"
        filter_parts.append(f"{video_inputs}concat=n={len(highlights)}:v=1:a=0[outv]")
        filter_parts.append(f"{audio_inputs}concat=n={len(highlights)}:v=0:a=1[outa]")
        
        filter_complex = ";".join(filter_parts)
        
        # Build FFmpeg command
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
        ]
        
        if use_nvenc:
            # NVIDIA hardware acceleration
            cmd.extend([
                '-c:v', 'h264_nvenc',
                '-preset', 'medium',
                '-pix_fmt', 'yuv420p',
                '-b:v', '30M',
                '-maxrate', '35M',
                '-bufsize', '60M',
                '-g', '30',
                '-forced-idr', '1',
            ])
        else:
            # CPU encoding fallback
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-pix_fmt', 'yuv420p',
                '-b:v', '30M',
                '-maxrate', '35M',
                '-bufsize', '60M',
                '-g', '30',
                '-keyint_min', '15',
                '-sc_threshold', '40',
            ])
        
        # Audio and output settings
        cmd.extend([
            '-r', '60',
            '-vsync', 'cfr',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',
            '-ac', '2',
            '-movflags', '+faststart',
            '-y',
            str(output_path)
        ])
        
        try:
            encoder_type = "NVENC" if use_nvenc else "CPU"
            logger.info(f"Creating compilation using {encoder_type} with filter_complex...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info(f"✓ Created compilation with {len(highlights)} segments: {output_path}")
            
            return str(output_path)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create compilation: {e.stderr}")
            raise

    def process_video_highlights(self, video_path: str, highlights: List[Dict[str, Any]]) -> str:
        """
        Complete processing pipeline: merge overlapping clips and create compilation.
        
        Args:
            video_path: Path to source video
            highlights: List of highlight dicts
            
        Returns:
            Path to final compilation video
        """
        if not highlights:
            logger.warning(f"No highlights found for {video_path}")
            return None
        
        video_name = Path(video_path).stem
        
        # Randomly select a title from the highlights
        titles_with_content = [h.get('title', '') for h in highlights if h.get('title', '').strip()]
        if titles_with_content:
            selected_title = random.choice(titles_with_content)
            # Minimal sanitization - only remove characters that are truly problematic for filenames
            # Keep spaces, but remove: < > : " | ? * \ /
            problematic_chars = '<>:"|?*\\/'
            sanitized_title = "".join(c for c in selected_title if c not in problematic_chars).strip()
            # Limit length to avoid filesystem issues
            if len(sanitized_title) > 50:
                sanitized_title = sanitized_title[:50].strip()
            output_filename = f"{video_name}_{sanitized_title}.mp4"
            logger.info(f"Selected random title for video: '{selected_title}'")
        else:
            # Fallback to generic name if no titles available
            output_filename = f"{video_name}_kills_compilation.mp4"
            logger.warning("No titles found in highlights, using generic filename")
        
        # Step 1: Merge overlapping clips
        merged_highlights = self.merge_overlapping_clips(highlights)
        
        # Step 2: Create compilation directly with filter_complex
        final_video_path = self.create_compilation(video_path, merged_highlights, output_filename)
        
        logger.info(f"✓ Created kill compilation: {final_video_path}")
        
        # Step 3: Create shorts if enabled in config
        logger.info(f"Config make_short setting: {self.config.make_short}")
        logger.info(f"Config shorts_add_subtitles setting: {self.config.shorts_add_subtitles}")
        logger.info(f"Config shorts_no_webcam setting: {self.config.shorts_no_webcam}")
        if self.config.make_short:
            try:
                logger.info("Creating short video from compilation...")
                logger.info(f"Calling create_short_from_compilation with add_subtitles={self.config.shorts_add_subtitles}")
                short_path = self.shorts_creator.create_short_from_compilation(
                    final_video_path,
                    no_webcam=self.config.shorts_no_webcam,
                    add_subtitles=self.config.shorts_add_subtitles
                )
                if short_path:
                    logger.info(f"✓ Created short: {Path(short_path).name}")
                    if self.config.shorts_add_subtitles:
                        logger.info(f"✓ Short created with subtitles enabled")
                else:
                    logger.warning("Failed to create short video")
            except Exception as e:
                logger.error(f"Error creating short: {str(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
        else:
            logger.info("Shorts creation disabled in config")
        
        return final_video_path 