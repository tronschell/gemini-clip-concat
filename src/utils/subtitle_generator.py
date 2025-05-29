import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import subprocess

logger = logging.getLogger(__name__)

class SubtitleGenerator:
    """Generates subtitles with word-level timestamps using NVIDIA Parakeet TDT 0.6B V2."""
    
    def __init__(self):
        self.model = None
        self.device = "cpu"
        self._initialize_parakeet()
    
    def _initialize_parakeet(self):
        """Initialize Parakeet model with GPU fallback to CPU."""
        try:
            import nemo.collections.asr as nemo_asr
            import torch
            
            # Check CUDA availability and compatibility
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.info(f"✓ CUDA available with {torch.cuda.device_count()} GPU(s)")
            else:
                logger.warning("CUDA not available, using CPU")
            
            # Load Parakeet model
            logger.info("Loading NVIDIA Parakeet TDT 0.6B V2 model...")
            self.model = nemo_asr.models.ASRModel.from_pretrained(
                model_name="nvidia/parakeet-tdt-0.6b-v2"
            )
            
            # Move model to appropriate device
            if self.device == "cuda":
                self.model = self.model.to(self.device)
                logger.info("✓ Parakeet model loaded on GPU")
            else:
                logger.info("✓ Parakeet model loaded on CPU")
                
        except ImportError as e:
            logger.error(f"Failed to import NeMo toolkit: {e}")
            logger.error("Please install nemo_toolkit: pip install nemo_toolkit[asr]")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Parakeet model: {e}")
            raise

    def extract_audio(self, video_path: str) -> Optional[str]:
        """Extract audio from video using ffmpeg with hardware acceleration."""
        try:
            # Create temporary file for audio
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio.close()
            
            # Use ffmpeg with hardware acceleration for video decoding
            cmd = [
                'ffmpeg', '-y',
                '-hwaccel', 'auto',  # Auto-detect hardware acceleration
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit
                '-ar', '16000',  # 16kHz sample rate (required by Parakeet)
                '-ac', '1',  # Mono
                temp_audio.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg audio extraction failed: {result.stderr}")
                return None
            
            logger.info(f"✓ Audio extracted to: {temp_audio.name}")
            return temp_audio.name
            
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None

    def transcribe_audio(self, audio_path: str) -> Optional[Dict]:
        """Transcribe audio using Parakeet model with word-level timestamps."""
        try:
            if self.model is None:
                logger.error("Parakeet model not initialized")
                return None
            
            logger.info("Transcribing audio with Parakeet...")
            
            # Transcribe with timestamps
            try:
                output = self.model.transcribe([audio_path], timestamps=True)
            except Exception as transcribe_error:
                logger.error(f"Transcription failed: {transcribe_error}")
                # Try without timestamps as fallback
                logger.info("Attempting transcription without timestamps...")
                try:
                    output = self.model.transcribe([audio_path], timestamps=False)
                    logger.warning("Transcription succeeded without timestamps")
                except Exception as fallback_error:
                    logger.error(f"Fallback transcription also failed: {fallback_error}")
                    return None
            
            if not output or len(output) == 0:
                logger.error("No transcription output received")
                return None
            
            # Extract word-level timestamps from NeMo output
            transcription_result = output[0]
            
            # Check if timestamps are available
            if not hasattr(transcription_result, 'timestamp') or not transcription_result.timestamp:
                logger.warning("No timestamp information in transcription, using text-only fallback")
                # Create basic timestamps from text
                if transcription_result.text:
                    text_words = transcription_result.text.split()
                    words = []
                    word_duration = 0.5  # 0.5 seconds per word
                    for i, word in enumerate(text_words):
                        words.append({
                            'text': word,
                            'start': i * word_duration,
                            'end': (i + 1) * word_duration
                        })
                    
                    if words:
                        logger.info(f"✓ Created {len(words)} words with estimated timestamps")
                        return {
                            'text': transcription_result.text,
                            'words': words
                        }
                
                logger.error("No timestamp information and no text available")
                return None
            
            # Debug: Log the structure of timestamp data
            logger.info(f"Timestamp keys available: {list(transcription_result.timestamp.keys())}")
            if 'word' in transcription_result.timestamp and len(transcription_result.timestamp['word']) > 0:
                sample_word = transcription_result.timestamp['word'][0]
                logger.info(f"Sample word timestamp structure: {sample_word}")
            
            # Extract words with timestamps
            words = []
            if 'word' in transcription_result.timestamp:
                for i, word_info in enumerate(transcription_result.timestamp['word']):
                    try:
                        # Handle different possible key formats from NeMo models
                        word_text = word_info.get('word', word_info.get('text', ''))
                        start_time = word_info.get('start', word_info.get('start_time', 0.0))
                        end_time = word_info.get('end', word_info.get('end_time', 0.0))
                        
                        # Skip empty words
                        if not word_text:
                            logger.warning(f"Skipping word {i} with empty text")
                            continue
                        
                        words.append({
                            'text': word_text,
                            'start': float(start_time),
                            'end': float(end_time)
                        })
                    except Exception as e:
                        logger.error(f"Error processing word {i}: {e}, word_info: {word_info}")
                        continue
            
            # If no word-level timestamps, try segment-level timestamps
            if not words and 'segment' in transcription_result.timestamp:
                logger.info("No word-level timestamps found, using segment-level timestamps")
                for i, segment_info in enumerate(transcription_result.timestamp['segment']):
                    try:
                        segment_text = segment_info.get('segment', segment_info.get('text', ''))
                        start_time = segment_info.get('start', segment_info.get('start_time', 0.0))
                        end_time = segment_info.get('end', segment_info.get('end_time', 0.0))
                        
                        if segment_text:
                            # Split segment into individual words for compatibility
                            segment_words = segment_text.split()
                            if segment_words:
                                word_duration = (float(end_time) - float(start_time)) / len(segment_words)
                                for j, word in enumerate(segment_words):
                                    word_start = float(start_time) + j * word_duration
                                    word_end = word_start + word_duration
                                    words.append({
                                        'text': word,
                                        'start': word_start,
                                        'end': word_end
                                    })
                    except Exception as e:
                        logger.error(f"Error processing segment {i}: {e}, segment_info: {segment_info}")
                        continue
            
            # Final fallback: create basic timestamps from full text
            if not words and transcription_result.text:
                logger.warning("No timestamps available, creating basic word timing from full text")
                text_words = transcription_result.text.split()
                if text_words:
                    # Estimate 0.5 seconds per word as a basic fallback
                    word_duration = 0.5
                    for i, word in enumerate(text_words):
                        words.append({
                            'text': word,
                            'start': i * word_duration,
                            'end': (i + 1) * word_duration
                        })
            
            if not words:
                logger.error("No words or segments with timestamps found and no text available")
                return None
            
            logger.info(f"✓ Transcribed {len(words)} words with timestamps")
            
            return {
                'text': transcription_result.text,
                'words': words
            }
            
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return None

    def group_words_into_sentences(self, words: List[Dict], max_words: int = 3) -> List[Dict]:
        """Group words into sentences with specified maximum word count."""
        sentences = []
        
        for i in range(0, len(words), max_words):
            sentence_words = words[i:i + max_words]
            
            sentence = {
                'start': sentence_words[0]['start'],
                'end': sentence_words[-1]['end'],
                'text': ' '.join(word['text'] for word in sentence_words),
                'words': sentence_words
            }
            sentences.append(sentence)
        
        logger.info(f"✓ Grouped {len(words)} words into {len(sentences)} sentences")
        return sentences

    def generate_subtitles(self, video_path: str, output_path: str) -> Optional[str]:
        """Generate subtitles for video using Parakeet and GPU-accelerated rendering."""
        try:
            logger.info(f"Generating subtitles for: {video_path}")
            
            # Extract audio
            audio_path = self.extract_audio(video_path)
            if not audio_path:
                return None
            
            try:
                # Transcribe audio
                transcription = self.transcribe_audio(audio_path)
                if not transcription:
                    return None
                
                # Group words into sentences
                sentences = self.group_words_into_sentences(transcription['words'])
                
                # Create subtitle data
                subtitle_data = {
                    'sentences': sentences,
                    'full_text': transcription['text']
                }
                
                # Save subtitle data as JSON
                subtitle_json = output_path.replace('.mp4', '_subtitles.json')
                with open(subtitle_json, 'w', encoding='utf-8') as f:
                    json.dump(subtitle_data, f, indent=2, ensure_ascii=False)
                
                # Create video with subtitles using GPU acceleration
                success = self.create_gpu_subtitle_overlay(video_path, subtitle_data, output_path)
                
                if success:
                    logger.info(f"✓ Subtitles generated successfully: {output_path}")
                    return output_path
                else:
                    logger.error("Failed to create subtitle overlay")
                    return None
                    
            finally:
                # Clean up temporary audio file
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
                    
        except Exception as e:
            logger.error(f"Error generating subtitles: {e}")
            return None

    def create_gpu_subtitle_overlay(self, video_path: str, subtitle_data: Dict, output_path: str) -> bool:
        """Create subtitle overlay using GPU-accelerated FFmpeg processing."""
        try:
            # Create ASS subtitle file for better performance and styling
            ass_file = self._create_ass_subtitles(subtitle_data)
            if not ass_file:
                return False
            
            try:
                # Escape the ASS file path for FFmpeg filter
                escaped_ass_path = self._escape_path_for_ffmpeg_filter(ass_file)
                logger.info(f"Original ASS path: {ass_file}")
                logger.info(f"Escaped ASS path: {escaped_ass_path}")
                
                # Get font directory path for FFmpeg
                fonts_dir = Path(__file__).parent.parent.parent / "fonts"
                escaped_fonts_dir = self._escape_path_for_ffmpeg_filter(str(fonts_dir))
                
                # Use FFmpeg with full GPU acceleration pipeline
                cmd = [
                    'ffmpeg', '-y',
                    # Hardware acceleration for input
                    '-hwaccel', 'cuda',
                    '-hwaccel_output_format', 'cuda',
                    '-i', video_path,
                    # GPU-accelerated subtitle filter with properly escaped path and font directory
                    '-vf', f'subtitles={escaped_ass_path}:fontsdir={escaped_fonts_dir}',
                    # Hardware-accelerated encoding with NVENC
                    '-c:v', 'h264_nvenc',
                    '-preset', 'p4',  # Balanced preset
                    '-tune', 'hq',   # High quality
                    '-rc', 'vbr',    # Variable bitrate
                    '-cq', '23',     # Quality level
                    '-b:v', '5M',    # Target bitrate
                    '-maxrate', '8M', # Max bitrate
                    '-bufsize', '10M', # Buffer size
                    '-spatial_aq', '1',  # Spatial AQ
                    '-temporal_aq', '1', # Temporal AQ
                    '-rc-lookahead', '20', # Lookahead
                    '-bf', '3',      # B-frames
                    '-profile:v', 'high',
                    # Audio copy (no re-encoding)
                    '-c:a', 'copy',
                    output_path
                ]
                
                logger.info("Starting GPU-accelerated subtitle rendering...")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info("✓ GPU-accelerated subtitle rendering completed successfully")
                    return True
                else:
                    logger.warning(f"NVENC encoding failed: {result.stderr}")
                    # Fallback to CPU encoding
                    return self._fallback_cpu_encoding(video_path, ass_file, output_path)
                    
            finally:
                # Clean up ASS file
                if os.path.exists(ass_file):
                    os.unlink(ass_file)
                    
        except Exception as e:
            logger.error(f"Error creating GPU subtitle overlay: {e}")
            return False

    def _escape_path_for_ffmpeg_filter(self, path: str) -> str:
        """Escape file path for FFmpeg subtitle filter on Windows."""
        import platform
        
        if platform.system() == "Windows":
            # On Windows, FFmpeg subtitle filter requires special escaping:
            # - Each backslash needs to be escaped as \\\\
            # - Each colon needs to be escaped as \\:
            # This is due to FFmpeg's filter parsing layer
            escaped_path = path.replace('\\', '\\\\\\\\')  # Replace \ with \\\\
            escaped_path = escaped_path.replace(':', '\\\\:')  # Replace : with \\:
            return escaped_path
        else:
            # On Unix-like systems, just escape colons
            return path.replace(':', '\\:')

    def _create_ass_subtitles(self, subtitle_data: Dict) -> Optional[str]:
        """Create ASS subtitle file with word-level highlighting."""
        try:
            # Create temporary ASS file
            temp_ass = tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False, encoding='utf-8')
            
            # Get absolute path to fonts directory
            fonts_dir = Path(__file__).parent.parent.parent / "fonts"
            coolvetica_font = fonts_dir / "Coolvetica Rg.otf"
            
            # ASS file header with Coolvetica font, smaller size, thicker outline, and higher position
            temp_ass.write(f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Coolvetica Rg,36,&Hffffff,&Hffffff,&H000000,&H80000000,0,0,0,0,100,100,0,0,1,8,0,2,10,10,50,1
Style: Highlight,Coolvetica Rg,36,&Hffffff,&Hffffff,&H000000,&H80000000,0,0,0,0,100,100,0,0,1,8,0,2,10,10,50,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""")
            
            # Convert sentences to ASS events - only word-level highlights
            for sentence in subtitle_data['sentences']:
                # Create word-level highlights (white text)
                for word in sentence['words']:
                    word_start = self._seconds_to_ass_time(word['start'])
                    word_end = self._seconds_to_ass_time(word['end'])
                    word_text = word['text'].replace('\n', '\\N')
                    
                    # Create highlight effect using ASS override tags
                    highlight_text = f"{{\\c&Hffffff&}}{word_text}{{\\c&Hffffff&}}"
                    temp_ass.write(f"Dialogue: 1,{word_start},{word_end},Highlight,,0,0,0,,{highlight_text}\n")
            
            temp_ass.close()
            logger.info(f"✓ Created ASS subtitle file: {temp_ass.name}")
            return temp_ass.name
            
        except Exception as e:
            logger.error(f"Error creating ASS subtitles: {e}")
            return None

    def _seconds_to_ass_time(self, seconds: float) -> str:
        """Convert seconds to ASS time format (H:MM:SS.CC)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int((seconds % 1) * 100)
        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _fallback_cpu_encoding(self, video_path: str, ass_file: str, output_path: str) -> bool:
        """Fallback to CPU encoding if GPU encoding fails."""
        try:
            logger.info("Attempting CPU fallback encoding...")
            # Escape the ASS file path for FFmpeg filter
            escaped_ass_path = self._escape_path_for_ffmpeg_filter(ass_file)
            logger.info(f"CPU fallback - Original ASS path: {ass_file}")
            logger.info(f"CPU fallback - Escaped ASS path: {escaped_ass_path}")
            
            # Get font directory path for FFmpeg
            fonts_dir = Path(__file__).parent.parent.parent / "fonts"
            escaped_fonts_dir = self._escape_path_for_ffmpeg_filter(str(fonts_dir))
            
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-vf', f'subtitles={escaped_ass_path}:fontsdir={escaped_fonts_dir}',
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'copy',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("✓ CPU fallback encoding completed successfully")
                return True
            else:
                logger.error(f"CPU encoding also failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error in CPU fallback encoding: {e}")
            return False 