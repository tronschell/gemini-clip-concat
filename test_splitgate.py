from src.utils.process_monitor import GameProcessMonitor
from src.utils.config import Config

# Create monitor
monitor = GameProcessMonitor(Config())

# Get running games
games = monitor.get_running_game_processes()
print("All detected games:", games)

# Check specifically for Splitgate 2
splitgate_games = [k for k, v in games.items() if v == 'splitgate2']
print("Splitgate 2 processes:", splitgate_games)

# Check if Splitgate 2 is detected as active
active_game = monitor.detect_active_game()
print("Active game type:", active_game) 