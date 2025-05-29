import sys
import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import print as rprint

console = Console()

def setup_logging():
    """Setup logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def print_header():
    """Print application header with styling."""
    title = Text("🎮 Gemini Clip Concat", style="bold magenta")
    subtitle = Text("AI-powered gameplay video analysis tool", style="dim")
    
    panel = Panel.fit(
        f"{title}\n{subtitle}",
        border_style="bright_blue",
        padding=(1, 2)
    )
    console.print(panel)

def print_success(message: str):
    """Print success message with styling."""
    rprint(f"[bold green]✓[/bold green] {message}")

def print_error(message: str):
    """Print error message with styling."""
    rprint(f"[bold red]✗[/bold red] {message}")

def print_info(message: str):
    """Print info message with styling."""
    rprint(f"[bold blue]ℹ[/bold blue] {message}")

def show_results_table(results: list):
    """Display results in a formatted table."""
    if not results:
        print_info("No results to display")
        return
    
    table = Table(title="Processing Results", show_header=True, header_style="bold cyan")
    table.add_column("File", style="white", no_wrap=True)
    table.add_column("Status", justify="center")
    
    for result in results:
        if result:
            table.add_row(Path(result).name, "[bold green]✓ Success[/bold green]")
        else:
            table.add_row("Unknown", "[bold red]✗ Failed[/bold red]")
    
    console.print(table)

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """🎮 Gemini Clip Concat - AI-powered gameplay video analysis tool"""
    print_header()
    
    if ctx.invoked_subcommand is None:
        console.print("\n[bold yellow]Available commands:[/bold yellow]")
        console.print("  [bold cyan]watch[/bold cyan]   - Watch directory for new videos")
        console.print("  [bold cyan]process[/bold cyan] - Process video files or directory")
        console.print("  [bold cyan]analyze[/bold cyan] - Analyze video files for highlights")
        console.print("  [bold cyan]select[/bold cyan]  - Manually select videos via file dialog")
        console.print("  [bold cyan]concat[/bold cyan]  - Concatenate multiple videos with reordering")
        console.print("  [bold cyan]config[/bold cyan]  - Create config template")
        console.print("  [bold cyan]cleanup[/bold cyan] - Clean up uploaded files")
        console.print("\nUse [bold]--help[/bold] with any command for more details.")

@cli.command()
@click.option('--directory', '-d', type=str, help='Directory to watch (defaults to config setting)')
@click.option('--ignore-existing', is_flag=True, default=True, help='Ignore existing files and only process new ones')
def watch(directory: Optional[str], ignore_existing: bool):
    """Watch directory for new videos and process them automatically."""
    setup_logging()
    
    try:
        # Import here to avoid circular imports
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from kill_processor import KillProcessor
        
        processor = KillProcessor()
        
        with console.status("[bold green]Starting directory watch...", spinner="dots"):
            print_info(f"Watching directory: {directory or 'default from config'}")
            print_info(f"Ignore existing files: {ignore_existing}")
        
        processor.start_watching(directory, ignore_existing)
        
    except KeyboardInterrupt:
        print_info("Watch stopped by user")
    except Exception as e:
        print_error(f"Watch failed: {str(e)}")
        sys.exit(1)

@cli.command()
@click.argument('path', type=click.Path(exists=True))
def process(path: str):
    """Process video files or directory to extract kill highlights."""
    setup_logging()
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from kill_processor import KillProcessor
        
        processor = KillProcessor()
        file_path = Path(path)
        
        if file_path.is_file():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Processing {file_path.name}...", total=None)
                result = processor.process_single_video_sync(str(file_path))
                progress.remove_task(task)
            
            if result:
                print_success(f"Created compilation: {Path(result).name}")
            else:
                print_error("No kills found or processing failed")
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Processing directory {file_path.name}...", total=None)
                results = processor.process_directory(str(file_path))
                progress.remove_task(task)
            
            if results:
                print_success(f"Created {len(results)} compilation(s)")
                show_results_table(results)
            else:
                print_error("No videos processed successfully")
                
    except Exception as e:
        print_error(f"Processing failed: {str(e)}")
        sys.exit(1)

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--output', '-o', type=str, default='exported_metadata/highlights.json', help='Output file for highlights')
@click.option('--batch-size', '-b', type=int, help='Number of videos to process concurrently')
def analyze(path: str, output: str, batch_size: Optional[int]):
    """Analyze video files for highlights using AI."""
    setup_logging()
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.video_analysis import analyze_videos_sync
        
        file_path = Path(path)
        
        if file_path.is_file():
            # Single file
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Analyzing {file_path.name}...", total=None)
                results = analyze_videos_sync([str(file_path)], output, batch_size)
                progress.remove_task(task)
            
            if results and results[0][1]:  # Check if highlights were found
                print_success(f"Analysis complete: {len(results[0][1])} highlights found")
            else:
                print_error("No highlights found or analysis failed")
        else:
            # Directory
            video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm'}
            video_files = [
                str(f) for f in file_path.rglob('*') 
                if f.suffix.lower() in video_extensions
            ]
            
            if not video_files:
                print_error(f"No video files found in {file_path}")
                return
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"Analyzing {len(video_files)} videos...", total=None)
                results = analyze_videos_sync(video_files, output, batch_size)
                progress.remove_task(task)
            
            total_highlights = sum(len(highlights) for _, highlights in results)
            if total_highlights > 0:
                print_success(f"Analysis complete: {total_highlights} highlights found across {len(video_files)} videos")
            else:
                print_error("No highlights found in any videos")
                
    except Exception as e:
        print_error(f"Analysis failed: {str(e)}")
        sys.exit(1)

@cli.command()
def select():
    """Manually select videos via file dialog and process them."""
    setup_logging()
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from kill_processor import KillProcessor
        
        processor = KillProcessor()
        
        print_info("Starting video selection process...")
        print_info("You can process multiple batches of videos - you'll be asked after each batch if you want to continue.")
        
        results = processor.process_selected_videos()
        
        if results:
            print_success(f"All processing complete! Successfully processed {len(results)} video(s) total")
            show_results_table(results)
        else:
            print_info("No videos were processed")
            
    except Exception as e:
        print_error(f"Manual selection failed: {str(e)}")
        sys.exit(1)

@cli.command()
def concat():
    """Concatenate multiple videos with drag-and-drop reordering interface."""
    setup_logging()
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from utils.concat_gui import show_concatenation_dialog
        from utils.video_concatenator import VideoConcatenator
        from utils.config import Config
        
        print_info("Opening video selection dialog...")
        
        # Show the concatenation dialog
        selected_files = show_concatenation_dialog()
        
        if not selected_files:
            print_info("No videos selected for concatenation")
            return
        
        if len(selected_files) < 2:
            print_error("Need at least 2 videos to concatenate")
            return
        
        print_info(f"Selected {len(selected_files)} videos for concatenation")
        
        # Load config to determine if shorts should be created
        config = Config()
        create_shorts = config.make_short
        
        # Create concatenator and process videos
        concatenator = VideoConcatenator()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Concatenating videos...", total=None)
            
            # Run the concatenation asynchronously
            import asyncio
            results = asyncio.run(concatenator.concatenate_and_process(
                selected_files, 
                create_shorts=create_shorts
            ))
            
            progress.remove_task(task)
        
        if results:
            print_success(f"Successfully created {len(results)} video(s)!")
            
            # Show results
            for i, result_path in enumerate(results):
                file_name = Path(result_path).name
                if i == 0:
                    print_success(f"Regular compilation: {file_name}")
                else:
                    print_success(f"Shorts version: {file_name}")
            
            print_info(f"Videos saved to: exported_videos/")
        else:
            print_error("Failed to concatenate videos")
            sys.exit(1)
            
    except Exception as e:
        print_error(f"Concatenation failed: {str(e)}")
        sys.exit(1)

@cli.command()
@click.option('--output', '-o', type=str, default='config.json', help='Output path for config file')
def config(output: str):
    """Create a configuration template file."""
    setup_logging()
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from kill_processor import KillProcessor
        
        processor = KillProcessor()
        
        with console.status("[bold green]Creating config template...", spinner="dots"):
            processor.create_config_template(output)
        
        print_success(f"Config template created: {output}")
        
    except Exception as e:
        print_error(f"Config creation failed: {str(e)}")
        sys.exit(1)

@cli.command()
def cleanup():
    """Clean up uploaded files from Gemini Files API."""
    setup_logging()
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from kill_processor import KillProcessor
        
        processor = KillProcessor()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Cleaning up uploaded files...", total=None)
            success = processor.cleanup_uploaded_files()
            progress.remove_task(task)
        
        if success:
            print_success("File cleanup completed successfully")
        else:
            print_error("Failed to complete file cleanup")
            sys.exit(1)
            
    except Exception as e:
        print_error(f"Cleanup failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    cli() 