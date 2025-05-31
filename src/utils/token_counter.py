import logging
import csv
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

# Get module-specific logger
logger = logging.getLogger(__name__)

# Gemini API pricing per model (USD per 1M tokens)
GEMINI_PRICING = {
    # Gemini 2.5 Flash Preview
    "gemini-2.5-flash-preview": {
        "input": {"text": 0.15, "image": 0.15, "video": 0.15, "audio": 1.00},
        "output": {"non_thinking": 0.60, "thinking": 3.50}
    },
    # Gemini 2.5 Pro Preview
    "gemini-2.5-pro-preview": {
        "input": {
            "text": {"<=200k": 1.25, ">200k": 2.50},
            "image": {"<=200k": 1.25, ">200k": 2.50},
            "video": {"<=200k": 1.25, ">200k": 2.50},
            "audio": {"<=200k": 1.25, ">200k": 2.50}
        },
        "output": {"<=200k": 10.00, ">200k": 15.00}
    },
    # Gemini 2.0 Flash
    "gemini-2.0-flash": {
        "input": {"text": 0.10, "image": 0.10, "video": 0.10, "audio": 0.70},
        "output": {"default": 0.40}
    },
    # Default pricing if model not found
    "default": {
        "input": {"text": 0.10, "image": 0.10, "video": 0.10, "audio": 0.70},
        "output": {"default": 0.40}
    }
}

def get_model_pricing(model_name: str) -> Dict[str, Any]:
    """Get pricing for a specific model, falling back to default if not found."""
    # Try to match the model name with known pricing
    for pricing_key in GEMINI_PRICING:
        if pricing_key in model_name.lower():
            return GEMINI_PRICING[pricing_key]
    return GEMINI_PRICING["default"]

def calculate_cost(model_name: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0, use_thinking_mode: bool = True) -> float:
    """
    Calculate cost based on model-specific pricing.
    
    Args:
        model_name: Name of the Gemini model
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens  
        cached_tokens: Number of cached tokens (not charged)
        use_thinking_mode: Whether thinking mode is enabled (affects output pricing for 2.5 Flash)
    """
    pricing = get_model_pricing(model_name)
    
    # Calculate input cost (video input)
    input_tokens = prompt_tokens - cached_tokens
    input_cost = 0
    
    if "gemini-2.5-pro-preview" in model_name.lower():
        # Pro preview has different pricing based on token count
        if input_tokens <= 200000:
            input_cost = (input_tokens / 1000000) * pricing["input"]["video"]["<=200k"]
        else:
            input_cost = (input_tokens / 1000000) * pricing["input"]["video"][">200k"]
            
        # Output cost also varies based on token count
        if completion_tokens <= 200000:
            output_cost = (completion_tokens / 1000000) * pricing["output"]["<=200k"]
        else:
            output_cost = (completion_tokens / 1000000) * pricing["output"][">200k"]
    else:
        # Standard pricing for other models
        input_cost = (input_tokens / 1000000) * pricing["input"]["video"]
        
        # For Flash preview, check if thinking mode is enabled
        if "gemini-2.5-flash-preview" in model_name.lower():
            if use_thinking_mode:
                output_cost = (completion_tokens / 1000000) * pricing["output"]["thinking"]
                logger.debug(f"Using thinking mode pricing for {model_name}: ${pricing['output']['thinking']}/1M tokens")
            else:
                output_cost = (completion_tokens / 1000000) * pricing["output"]["non_thinking"]
                logger.debug(f"Using non-thinking mode pricing for {model_name}: ${pricing['output']['non_thinking']}/1M tokens")
        else:
            output_cost = (completion_tokens / 1000000) * pricing["output"]["default"]
    
    total_cost = input_cost + output_cost
    logger.debug(f"Cost breakdown - Input: ${input_cost:.6f}, Output: ${output_cost:.6f}, Total: ${total_cost:.6f}")
    
    return total_cost

def generate_csv_filename(mode: str, start_time: datetime = None) -> str:
    """Generate timestamped CSV filename for token tracking."""
    if start_time is None:
        start_time = datetime.now()
    
    timestamp = start_time.strftime("%Y%m%d_%H%M%S")
    return f"token_costs_{mode}_{timestamp}.csv"

def export_token_data_to_csv(token_data: List[Dict[str, Any]], mode: str, start_time: datetime = None) -> str:
    """
    Export token usage data to CSV file in exported_metadata folder.
    
    Args:
        token_data: List of token usage dictionaries
        mode: Processing mode ('select' or 'watch')
        start_time: Start time for filename generation (defaults to current time)
        
    Returns:
        Path to the created CSV file
    """
    # Ensure exported_metadata directory exists
    output_dir = Path("exported_metadata")
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename with timestamp
    filename = generate_csv_filename(mode, start_time)
    csv_path = output_dir / filename
    
    # Define CSV fieldnames
    fieldnames = [
        "timestamp",
        "video_path", 
        "video_name",
        "status",
        "model_name",
        "game_type",
        "thinking_mode",
        "prompt_tokens",
        "completion_tokens", 
        "cached_tokens",
        "total_tokens",
        "cost_usd"
    ]
    
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write individual video data (if any)
            for data in token_data:
                # Extract video name from path
                video_path = data.get("video", "")
                video_name = Path(video_path).name if video_path and video_path != "TOTAL" else video_path
                
                # Determine if thinking mode was used based on model
                thinking_mode = data.get("thinking_mode", True if "gemini-2.5-flash-preview" in data.get("model_name", "").lower() else False)
                
                row = {
                    "timestamp": data.get("timestamp", datetime.now().isoformat()),
                    "video_path": video_path,
                    "video_name": video_name,
                    "status": data.get("status", "unknown"),
                    "model_name": data.get("model_name", ""),
                    "game_type": data.get("game_type", ""),
                    "thinking_mode": thinking_mode,
                    "prompt_tokens": data.get("prompt_tokens", 0),
                    "completion_tokens": data.get("completion_tokens", 0),
                    "cached_tokens": data.get("cached_tokens", 0),
                    "total_tokens": data.get("total_tokens", 0),
                    "cost_usd": data.get("cost", 0.0)
                }
                writer.writerow(row)
        
        if token_data:
            logger.info(f"✓ Token usage data exported to {csv_path}")
        else:
            logger.info(f"✓ Token tracking CSV initialized: {csv_path}")
        return str(csv_path)
        
    except Exception as e:
        logger.error(f"Failed to export token data to CSV: {str(e)}")
        raise

def append_token_data_to_csv(token_data: Dict[str, Any], csv_path: str) -> None:
    """
    Append a single token usage record to existing CSV file.
    
    Args:
        token_data: Token usage dictionary for a single video
        csv_path: Path to the existing CSV file
    """
    try:
        # Check if file exists
        if not Path(csv_path).exists():
            logger.warning(f"CSV file {csv_path} does not exist, creating new file")
            export_token_data_to_csv([token_data], "watch")
            return
        
        # Extract video name from path
        video_path = token_data.get("video", "")
        video_name = Path(video_path).name if video_path else ""
        
        # Prepare row data
        row = {
            "timestamp": token_data.get("timestamp", datetime.now().isoformat()),
            "video_path": video_path,
            "video_name": video_name,
            "status": token_data.get("status", "unknown"),
            "model_name": token_data.get("model_name", ""),
            "game_type": token_data.get("game_type", ""),
            "thinking_mode": token_data.get("thinking_mode", True if "gemini-2.5-flash-preview" in token_data.get("model_name", "").lower() else False),
            "prompt_tokens": token_data.get("prompt_tokens", 0),
            "completion_tokens": token_data.get("completion_tokens", 0),
            "cached_tokens": token_data.get("cached_tokens", 0),
            "total_tokens": token_data.get("total_tokens", 0),
            "cost_usd": token_data.get("cost", 0.0)
        }
        
        # Append to existing file
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                "timestamp", "video_path", "video_name", "status", "model_name", 
                "game_type", "thinking_mode", "prompt_tokens", "completion_tokens", "cached_tokens", 
                "total_tokens", "cost_usd"
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writerow(row)
        
        logger.debug(f"✓ Appended token data for {video_name} to {csv_path}")
        
    except Exception as e:
        logger.error(f"Failed to append token data to CSV: {str(e)}")
        raise

def log_token_summary(token_data: List[Dict[str, Any]]) -> None:
    """
    Log a summary of token usage and costs.
    
    Args:
        token_data: List of token usage dictionaries
    """
    if not token_data:
        logger.info("No token usage data to summarize")
        return
    
    # Filter out summary/total rows
    video_data = [data for data in token_data if data.get("video", "") != "TOTAL" and data.get("status", "") != "summary"]
    
    if not video_data:
        logger.info("No video token data to summarize")
        return
    
    # Calculate totals
    total_prompt_tokens = sum(data.get("prompt_tokens", 0) for data in video_data)
    total_completion_tokens = sum(data.get("completion_tokens", 0) for data in video_data)
    total_cached_tokens = sum(data.get("cached_tokens", 0) for data in video_data)
    total_tokens = total_prompt_tokens + total_completion_tokens
    total_cost = sum(data.get("cost", 0.0) for data in video_data)
    
    # Count successful vs failed videos
    successful_videos = len([data for data in video_data if data.get("status") == "success"])
    failed_videos = len([data for data in video_data if data.get("status") in ["error", "failed"]])
    
    # Log summary
    logger.info("=" * 50)
    logger.info("TOKEN USAGE SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Videos processed: {len(video_data)} (✓ {successful_videos} successful, ✗ {failed_videos} failed)")
    logger.info(f"Total tokens: {total_tokens:,}")
    logger.info(f"  - Input tokens: {total_prompt_tokens:,}")
    logger.info(f"  - Output tokens: {total_completion_tokens:,}")
    logger.info(f"  - Cached tokens: {total_cached_tokens:,}")
    logger.info(f"Estimated cost: ${total_cost:.4f}")
    logger.info("=" * 50) 