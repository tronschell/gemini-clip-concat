# YouTube Upload Agent

An AI-powered agent that automates video uploads to YouTube using Browser Use and Gemini Flash 2.0.

## Features

- 🤖 AI-powered browser automation using Browser Use
- 🧠 Powered by Google's Gemini Flash 2.0 model
- 🍪 Persistent browser sessions with cookie storage
- 📁 Native file dialog for video selection
- 🔐 One-time login with session persistence
- 📤 Batch video upload support

## Requirements

- Python 3.9 or higher (required for google-genai package)
- Google API Key for Gemini

## Setup

1. **Install dependencies:**
   ```bash
   pip install browser-use playwright google-genai python-dotenv
   ```

2. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

3. **Set up environment variables:**
   Create a `.env` file in the project root:
   ```
   GOOGLE_API_KEY=your_google_api_key_here
   ```

4. **Get Google API Key:**
   - Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
   - Create a new API key
   - Add it to your `.env` file

## Usage

### Command Line Interface

Run the CLI:
```bash
python src/youtube_upload_agent/cli.py
```

### Programmatic Usage

```python
import asyncio
from src.youtube_upload_agent import YouTubeUploadAgent

async def main():
    agent = YouTubeUploadAgent(headless=False)
    
    # First time: login and save session
    await agent.login_to_youtube()
    
    # Upload videos (will open file dialog)
    result = await agent.upload_videos()
    print(result)

asyncio.run(main())
```

## How It Works

1. **Custom Browser with Persistent Cookies:**
   - Creates a dedicated browser profile in `~/.config/browseruse/profiles/youtube_uploader`
   - Saves cookies and session data for future use
   - No need to login every time

2. **AI-Powered Automation:**
   - Uses Gemini Flash 2.0 via the official Google Gen AI SDK
   - Handles dynamic page elements and UI changes
   - Provides intelligent error handling and retry logic

3. **File Selection:**
   - Native OS file dialog for selecting multiple videos
   - Supports common video formats (MP4, AVI, MOV, MKV, etc.)
   - Shows file sizes and selection summary

4. **Upload Process:**
   - Navigates to YouTube Studio
   - Handles the upload workflow automatically
   - Sets videos to "Unlisted" by default
   - Provides upload status and summary

## Browser Profile Location

The agent stores browser data in:
- **Windows:** `%USERPROFILE%\.config\browseruse\profiles\youtube_uploader`
- **macOS/Linux:** `~/.config/browseruse/profiles/youtube_uploader`

## Supported Video Formats

- MP4, AVI, MOV, MKV, WMV, FLV, WebM

## Security Notes

- Browser sessions are isolated to YouTube and Google domains only
- Cookies are stored locally in your user profile
- No credentials are stored in code or logs
- Uses secure browser automation practices

## Troubleshooting

1. **"GOOGLE_API_KEY not found":**
   - Make sure you have a `.env` file with your Google API key

2. **Python version error:**
   - Ensure you have Python 3.9 or higher installed
   - The google-genai package requires Python 3.9+

3. **Browser won't start:**
   - Run `playwright install chromium` to install browser
   - Check if you have sufficient permissions

4. **Upload fails:**
   - Ensure you're logged into the correct YouTube account
   - Check video file formats and sizes
   - Verify YouTube Studio is accessible

5. **Session expired:**
   - Run the login process again (option 1 in CLI)
   - Clear browser profile if needed: delete the profile directory

## Package Updates

This agent now uses the official [google-genai](https://pypi.org/project/google-genai/) package instead of the deprecated `google-generativeai` package. The new package provides:

- Better API stability and support
- Improved error handling
- Official Google maintenance and updates
- Support for both Gemini Developer API and Vertex AI 