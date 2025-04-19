"""
Database utilities for storing and retrieving bot data.
"""
import os
import json
import logging
from typing import Dict, List, Any, Optional

class Database:
    """Simple JSON file-based database."""
    
    @staticmethod
    def load_data(filename: str) -> Dict:
        """Load data from a JSON file."""
        filepath = os.path.join('data', filename)
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as file:
                    return json.load(file)
            else:
                # Return empty dict if file doesn't exist
                return {}
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from {filepath}")
            return {}
        except Exception as e:
            logging.error(f"Error loading data from {filepath}: {e}")
            return {}
    
    @staticmethod
    def save_data(filename: str, data: Dict) -> bool:
        """Save data to a JSON file."""
        filepath = os.path.join('data', filename)
        try:
            with open(filepath, 'w') as file:
                json.dump(data, file, indent=4)
            return True
        except Exception as e:
            logging.error(f"Error saving data to {filepath}: {e}")
            return False
    
    @staticmethod
    def get_guild_data(filename: str, guild_id: int) -> Dict:
        """Get data for a specific guild."""
        data = Database.load_data(filename)
        guild_id_str = str(guild_id)
        
        if guild_id_str not in data:
            data[guild_id_str] = {}
            Database.save_data(filename, data)
        
        return data[guild_id_str]
    
    @staticmethod
    def save_guild_data(filename: str, guild_id: int, guild_data: Dict) -> bool:
        """Save data for a specific guild."""
        data = Database.load_data(filename)
        guild_id_str = str(guild_id)
        
        data[guild_id_str] = guild_data
        return Database.save_data(filename, data)
    
    # Specific data management methods
    @staticmethod
    def get_warns(guild_id: int, user_id: int) -> List[Dict]:
        """Get warnings for a specific user in a guild."""
        guild_data = Database.get_guild_data('warns.json', guild_id)
        user_id_str = str(user_id)
        
        if 'warns' not in guild_data:
            guild_data['warns'] = {}
        
        if user_id_str not in guild_data['warns']:
            guild_data['warns'][user_id_str] = []
        
        return guild_data['warns'][user_id_str]
    
    @staticmethod
    def add_warn(guild_id: int, user_id: int, moderator_id: int, reason: str) -> bool:
        """Add a warning for a user."""
        guild_data = Database.get_guild_data('warns.json', guild_id)
        user_id_str = str(user_id)
        
        if 'warns' not in guild_data:
            guild_data['warns'] = {}
        
        if user_id_str not in guild_data['warns']:
            guild_data['warns'][user_id_str] = []
        
        import time
        warn = {
            'moderator_id': moderator_id,
            'reason': reason,
            'timestamp': int(time.time())
        }
        
        guild_data['warns'][user_id_str].append(warn)
        return Database.save_guild_data('warns.json', guild_id, guild_data)
    
    @staticmethod
    def clear_warns(guild_id: int, user_id: int) -> bool:
        """Clear all warnings for a user."""
        guild_data = Database.get_guild_data('warns.json', guild_id)
        user_id_str = str(user_id)
        
        if 'warns' not in guild_data:
            guild_data['warns'] = {}
        
        if user_id_str in guild_data['warns']:
            guild_data['warns'][user_id_str] = []
            return Database.save_guild_data('warns.json', guild_id, guild_data)
        
        return True
    
    @staticmethod
    def get_auto_messages(guild_id: int) -> List[Dict]:
        """Get auto messages for a guild."""
        guild_data = Database.get_guild_data('auto_messages.json', guild_id)
        
        if 'auto_messages' not in guild_data:
            guild_data['auto_messages'] = []
            Database.save_guild_data('auto_messages.json', guild_id, guild_data)
        
        return guild_data['auto_messages']
    
    @staticmethod
    def add_auto_message(guild_id: int, channel_id: int, message: str, interval: int) -> int:
        """Add an auto message for a guild, returns the message ID."""
        guild_data = Database.get_guild_data('auto_messages.json', guild_id)
        
        if 'auto_messages' not in guild_data:
            guild_data['auto_messages'] = []
        
        if 'next_id' not in guild_data:
            guild_data['next_id'] = 1
        
        message_id = guild_data['next_id']
        guild_data['next_id'] += 1
        
        auto_message = {
            'id': message_id,
            'channel_id': channel_id,
            'message': message,
            'interval': interval,
            'active': True
        }
        
        guild_data['auto_messages'].append(auto_message)
        Database.save_guild_data('auto_messages.json', guild_id, guild_data)
        
        return message_id
    
    @staticmethod
    def stop_auto_message(guild_id: int, message_id: int) -> bool:
        """Stop an auto message by setting it to inactive."""
        guild_data = Database.get_guild_data('auto_messages.json', guild_id)
        
        if 'auto_messages' not in guild_data:
            return False
        
        for msg in guild_data['auto_messages']:
            if msg['id'] == message_id:
                msg['active'] = False
                return Database.save_guild_data('auto_messages.json', guild_id, guild_data)
        
        return False
    
    @staticmethod
    def get_config(guild_id: int) -> Dict:
        """Get configuration for a guild."""
        return Database.get_guild_data('config.json', guild_id)
    
    @staticmethod
    def save_config(guild_id: int, config: Dict) -> bool:
        """Save configuration for a guild."""
        return Database.save_guild_data('config.json', guild_id, config)
    
    @staticmethod
    def get_giveaways(guild_id: int) -> List[Dict]:
        """Get active giveaways for a guild."""
        guild_data = Database.get_guild_data('giveaways.json', guild_id)
        
        if 'giveaways' not in guild_data:
            guild_data['giveaways'] = []
            Database.save_guild_data('giveaways.json', guild_id, guild_data)
        
        return guild_data['giveaways']
    
    @staticmethod
    def add_giveaway(guild_id: int, channel_id: int, message_id: int, prize: str, winners: int, end_time: int) -> bool:
        """Add a giveaway to the database."""
        guild_data = Database.get_guild_data('giveaways.json', guild_id)
        
        if 'giveaways' not in guild_data:
            guild_data['giveaways'] = []
        
        giveaway = {
            'channel_id': channel_id,
            'message_id': message_id,
            'prize': prize,
            'winners': winners,
            'end_time': end_time,
            'ended': False,
            'participants': []
        }
        
        guild_data['giveaways'].append(giveaway)
        return Database.save_guild_data('giveaways.json', guild_id, guild_data)
    
    @staticmethod
    def get_applications(guild_id: int) -> Dict:
        """Get application configurations for a guild."""
        guild_data = Database.get_guild_data('applications.json', guild_id)
        
        if 'applications' not in guild_data:
            guild_data['applications'] = {}
            Database.save_guild_data('applications.json', guild_id, guild_data)
        
        return guild_data['applications']
    
    @staticmethod
    def create_application(guild_id: int, name: str, questions: List[str]) -> bool:
        """Create an application configuration."""
        guild_data = Database.get_guild_data('applications.json', guild_id)
        
        if 'applications' not in guild_data:
            guild_data['applications'] = {}
        
        guild_data['applications'][name] = {
            'questions': questions,
            'active': True
        }
        
        return Database.save_guild_data('applications.json', guild_id, guild_data)
    
    @staticmethod
    def get_tickets(guild_id: int) -> Dict:
        """Get ticket configuration for a guild."""
        guild_data = Database.get_guild_data('tickets.json', guild_id)
        
        if 'tickets' not in guild_data:
            guild_data['tickets'] = {
                'enabled': False,
                'category_id': None,
                'log_channel_id': None,
                'support_role_id': None,
                'active_tickets': {}
            }
            Database.save_guild_data('tickets.json', guild_id, guild_data)
        
        return guild_data['tickets']
    
    @staticmethod
    def save_tickets(guild_id: int, ticket_data: Dict) -> bool:
        """Save ticket configuration for a guild."""
        guild_data = Database.get_guild_data('tickets.json', guild_id)
        guild_data['tickets'] = ticket_data
        return Database.save_guild_data('tickets.json', guild_id, guild_data)
    
    @staticmethod
    def get_invites(guild_id: int) -> Dict:
        """Get invite tracking data for a guild."""
        guild_data = Database.get_guild_data('invites.json', guild_id)
        
        if 'invites' not in guild_data:
            guild_data['invites'] = {
                'tracking': False,
                'channel_id': None,
                'members': {}
            }
            Database.save_guild_data('invites.json', guild_id, guild_data)
        
        return guild_data['invites']
    
    @staticmethod
    def save_invites(guild_id: int, invite_data: Dict) -> bool:
        """Save invite tracking data for a guild."""
        guild_data = Database.get_guild_data('invites.json', guild_id)
        guild_data['invites'] = invite_data
        return Database.save_guild_data('invites.json', guild_id, guild_data)
    
    @staticmethod
    def get_bump_data(guild_id: int) -> Dict:
        """Get bump system data for a guild."""
        guild_data = Database.get_guild_data('bump.json', guild_id)
        
        if 'bump' not in guild_data:
            guild_data['bump'] = {
                'enabled': False,
                'channel_id': None,
                'cooldown': 7200,  # 2 hours in seconds
                'last_bump': 0,
                'bump_count': 0,
                'banner': None
            }
            Database.save_guild_data('bump.json', guild_id, guild_data)
        
        return guild_data['bump']
    
    @staticmethod
    def save_bump_data(guild_id: int, bump_data: Dict) -> bool:
        """Save bump system data for a guild."""
        guild_data = Database.get_guild_data('bump.json', guild_id)
        guild_data['bump'] = bump_data
        return Database.save_guild_data('bump.json', guild_id, guild_data)
