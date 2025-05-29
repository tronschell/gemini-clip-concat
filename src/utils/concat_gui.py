import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Optional, Callable
import logging

logger = logging.getLogger(__name__)

class DragDropListbox(tk.Listbox):
    """Listbox with drag and drop functionality for reordering items."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.bind('<Button-1>', self.on_click)
        self.bind('<B1-Motion>', self.on_drag)
        self.bind('<ButtonRelease-1>', self.on_drop)
        self.drag_start_index = None
        
    def on_click(self, event):
        """Handle mouse click to start drag operation."""
        self.drag_start_index = self.nearest(event.y)
        
    def on_drag(self, event):
        """Handle mouse drag to show visual feedback."""
        if self.drag_start_index is not None:
            current_index = self.nearest(event.y)
            if current_index != self.drag_start_index:
                # Visual feedback could be added here
                pass
                
    def on_drop(self, event):
        """Handle mouse release to complete drag operation."""
        if self.drag_start_index is not None:
            drop_index = self.nearest(event.y)
            if drop_index != self.drag_start_index and 0 <= drop_index < self.size():
                # Move the item
                item = self.get(self.drag_start_index)
                self.delete(self.drag_start_index)
                self.insert(drop_index, item)
                self.selection_clear(0, tk.END)
                self.selection_set(drop_index)
                
                # Notify parent to update the underlying file list
                if hasattr(self.master.master.master, '_on_item_moved'):
                    self.master.master.master._on_item_moved(self.drag_start_index, drop_index)
        self.drag_start_index = None

class ConcatenationGUI:
    """GUI for selecting and reordering video files for concatenation."""
    
    def __init__(self, on_concatenate: Optional[Callable[[List[str]], None]] = None):
        self.root = None
        self.video_files = []
        self.on_concatenate = on_concatenate
        self.result = None
        
    def show_dialog(self) -> Optional[List[str]]:
        """
        Show the concatenation dialog and return the ordered list of video files.
        
        Returns:
            List of video file paths in the order to concatenate, or None if cancelled
        """
        self.root = tk.Tk()
        self.root.title("Video Concatenation")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Center the window
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.root.winfo_screenheight() // 2) - (500 // 2)
        self.root.geometry(f"600x500+{x}+{y}")
        
        self._create_widgets()
        
        # Make dialog modal
        self.root.transient()
        self.root.grab_set()
        
        # Start with file selection
        self._select_files()
        
        # Run the dialog
        self.root.mainloop()
        
        return self.result
    
    def _create_widgets(self):
        """Create the GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Video Concatenation", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, pady=(0, 10))
        
        # Instructions
        instructions = ttk.Label(main_frame, 
                                text="Drag and drop to reorder videos. Left = first, Right = last.",
                                font=("Arial", 10))
        instructions.grid(row=1, column=0, pady=(0, 10))
        
        # File list frame
        list_frame = ttk.LabelFrame(main_frame, text="Selected Videos (in order)", padding="5")
        list_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Scrollable listbox with drag-drop
        list_container = ttk.Frame(list_frame)
        list_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)
        
        self.file_listbox = DragDropListbox(list_container, height=10)
        self.file_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Scrollbar for listbox
        scrollbar = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.file_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, pady=(0, 10))
        
        # Buttons
        ttk.Button(button_frame, text="Add Videos", 
                  command=self._add_videos).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Remove Selected", 
                  command=self._remove_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Clear All", 
                  command=self._clear_all).pack(side=tk.LEFT, padx=(0, 20))
        
        # Action buttons
        ttk.Button(button_frame, text="Concatenate", 
                  command=self._concatenate, style="Accent.TButton").pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="Cancel", 
                  command=self._cancel).pack(side=tk.RIGHT)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Select video files to concatenate")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=4, column=0, sticky=(tk.W, tk.E))
    
    def _select_files(self):
        """Open file dialog to select initial video files."""
        filetypes = [
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v"),
            ("MP4 files", "*.mp4"),
            ("All files", "*.*")
        ]
        
        file_paths = filedialog.askopenfilenames(
            title="Select Video Files to Concatenate",
            filetypes=filetypes,
            parent=self.root
        )
        
        if file_paths:
            self.video_files = [str(Path(fp).resolve()) for fp in file_paths]
            self._update_file_list()
            self.status_var.set(f"Selected {len(self.video_files)} video(s)")
        else:
            # If no files selected, close the dialog
            self._cancel()
    
    def _add_videos(self):
        """Add more video files to the list."""
        filetypes = [
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v"),
            ("MP4 files", "*.mp4"),
            ("All files", "*.*")
        ]
        
        file_paths = filedialog.askopenfilenames(
            title="Add More Video Files",
            filetypes=filetypes,
            parent=self.root
        )
        
        if file_paths:
            new_files = [str(Path(fp).resolve()) for fp in file_paths]
            # Avoid duplicates
            for file_path in new_files:
                if file_path not in self.video_files:
                    self.video_files.append(file_path)
            
            self._update_file_list()
            self.status_var.set(f"Total: {len(self.video_files)} video(s)")
    
    def _remove_selected(self):
        """Remove selected video from the list."""
        selection = self.file_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.video_files):
                removed_file = self.video_files.pop(index)
                self._update_file_list()
                self.status_var.set(f"Removed {Path(removed_file).name}")
    
    def _clear_all(self):
        """Clear all videos from the list."""
        if self.video_files:
            result = messagebox.askyesno("Clear All", 
                                       "Are you sure you want to remove all videos?",
                                       parent=self.root)
            if result:
                self.video_files.clear()
                self._update_file_list()
                self.status_var.set("All videos cleared")
    
    def _update_file_list(self):
        """Update the listbox with current video files."""
        self.file_listbox.delete(0, tk.END)
        for i, file_path in enumerate(self.video_files):
            filename = Path(file_path).name
            self.file_listbox.insert(tk.END, f"{i+1}. {filename}")
    
    def _on_item_moved(self, from_index: int, to_index: int):
        """Handle when an item is moved in the listbox."""
        if 0 <= from_index < len(self.video_files) and 0 <= to_index < len(self.video_files):
            # Move the file in the underlying list
            file_to_move = self.video_files.pop(from_index)
            self.video_files.insert(to_index, file_to_move)
            # Update the display to reflect the new order
            self._update_file_list()
    
    def _get_ordered_files(self) -> List[str]:
        """Get the current order of files."""
        return self.video_files.copy()
    
    def _concatenate(self):
        """Handle concatenate button click."""
        if len(self.video_files) < 2:
            messagebox.showerror("Error", 
                               "Please select at least 2 video files to concatenate.",
                               parent=self.root)
            return
        
        # Get the ordered files
        ordered_files = self._get_ordered_files()
        
        # Confirm concatenation
        file_list = "\n".join([f"{i+1}. {Path(f).name}" for i, f in enumerate(ordered_files)])
        message = f"Concatenate {len(ordered_files)} videos in this order?\n\n{file_list}"
        
        result = messagebox.askyesno("Confirm Concatenation", message, parent=self.root)
        if result:
            self.result = ordered_files
            self.root.quit()
            self.root.destroy()
    
    def _cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.root.quit()
        self.root.destroy()

def show_concatenation_dialog() -> Optional[List[str]]:
    """
    Show the concatenation dialog and return the selected video files in order.
    
    Returns:
        List of video file paths in the order to concatenate, or None if cancelled
    """
    try:
        gui = ConcatenationGUI()
        return gui.show_dialog()
    except Exception as e:
        logger.error(f"Error in concatenation dialog: {str(e)}")
        return None 