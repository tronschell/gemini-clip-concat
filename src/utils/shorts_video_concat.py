#!/usr/bin/env python
import os
import sys # Add sys for path manipulation
import shutil

# Ensure the project root is in sys.path for imports to work when run directly
if __name__ == '__main__' and __package__ is None:
    script_path = os.path.abspath(__file__)
    src_dir = os.path.dirname(script_path)
    project_root = os.path.dirname(src_dir)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

import json
import argparse
import subprocess
import logging
import tempfile
import hashlib
import time
import csv
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import asyncio
from utils.config import Config
import video_analysis
from utils.analysis_tracker import AnalysisTracker
from subtitle_generator import SubtitleGenerator, generate_subtitles_for_video, cleanup_temp_files

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShortsCreator:
    def __init__(self):
        pass

    async def create_shorts_video(self, video_path: str, start_time: int, end_time: int, output_path: str = None, no_webcam: bool = False, add_subtitles: bool = False, use_whole_video: bool = False):
        """Create a shorts-style video with webcam at top 1/3 and gameplay at bottom 2/3."""
        # Generate output path if not provided
        if output_path is None:
            export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'exported_videos')
            os.makedirs(export_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(export_dir, f"short_{timestamp}.mp4")
        
        if not os.path.exists(video_path):
            logger.error(f"Source video not found: {video_path}")
            return None
        
        if end_time <= start_time and not use_whole_video:
            logger.error("Invalid timestamp range")
            return None
        
        duration = end_time - start_time
        
        # Create temp directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract clip from source video or use whole video
            clip_path = os.path.join(temp_dir, "clip.mp4")
            
            if use_whole_video or (start_time == 0 and end_time == int(subprocess.check_output([
                    "ffprobe", 
                    "-v", "error", 
                    "-show_entries", "format=duration", 
                    "-of", "default=noprint_wrappers=1:nokey=1", 
                    video_path
                ]).decode().strip())):
                # Use whole video without clipping
                logger.info(f"Using entire video without clipping: {os.path.basename(video_path)}")
                # Create a symlink or copy the video
                if os.name == 'nt':  # Windows
                    shutil.copy(video_path, clip_path)
                else:  # Unix-like
                    os.symlink(os.path.abspath(video_path), clip_path)
            else:
                # Extract clip from source video
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", video_path, 
                    "-ss", str(start_time), "-t", str(duration),
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                    "-c:a", "aac", "-b:a", "192k",
                    clip_path
                ], check=True)
            
            # Generate subtitles if requested
            subtitle_path = None
            if add_subtitles and os.path.exists(clip_path):
                try:
                    logger.info(f"Generating subtitles for shorts clip")
                    subtitle_path = generate_subtitles_for_video(clip_path, is_short=True)
                    
                    # Verify the subtitle file exists and is readable
                    if subtitle_path and os.path.exists(subtitle_path):
                        logger.info(f"Subtitles generated for shorts clip: {subtitle_path}")
                        # Check if the subtitle file is not empty
                        with open(subtitle_path, 'r', encoding='utf-8') as f:
                            subtitle_content = f.read().strip()
                            if subtitle_content:
                                logger.info(f"Subtitle file contains {len(subtitle_content.splitlines())} lines")
                            else:
                                logger.warning(f"Subtitle file exists but is empty: {subtitle_path}")
                                subtitle_path = None
                    else:
                        logger.warning(f"Subtitle file was not created or does not exist: {subtitle_path}")
                        subtitle_path = None
                except Exception as e:
                    logger.error(f"Failed to generate subtitles for shorts clip: {str(e)}")
                    subtitle_path = None
                    # Continue without subtitles if generation fails
            
            # Get source video dimensions
            try:
                src_width = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", 
                                                     "-show_entries", "stream=width", "-of", "csv=p=0", 
                                                     clip_path]).decode().strip())
                src_height = int(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", 
                                                      "-show_entries", "stream=height", "-of", "csv=p=0", 
                                                      clip_path]).decode().strip())
                logger.info(f"Source video dimensions: {src_width}x{src_height}")
            except Exception as e:
                logger.error(f"Error getting video dimensions: {str(e)}")
                src_width, src_height = 1920, 1080  # Default to common resolution if probe fails
            
            # Set output dimensions - TikTok's preferred resolution
            output_width = 1080
            output_height = 1920
            
            # Set dimensions based on whether webcam is used or not
            if no_webcam:
                gameplay_height_percent = 0.85  # 85% of screen for gameplay to reduce blur
                gameplay_area_height = int(output_height * gameplay_height_percent)
                top_bar_height = int((output_height - gameplay_area_height) / 2)
                bottom_bar_height = output_height - gameplay_area_height - top_bar_height
                webcam_height = 0
            else:
                webcam_height = round(output_height / 3)  # Webcam is top 1/3
                # Make gameplay larger to reduce blur area - use 85% of remaining space
                remaining_height = output_height - webcam_height
                gameplay_area_height = int(remaining_height * 0.85)
                
            killfeed_scale_factor = 0.6 # Scale killfeed to 60% of output_width
            
            # Create blurred background
            blurred_bg = os.path.join(temp_dir, "blurred_bg.mp4")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", clip_path,
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5",
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", "-an",
                blurred_bg
            ], check=True)
            
            # Extract webcam using hardcoded values from the screenshot
            webcam_path = os.path.join(temp_dir, "webcam.mp4")
            
            if not no_webcam:
                # Hardcoded coordinates and dimensions based on user's latest specification
                # for a 1440p (2560x1440) source video. Coordinates are from top-left.
                # Left edge: 43px from left screen edge
                # Right edge: 1959px from right screen edge (i.e., 2560 - 1959 = 601px from left)
                # Top edge: 463px from top screen edge
                # Bottom edge: 663px from top screen edge
                
                desired_crop_x = 43
                desired_crop_y = 463
                desired_crop_width = 558  # Calculated as (2560 - 1959) - 43
                desired_crop_height = 300 # Calculated as 663 - 463

                # Calculate actual crop dimensions and positions, 
                # ensuring they are within the source video's bounds.
                
                # Ensure x and y are within [0, source_dimension - 1]
                x = max(0, min(desired_crop_x, src_width - 1 if src_width > 0 else 0))
                y = max(0, min(desired_crop_y, src_height - 1 if src_height > 0 else 0))
                
                # Adjust width: ensure it's at least 1px and does not exceed available width from x.
                width = max(1, min(desired_crop_width, src_width - x if src_width > x else 0))
                
                # Adjust height: ensure it's at least 1px and does not exceed available height from y.
                height = max(1, min(desired_crop_height, src_height - y if src_height > y else 0))
                
                logger.info(f"Attempting to extract webcam from coordinates: x={x}, y={y}, width={width}, height={height}")
                
                # Extract webcam region
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", clip_path,
                    "-vf", f"crop={width}:{height}:{x}:{y}", 
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", "-an",
                    webcam_path
                ], check=True)
            
            # Killfeed extraction
            kf_desired_crop_x = 2069
            kf_desired_crop_y = 78
            kf_desired_crop_width = 475
            kf_desired_crop_height = 201

            kf_x = max(0, min(kf_desired_crop_x, src_width - 1 if src_width > 0 else 0))
            kf_y = max(0, min(kf_desired_crop_y, src_height - 1 if src_height > 0 else 0))
            # Ensure width/height are at least 1 and do not exceed available dimensions from x/y
            kf_crop_w = max(1, min(kf_desired_crop_width, src_width - kf_x if src_width > kf_x else 0))
            kf_crop_h = max(1, min(kf_desired_crop_height, src_height - kf_y if src_height > kf_y else 0))

            killfeed_path = os.path.join(temp_dir, "killfeed.mp4")
            logger.info(f"Attempting to extract killfeed from coordinates: x={kf_x}, y={kf_y}, width={kf_crop_w}, height={kf_crop_h}")
            subprocess.run([
                "ffmpeg", "-y", "-hwaccel", "cuda",
                "-i", clip_path,
                "-vf", f"crop={kf_crop_w}:{kf_crop_h}:{kf_x}:{kf_y}",
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "10M", "-maxrate", "15M", "-bufsize", "30M", "-an", # Adjusted bitrate for smaller element
                killfeed_path
            ], check=True)
            logger.info(f"Killfeed extracted to {killfeed_path}")
            
            # Create gameplay video with slight zoom for better visibility
            gameplay_path = os.path.join(temp_dir, "gameplay.mp4")
            
            # Add subtitles to gameplay if requested
            if subtitle_path and add_subtitles:
                logger.info("Adding subtitles to gameplay video")
                
                # First extract clip without zoom to a temporary file
                zoomed_clip_path = os.path.join(temp_dir, "zoomed_clip.mp4")
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", clip_path,
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                    "-c:a", "copy",
                    zoomed_clip_path
                ], check=True)
                
                # Then add subtitles as a second pass - this avoids complex filter chains
                try:
                    # Convert to absolute POSIX path for consistency
                    posix_path = Path(subtitle_path).resolve().as_posix()
                    # Escape the colon for Windows drive letters for FFmpeg filter syntax
                    # e.g., C:/path/to/srt -> C\\:/path/to/srt
                    ffmpeg_filter_path = posix_path.replace(':', '\\:')
                    
                    # For Windows, we need to ensure proper path handling
                    # Use direct path with proper escaping for Windows
                    if os.name == 'nt':  # Check if running on Windows
                        # On Windows, create a copy of the subtitle file in the temp directory to avoid path issues
                        temp_srt_path = os.path.join(temp_dir, "subtitles.srt")
                        shutil.copy(subtitle_path, temp_srt_path)
                        # Use the new path with simpler naming
                        posix_path = Path(temp_srt_path).resolve().as_posix()
                        ffmpeg_filter_path = posix_path.replace(':', '\\:')
                        logger.info(f"Using temporary subtitle file at: {temp_srt_path}")
                    
                    # Construct the video filter string for subtitles with styling
                    # Note: No extra single quotes around ffmpeg_filter_path for filename value
                    # Use much larger font size and stronger outline for better visibility in shorts format
                    vf_filter = f"subtitles=filename='{ffmpeg_filter_path}':force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF,BackColour=&H00000000,OutlineColour=&HAA000000,BorderStyle=1,Outline=1,Shadow=1,MarginV={{int(src_height * 0.6)}}'"
                    
                    subprocess.run([
                        "ffmpeg", "-y", "-hwaccel", "cuda",
                        "-i", zoomed_clip_path,
                        "-vf", vf_filter,
                        "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                        "-c:a", "copy",
                        gameplay_path
                    ], check=True)
                    logger.info(f"Successfully added subtitles to gameplay video with filter: {vf_filter}")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error adding subtitles: {str(e)}")
                    logger.warning("Falling back to processing without subtitles")
                    # Use the zoomed clip directly if subtitle overlay fails
                    shutil.copy(zoomed_clip_path, gameplay_path)
                    
                    # Log more detailed error information for debugging
                    if hasattr(e, 'stderr') and e.stderr:
                        logger.error(f"FFmpeg stderr: {e.stderr.decode(errors='ignore')}")
                    if hasattr(e, 'stdout') and e.stdout:
                        logger.error(f"FFmpeg stdout: {e.stdout.decode(errors='ignore')}")
                
                # Clean up temporary file
                try:
                    if os.path.exists(zoomed_clip_path):
                        os.unlink(zoomed_clip_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {e}")
            else:
                # No subtitles, no zoom - use original scale
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", clip_path,
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                    "-c:a", "copy",
                    gameplay_path
                ], check=True)
            
            # Create filter complex for ffmpeg
            filter_complex = []
            
            if no_webcam:
                # For no webcam mode, the gameplay takes up 70% of the screen with blurry bars
                filter_complex.extend([
                    # Gameplay - scale to fit the 70% height while maintaining aspect ratio
                    f"[2:v]scale=-1:{gameplay_area_height}:force_original_aspect_ratio=1[gameplay_base]",
                    
                    # Killfeed processing: scale and set opacity
                    f"[3:v]scale={output_width}*{killfeed_scale_factor}:-1,format=rgba,colorchannelmixer=aa=0.6[killfeed_scaled]",
                    
                    # Overlay killfeed at the top of gameplay
                    f"[gameplay_base][killfeed_scaled]overlay=x=(W-w)/2:y=0[gameplay_with_killfeed]",
                    
                    # Overlay gameplay_with_killfeed onto blurred background, positioned in the middle
                    f"[0:v][gameplay_with_killfeed]overlay=x=(W-w)/2:y={top_bar_height}[v]"
                ])
            else:
                # Original layout with webcam at top
                filter_complex.extend([
                    # Webcam at top - scale to fit the container, potentially changing aspect ratio
                    f"[1:v]scale={output_width}:{webcam_height}[webcam_scaled]",
                    
                    # Gameplay at bottom - scale to fill gameplay_height (cropping width if needed)
                    f"[2:v]scale={output_width}:{gameplay_area_height}:force_original_aspect_ratio=increase,crop={output_width}:{gameplay_area_height}[gameplay_base]",
                    
                    # Killfeed processing: scale and set opacity
                    f"[3:v]scale={output_width}*{killfeed_scale_factor}:-1,format=rgba,colorchannelmixer=aa=0.6[killfeed_scaled]",
                    
                    # Overlay killfeed onto the top of gameplay_base
                    f"[gameplay_base][killfeed_scaled]overlay=x=(W-w)/2:y=0[gameplay_with_killfeed]",
                    
                    # Overlay webcam_scaled onto blurred_bg
                    f"[0:v][webcam_scaled]overlay=x=0:y=0[bg_plus_webcam]",
                    
                    # Overlay gameplay_with_killfeed onto bg_plus_webcam, positioned below webcam
                    f"[bg_plus_webcam][gameplay_with_killfeed]overlay=x=0:y={webcam_height}[v]"
                ])
            
            try:
                # Final composition
                ffmpeg_command = [
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", blurred_bg,
                ]
                
                if not no_webcam:
                    ffmpeg_command.append("-i")
                    ffmpeg_command.append(webcam_path)
                else:
                    # Add a dummy input for consistency in filter_complex indexing
                    ffmpeg_command.append("-f")
                    ffmpeg_command.append("lavfi")
                    ffmpeg_command.append("-i")
                    ffmpeg_command.append("color=c=black:s=16x16:r=30")
                
                ffmpeg_command.extend([
                    "-i", gameplay_path,
                    "-i", killfeed_path,
                    "-filter_complex", ";".join(filter_complex),
                    "-map", "[v]", "-map", "2:a",
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M",
                    "-c:a", "aac", "-b:a", "192k",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    "-s", f"{output_width}x{output_height}",
                    output_path
                ])
                
                subprocess.run(ffmpeg_command, check=True)
                logger.info(f"Created shorts video: {output_path}")
                return output_path
            except subprocess.CalledProcessError as e:
                logger.error(f"Error executing FFmpeg command: {str(e)}")
                logger.error(f"Filter complex: {';'.join(filter_complex)}")
                return None

async def _concatenate_videos_ffmpeg(input_files: List[str]) -> Optional[str]:
    """Concatenate multiple video files into a single temporary file using ffmpeg.
    
    Videos are concatenated in the exact order provided in the input_files list.
    """
    if not input_files or len(input_files) < 2: # No need to concatenate if less than 2 files
        return input_files[0] if input_files else None

    # Create a temporary file for ffmpeg's file list
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as tmp_filelist:
        # Write each video path to the file list in the order provided
        for video_file in input_files:
            abs_video_path = os.path.abspath(video_file)
            # Ensure path escaping for ffmpeg if necessary, though quotes should handle most cases.
            # For 'file' directive, paths with special characters might need careful handling.
            # Using forward slashes is generally safer with ffmpeg's concat demuxer.
            safe_path = abs_video_path.replace("\\\\", "/").replace("\\", "/")
            tmp_filelist.write(f"file '{safe_path}'\n")
        filelist_path = tmp_filelist.name
    
    concatenated_video_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    output_path = concatenated_video_temp_file.name
    concatenated_video_temp_file.close()

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", filelist_path,
        "-c", "copy",
        output_path
    ]
    
    logger.info(f"Attempting to concatenate videos: {input_files} into {output_path}")
    try:
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg concatenation failed. Return code: {process.returncode}")
            logger.error(f"FFmpeg stdout: {stdout.decode(errors='ignore') if stdout else 'N/A'}")
            logger.error(f"FFmpeg stderr: {stderr.decode(errors='ignore') if stderr else 'N/A'}")
            if os.path.exists(output_path): os.remove(output_path)
            final_output_path = None
        else:
            logger.info(f"Successfully concatenated videos into {output_path}")
            final_output_path = output_path
            
    except Exception as e:
        logger.error(f"Error during video concatenation: {str(e)}")
        if os.path.exists(output_path): os.remove(output_path)
        final_output_path = None
    finally:
        if os.path.exists(filelist_path): os.remove(filelist_path)

    return final_output_path

async def process_video(video_path_for_highlight_lookup: str, video_path_for_short_creation: str, output_path: Optional[str] = None, no_webcam: bool = False, add_subtitles: bool = False, provided_highlights: List[Dict[str, Any]] = None, is_concatenated: bool = False):
    """Process a single video to create a shorts video, using metadata from one path and media from another."""
    try:
        if not os.path.exists(video_path_for_short_creation):
            logger.error(f"Video file for short creation not found: {video_path_for_short_creation}")
            return False
        if not os.path.exists(video_path_for_highlight_lookup):
            logger.error(f"Video file for highlight lookup not found: {video_path_for_highlight_lookup}")
            return False
        
        analysis_tracker = AnalysisTracker()
        creator = ShortsCreator()
        
        # Clean up any temporary files at the end
        temp_files_to_clean = []

        # If this is a concatenated video, we'll use the entire video instead of extracting highlights
        if is_concatenated:
            logger.info(f"Processing concatenated video as a whole: {os.path.basename(video_path_for_short_creation)}")
            
            # Get video duration
            try:
                duration_str = subprocess.check_output([
                    "ffprobe", 
                    "-v", "error", 
                    "-show_entries", "format=duration", 
                    "-of", "default=noprint_wrappers=1:nokey=1", 
                    video_path_for_short_creation
                ]).decode().strip()
                duration = float(duration_str)
                
                # Use entire video
                start_time = 0
                end_time = int(duration)
                
                logger.info(f"Using entire concatenated video duration: {end_time} seconds")
                
                # If the video is too long for a short, suggest clipping
                if end_time > 60:
                    logger.warning(f"Concatenated video is {end_time} seconds long, which exceeds the typical 60-second limit for shorts")
                
                result = await creator.create_shorts_video(
                    video_path_for_short_creation, start_time, end_time, output_path, no_webcam, add_subtitles, True
                )
                return result is not None
                
            except Exception as e:
                logger.error(f"Error getting duration for concatenated video: {str(e)}")
                return False
        
        # Regular highlight extraction for non-concatenated videos
        abs_lookup_path = os.path.abspath(video_path_for_highlight_lookup)
        highlights_to_use = provided_highlights

        if not highlights_to_use and analysis_tracker.is_clip_analyzed(abs_lookup_path):
            logger.info(f"Found existing analysis for {os.path.basename(abs_lookup_path)} via AnalysisTracker.")
            highlights_to_use = analysis_tracker.get_clip_results(abs_lookup_path)
            if not highlights_to_use:
                 logger.warning(f"AnalysisTracker reported clip as analyzed, but no highlights were retrieved for {os.path.basename(abs_lookup_path)}. Re-analyzing.")
                 # Fall through to analysis block
        
        if not highlights_to_use:
            logger.info(f"No existing valid highlights for {os.path.basename(abs_lookup_path)} via AnalysisTracker. Analyzing video...")
            try:
                # video_analysis.analyze_video returns (highlights_list, token_data_dict)
                newly_analyzed_highlights, _ = await video_analysis.analyze_video(
                    video_path=abs_lookup_path, 
                    output_file=None  # Prevent analyze_video from writing to its default file
                )

                if newly_analyzed_highlights:
                    logger.info(f"Successfully analyzed {os.path.basename(abs_lookup_path)}, found {len(newly_analyzed_highlights)} highlights.")
                    analysis_tracker.mark_clip_as_analyzed(abs_lookup_path, newly_analyzed_highlights)
                    analysis_tracker.save_analyzed_clips()
                    logger.info(f"Saved new highlights for {os.path.basename(abs_lookup_path)} using AnalysisTracker.")
                    highlights_to_use = newly_analyzed_highlights
                else:
                    logger.error(f"Analysis of {os.path.basename(abs_lookup_path)} yielded no highlights.")
                    return False
            except Exception as e:
                logger.error(f"Error during analysis of {os.path.basename(abs_lookup_path)}: {str(e)}")
                return False
        
        if highlights_to_use:
            # Using the first highlight found
            if not isinstance(highlights_to_use, list) or not highlights_to_use:
                logger.error(f"Highlights for {os.path.basename(abs_lookup_path)} are not in the expected format or empty. Cannot create short.")
                return False

            first_highlight = highlights_to_use[0]
            start_time = first_highlight.get("timestamp_start_seconds")
            end_time = first_highlight.get("timestamp_end_seconds")

            if start_time is None or end_time is None:
                logger.error(f"Highlight for {os.path.basename(abs_lookup_path)} is missing start or end time. Highlight data: {first_highlight}")
                return False
            
            logger.info(f"Creating short from '{os.path.basename(video_path_for_short_creation)}' using highlight: {first_highlight.get('clip_description')}")
            result = await creator.create_shorts_video(
                video_path_for_short_creation, start_time, end_time, output_path, no_webcam, add_subtitles, False
            )
            return result is not None
        else:
            logger.error(f"No highlights available for {os.path.basename(abs_lookup_path)} to create a short video after attempting analysis.")
            return False
    
    except Exception as e:
        logger.error(f"An error occurred in process_video for {video_path_for_highlight_lookup}: {str(e)}")
        return False
    finally:
        # Clean up any temporary filter script files
        for i in range(len(temp_files_to_clean)):
            try:
                temp_file = temp_files_to_clean[i]
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Cleaned up temporary filter script: {temp_file}")
            except Exception as e:
                logger.warning(f"Error cleaning up temporary file: {e}")

async def main_async():
    parser = argparse.ArgumentParser(description="Create a shorts-style video from analyzed clips")
    parser.add_argument("--video-path", "--video-paths", dest="video_paths", nargs='+', required=True, help="Path(s) to video file(s) to use. If multiple, they will be concatenated in the order provided.")
    parser.add_argument("--output", "-o", help="Output video path (optional)")
    parser.add_argument("--no-webcam", action="store_true", help="Create video without webcam, gameplay takes up most of the screen")
    parser.add_argument("--subtitles", action="store_true", help="Add subtitles to the video (3 words per line)")
    parser.add_argument("--keep-full", action="store_true", help="Keep the full concatenated video without extracting highlights")
    args = parser.parse_args()
    
    if not args.video_paths:
        logger.error("No video paths provided.")
        return

    actual_video_file_for_short = None
    temp_concatenated_video_path = None 
    is_concatenated = False
    highlight_clips = []
    temp_directory = None

    try:
        # Initialize analysis tracker once
        analysis_tracker = AnalysisTracker()
        
        # Create a temporary directory to store extracted highlight clips
        temp_directory = tempfile.TemporaryDirectory()
        temp_dir_path = temp_directory.name
        
        # Check if all videos have been analyzed for highlights
        videos_without_highlights = []
            
        for video_path in args.video_paths:
            abs_path = os.path.abspath(video_path)
            if not os.path.exists(abs_path):
                logger.error(f"Video file not found: {abs_path}")
                return
            
            if not analysis_tracker.is_clip_analyzed(abs_path):
                logger.info(f"Video not previously analyzed: {os.path.basename(abs_path)}")
                videos_without_highlights.append(abs_path)
        
        # Analyze any videos that don't have highlights
        if videos_without_highlights and not args.keep_full:
            logger.info(f"Analyzing {len(videos_without_highlights)} videos without highlights")
            for video_path in videos_without_highlights:
                logger.info(f"Analyzing video: {os.path.basename(video_path)}")
                try:
                    newly_analyzed_highlights, _ = await video_analysis.analyze_video(
                        video_path=video_path,
                        output_file=None  # Prevent analyze_video from writing to its default file
                    )
                    
                    if newly_analyzed_highlights:
                        logger.info(f"Successfully analyzed {os.path.basename(video_path)}, found {len(newly_analyzed_highlights)} highlights.")
                        analysis_tracker.mark_clip_as_analyzed(video_path, newly_analyzed_highlights)
                        analysis_tracker.save_analyzed_clips()
                    else:
                        logger.error(f"Analysis of {os.path.basename(video_path)} yielded no highlights.")
                        return
                except Exception as e:
                    logger.error(f"Error analyzing video {os.path.basename(video_path)}: {str(e)}")
                    return
        
        # Extract highlights from each video
        for i, video_path in enumerate(args.video_paths):
            abs_path = os.path.abspath(video_path)
            highlights = analysis_tracker.get_clip_results(abs_path)
            
            if not highlights:
                logger.warning(f"No highlights found for {os.path.basename(abs_path)}")
                continue
                
            # Use the first highlight from this video
            first_highlight = highlights[0]
            start_time = first_highlight.get("timestamp_start_seconds")
            end_time = first_highlight.get("timestamp_end_seconds")
            
            if start_time is None or end_time is None:
                logger.error(f"Highlight for {os.path.basename(abs_path)} is missing start or end time")
                continue
                
            # Create a temporary file for this highlight
            highlight_clip_path = os.path.join(temp_dir_path, f"highlight_{i}.mp4")
            
            # Extract the highlight segment
            try:
                duration = end_time - start_time
                logger.info(f"Extracting highlight from {os.path.basename(abs_path)} ({start_time}s to {end_time}s)")
                
                subprocess.run([
                    "ffmpeg", "-y", "-hwaccel", "cuda",
                    "-i", abs_path, 
                    "-ss", str(start_time), "-t", str(duration),
                    "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "30M", "-maxrate", "30M", "-bufsize", "60M", 
                    "-c:a", "aac", "-b:a", "192k",
                    highlight_clip_path
                ], check=True)
                
                highlight_clips.append(highlight_clip_path)
                logger.info(f"Extracted highlight clip to {highlight_clip_path}")
            except Exception as e:
                logger.error(f"Error extracting highlight from {os.path.basename(abs_path)}: {str(e)}")
        
        if not highlight_clips:
            logger.error("No highlight clips were extracted from any of the videos")
            return
            
        if len(highlight_clips) == 1:
            # Only one highlight clip, no need to concatenate
            actual_video_file_for_short = highlight_clips[0]
            logger.info(f"Only one highlight extracted, using it directly: {actual_video_file_for_short}")
        else:
            # Concatenate the highlight clips
            logger.info(f"Concatenating {len(highlight_clips)} highlight clips in the order provided")
            temp_concatenated_video_path = await _concatenate_videos_ffmpeg(highlight_clips)
            if not temp_concatenated_video_path:
                logger.error("Failed to concatenate highlight clips. Aborting.")
                return
            actual_video_file_for_short = temp_concatenated_video_path
            is_concatenated = True
            logger.info(f"Successfully concatenated {len(highlight_clips)} highlight clips into one file")
        
        # Now process the short video from the concatenated highlights
        creator = ShortsCreator()
        
        # Generate output path if not provided
        if args.output is None:
            export_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'exported_videos')
            os.makedirs(export_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(export_dir, f"short_{timestamp}.mp4")
        else:
            output_path = args.output
        
        logger.info(f"Creating shorts-style video from concatenated highlights")
        logger.info(f"Output path: {output_path}")
        logger.info(f"No webcam mode: {args.no_webcam}")
        logger.info(f"Add subtitles: {args.subtitles}")
        
        # Get the full duration of the concatenated video
        try:
            duration_str = subprocess.check_output([
                "ffprobe", 
                "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                actual_video_file_for_short
            ]).decode().strip()
            duration = float(duration_str)
            
            result = await creator.create_shorts_video(
                actual_video_file_for_short, 0, int(duration), output_path, args.no_webcam, args.subtitles, True
            )
            
            if result:
                logger.info(f"Successfully created shorts video from concatenated highlights at: {output_path}")
            else:
                logger.error(f"Failed to create shorts video from concatenated highlights")
        
        except Exception as e:
            logger.error(f"Error creating shorts video: {str(e)}")

    finally:
        # Clean up temporary files
        if temp_concatenated_video_path and os.path.exists(temp_concatenated_video_path):
            logger.info(f"Cleaning up temporary concatenated video: {temp_concatenated_video_path}")
            try:
                os.remove(temp_concatenated_video_path)
            except Exception as e:
                logger.error(f"Error cleaning up temporary file {temp_concatenated_video_path}: {e}")
        
        # Clean up temporary directory
        if temp_directory:
            try:
                temp_directory.cleanup()
                logger.info("Cleaned up temporary directory with highlight clips")
            except Exception as e:
                logger.error(f"Error cleaning up temporary directory: {str(e)}")

def main():
    """Entry point that runs the async main function."""
    try:
        asyncio.run(main_async())
    finally:
        # Clean up any temporary files created by the subtitle generator
        cleanup_temp_files()

if __name__ == "__main__":
    main()
