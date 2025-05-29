import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class FileSelector:
    """Cross-platform file selector using tkinter."""
    
    def __init__(self):
        self.root = None
    
    def _init_tk(self):
        """Initialize tkinter root window (hidden)."""
        if self.root is None:
            self.root = tk.Tk()
            self.root.withdraw()  # Hide the main window
    
    def select_video_files(self, title: str = "Select Video Files") -> List[str]:
        """
        Open file dialog to select multiple video files.
        
        Args:
            title: Dialog window title
            
        Returns:
            List of selected file paths
        """
        try:
            self._init_tk()
            
            # Define video file types
            filetypes = [
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v"),
                ("MP4 files", "*.mp4"),
                ("AVI files", "*.avi"),
                ("MOV files", "*.mov"),
                ("MKV files", "*.mkv"),
                ("All files", "*.*")
            ]
            
            file_paths = filedialog.askopenfilenames(
                title=title,
                filetypes=filetypes,
                multiple=True
            )
            
            # Convert to list and filter out empty strings
            selected_files = [str(Path(fp).resolve()) for fp in file_paths if fp]
            
            logger.info(f"Selected {len(selected_files)} video file(s)")
            return selected_files
            
        except Exception as e:
            logger.error(f"Error in file selection: {str(e)}")
            return []
    
    def confirm_reanalysis(self, video_path: str) -> bool:
        """
        Show confirmation dialog for re-analyzing an already processed video.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            True if user confirms re-analysis, False otherwise
        """
        try:
            self._init_tk()
            
            video_name = Path(video_path).name
            message = (
                f"The video '{video_name}' has already been analyzed.\n\n"
                f"Do you want to re-analyze it?"
            )
            
            result = messagebox.askyesno(
                "Re-analyze Video?",
                message,
                icon="question"
            )
            
            logger.info(f"Re-analysis confirmation for {video_name}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in confirmation dialog: {str(e)}")
            return False
    
    def confirm_continue_processing(self) -> bool:
        """
        Show confirmation dialog asking if user wants to process more videos.
        
        Returns:
            True if user wants to continue processing, False otherwise
        """
        try:
            self._init_tk()
            
            message = (
                "Would you like to process more videos?\n\n"
                "Click 'Yes' to select and process another batch of videos.\n"
                "Click 'No' to finish and exit."
            )
            
            result = messagebox.askyesno(
                "Process More Videos?",
                message,
                icon="question"
            )
            
            logger.info(f"Continue processing confirmation: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in continue processing dialog: {str(e)}")
            return False
    
    def show_info(self, title: str, message: str):
        """Show information dialog."""
        try:
            self._init_tk()
            messagebox.showinfo(title, message)
        except Exception as e:
            logger.error(f"Error showing info dialog: {str(e)}")
    
    def show_error(self, title: str, message: str):
        """Show error dialog."""
        try:
            self._init_tk()
            messagebox.showerror(title, message)
        except Exception as e:
            logger.error(f"Error showing error dialog: {str(e)}")
    
    def cleanup(self):
        """Clean up tkinter resources."""
        if self.root:
            try:
                self.root.destroy()
                self.root = None
            except Exception as e:
                logger.error(f"Error cleaning up tkinter: {str(e)}") 