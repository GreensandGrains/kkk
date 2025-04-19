"""
Configuration utilities for the bot.
"""
import discord
from utils.db import Database

class ConfigManager:
    """Manages configuration for each guild."""
    
    @staticmethod
    def initialize_guild(guild_id: int) -> None:
        """Initialize config for a new guild."""
        config = Database.get_config(guild_id)
        
        # Set default values if they don't exist
        if 'admin_roles' not in config:
            config['admin_roles'] = []
        
        if 'mod_roles' not in config:
            config['mod_roles'] = []
        
        Database.save_config(guild_id, config)
    
    @staticmethod
    def set_admin_role(guild_id: int, role_id: int) -> bool:
        """Add a role to the list of admin roles."""
        config = Database.get_config(guild_id)
        
        if 'admin_roles' not in config:
            config['admin_roles'] = []
        
        if role_id not in config['admin_roles']:
            config['admin_roles'].append(role_id)
            return Database.save_config(guild_id, config)
        
        return True
    
    @staticmethod
    def remove_admin_role(guild_id: int, role_id: int) -> bool:
        """Remove a role from the list of admin roles."""
        config = Database.get_config(guild_id)
        
        if 'admin_roles' not in config:
            config['admin_roles'] = []
            return True
        
        if role_id in config['admin_roles']:
            config['admin_roles'].remove(role_id)
            return Database.save_config(guild_id, config)
        
        return True
    
    @staticmethod
    def set_mod_role(guild_id: int, role_id: int) -> bool:
        """Add a role to the list of mod roles."""
        config = Database.get_config(guild_id)
        
        if 'mod_roles' not in config:
            config['mod_roles'] = []
        
        if role_id not in config['mod_roles']:
            config['mod_roles'].append(role_id)
            return Database.save_config(guild_id, config)
        
        return True
    
    @staticmethod
    def remove_mod_role(guild_id: int, role_id: int) -> bool:
        """Remove a role from the list of mod roles."""
        config = Database.get_config(guild_id)
        
        if 'mod_roles' not in config:
            config['mod_roles'] = []
            return True
        
        if role_id in config['mod_roles']:
            config['mod_roles'].remove(role_id)
            return Database.save_config(guild_id, config)
        
        return True
    
    @staticmethod
    def get_admin_roles(guild_id: int) -> list:
        """Get the list of admin role IDs."""
        config = Database.get_config(guild_id)
        return config.get('admin_roles', [])
    
    @staticmethod
    def get_mod_roles(guild_id: int) -> list:
        """Get the list of mod role IDs."""
        config = Database.get_config(guild_id)
        return config.get('mod_roles', [])
    
    @staticmethod
    def set_invite_tracking(guild_id: int, enabled: bool, channel_id: int = None) -> bool:
        """Configure invite tracking for a guild."""
        invite_data = Database.get_invites(guild_id)
        
        invite_data['tracking'] = enabled
        if channel_id is not None:
            invite_data['channel_id'] = channel_id
        
        return Database.save_invites(guild_id, invite_data)
    
    @staticmethod
    def set_ticket_system(
        guild_id: int, 
        enabled: bool, 
        category_id: int = None, 
        log_channel_id: int = None, 
        support_role_id: int = None
    ) -> bool:
        """Configure ticket system for a guild."""
        ticket_data = Database.get_tickets(guild_id)
        
        ticket_data['enabled'] = enabled
        
        if category_id is not None:
            ticket_data['category_id'] = category_id
        
        if log_channel_id is not None:
            ticket_data['log_channel_id'] = log_channel_id
        
        if support_role_id is not None:
            ticket_data['support_role_id'] = support_role_id
        
        return Database.save_tickets(guild_id, ticket_data)
