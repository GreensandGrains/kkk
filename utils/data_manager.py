import json
import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
import config

logger = logging.getLogger(__name__)

def create_default_files():
    """
    Create default data files if they don't exist.
    This should be called when the bot starts.
    """
    # Create data directory if it doesn't exist
    if not os.path.exists(config.DATA_DIR):
        os.makedirs(config.DATA_DIR)
        logger.info(f"Created data directory at {config.DATA_DIR}")
    
    # Default empty data for each file
    default_data = {
        config.GIVEAWAYS_FILE: {},
        config.APPLICATIONS_FILE: {},
        config.TICKETS_FILE: {},
        config.INVITES_FILE: {},
        config.AUTO_MESSAGES_FILE: {},
        config.SERVER_SETTINGS_FILE: {},
        config.WARNS_FILE: {},
        config.BUMP_FILE: {}
    }
    
    # Create each file if it doesn't exist
    for file_path, default_content in default_data.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                json.dump(default_content, f, indent=4)
            logger.info(f"Created default data file at {file_path}")

def load_data(file_path: str) -> Dict:
    """
    Load data from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dict containing the loaded data
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading data from {file_path}: {e}")
        return {}

def save_data(file_path: str, data: Dict) -> bool:
    """
    Save data to a JSON file.
    
    Args:
        file_path: Path to the JSON file
        data: Data to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving data to {file_path}: {e}")
        return False

async def get_guild_data(file_path: str, guild_id: int) -> Dict:
    """
    Get data for a specific guild from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        guild_id: ID of the guild
        
    Returns:
        Dict containing the guild data
    """
    data = load_data(file_path)
    guild_id_str = str(guild_id)
    
    if guild_id_str not in data:
        data[guild_id_str] = {}
        save_data(file_path, data)
    
    return data[guild_id_str]

async def update_guild_data(file_path: str, guild_id: int, new_data: Dict) -> bool:
    """
    Update data for a specific guild in a JSON file.
    
    Args:
        file_path: Path to the JSON file
        guild_id: ID of the guild
        new_data: New data to save
        
    Returns:
        True if successful, False otherwise
    """
    data = load_data(file_path)
    guild_id_str = str(guild_id)
    
    data[guild_id_str] = new_data
    return save_data(file_path, data)

async def add_to_guild_data(file_path: str, guild_id: int, key: str, value: Any) -> bool:
    """
    Add a key-value pair to guild data.
    
    Args:
        file_path: Path to the JSON file
        guild_id: ID of the guild
        key: Key to add
        value: Value to add
        
    Returns:
        True if successful, False otherwise
    """
    data = load_data(file_path)
    guild_id_str = str(guild_id)
    
    if guild_id_str not in data:
        data[guild_id_str] = {}
    
    data[guild_id_str][key] = value
    return save_data(file_path, data)

async def remove_from_guild_data(file_path: str, guild_id: int, key: str) -> bool:
    """
    Remove a key-value pair from guild data.
    
    Args:
        file_path: Path to the JSON file
        guild_id: ID of the guild
        key: Key to remove
        
    Returns:
        True if successful, False otherwise
    """
    data = load_data(file_path)
    guild_id_str = str(guild_id)
    
    if guild_id_str in data and key in data[guild_id_str]:
        del data[guild_id_str][key]
        return save_data(file_path, data)
    
    return False

async def get_server_setting(guild_id: int, setting: str, default=None) -> Any:
    """
    Get a server setting from the settings file.
    
    Args:
        guild_id: ID of the guild
        setting: Setting key to get
        default: Default value if setting doesn't exist
        
    Returns:
        Value of the setting
    """
    guild_data = await get_guild_data(config.SERVER_SETTINGS_FILE, guild_id)
    return guild_data.get(setting, default)

async def set_server_setting(guild_id: int, setting: str, value: Any) -> bool:
    """
    Set a server setting in the settings file.
    
    Args:
        guild_id: ID of the guild
        setting: Setting key to set
        value: Value to set
        
    Returns:
        True if successful, False otherwise
    """
    guild_data = await get_guild_data(config.SERVER_SETTINGS_FILE, guild_id)
    guild_data[setting] = value
    return await update_guild_data(config.SERVER_SETTINGS_FILE, guild_id, guild_data)
