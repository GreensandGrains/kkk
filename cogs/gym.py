import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List
import json
import os
import datetime

from utils import has_mod_permissions, has_admin_permissions
from data_manager import DataManager

class GymBattleModal(discord.ui.Modal, title="Gym Battle Request"):
    """Modal for submitting a gym battle request"""
    
    reason = discord.ui.TextInput(
        label="Why do you want to challenge this gym?",
        placeholder="Explain your reason for challenging...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    def __init__(self, cog, gym_id):
        super().__init__()
        self.cog = cog
        self.gym_id = gym_id
    
    async def on_submit(self, interaction: discord.Interaction):
        # Process the gym battle request
        await self.cog.process_gym_request(interaction, self.gym_id, self.reason.value)

class GymSystem(commands.Cog):
    """Gym battle system for Pokemon trainers"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.data_file = "data/gyms.json"
        self.ensure_data_file()
        self.gym_data = self.load_gym_data()
    
    def ensure_data_file(self):
        """Ensure the gym data file exists"""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, 'w') as f:
                json.dump({"gyms": {}, "battles": {}}, f)
    
    def load_gym_data(self):
        """Load gym data from file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"gyms": {}, "battles": {}}
    
    def save_gym_data(self):
        """Save gym data to file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.gym_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving gym data: {e}")
            return False
    
    def is_server_founder(self, user: discord.Member):
        """Check if a user is the founder (owner) of their server"""
        return user.id == user.guild.owner_id
    
    def get_gym(self, guild_id: int, gym_id: str):
        """Get a gym by its ID"""
        guild_id = str(guild_id)
        
        if guild_id not in self.gym_data["gyms"]:
            return None
            
        return self.gym_data["gyms"][guild_id].get(gym_id)
    
    def get_gyms(self, guild_id: int):
        """Get all gyms for a guild"""
        guild_id = str(guild_id)
        
        if guild_id not in self.gym_data["gyms"]:
            self.gym_data["gyms"][guild_id] = {}
            
        return self.gym_data["gyms"][guild_id]
    
    def create_gym(self, guild_id: int, name: str, description: str, leader_id: int, min_level: int, channel_id: int = None):
        """Create a new gym"""
        guild_id = str(guild_id)
        
        if guild_id not in self.gym_data["gyms"]:
            self.gym_data["gyms"][guild_id] = {}
        
        # Generate a gym ID (lowercase name with underscores)
        gym_id = name.lower().replace(" ", "_")
        
        # Check if gym ID already exists
        if gym_id in self.gym_data["gyms"][guild_id]:
            return False
        
        # Create gym data
        self.gym_data["gyms"][guild_id][gym_id] = {
            "name": name,
            "description": description,
            "leader_id": leader_id,
            "min_level": min_level,
            "channel_id": channel_id,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "badge_emoji": "🏅",  # Default badge emoji
            "active": True
        }
        
        self.save_gym_data()
        return gym_id
    
    def update_gym(self, guild_id: int, gym_id: str, **kwargs):
        """Update gym properties"""
        guild_id = str(guild_id)
        
        if guild_id not in self.gym_data["gyms"] or gym_id not in self.gym_data["gyms"][guild_id]:
            return False
        
        # Update specified properties
        for key, value in kwargs.items():
            self.gym_data["gyms"][guild_id][gym_id][key] = value
        
        self.save_gym_data()
        return True
    
    def delete_gym(self, guild_id: int, gym_id: str):
        """Delete a gym"""
        guild_id = str(guild_id)
        
        if guild_id not in self.gym_data["gyms"] or gym_id not in self.gym_data["gyms"][guild_id]:
            return False
        
        del self.gym_data["gyms"][guild_id][gym_id]
        self.save_gym_data()
        return True
    
    def record_battle(self, guild_id: int, gym_id: str, challenger_id: int, result: str, notes: str = None):
        """Record a gym battle result"""
        guild_id = str(guild_id)
        
        if "battles" not in self.gym_data:
            self.gym_data["battles"] = {}
            
        if guild_id not in self.gym_data["battles"]:
            self.gym_data["battles"][guild_id] = {}
        
        battle_id = f"{gym_id}_{challenger_id}_{int(datetime.datetime.utcnow().timestamp())}"
        
        self.gym_data["battles"][guild_id][battle_id] = {
            "gym_id": gym_id,
            "challenger_id": challenger_id,
            "result": result,  # "win", "loss", or "badge"
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "notes": notes
        }
        
        self.save_gym_data()
        return battle_id
    
    def get_user_badge_count(self, guild_id: int, user_id: int):
        """Get the number of gym badges a user has earned"""
        guild_id = str(guild_id)
        user_id = str(user_id)
        
        if "battles" not in self.gym_data or guild_id not in self.gym_data["battles"]:
            return 0
        
        # Count battles where the user earned a badge
        badge_count = 0
        
        for battle_data in self.gym_data["battles"][guild_id].values():
            if str(battle_data.get("challenger_id")) == user_id and battle_data.get("result") == "badge":
                badge_count += 1
        
        return badge_count
    
    def get_user_badges(self, guild_id: int, user_id: int):
        """Get the gym badges a user has earned"""
        guild_id = str(guild_id)
        user_id = str(user_id)
        
        if "battles" not in self.gym_data or guild_id not in self.gym_data["battles"]:
            return []
        
        # Find battles where the user earned a badge
        badges = []
        
        for battle_data in self.gym_data["battles"][guild_id].values():
            if str(battle_data.get("challenger_id")) == user_id and battle_data.get("result") == "badge":
                gym_id = battle_data.get("gym_id")
                if gym_id and gym_id in self.gym_data["gyms"].get(guild_id, {}):
                    badges.append(self.gym_data["gyms"][guild_id][gym_id])
        
        return badges
    
    async def process_gym_request(self, interaction: discord.Interaction, gym_id: str, reason: str):
        """Process a gym battle request"""
        # Get the gym
        gym = self.get_gym(interaction.guild.id, gym_id)
        
        if not gym:
            await interaction.response.send_message(
                "This gym no longer exists.",
                ephemeral=True
            )
            return
        
        # Check if user meets level requirement
        user_level = self.data_manager.get_user_level(interaction.guild.id, interaction.user.id)
        
        if user_level < gym.get("min_level", 1):
            await interaction.response.send_message(
                f"You need to be at least level {gym['min_level']} to challenge this gym. "
                f"Your current level is {user_level}.",
                ephemeral=True
            )
            return
        
        # Get the gym leader
        leader_id = gym.get("leader_id")
        leader = interaction.guild.get_member(leader_id) if leader_id else None
        
        # Send gym battle request to the gym channel or leader
        notification_sent = False
        
        # Try to send to gym channel first
        channel_id = gym.get("channel_id")
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                # Create request embed
                embed = discord.Embed(
                    title=f"🏆 Gym Battle Request",
                    description=f"{interaction.user.mention} wants to challenge the **{gym['name']}** gym!",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="Challenger",
                    value=f"{interaction.user.mention} (Level {user_level})",
                    inline=True
                )
                
                if leader:
                    embed.add_field(
                        name="Gym Leader",
                        value=leader.mention,
                        inline=True
                    )
                
                embed.add_field(
                    name="Reason for Challenge",
                    value=reason,
                    inline=False
                )
                
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                
                await channel.send(
                    content=f"{leader.mention if leader else 'Gym Leader'}, you have a challenger!",
                    embed=embed
                )
                notification_sent = True
        
        # If couldn't send to channel, try to DM the leader
        if not notification_sent and leader:
            try:
                # Create request embed
                embed = discord.Embed(
                    title=f"🏆 Gym Battle Request",
                    description=f"{interaction.user.mention} wants to challenge your **{gym['name']}** gym!",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="Challenger",
                    value=f"{interaction.user.mention} (Level {user_level})",
                    inline=True
                )
                
                embed.add_field(
                    name="Server",
                    value=interaction.guild.name,
                    inline=True
                )
                
                embed.add_field(
                    name="Reason for Challenge",
                    value=reason,
                    inline=False
                )
                
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                
                await leader.send(embed=embed)
                notification_sent = True
            except discord.HTTPException:
                # Couldn't DM the leader
                pass
        
        # Respond to the user
        if notification_sent:
            await interaction.response.send_message(
                f"Your challenge request for the **{gym['name']}** gym has been sent! "
                f"The gym leader will contact you to arrange the battle.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Your challenge request was submitted, but I couldn't notify the gym leader. "
                f"Please contact them directly to arrange the battle.",
                ephemeral=True
            )
    
    @app_commands.command(name="gymcreate", description="Create a new gym (Founder only)")
    @app_commands.describe(
        name="Name of the gym",
        description="Description of the gym",
        leader="The gym leader",
        min_level="Minimum level required to challenge",
        channel="Channel for gym battle requests"
    )
    async def gym_create_command(
        self, 
        interaction: discord.Interaction, 
        name: str,
        description: str,
        leader: discord.Member,
        min_level: int,
        channel: Optional[discord.TextChannel] = None
    ):
        # Check if user is founder
        if not self.is_server_founder(interaction.user):
            await interaction.response.send_message(
                "Only the server founder can create gyms.",
                ephemeral=True
            )
            return
        
        # Validate min_level
        if min_level < 1 or min_level > 100:
            await interaction.response.send_message(
                "Minimum level must be between 1 and 100.",
                ephemeral=True
            )
            return
        
        # Create the gym
        channel_id = channel.id if channel else None
        
        gym_id = self.create_gym(
            interaction.guild.id,
            name,
            description,
            leader.id,
            min_level,
            channel_id
        )
        
        if not gym_id:
            await interaction.response.send_message(
                f"A gym with a similar name already exists. Please choose a different name.",
                ephemeral=True
            )
            return
        
        # Send confirmation
        embed = discord.Embed(
            title="🏆 Gym Created",
            description=f"The **{name}** gym has been created!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Description",
            value=description,
            inline=False
        )
        
        embed.add_field(
            name="Gym Leader",
            value=leader.mention,
            inline=True
        )
        
        embed.add_field(
            name="Minimum Level",
            value=str(min_level),
            inline=True
        )
        
        if channel:
            embed.add_field(
                name="Challenge Channel",
                value=channel.mention,
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
        
        # Notify the gym leader
        try:
            leader_embed = discord.Embed(
                title="🏆 You're a Gym Leader!",
                description=f"You've been appointed as the leader of the **{name}** gym in **{interaction.guild.name}**!",
                color=discord.Color.blue()
            )
            
            leader_embed.add_field(
                name="Description",
                value=description,
                inline=False
            )
            
            leader_embed.add_field(
                name="Minimum Level",
                value=str(min_level),
                inline=True
            )
            
            if channel:
                leader_embed.add_field(
                    name="Challenge Channel",
                    value=f"#{channel.name}",
                    inline=True
                )
            
            await leader.send(embed=leader_embed)
        except discord.HTTPException:
            # Couldn't DM the leader, ignore
            pass
    
    @app_commands.command(name="gymedit", description="Edit a gym (Founder only)")
    @app_commands.describe(
        gym_id="ID of the gym to edit",
        name="New name for the gym",
        description="New description for the gym",
        leader="New gym leader",
        min_level="New minimum level required",
        channel="New channel for gym battle requests",
        badge_emoji="Badge emoji for the gym"
    )
    async def gym_edit_command(
        self, 
        interaction: discord.Interaction, 
        gym_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        leader: Optional[discord.Member] = None,
        min_level: Optional[int] = None,
        channel: Optional[discord.TextChannel] = None,
        badge_emoji: Optional[str] = None
    ):
        # Check if user is founder
        if not self.is_server_founder(interaction.user):
            await interaction.response.send_message(
                "Only the server founder can edit gyms.",
                ephemeral=True
            )
            return
        
        # Get the gym
        gym = self.get_gym(interaction.guild.id, gym_id)
        
        if not gym:
            await interaction.response.send_message(
                f"Gym with ID '{gym_id}' not found.",
                ephemeral=True
            )
            return
        
        # Validate min_level if provided
        if min_level is not None and (min_level < 1 or min_level > 100):
            await interaction.response.send_message(
                "Minimum level must be between 1 and 100.",
                ephemeral=True
            )
            return
        
        # Update gym properties
        updates = {}
        
        if name is not None:
            updates["name"] = name
        
        if description is not None:
            updates["description"] = description
        
        if leader is not None:
            updates["leader_id"] = leader.id
        
        if min_level is not None:
            updates["min_level"] = min_level
        
        if channel is not None:
            updates["channel_id"] = channel.id
        
        if badge_emoji is not None:
            updates["badge_emoji"] = badge_emoji
        
        if not updates:
            await interaction.response.send_message(
                "No changes specified. Gym remains unchanged.",
                ephemeral=True
            )
            return
        
        # Apply updates
        success = self.update_gym(interaction.guild.id, gym_id, **updates)
        
        if not success:
            await interaction.response.send_message(
                "Failed to update the gym. Please try again.",
                ephemeral=True
            )
            return
        
        # Get updated gym
        updated_gym = self.get_gym(interaction.guild.id, gym_id)
        
        # Send confirmation
        embed = discord.Embed(
            title="🏆 Gym Updated",
            description=f"The **{updated_gym['name']}** gym has been updated!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Description",
            value=updated_gym["description"],
            inline=False
        )
        
        # Get gym leader
        leader_id = updated_gym.get("leader_id")
        leader = interaction.guild.get_member(leader_id) if leader_id else None
        
        embed.add_field(
            name="Gym Leader",
            value=leader.mention if leader else "Unknown",
            inline=True
        )
        
        embed.add_field(
            name="Minimum Level",
            value=str(updated_gym.get("min_level", 1)),
            inline=True
        )
        
        embed.add_field(
            name="Badge",
            value=updated_gym.get("badge_emoji", "🏅"),
            inline=True
        )
        
        channel_id = updated_gym.get("channel_id")
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name="Challenge Channel",
                    value=channel.mention,
                    inline=True
                )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="gymdelete", description="Delete a gym (Founder only)")
    @app_commands.describe(
        gym_id="ID of the gym to delete"
    )
    async def gym_delete_command(
        self, 
        interaction: discord.Interaction, 
        gym_id: str
    ):
        # Check if user is founder
        if not self.is_server_founder(interaction.user):
            await interaction.response.send_message(
                "Only the server founder can delete gyms.",
                ephemeral=True
            )
            return
        
        # Get the gym
        gym = self.get_gym(interaction.guild.id, gym_id)
        
        if not gym:
            await interaction.response.send_message(
                f"Gym with ID '{gym_id}' not found.",
                ephemeral=True
            )
            return
        
        # Confirm deletion
        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=f"Are you sure you want to delete the **{gym['name']}** gym? This action cannot be undone.",
            color=discord.Color.red()
        )
        
        # Create view with confirmation buttons
        class ConfirmView(discord.ui.View):
            def __init__(self, timeout=60):
                super().__init__(timeout=timeout)
                self.value = None
            
            @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
            async def delete(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
                await button_interaction.response.defer()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
                await button_interaction.response.defer()
        
        view = ConfirmView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Wait for the user's response
        await view.wait()
        
        if view.value is None:
            await interaction.edit_original_response(
                content="Deletion timed out. The gym was not deleted.",
                embed=None,
                view=None
            )
            return
        
        if not view.value:
            await interaction.edit_original_response(
                content="Deletion cancelled. The gym was not deleted.",
                embed=None,
                view=None
            )
            return
        
        # Delete the gym
        success = self.delete_gym(interaction.guild.id, gym_id)
        
        if not success:
            await interaction.edit_original_response(
                content="Failed to delete the gym. Please try again.",
                embed=None,
                view=None
            )
            return
        
        await interaction.edit_original_response(
            content=f"The **{gym['name']}** gym has been deleted.",
            embed=None,
            view=None
        )
    
    @app_commands.command(name="gyms", description="List all gyms in the server")
    async def gyms_command(self, interaction: discord.Interaction):
        # Get all gyms
        gyms = self.get_gyms(interaction.guild.id)
        
        if not gyms:
            await interaction.response.send_message(
                "There are no gyms in this server yet.",
                ephemeral=True
            )
            return
        
        # Create embed for gym list
        embed = discord.Embed(
            title="🏆 Server Gyms",
            description=f"There are **{len(gyms)}** gyms in this server:",
            color=discord.Color.blue()
        )
        
        # Add gyms to embed
        for gym_id, gym in gyms.items():
            if not gym.get("active", True):
                continue  # Skip inactive gyms
                
            # Get gym leader
            leader_id = gym.get("leader_id")
            leader = interaction.guild.get_member(leader_id) if leader_id else None
            
            value = f"Leader: {leader.mention if leader else 'Unknown'}\n"
            value += f"Min Level: {gym.get('min_level', 1)}\n"
            value += f"Badge: {gym.get('badge_emoji', '🏅')}\n"
            value += f"ID: `{gym_id}`"
            
            embed.add_field(
                name=gym.get("name", "Unknown Gym"),
                value=value,
                inline=True
            )
        
        embed.set_footer(text="Use /gym <id> to view details about a specific gym")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="gym", description="View details of a specific gym")
    @app_commands.describe(
        gym_id="ID of the gym to view"
    )
    async def gym_command(
        self, 
        interaction: discord.Interaction, 
        gym_id: str
    ):
        # Get the gym
        gym = self.get_gym(interaction.guild.id, gym_id)
        
        if not gym:
            await interaction.response.send_message(
                f"Gym with ID '{gym_id}' not found.",
                ephemeral=True
            )
            return
        
        # Create embed for gym details
        embed = discord.Embed(
            title=f"🏆 {gym.get('name', 'Unknown Gym')}",
            description=gym.get("description", "No description provided."),
            color=discord.Color.blue()
        )
        
        # Get gym leader
        leader_id = gym.get("leader_id")
        leader = interaction.guild.get_member(leader_id) if leader_id else None
        
        embed.add_field(
            name="Gym Leader",
            value=leader.mention if leader else "Unknown",
            inline=True
        )
        
        embed.add_field(
            name="Minimum Level",
            value=str(gym.get("min_level", 1)),
            inline=True
        )
        
        embed.add_field(
            name="Badge",
            value=gym.get("badge_emoji", "🏅"),
            inline=True
        )
        
        # Add challenge channel if it exists
        channel_id = gym.get("channel_id")
        if channel_id:
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                embed.add_field(
                    name="Challenge Channel",
                    value=channel.mention,
                    inline=True
                )
        
        # Add button to challenge the gym
        class ChallengeView(discord.ui.View):
            def __init__(self, cog, gym_id, timeout=180):
                super().__init__(timeout=timeout)
                self.cog = cog
                self.gym_id = gym_id
            
            @discord.ui.button(label="Challenge Gym", style=discord.ButtonStyle.primary, emoji="⚔️")
            async def challenge(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                # Open modal for challenge submission
                await button_interaction.response.send_modal(GymBattleModal(self.cog, self.gym_id))
        
        # Check if user meets the level requirement
        user_level = self.data_manager.get_user_level(interaction.guild.id, interaction.user.id)
        if user_level >= gym.get("min_level", 1):
            view = ChallengeView(self, gym_id)
            embed.set_footer(text=f"Click the Challenge Gym button to request a battle!")
        else:
            view = None
            embed.set_footer(text=f"You need to be level {gym.get('min_level', 1)} to challenge this gym. Your current level is {user_level}.")
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="gymbattle", description="Record a gym battle result (Gym Leaders only)")
    @app_commands.describe(
        challenger="The user who challenged the gym",
        result="The result of the battle",
        notes="Optional notes about the battle"
    )
    @app_commands.choices(result=[
        app_commands.Choice(name="Win (Leader won)", value="win"),
        app_commands.Choice(name="Loss (Challenger won)", value="loss"),
        app_commands.Choice(name="Badge Awarded", value="badge")
    ])
    async def gym_battle_command(
        self, 
        interaction: discord.Interaction, 
        challenger: discord.Member,
        result: str,
        notes: Optional[str] = None
    ):
        # Get gyms where the user is a leader
        gyms = self.get_gyms(interaction.guild.id)
        user_gyms = []
        
        for gym_id, gym in gyms.items():
            if gym.get("leader_id") == interaction.user.id:
                user_gyms.append((gym_id, gym))
        
        if not user_gyms:
            await interaction.response.send_message(
                "You are not a gym leader in this server.",
                ephemeral=True
            )
            return
        
        # If user is leader of multiple gyms, ask which one
        if len(user_gyms) > 1:
            # Create dropdown for gym selection
            class GymSelect(discord.ui.Select):
                def __init__(self, gyms):
                    options = [
                        discord.SelectOption(
                            label=gym["name"],
                            value=gym_id,
                            description=f"Min Level: {gym.get('min_level', 1)}"
                        )
                        for gym_id, gym in gyms
                    ]
                    super().__init__(
                        placeholder="Select a gym...",
                        options=options
                    )
                
                async def callback(self, select_interaction: discord.Interaction):
                    # Record the battle for the selected gym
                    await select_interaction.response.defer(ephemeral=True)
                    
                    gym_id = self.values[0]
                    gym = gyms[gym_id]
                    
                    battle_id = self.view.cog.record_battle(
                        select_interaction.guild.id,
                        gym_id,
                        challenger.id,
                        result,
                        notes
                    )
                    
                    if not battle_id:
                        await select_interaction.followup.send(
                            "Failed to record battle result. Please try again.",
                            ephemeral=True
                        )
                        return
                    
                    # Send confirmation
                    result_text = {
                        "win": "You won! The challenger did not earn a badge.",
                        "loss": "You lost! The challenger did not earn a badge.",
                        "badge": f"The challenger earned the {gym.get('badge_emoji', '🏅')} badge!"
                    }
                    
                    embed = discord.Embed(
                        title="⚔️ Battle Result Recorded",
                        description=f"Battle between **{gym['name']}** gym and {challenger.mention} has been recorded!",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="Result",
                        value=result_text.get(result, "Unknown result"),
                        inline=False
                    )
                    
                    if notes:
                        embed.add_field(
                            name="Notes",
                            value=notes,
                            inline=False
                        )
                    
                    await select_interaction.followup.send(embed=embed, ephemeral=True)
                    
                    # Notify challenger of battle result
                    try:
                        challenger_embed = discord.Embed(
                            title="⚔️ Gym Battle Result",
                            description=f"Your battle against the **{gym['name']}** gym has been recorded!",
                            color=discord.Color.blue()
                        )
                        
                        challenger_embed.add_field(
                            name="Result",
                            value=result_text.get(result, "Unknown result"),
                            inline=False
                        )
                        
                        if notes:
                            challenger_embed.add_field(
                                name="Leader's Notes",
                                value=notes,
                                inline=False
                            )
                        
                        await challenger.send(embed=challenger_embed)
                    except discord.HTTPException:
                        # Couldn't DM the challenger, ignore
                        pass
                    
                    # Set view as completed
                    self.view.stop()
            
            class GymSelectView(discord.ui.View):
                def __init__(self, cog, gyms, timeout=180):
                    super().__init__(timeout=timeout)
                    self.cog = cog
                    self.add_item(GymSelect(gyms))
            
            view = GymSelectView(self, user_gyms)
            
            await interaction.response.send_message(
                "You are a leader of multiple gyms. Please select which gym this battle was for:",
                view=view,
                ephemeral=True
            )
        else:
            # Only one gym, use that one
            gym_id, gym = user_gyms[0]
            
            battle_id = self.record_battle(
                interaction.guild.id,
                gym_id,
                challenger.id,
                result,
                notes
            )
            
            if not battle_id:
                await interaction.response.send_message(
                    "Failed to record battle result. Please try again.",
                    ephemeral=True
                )
                return
            
            # Send confirmation
            result_text = {
                "win": "You won! The challenger did not earn a badge.",
                "loss": "You lost! The challenger did not earn a badge.",
                "badge": f"The challenger earned the {gym.get('badge_emoji', '🏅')} badge!"
            }
            
            embed = discord.Embed(
                title="⚔️ Battle Result Recorded",
                description=f"Battle between **{gym['name']}** gym and {challenger.mention} has been recorded!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Result",
                value=result_text.get(result, "Unknown result"),
                inline=False
            )
            
            if notes:
                embed.add_field(
                    name="Notes",
                    value=notes,
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Notify challenger of battle result
            try:
                challenger_embed = discord.Embed(
                    title="⚔️ Gym Battle Result",
                    description=f"Your battle against the **{gym['name']}** gym has been recorded!",
                    color=discord.Color.blue()
                )
                
                challenger_embed.add_field(
                    name="Result",
                    value=result_text.get(result, "Unknown result"),
                    inline=False
                )
                
                if notes:
                    challenger_embed.add_field(
                        name="Leader's Notes",
                        value=notes,
                        inline=False
                    )
                
                await challenger.send(embed=challenger_embed)
            except discord.HTTPException:
                # Couldn't DM the challenger, ignore
                pass
    
    @app_commands.command(name="badges", description="View your gym badges")
    @app_commands.describe(
        user="The user to check badges for (defaults to yourself)"
    )
    async def badges_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None
    ):
        # Use command invoker if no user is specified
        target_user = user or interaction.user
        
        # Get user's badges
        badges = self.get_user_badges(interaction.guild.id, target_user.id)
        
        if not badges:
            await interaction.response.send_message(
                f"{target_user.mention} has not earned any gym badges yet.",
                ephemeral=True
            )
            return
        
        # Create badge list embed
        embed = discord.Embed(
            title=f"{target_user.display_name}'s Gym Badges",
            description=f"{target_user.mention} has earned **{len(badges)}** gym badges!",
            color=discord.Color.gold()
        )
        
        # Add badges to embed
        badge_text = ""
        for gym in badges:
            badge_text += f"{gym.get('badge_emoji', '🏅')} **{gym.get('name', 'Unknown Gym')}**\n"
        
        embed.add_field(
            name="Badges",
            value=badge_text,
            inline=False
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Only show to the user if checking someone else's badges
        ephemeral = user is not None and user.id != interaction.user.id
        
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

async def setup(bot):
    await bot.add_cog(GymSystem(bot))