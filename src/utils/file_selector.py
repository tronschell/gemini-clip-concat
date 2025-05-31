import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import List, Optional, Dict, Tuple
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
    
    def select_prompt_types(self, video_files: List[str]) -> Dict[str, str]:
        """
        Show dialog to select prompt types for each video file.
        
        Args:
            video_files: List of video file paths
            
        Returns:
            Dictionary mapping video file paths to selected prompt types
        """
        try:
            self._init_tk()
            
            # Available prompt types
            prompt_types = [
                ("cs2", "Counter-Strike 2"),
                ("overwatch2", "Overwatch 2"),
                ("the_finals", "The Finals"),
                ("league_of_legends", "League of Legends"),
                ("kills", "Kill Feed Detection"),
                ("custom", "Custom/General")
            ]
            
            # Create dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Prompt Types")
            dialog.geometry("600x500")
            dialog.resizable(True, True)
            dialog.grab_set()  # Make dialog modal
            
            # Center the dialog
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
            y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # Main frame with scrollbar
            main_frame = ttk.Frame(dialog)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Title
            title_label = ttk.Label(main_frame, text="Select Prompt Type for Each Video", 
                                  font=("Arial", 12, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Apply to all section
            apply_all_frame = ttk.LabelFrame(main_frame, text="Apply to All", padding=10)
            apply_all_frame.pack(fill=tk.X, pady=(0, 10))
            
            apply_all_var = tk.BooleanVar()
            apply_all_checkbox = ttk.Checkbutton(apply_all_frame, text="Apply same prompt type to all videos", 
                                               variable=apply_all_var)
            apply_all_checkbox.pack(anchor=tk.W)
            
            # Global prompt type selection
            global_prompt_var = tk.StringVar(value="cs2")
            global_prompt_frame = ttk.Frame(apply_all_frame)
            global_prompt_frame.pack(fill=tk.X, pady=(5, 0))
            
            ttk.Label(global_prompt_frame, text="Prompt type:").pack(side=tk.LEFT)
            global_prompt_combo = ttk.Combobox(global_prompt_frame, textvariable=global_prompt_var, 
                                             values=[f"{code} - {name}" for code, name in prompt_types],
                                             state="readonly", width=30)
            global_prompt_combo.pack(side=tk.LEFT, padx=(5, 0))
            global_prompt_combo.set("cs2 - Counter-Strike 2")
            
            # Individual video selections frame
            videos_frame = ttk.LabelFrame(main_frame, text="Individual Video Settings", padding=10)
            videos_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            # Create scrollable frame for videos
            canvas = tk.Canvas(videos_frame)
            scrollbar = ttk.Scrollbar(videos_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Store individual prompt variables
            individual_prompt_vars = {}
            
            # Create selection for each video
            for i, video_path in enumerate(video_files):
                video_name = Path(video_path).name
                
                video_frame = ttk.Frame(scrollable_frame)
                video_frame.pack(fill=tk.X, pady=2)
                
                # Video name label
                name_label = ttk.Label(video_frame, text=f"{i+1}. {video_name}", 
                                     font=("Arial", 9))
                name_label.pack(anchor=tk.W)
                
                # Prompt type selection
                prompt_var = tk.StringVar(value="cs2")
                individual_prompt_vars[video_path] = prompt_var
                
                prompt_combo = ttk.Combobox(video_frame, textvariable=prompt_var,
                                          values=[f"{code} - {name}" for code, name in prompt_types],
                                          state="readonly", width=40)
                prompt_combo.pack(anchor=tk.W, padx=(10, 0))
                prompt_combo.set("cs2 - Counter-Strike 2")
            
            # Function to toggle individual controls based on apply_all checkbox
            def toggle_individual_controls():
                state = "disabled" if apply_all_var.get() else "readonly"
                for child in scrollable_frame.winfo_children():
                    for widget in child.winfo_children():
                        if isinstance(widget, ttk.Combobox):
                            widget.configure(state=state)
            
            apply_all_var.trace("w", lambda *args: toggle_individual_controls())
            
            # Buttons frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            result = {"cancelled": True, "prompt_types": {}}
            
            def on_ok():
                if apply_all_var.get():
                    # Apply global selection to all videos
                    global_selection = global_prompt_var.get().split(" - ")[0]
                    for video_path in video_files:
                        result["prompt_types"][video_path] = global_selection
                else:
                    # Use individual selections
                    for video_path, var in individual_prompt_vars.items():
                        selection = var.get().split(" - ")[0]
                        result["prompt_types"][video_path] = selection
                
                result["cancelled"] = False
                dialog.destroy()
            
            def on_cancel():
                result["cancelled"] = True
                dialog.destroy()
            
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=(5, 0))
            ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.RIGHT)
            
            # Wait for dialog to close
            dialog.wait_window()
            
            if result["cancelled"]:
                return {}
            
            logger.info(f"Selected prompt types for {len(result['prompt_types'])} video(s)")
            return result["prompt_types"]
            
        except Exception as e:
            logger.error(f"Error in prompt type selection: {str(e)}")
            return {}
    
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