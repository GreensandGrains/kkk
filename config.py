import os
import json
import os.path

# Default configuration
DEFAULT_CONFIG = {
    "admin_roles": {},
    "mod_roles": {},
    "invite_tracking": {},
    "auto_messages": {},
    "giveaways": {},
    "application_systems": {},
    "ticket_systems": {},
    "tournament_systems": {},
    "bump_systems": {}
}

class Config:
    def __init__(self):
        self.data_folder = "data"
        self.ensure_data_folder()
        
    def ensure_data_folder(self):
        """Ensure data folder exists"""
        if not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)
            
    def get_guild_config_path(self, guild_id):
        """Get the file path for guild config"""
        return os.path.join(self.data_folder, f"{guild_id}.json")
    
    def load_guild_config(self, guild_id):
        """Load guild configuration from file"""
        path = self.get_guild_config_path(guild_id)
        if not os.path.exists(path):
            return self.create_guild_config(guild_id)
        
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading guild config: {e}")
            return self.create_guild_config(guild_id)
    
    def save_guild_config(self, guild_id, config_data):
        """Save guild configuration to file"""
        path = self.get_guild_config_path(guild_id)
        try:
            with open(path, 'w') as f:
                json.dump(config_data, f, indent=4)
            return True
        except IOError as e:
            print(f"Error saving guild config: {e}")
            return False
    
    def create_guild_config(self, guild_id):
        """Create default guild configuration"""
        config = DEFAULT_CONFIG.copy()
        self.save_guild_config(guild_id, config)
        return config
    
    def update_guild_config(self, guild_id, key, value):
        """Update a specific key in guild configuration"""
        config = self.load_guild_config(guild_id)
        config[key] = value
        return self.save_guild_config(guild_id, config)
    
    def get_guild_setting(self, guild_id, key, default=None):
        """Get a specific setting from guild configuration"""
        config = self.load_guild_config(guild_id)
        return config.get(key, default)

# Bot settings
EMBED_COLOR = 0x5865F2  # Discord blurple color
MAX_WARNS = 3           # Maximum warnings before automatic kick
DEFAULT_TIMEOUT = 60 * 60  # Default timeout duration (1 hour)
GIVEAWAY_CHECK_INTERVAL = 15  # Check giveaways every 15 seconds
MAX_AUTO_MESSAGES = 5   # Maximum auto messages per guild
