# Gemini Clip Concat - AI-Powered Gaming Highlight Tool

Advanced AI-powered gameplay video analysis tool for extracting and compiling highlights using Google Gemini AI. Automatically detects kills, creates compilations, generates shorts, and supports multiple games with intelligent process monitoring.

## 🎮 Features

### Core Functionality
- **🎯 AI-Powered Kill Detection**: Uses Google Gemini 2.5 Flash to analyze gameplay videos and identify kills with precise timestamps
- **⚡ Multi-Game Support**: Dedicated prompts for CS2, Overwatch 2, The Finals, League of Legends, and custom games
- **🔄 Automatic Process Monitoring**: Detects running games and switches analysis configurations automatically
- **📁 Directory Watching**: Continuously monitors folders for new video files with intelligent file stability checking
- **🎬 Smart Clip Creation**: Creates precise highlight clips with configurable duration and overlap merging
- **🔗 Video Concatenation**: Combines multiple videos with drag-and-drop reordering interface

### Advanced Video Processing
- **📱 TikTok/YouTube Shorts Creation**: Automatically generates vertical short videos (1080x1920) with:
  - Blurred background for cinematic effect
  - Webcam overlay positioning (optional)
  - Kill feed extraction and overlay
  - GPU-accelerated processing with NVENC support
- **🎤 AI Subtitle Generation**: Uses NVIDIA Parakeet TDT 0.6B V2 for automatic subtitle generation
- **🖥️ Hardware Acceleration**: CUDA and NVENC support for faster processing
- **📊 Batch Processing**: Process multiple videos concurrently with configurable batch sizes

### User Interface & Experience
- **🎨 Rich CLI Interface**: Beautiful terminal interface with progress bars, tables, and colored output
- **📂 File Selection Dialog**: Native OS file dialogs for easy video selection
- **🔄 Interactive Concatenation**: Drag-and-drop interface for video reordering
- **📈 Processing Status**: Real-time progress tracking and detailed logging
- **🧹 Automatic Cleanup**: Manages temporary files and uploaded content

### Upload & Sharing
- **📤 YouTube Upload Agent**: AI-powered browser automation for uploading videos to YouTube
- **🍪 Session Persistence**: Maintains login sessions across uploads
- **🔐 Secure Authentication**: Browser-based login with local session storage

## 🛠️ Requirements

- **Python**: 3.12+ (required for latest AI models)
- **FFmpeg**: For video processing (with CUDA support recommended)
- **Google Gemini API Key**: For AI analysis
- **NVIDIA GPU**: Optional but recommended for hardware acceleration

## 📦 Installation

### 1. Clone Repository
```bash
git clone <repository-url>
cd gemini-clip-concat
```

### 2. Install Dependencies
```bash
# Install the package in development mode
pip install -e .

# Or install from requirements.txt
pip install -r requirements.txt
```

### 3. Install Additional Components
```bash
# Install Playwright for YouTube uploads
playwright install chromium

# Ensure FFmpeg is installed and in PATH
# Windows: Download from https://ffmpeg.org/
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

### 4. Set Up API Key
```bash
# Create .env file
echo "GOOGLE_API_KEY=your-api-key-here" > .env

# Or set environment variable
export GOOGLE_API_KEY="your-api-key-here"
```

## 🚀 Quick Start

### Create Configuration
```bash
python main.py config
```

Edit the generated `config.json`:
```json
{
  "username": "your_ingame_name",
  "game_type": "kills",
  "make_short": true,
  "shorts": {
    "no_webcam": false,
    "add_subtitles": true
  }
}
```

### Watch Directory (Recommended)
```bash
# Watch default directory from config
python main.py watch

# Watch specific directory
python main.py watch --directory "/path/to/recordings"
```

### Process Videos
```bash
# Process single video
python main.py process video.mp4

# Process entire directory
python main.py process /path/to/videos

# Interactive file selection
python main.py select

# Concatenate multiple videos
python main.py concat
```

## 🎮 Supported Games

| Game | Game Type | Features |
|------|-----------|----------|
| Counter-Strike 2 | `kills` | Kill detection, process monitoring |
| Overwatch 2 | `overwatch2` | Hero-specific analysis, ultimate tracking |
| The Finals | `the_finals` | Destruction-based highlights |
| League of Legends | `league_of_legends` | Champion kills, objectives |
| Valorant | `kills` | Agent-based kill detection |
| Custom Games | `custom` | General-purpose analysis |

### Automatic Game Detection
The tool automatically detects running games and switches configurations:
- **CS2/CS:GO**: `cs2.exe`, `csgo.exe` → `kills` mode
- **Overwatch**: `overwatch.exe`, `overwatch2.exe` → `overwatch2` mode
- **Valorant**: `valorant.exe` → `kills` mode
- **The Finals**: `thefinals.exe` → `the_finals` mode
- **League of Legends**: `leagueoflegends.exe` → `league_of_legends` mode

## ⚙️ Configuration Options

### Core Settings
```json
{
  "username": "player_name",
  "game_type": "kills",
  "model_name": "gemini-2.5-flash-preview-05-20",
  "batch_size": 5,
  "min_highlight_duration_seconds": 5,
  "max_retries": 10,
  "max_zero_highlight_retries": 3
}
```

### Shorts Configuration
```json
{
  "make_short": true,
  "shorts": {
    "no_webcam": false,
    "add_subtitles": true
  }
}
```

### Directory Watching
```json
{
  "folder_watcher": {
    "watch_directory": "/path/to/recordings",
    "polling_interval_seconds": 2,
    "process_immediately": true,
    "reprocess_analyzed_videos": false
  }
}
```

## 📁 Output Structure

```
exported_videos/
├── regular_compilations/
│   └── player_kills_compilation_20241201_143022.mp4
└── shorts/
    ├── player_short_20241201_143025.mp4
    └── player_short_20241201_143025_with_subtitles.mp4

exported_metadata/
├── kills.json
└── highlights.json

logs/
└── gemini_clip_concat.log
```

## 🎬 Video Processing Pipeline

1. **📹 Video Analysis**: AI analyzes gameplay footage for highlights
2. **⏱️ Timestamp Extraction**: Precise start/end times for each highlight
3. **✂️ Clip Creation**: Extracts individual highlight clips
4. **🔗 Overlap Merging**: Combines overlapping clips seamlessly
5. **🎞️ Compilation**: Concatenates all clips into final video
6. **📱 Shorts Generation**: Creates vertical format for social media
7. **🎤 Subtitle Addition**: Adds AI-generated subtitles (optional)

## 🔧 Advanced Usage

### Custom Game Prompts
Create custom analysis prompts for new games:

1. Create `src/utils/prompts/your_game.py`:
```python
from string import Template

HIGHLIGHT_PROMPT = Template('''
Analyze this ${game_name} gameplay for player "${username}".
Find highlights longer than ${min_highlight_duration_seconds} seconds.
Return JSON array with timestamp_start_seconds, timestamp_end_seconds, clip_description.
''')
```

2. Update `src/utils/prompts/__init__.py` to include your prompt
3. Set `"game_type": "your_game"` in config

### YouTube Upload Automation
```bash
# Set up YouTube upload agent
cd src/youtube_upload_agent
python cli.py

# Upload videos programmatically
python -c "
import asyncio
from src.youtube_upload_agent import YouTubeUploadAgent

async def upload():
    agent = YouTubeUploadAgent()
    await agent.upload_videos()

asyncio.run(upload())
"
```

### Batch Analysis
```bash
# Analyze without creating compilations
python main.py analyze /path/to/videos --output analysis.json --batch-size 10
```

## 🎯 Performance Optimization

### Hardware Acceleration
- **NVIDIA GPU**: Automatic NVENC detection for faster encoding
- **CUDA**: GPU-accelerated video processing
- **Memory Management**: Efficient handling of large video files

### Processing Tips
- Use SSD storage for faster I/O
- Enable hardware acceleration in config
- Adjust batch size based on available RAM
- Use appropriate video quality settings

## 🔍 Troubleshooting

### Common Issues

**API Key Not Found**
```bash
# Verify environment variable
echo $GOOGLE_API_KEY

# Or check .env file
cat .env
```

**FFmpeg Not Found**
```bash
# Test FFmpeg installation
ffmpeg -version

# Add to PATH if needed (Windows)
set PATH=%PATH%;C:\path\to\ffmpeg\bin
```

**No Kills Detected**
- Verify username matches in-game name exactly
- Check game_type matches your game
- Ensure video quality is sufficient for AI analysis
- Try increasing max_zero_highlight_retries

**Processing Fails**
- Check video file isn't being written to
- Verify sufficient disk space
- Review logs in `logs/` directory
- Ensure video format is supported

### Performance Issues
- Reduce batch_size for lower memory usage
- Enable hardware acceleration
- Use lower quality settings for faster processing
- Close other GPU-intensive applications

## 📊 Supported Formats

### Input Video Formats
- MP4, AVI, MOV, MKV, WMV, FLV, WebM

### Output Formats
- **Compilations**: MP4 (H.264)
- **Shorts**: MP4 (H.264, 1080x1920)
- **Subtitles**: SRT format

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Follow PEP-8 coding standards
4. Add tests for new functionality
5. Submit pull request


## 🙏 Acknowledgments

- **Google Gemini AI**: For advanced video analysis capabilities
- **NVIDIA**: For GPU acceleration and AI models
- **FFmpeg**: For video processing foundation
- **Rich**: For beautiful terminal interfaces

---

**🎮 Ready to create amazing gaming highlights? Start with `python main.py watch` and let the AI do the work!**
