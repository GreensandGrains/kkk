import json
import os
import asyncio
from datetime import datetime, timedelta
import config

class DataManager:
    def __init__(self):
        self.config = config.Config()
        self.data_lock = asyncio.Lock()
        self.warns = {}
        self.temporary_channels = {}
        self.load_warns()
    
    # ===== General Data Management =====
    
    def load_warns(self):
        """Load warnings from file"""
        warn_path = os.path.join(self.config.data_folder, "warns.json")
        if os.path.exists(warn_path):
            try:
                with open(warn_path, 'r') as f:
                    self.warns = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading warns: {e}")
                self.warns = {}
    
    def save_warns(self):
        """Save warnings to file"""
        warn_path = os.path.join(self.config.data_folder, "warns.json")
        try:
            with open(warn_path, 'w') as f:
                json.dump(self.warns, f, indent=4)
            return True
        except IOError as e:
            print(f"Error saving warns: {e}")
            return False
    
    async def add_warning(self, guild_id, user_id, reason, moderator_id):
        """Add a warning to a user"""
        async with self.data_lock:
            guild_id = str(guild_id)
            user_id = str(user_id)
            
            if guild_id not in self.warns:
                self.warns[guild_id] = {}
            
            if user_id not in self.warns[guild_id]:
                self.warns[guild_id][user_id] = []
            
            warning = {
                "reason": reason,
                "moderator_id": str(moderator_id),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            self.warns[guild_id][user_id].append(warning)
            self.save_warns()
            
            return len(self.warns[guild_id][user_id])
    
    async def get_warnings(self, guild_id, user_id):
        """Get all warnings for a user"""
        guild_id, user_id = str(guild_id), str(user_id)
        
        if guild_id not in self.warns:
            return []
        
        if user_id not in self.warns[guild_id]:
            return []
        
        return self.warns[guild_id][user_id]
    
    async def clear_warnings(self, guild_id, user_id):
        """Clear all warnings for a user"""
        async with self.data_lock:
            guild_id, user_id = str(guild_id), str(user_id)
            
            if guild_id not in self.warns:
                return 0
            
            if user_id not in self.warns[guild_id]:
                return 0
            
            count = len(self.warns[guild_id][user_id])
            self.warns[guild_id][user_id] = []
            self.save_warns()
            
            return count
    
    # ===== Role Management =====
    
    def get_admin_roles(self, guild_id):
        """Get admin roles for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("admin_roles", {}).get(str(guild_id), [])
    
    def set_admin_role(self, guild_id, role_id):
        """Set an admin role for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "admin_roles" not in config_data:
            config_data["admin_roles"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["admin_roles"]:
            config_data["admin_roles"][guild_id] = []
        
        if role_id not in config_data["admin_roles"][guild_id]:
            config_data["admin_roles"][guild_id].append(role_id)
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def remove_admin_role(self, guild_id, role_id):
        """Remove an admin role from a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "admin_roles" not in config_data or guild_id not in config_data["admin_roles"]:
            return False
        
        if role_id in config_data["admin_roles"][guild_id]:
            config_data["admin_roles"][guild_id].remove(role_id)
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    def get_mod_roles(self, guild_id):
        """Get mod roles for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("mod_roles", {}).get(str(guild_id), [])
    
    def set_mod_role(self, guild_id, role_id):
        """Set a mod role for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "mod_roles" not in config_data:
            config_data["mod_roles"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["mod_roles"]:
            config_data["mod_roles"][guild_id] = []
        
        if role_id not in config_data["mod_roles"][guild_id]:
            config_data["mod_roles"][guild_id].append(role_id)
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def remove_mod_role(self, guild_id, role_id):
        """Remove a mod role from a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "mod_roles" not in config_data or guild_id not in config_data["mod_roles"]:
            return False
        
        if role_id in config_data["mod_roles"][guild_id]:
            config_data["mod_roles"][guild_id].remove(role_id)
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    # ===== Auto Message Management =====
    
    def get_auto_messages(self, guild_id):
        """Get auto messages for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("auto_messages", {}).get(str(guild_id), {})
    
    def add_auto_message(self, guild_id, channel_id, message, interval_seconds, message_id=None):
        """Add an auto message for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "auto_messages" not in config_data:
            config_data["auto_messages"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["auto_messages"]:
            config_data["auto_messages"][guild_id] = {}
        
        # Generate a unique ID if not provided
        if message_id is None:
            message_id = str(len(config_data["auto_messages"][guild_id]) + 1)
        
        config_data["auto_messages"][guild_id][message_id] = {
            "channel_id": channel_id,
            "message": message,
            "interval": interval_seconds,
            "last_sent": datetime.utcnow().isoformat(),
            "active": True
        }
        
        return self.config.save_guild_config(guild_id, config_data), message_id
    
    def remove_auto_message(self, guild_id, message_id):
        """Remove an auto message from a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "auto_messages" not in config_data or guild_id not in config_data["auto_messages"]:
            return False
        
        if message_id in config_data["auto_messages"][guild_id]:
            del config_data["auto_messages"][guild_id][message_id]
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    def toggle_auto_message(self, guild_id, message_id, active=None):
        """Toggle an auto message active/inactive"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "auto_messages" not in config_data or guild_id not in config_data["auto_messages"]:
            return False
        
        if message_id in config_data["auto_messages"][guild_id]:
            # If active is None, toggle the current value
            if active is None:
                active = not config_data["auto_messages"][guild_id][message_id].get("active", True)
            
            config_data["auto_messages"][guild_id][message_id]["active"] = active
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    def update_auto_message_timestamp(self, guild_id, message_id):
        """Update the last sent timestamp for an auto message"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "auto_messages" not in config_data or guild_id not in config_data["auto_messages"]:
            return False
        
        if message_id in config_data["auto_messages"][guild_id]:
            config_data["auto_messages"][guild_id][message_id]["last_sent"] = datetime.utcnow().isoformat()
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    # ===== Giveaway Management =====
    
    def add_giveaway(self, guild_id, channel_id, message_id, prize, end_time, host_id):
        """Add a new giveaway"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "giveaways" not in config_data:
            config_data["giveaways"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["giveaways"]:
            config_data["giveaways"][guild_id] = {}
        
        config_data["giveaways"][guild_id][str(message_id)] = {
            "channel_id": channel_id,
            "prize": prize,
            "end_time": end_time.isoformat(),
            "host_id": host_id,
            "active": True
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_giveaways(self, guild_id):
        """Get all active giveaways for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("giveaways", {}).get(str(guild_id), {})
    
    def end_giveaway(self, guild_id, message_id):
        """Mark a giveaway as ended"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "giveaways" not in config_data or guild_id not in config_data["giveaways"]:
            return False
        
        message_id = str(message_id)
        if message_id in config_data["giveaways"][guild_id]:
            config_data["giveaways"][guild_id][message_id]["active"] = False
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    # ===== Application System Management =====
    
    def create_application_system(self, guild_id, name, questions, log_channel_id, role_id=None):
        """Create a new application system"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "application_systems" not in config_data:
            config_data["application_systems"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["application_systems"]:
            config_data["application_systems"][guild_id] = {}
        
        config_data["application_systems"][guild_id][name] = {
            "questions": questions,
            "log_channel_id": log_channel_id,
            "role_id": role_id
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_application_system(self, guild_id, name):
        """Get an application system by name"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "application_systems" not in config_data or guild_id not in config_data["application_systems"]:
            return None
        
        return config_data["application_systems"][guild_id].get(name)
    
    def get_application_systems(self, guild_id):
        """Get all application systems for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("application_systems", {}).get(str(guild_id), {})
    
    def edit_application_question(self, guild_id, app_name, question_index, new_question):
        """Edit a question in an application system"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "application_systems" not in config_data or guild_id not in config_data["application_systems"]:
            return False
        
        if app_name not in config_data["application_systems"][guild_id]:
            return False
        
        if question_index < 0 or question_index >= len(config_data["application_systems"][guild_id][app_name]["questions"]):
            return False
        
        config_data["application_systems"][guild_id][app_name]["questions"][question_index] = new_question
        return self.config.save_guild_config(guild_id, config_data)
    
    def delete_application_system(self, guild_id, app_name):
        """Delete an application system"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "application_systems" not in config_data or guild_id not in config_data["application_systems"]:
            return False
        
        if app_name in config_data["application_systems"][guild_id]:
            del config_data["application_systems"][guild_id][app_name]
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    # ===== Ticket System Management =====
    
    def create_ticket_system(self, guild_id, name, description, category_id, log_channel_id, support_role_id=None):
        """Create a new ticket system"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "ticket_systems" not in config_data:
            config_data["ticket_systems"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["ticket_systems"]:
            config_data["ticket_systems"][guild_id] = {}
        
        config_data["ticket_systems"][guild_id][name] = {
            "description": description,
            "category_id": category_id,
            "log_channel_id": log_channel_id,
            "support_role_id": support_role_id,
            "ticket_count": 0
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_ticket_system(self, guild_id, name):
        """Get a ticket system by name"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "ticket_systems" not in config_data or guild_id not in config_data["ticket_systems"]:
            return None
        
        return config_data["ticket_systems"][guild_id].get(name)
    
    def get_ticket_systems(self, guild_id):
        """Get all ticket systems for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("ticket_systems", {}).get(str(guild_id), {})
    
    def increment_ticket_count(self, guild_id, system_name):
        """Increment the ticket count for a system and return the new count"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "ticket_systems" not in config_data or guild_id not in config_data["ticket_systems"]:
            return None
        
        if system_name not in config_data["ticket_systems"][guild_id]:
            return None
        
        ticket_count = config_data["ticket_systems"][guild_id][system_name].get("ticket_count", 0) + 1
        config_data["ticket_systems"][guild_id][system_name]["ticket_count"] = ticket_count
        
        if self.config.save_guild_config(guild_id, config_data):
            return ticket_count
        
        return None
    
    def delete_ticket_system(self, guild_id, system_name):
        """Delete a ticket system"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "ticket_systems" not in config_data or guild_id not in config_data["ticket_systems"]:
            return False
        
        if system_name in config_data["ticket_systems"][guild_id]:
            del config_data["ticket_systems"][guild_id][system_name]
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    # ===== Invite Tracking =====
    
    def set_invite_tracking(self, guild_id, channel_id, enabled=True):
        """Enable or disable invite tracking for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "invite_tracking" not in config_data:
            config_data["invite_tracking"] = {}
        
        guild_id = str(guild_id)
        config_data["invite_tracking"][guild_id] = {
            "enabled": enabled,
            "channel_id": channel_id
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_invite_tracking(self, guild_id):
        """Get invite tracking settings for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("invite_tracking", {}).get(str(guild_id))
    
    # ===== Tournament System =====
    
    def create_tournament(self, guild_id, name, team_size, team_count, channel_id):
        """Create a new tournament"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "tournament_systems" not in config_data:
            config_data["tournament_systems"] = {}
        
        guild_id = str(guild_id)
        if guild_id not in config_data["tournament_systems"]:
            config_data["tournament_systems"][guild_id] = {}
        
        config_data["tournament_systems"][guild_id][name] = {
            "team_size": team_size,
            "team_count": team_count,
            "channel_id": channel_id,
            "teams": {},
            "matches": [],
            "status": "registration"  # registration, ongoing, completed
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_tournament(self, guild_id, name):
        """Get a tournament by name"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "tournament_systems" not in config_data or guild_id not in config_data["tournament_systems"]:
            return None
        
        return config_data["tournament_systems"][guild_id].get(name)
    
    def get_tournaments(self, guild_id):
        """Get all tournaments for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("tournament_systems", {}).get(str(guild_id), {})
    
    def add_team_to_tournament(self, guild_id, tournament_name, team_name, member_ids):
        """Add a team to a tournament"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "tournament_systems" not in config_data or guild_id not in config_data["tournament_systems"]:
            return False
        
        if tournament_name not in config_data["tournament_systems"][guild_id]:
            return False
        
        tournament = config_data["tournament_systems"][guild_id][tournament_name]
        
        if tournament["status"] != "registration":
            return False
        
        # Validate team size
        if len(member_ids) != tournament["team_size"]:
            return False
        
        # Check if team name is unique
        if team_name in tournament["teams"]:
            return False
        
        # Check if any member is already in another team
        all_members = []
        for team in tournament["teams"].values():
            all_members.extend(team["members"])
        
        if any(member_id in all_members for member_id in member_ids):
            return False
        
        # Add the team
        tournament["teams"][team_name] = {
            "members": member_ids,
            "score": 0
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def start_tournament(self, guild_id, tournament_name):
        """Start a tournament and generate initial matches"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "tournament_systems" not in config_data or guild_id not in config_data["tournament_systems"]:
            return False
        
        if tournament_name not in config_data["tournament_systems"][guild_id]:
            return False
        
        tournament = config_data["tournament_systems"][guild_id][tournament_name]
        
        if tournament["status"] != "registration":
            return False
        
        # Check if we have enough teams
        if len(tournament["teams"]) < 2:
            return False
        
        # Generate matches
        teams = list(tournament["teams"].keys())
        matches = []
        
        # Simple round-robin for now
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                matches.append({
                    "team1": teams[i],
                    "team2": teams[j],
                    "winner": None,
                    "completed": False,
                    "match_id": len(matches) + 1
                })
        
        tournament["matches"] = matches
        tournament["status"] = "ongoing"
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def set_match_winner(self, guild_id, tournament_name, match_id, winner_team):
        """Set the winner for a match"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "tournament_systems" not in config_data or guild_id not in config_data["tournament_systems"]:
            return False
        
        if tournament_name not in config_data["tournament_systems"][guild_id]:
            return False
        
        tournament = config_data["tournament_systems"][guild_id][tournament_name]
        
        if tournament["status"] != "ongoing":
            return False
        
        # Find the match
        match_found = False
        for match in tournament["matches"]:
            if match["match_id"] == match_id:
                # Verify winner is valid
                if winner_team not in [match["team1"], match["team2"]]:
                    return False
                
                match["winner"] = winner_team
                match["completed"] = True
                match_found = True
                
                # Update the winner's score
                tournament["teams"][winner_team]["score"] += 1
                break
        
        if not match_found:
            return False
        
        # Check if all matches are complete
        all_complete = all(match["completed"] for match in tournament["matches"])
        if all_complete:
            tournament["status"] = "completed"
        
        return self.config.save_guild_config(guild_id, config_data)
    
    # ===== Bump System =====
    
    def setup_bump_system(self, guild_id, channel_id, message, cooldown_hours=24):
        """Set up a bump system for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "bump_systems" not in config_data:
            config_data["bump_systems"] = {}
        
        guild_id = str(guild_id)
        config_data["bump_systems"][guild_id] = {
            "channel_id": channel_id,
            "message": message,
            "cooldown_hours": cooldown_hours,
            "last_bump": None,
            "bump_count": 0,
            "user_bumps": {}
        }
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_bump_system(self, guild_id):
        """Get bump system for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        return config_data.get("bump_systems", {}).get(str(guild_id))
    
    def record_bump(self, guild_id, user_id):
        """Record a bump for a guild and return the new count"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id, user_id = str(guild_id), str(user_id)
        if "bump_systems" not in config_data or guild_id not in config_data["bump_systems"]:
            return None
        
        bump_system = config_data["bump_systems"][guild_id]
        
        # Update bump count
        bump_count = bump_system.get("bump_count", 0) + 1
        bump_system["bump_count"] = bump_count
        
        # Update user's bump count
        if "user_bumps" not in bump_system:
            bump_system["user_bumps"] = {}
        
        if user_id not in bump_system["user_bumps"]:
            bump_system["user_bumps"][user_id] = 0
        
        bump_system["user_bumps"][user_id] += 1
        
        # Update last bump time
        bump_system["last_bump"] = datetime.utcnow().isoformat()
        
        if self.config.save_guild_config(guild_id, config_data):
            return bump_count
        
        return None
    
    def get_user_bump_count(self, guild_id, user_id):
        """Get the number of bumps for a user"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id, user_id = str(guild_id), str(user_id)
        if "bump_systems" not in config_data or guild_id not in config_data["bump_systems"]:
            return 0
        
        bump_system = config_data["bump_systems"][guild_id]
        
        if "user_bumps" not in bump_system:
            return 0
        
        return bump_system["user_bumps"].get(user_id, 0)
    
    def clear_bump_count(self, guild_id):
        """Clear the bump count for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "bump_systems" not in config_data or guild_id not in config_data["bump_systems"]:
            return False
        
        bump_system = config_data["bump_systems"][guild_id]
        bump_system["bump_count"] = 0
        bump_system["user_bumps"] = {}
        
        return self.config.save_guild_config(guild_id, config_data)
    
    def is_bump_on_cooldown(self, guild_id):
        """Check if bump is on cooldown"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        if "bump_systems" not in config_data or guild_id not in config_data["bump_systems"]:
            return False
        
        bump_system = config_data["bump_systems"][guild_id]
        last_bump = bump_system.get("last_bump")
        
        if not last_bump:
            return False
        
        last_bump_time = datetime.fromisoformat(last_bump)
        cooldown_hours = bump_system.get("cooldown_hours", 24)
        
        return datetime.utcnow() < last_bump_time + timedelta(hours=cooldown_hours)
    
    # ===== Leveling System =====
    
    def get_leveling_config(self, guild_id):
        """Get leveling system configuration for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "leveling" not in config_data:
            config_data["leveling"] = {
                "enabled": False,
                "xp_multiplier": 1.0,
                "level_channel_id": None
            }
            self.config.save_guild_config(guild_id, config_data)
        
        return config_data["leveling"]
    
    def save_leveling_config(self, guild_id, config):
        """Save leveling system configuration for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        config_data["leveling"] = config
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_level_roles(self, guild_id):
        """Get role rewards for different levels"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "level_roles" not in config_data:
            config_data["level_roles"] = {}
            self.config.save_guild_config(guild_id, config_data)
        
        return config_data["level_roles"]
    
    def set_level_role(self, guild_id, level, role_id):
        """Set a role to be awarded at a specific level"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "level_roles" not in config_data:
            config_data["level_roles"] = {}
        
        config_data["level_roles"][str(level)] = role_id
        return self.config.save_guild_config(guild_id, config_data)
    
    def remove_level_role(self, guild_id, level):
        """Remove a role award from a specific level"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "level_roles" not in config_data:
            return False
        
        level_str = str(level)
        if level_str in config_data["level_roles"]:
            del config_data["level_roles"][level_str]
            return self.config.save_guild_config(guild_id, config_data)
        
        return False
    
    def get_user_level_data(self, guild_id, user_id):
        """Get a user's level data"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        user_id = str(user_id)
        
        if "user_levels" not in config_data:
            config_data["user_levels"] = {}
            self.config.save_guild_config(guild_id, config_data)
        
        if guild_id not in config_data["user_levels"]:
            config_data["user_levels"][guild_id] = {}
            self.config.save_guild_config(guild_id, config_data)
        
        return config_data["user_levels"][guild_id].get(user_id, {"level": 1, "xp": 0, "total_xp": 0})
    
    def get_user_level(self, guild_id, user_id):
        """Get a user's level"""
        user_data = self.get_user_level_data(guild_id, user_id)
        return user_data.get("level", 1)
    
    async def add_user_xp(self, guild_id, user_id, xp_amount):
        """Add XP to a user and level up if necessary"""
        async with self.data_lock:
            config_data = self.config.load_guild_config(guild_id)
            
            guild_id = str(guild_id)
            user_id = str(user_id)
            
            # Initialize user_levels if it doesn't exist
            if "user_levels" not in config_data:
                config_data["user_levels"] = {}
            
            if guild_id not in config_data["user_levels"]:
                config_data["user_levels"][guild_id] = {}
            
            # Initialize user if they don't exist
            if user_id not in config_data["user_levels"][guild_id]:
                config_data["user_levels"][guild_id][user_id] = {
                    "level": 1,
                    "xp": 0,
                    "total_xp": 0
                }
            
            # Get current XP and level
            current_level = config_data["user_levels"][guild_id][user_id].get("level", 1)
            current_xp = config_data["user_levels"][guild_id][user_id].get("xp", 0)
            total_xp = config_data["user_levels"][guild_id][user_id].get("total_xp", 0)
            
            # Apply XP multiplier
            xp_multiplier = config_data.get("leveling", {}).get("xp_multiplier", 1.0)
            xp_gained = int(xp_amount * xp_multiplier)
            
            # Update XP
            current_xp += xp_gained
            total_xp += xp_gained
            
            # Calculate XP needed for next level
            base_xp = 100
            xp_for_next_level = base_xp * (current_level * 1.5)
            
            # Check if user leveled up
            leveled_up = False
            while current_xp >= xp_for_next_level:
                # Level up!
                current_xp -= int(xp_for_next_level)
                current_level += 1
                leveled_up = True
                
                # Calculate new XP requirement
                xp_for_next_level = base_xp * (current_level * 1.5)
            
            # Update user data
            config_data["user_levels"][guild_id][user_id]["level"] = current_level
            config_data["user_levels"][guild_id][user_id]["xp"] = current_xp
            config_data["user_levels"][guild_id][user_id]["total_xp"] = total_xp
            
            # Save the updated data
            self.config.save_guild_config(guild_id, config_data)
            
            # Return updated user data
            return {
                "level": current_level,
                "xp": current_xp,
                "total_xp": total_xp,
                "leveled_up": leveled_up
            }
    
    def get_level_leaderboard(self, guild_id):
        """Get the level leaderboard for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        guild_id = str(guild_id)
        
        if "user_levels" not in config_data or guild_id not in config_data["user_levels"]:
            return []
        
        # Create a list of (user_id, level_data) tuples
        leaderboard = list(config_data["user_levels"][guild_id].items())
        
        # Sort by total XP (highest first)
        leaderboard.sort(key=lambda x: x[1].get("total_xp", 0), reverse=True)
        
        return leaderboard
    
    # ===== Welcome System =====
    
    def get_welcome_config(self, guild_id):
        """Get welcome message configuration for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "welcome" not in config_data:
            config_data["welcome"] = {
                "enabled": False,
                "channel_id": None,
                "message": "Welcome to the server, {user}! We hope you enjoy your stay."
            }
            self.config.save_guild_config(guild_id, config_data)
        
        return config_data["welcome"]
    
    def save_welcome_config(self, guild_id, config):
        """Save welcome message configuration for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        config_data["welcome"] = config
        return self.config.save_guild_config(guild_id, config_data)
    
    def get_goodbye_config(self, guild_id):
        """Get goodbye message configuration for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        if "goodbye" not in config_data:
            config_data["goodbye"] = {
                "enabled": False,
                "channel_id": None,
                "message": "Goodbye, {username}. We'll miss you!"
            }
            self.config.save_guild_config(guild_id, config_data)
        
        return config_data["goodbye"]
    
    def save_goodbye_config(self, guild_id, config):
        """Save goodbye message configuration for a guild"""
        config_data = self.config.load_guild_config(guild_id)
        
        config_data["goodbye"] = config
        return self.config.save_guild_config(guild_id, config_data)
