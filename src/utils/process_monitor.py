import os
import time
import logging
import psutil
from typing import Optional, Dict, Set
from threading import Thread, Event
from utils.config import Config

logger = logging.getLogger(__name__)

class GameProcessMonitor:
    """Monitor running processes to automatically detect games and switch configurations."""
    
    # Mapping of process names to game types
    GAME_PROCESS_MAP = {
        'cs2.exe': 'kills',  # CS2 uses kills detection, not cs2 prompt
        'csgo.exe': 'kills',  # CS:GO also uses kills detection
        'overwatch.exe': 'overwatch2',
        'overwatch2.exe': 'overwatch2',
        'valorant.exe': 'kills',  # Valorant can use kills detection
        'valorant-win64-shipping.exe': 'kills',
        'thefinals.exe': 'the_finals',
        'leagueoflegends.exe': 'league_of_legends',
        'league of legends.exe': 'league_of_legends',
    }
    
    def __init__(self, config: Config, check_interval: float = 5.0):
        """
        Initialize the process monitor.
        
        Args:
            config: Configuration instance to update
            check_interval: How often to check for processes (seconds)
        """
        self.config = config
        self.check_interval = check_interval
        self.current_game_type: Optional[str] = None
        self.detected_processes: Set[str] = set()
        self.monitoring = False
        self.monitor_thread: Optional[Thread] = None
        self.stop_event = Event()
        
    def get_running_game_processes(self) -> Dict[str, str]:
        """
        Get currently running game processes and their corresponding game types.
        
        Returns:
            Dictionary mapping process names to game types
        """
        running_games = {}
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    
                    # Check if this process matches any of our monitored games
                    for game_process, game_type in self.GAME_PROCESS_MAP.items():
                        if proc_name == game_process.lower():
                            running_games[game_process] = game_type
                            break
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # Process might have ended or we don't have access
                    continue
                    
        except Exception as e:
            logger.error(f"Error scanning processes: {str(e)}")
            
        return running_games
    
    def detect_active_game(self) -> Optional[str]:
        """
        Detect the currently active game and return its game type.
        
        Returns:
            Game type string if a game is detected, None otherwise
        """
        running_games = self.get_running_game_processes()
        
        if not running_games:
            return None
            
        # If multiple games are running, prioritize based on order in GAME_PROCESS_MAP
        for game_process in self.GAME_PROCESS_MAP.keys():
            if game_process in running_games:
                return running_games[game_process]
                
        return None
    
    def update_game_type(self, new_game_type: str) -> bool:
        """
        Update the configuration with the new game type.
        
        Args:
            new_game_type: The new game type to set
            
        Returns:
            True if the game type was changed, False if it was already set
        """
        if self.current_game_type == new_game_type:
            return False
            
        # Update the config's internal game type
        # Note: This is a runtime change, not persisted to config.json
        self.config._config['game_type'] = new_game_type
        self.current_game_type = new_game_type
        
        logger.info(f"🎮 Game detected: Switched to '{new_game_type}' configuration")
        return True
    
    def monitor_loop(self):
        """Main monitoring loop that runs in a separate thread."""
        logger.info(f"🔍 Starting game process monitoring (checking every {self.check_interval}s)")
        
        while not self.stop_event.wait(self.check_interval):
            try:
                detected_game_type = self.detect_active_game()
                running_games = self.get_running_game_processes()
                
                # Update detected processes for logging
                current_processes = set(running_games.keys())
                
                # Log newly detected processes
                new_processes = current_processes - self.detected_processes
                for process in new_processes:
                    game_type = running_games[process]
                    logger.info(f"🎮 Game process detected: {process} → using '{game_type}' config")
                
                # Log processes that stopped
                stopped_processes = self.detected_processes - current_processes
                for process in stopped_processes:
                    logger.info(f"🎮 Game process stopped: {process}")
                
                self.detected_processes = current_processes
                
                if detected_game_type:
                    self.update_game_type(detected_game_type)
                elif self.current_game_type:
                    # No game detected, but we had one before
                    logger.info("🎮 No game processes detected, keeping current configuration")
                    
            except Exception as e:
                logger.error(f"Error in process monitoring loop: {str(e)}")
                
        logger.info("🔍 Game process monitoring stopped")
    
    def start_monitoring(self):
        """Start monitoring game processes in a background thread."""
        if self.monitoring:
            logger.warning("Process monitoring is already running")
            return
            
        self.monitoring = True
        self.stop_event.clear()
        
        # Do an initial check
        initial_game_type = self.detect_active_game()
        if initial_game_type:
            self.update_game_type(initial_game_type)
        else:
            logger.info("🎮 No game processes detected at startup")
            
        # Start monitoring thread
        self.monitor_thread = Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop monitoring game processes."""
        if not self.monitoring:
            return
            
        logger.info("🔍 Stopping game process monitoring...")
        self.monitoring = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2.0)
            
        self.monitor_thread = None
        
    def get_current_game_info(self) -> Dict[str, str]:
        """
        Get information about the currently detected game.
        
        Returns:
            Dictionary with current game information
        """
        running_games = self.get_running_game_processes()
        
        return {
            'current_game_type': self.current_game_type or 'none',
            'detected_processes': list(self.detected_processes),
            'running_games': running_games
        } 