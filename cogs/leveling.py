import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import random
import asyncio
import math

from utils import has_mod_permissions, has_admin_permissions
from data_manager import DataManager

class Leveling(commands.Cog):
    """Commands for the server leveling system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.cooldowns = {}  # Store user XP cooldowns
        self.xp_per_message = 15  # Base XP per message
        self.random_xp_range = 10  # Random XP bonus range
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize leveling settings when bot is ready"""
        # Clear cooldowns
        self.cooldowns = {}
        
        # Initialize leveling settings for all guilds
        for guild in self.bot.guilds:
            config = self.data_manager.get_leveling_config(guild.id)
            if not config:
                continue
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP for messages"""
        # Don't process commands or bot messages
        if message.author.bot or not message.guild:
            return
        
        # Check if message is too short
        if len(message.content) < 5:
            return
            
        # Get user and guild
        user_id = message.author.id
        guild_id = message.guild.id
        
        # Check cooldown (1 minute)
        cooldown_key = f"{guild_id}_{user_id}"
        current_time = asyncio.get_event_loop().time()
        
        if cooldown_key in self.cooldowns:
            time_diff = current_time - self.cooldowns[cooldown_key]
            if time_diff < 60:  # 60 seconds cooldown
                return
        
        # Update cooldown
        self.cooldowns[cooldown_key] = current_time
        
        # Get guild config
        guild_config = self.data_manager.get_leveling_config(guild_id)
        if not guild_config.get("enabled", False):
            return
            
        # Calculate XP to award
        xp_to_award = self.xp_per_message + random.randint(0, self.random_xp_range)
        
        # Check for level roles
        level_roles = self.data_manager.get_level_roles(guild_id)
        
        # Award XP and check for level up
        level_data = await self.data_manager.add_user_xp(guild_id, user_id, xp_to_award)
        
        if level_data and level_data.get("leveled_up", False):
            # User leveled up!
            new_level = level_data.get("level")
            
            # Send level up message
            level_channel_id = guild_config.get("level_channel_id")
            level_channel = None
            
            if level_channel_id:
                level_channel = message.guild.get_channel(level_channel_id)
            
            level_up_channel = level_channel or message.channel
            
            # Create level up embed
            embed = discord.Embed(
                title="🎉 Level Up!",
                description=f"{message.author.mention} is now level **{new_level}**!",
                color=discord.Color.green()
            )
            
            embed.set_thumbnail(url=message.author.display_avatar.url)
            
            try:
                await level_up_channel.send(embed=embed)
            except discord.HTTPException:
                # Failed to send level up message
                pass
            
            # Check if user should receive a role reward
            level_str = str(new_level)
            if level_str in level_roles:
                role_id = level_roles[level_str]
                role = message.guild.get_role(int(role_id))
                
                if role and role not in message.author.roles:
                    try:
                        await message.author.add_roles(role)
                        
                        # Send role reward message
                        reward_embed = discord.Embed(
                            title="🏆 Role Reward!",
                            description=f"You've been awarded the {role.mention} role for reaching level {new_level}!",
                            color=discord.Color.gold()
                        )
                        
                        try:
                            await message.author.send(embed=reward_embed)
                        except discord.HTTPException:
                            # Cannot DM user, send in channel
                            try:
                                await level_up_channel.send(
                                    content=message.author.mention,
                                    embed=reward_embed
                                )
                            except discord.HTTPException:
                                pass
                    except discord.HTTPException:
                        # Failed to add role
                        pass
    
    @app_commands.command(name="rank", description="Check your rank and level")
    @app_commands.describe(
        user="The user to check the rank for (defaults to yourself)"
    )
    async def rank_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None
    ):
        # Use command invoker if no user is specified
        target_user = user or interaction.user
        
        # Get user level data
        user_data = self.data_manager.get_user_level_data(interaction.guild.id, target_user.id)
        
        if not user_data:
            await interaction.response.send_message(
                f"{target_user.mention} hasn't earned any XP yet.",
                ephemeral=True
            )
            return
        
        # Get user's rank on leaderboard
        leaderboard = self.data_manager.get_level_leaderboard(interaction.guild.id)
        user_position = None
        
        for i, (user_id, _) in enumerate(leaderboard):
            if int(user_id) == target_user.id:
                user_position = i + 1
                break
        
        # Create rank embed
        level = user_data.get("level", 1)
        xp = user_data.get("xp", 0)
        total_xp = user_data.get("total_xp", 0)
        
        # Calculate XP needed for next level
        base_xp = 100
        xp_for_next_level = int(base_xp * (level * 1.5))
        
        # Create progress percentage
        xp_progress = xp / xp_for_next_level if xp_for_next_level > 0 else 0
        progress_bar = self.create_progress_bar(xp_progress)
        
        embed = discord.Embed(
            title=f"{target_user.display_name}'s Rank",
            description=f"**Rank:** #{user_position if user_position else 'N/A'}\n**Level:** {level}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name=f"XP: {xp}/{xp_for_next_level}",
            value=progress_bar,
            inline=False
        )
        
        embed.add_field(
            name="Total XP Earned",
            value=f"{total_xp:,} XP",
            inline=True
        )
        
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Only show to the user if checking someone else's rank
        ephemeral = user is not None and user.id != interaction.user.id
        
        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
    
    @app_commands.command(name="leaderboard", description="Show the server level leaderboard")
    @app_commands.describe(
        page="The page of the leaderboard to view"
    )
    async def leaderboard_command(
        self, 
        interaction: discord.Interaction, 
        page: Optional[int] = 1
    ):
        # Get the leaderboard
        leaderboard = self.data_manager.get_level_leaderboard(interaction.guild.id)
        
        if not leaderboard:
            await interaction.response.send_message(
                "There's no leaderboard data for this server yet.",
                ephemeral=True
            )
            return
        
        # Calculate pagination
        items_per_page = 10
        max_pages = math.ceil(len(leaderboard) / items_per_page)
        
        # Normalize page number
        page = max(1, min(page, max_pages))
        
        # Get items for this page
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = leaderboard[start_idx:end_idx]
        
        # Create leaderboard embed
        embed = discord.Embed(
            title=f"🏆 Level Leaderboard",
            description=f"Top members by XP in {interaction.guild.name}",
            color=discord.Color.gold()
        )
        
        # Add leaderboard entries
        for i, (user_id, user_data) in enumerate(page_items, start=start_idx + 1):
            # Get user
            member = interaction.guild.get_member(int(user_id))
            
            if member:
                name = member.display_name
            else:
                # Try to fetch user info if not in guild
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    name = f"{user.name} (Not in server)"
                except discord.NotFound:
                    name = f"Unknown User ({user_id})"
            
            # Format entry
            level = user_data.get("level", 1)
            total_xp = user_data.get("total_xp", 0)
            
            value = f"Level: **{level}** | XP: **{total_xp:,}**"
            
            # Use medal emoji for top 3
            if i == 1:
                prefix = "🥇 "
            elif i == 2:
                prefix = "🥈 "
            elif i == 3:
                prefix = "🥉 "
            else:
                prefix = f"#{i} "
            
            embed.add_field(
                name=f"{prefix}{name}",
                value=value,
                inline=False
            )
        
        # Add pagination info
        embed.set_footer(text=f"Page {page}/{max_pages} • Use /leaderboard <page> to view more")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="levelconfig", description="Configure the leveling system (Admin only)")
    @app_commands.describe(
        enable="Enable or disable the leveling system",
        level_channel="Channel to send level up messages (leave empty for current channel)",
        xp_multiplier="XP multiplier (1.0 is normal)"
    )
    @has_admin_permissions()
    async def level_config_command(
        self, 
        interaction: discord.Interaction, 
        enable: Optional[bool] = None,
        level_channel: Optional[discord.TextChannel] = None,
        xp_multiplier: Optional[float] = None
    ):
        # Get current configuration
        config = self.data_manager.get_leveling_config(interaction.guild.id)
        
        # Update configuration based on parameters
        updated = False
        
        if enable is not None:
            config["enabled"] = enable
            updated = True
        
        if level_channel is not None:
            config["level_channel_id"] = level_channel.id
            updated = True
        
        if xp_multiplier is not None:
            # Ensure multiplier is reasonable
            if xp_multiplier < 0.1:
                xp_multiplier = 0.1
            elif xp_multiplier > 5.0:
                xp_multiplier = 5.0
                
            config["xp_multiplier"] = xp_multiplier
            updated = True
        
        if updated:
            # Save updated configuration
            success = self.data_manager.save_leveling_config(interaction.guild.id, config)
            
            if success:
                # Show new configuration
                status = "enabled" if config.get("enabled", False) else "disabled"
                
                level_channel_id = config.get("level_channel_id")
                level_channel_text = "default (message channel)" if not level_channel_id else f"<#{level_channel_id}>"
                
                embed = discord.Embed(
                    title="Leveling System Configuration",
                    description="Configuration updated successfully!",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Level Channel", value=level_channel_text, inline=True)
                embed.add_field(name="XP Multiplier", value=f"{config.get('xp_multiplier', 1.0)}x", inline=True)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Failed to update leveling configuration. Please try again.",
                    ephemeral=True
                )
        else:
            # Show current configuration
            status = "enabled" if config.get("enabled", False) else "disabled"
            
            level_channel_id = config.get("level_channel_id")
            level_channel_text = "default (message channel)" if not level_channel_id else f"<#{level_channel_id}>"
            
            embed = discord.Embed(
                title="Leveling System Configuration",
                description="Current leveling settings:",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Level Channel", value=level_channel_text, inline=True)
            embed.add_field(name="XP Multiplier", value=f"{config.get('xp_multiplier', 1.0)}x", inline=True)
            
            embed.add_field(
                name="Usage",
                value="Use `/levelconfig parameter:value` to change settings.\n"
                "For example: `/levelconfig enable:True xp_multiplier:1.5`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="setlevelrole", description="Set a role to be awarded at a specific level (Admin only)")
    @app_commands.describe(
        level="The level at which to award the role",
        role="The role to award"
    )
    @has_admin_permissions()
    async def set_level_role_command(
        self, 
        interaction: discord.Interaction, 
        level: int,
        role: discord.Role
    ):
        # Validate level
        if level < 1 or level > 100:
            await interaction.response.send_message(
                "Level must be between 1 and 100.",
                ephemeral=True
            )
            return
        
        # Check if role is manageable by the bot
        if role.managed or role.is_default():
            await interaction.response.send_message(
                f"I cannot assign the {role.mention} role. It's either managed by an integration or is the @everyone role.",
                ephemeral=True
            )
            return
        
        # Check if role is above the bot's highest role
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message(
                f"I cannot assign the {role.mention} role as it's positioned above my highest role in the server settings.",
                ephemeral=True
            )
            return
        
        # Set the role for the level
        success = self.data_manager.set_level_role(interaction.guild.id, level, role.id)
        
        if success:
            await interaction.response.send_message(
                f"The {role.mention} role will now be awarded to members who reach level {level}!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to set the level role. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="removelevelrole", description="Remove a role reward from a level (Admin only)")
    @app_commands.describe(
        level="The level to remove the role reward from"
    )
    @has_admin_permissions()
    async def remove_level_role_command(
        self, 
        interaction: discord.Interaction, 
        level: int
    ):
        # Check if a role exists for this level
        level_roles = self.data_manager.get_level_roles(interaction.guild.id)
        level_str = str(level)
        
        if level_str not in level_roles:
            await interaction.response.send_message(
                f"There's no role reward set for level {level}.",
                ephemeral=True
            )
            return
        
        # Remove the role
        success = self.data_manager.remove_level_role(interaction.guild.id, level)
        
        if success:
            await interaction.response.send_message(
                f"The role reward for level {level} has been removed.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to remove the level role. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="levelroles", description="List all level role rewards")
    async def level_roles_command(
        self, 
        interaction: discord.Interaction
    ):
        # Get level roles
        level_roles = self.data_manager.get_level_roles(interaction.guild.id)
        
        if not level_roles:
            await interaction.response.send_message(
                "There are no level role rewards set up yet.",
                ephemeral=True
            )
            return
        
        # Create embed for level roles
        embed = discord.Embed(
            title="Level Role Rewards",
            description="The following roles are awarded at specific levels:",
            color=discord.Color.blue()
        )
        
        # Sort levels numerically
        sorted_levels = sorted(level_roles.items(), key=lambda x: int(x[0]))
        
        for level, role_id in sorted_levels:
            role = interaction.guild.get_role(int(role_id))
            value = role.mention if role else f"Unknown Role (ID: {role_id})"
            
            embed.add_field(
                name=f"Level {level}",
                value=value,
                inline=True
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="addxp", description="Add XP to a user (Admin only)")
    @app_commands.describe(
        user="The user to add XP to",
        amount="Amount of XP to add"
    )
    @has_admin_permissions()
    async def add_xp_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        amount: int
    ):
        # Validate amount
        if amount <= 0:
            await interaction.response.send_message(
                "You must add a positive amount of XP.",
                ephemeral=True
            )
            return
            
        if amount > 10000:
            await interaction.response.send_message(
                "For stability reasons, you cannot add more than 10,000 XP at once.",
                ephemeral=True
            )
            return
        
        # Add XP to user
        result = await self.data_manager.add_user_xp(interaction.guild.id, user.id, amount)
        
        if not result:
            await interaction.response.send_message(
                "Failed to add XP. Please try again.",
                ephemeral=True
            )
            return
        
        # Send confirmation
        new_level = result.get("level", 1)
        new_xp = result.get("xp", 0)
        total_xp = result.get("total_xp", 0)
        leveled_up = result.get("leveled_up", False)
        
        embed = discord.Embed(
            title="XP Added",
            description=f"Added **{amount} XP** to {user.mention}!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Current Level",
            value=str(new_level),
            inline=True
        )
        
        embed.add_field(
            name="XP Progress",
            value=f"{new_xp}/{int(100 * (new_level * 1.5))}",
            inline=True
        )
        
        embed.add_field(
            name="Total XP",
            value=f"{total_xp:,}",
            inline=True
        )
        
        if leveled_up:
            embed.add_field(
                name="Level Up!",
                value=f"{user.display_name} leveled up to level {new_level}!",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def create_progress_bar(self, percent, length=10):
        """Create a text-based progress bar
        
        Args:
            percent: Percentage of completion (0.0 to 1.0)
            length: Length of the progress bar
            
        Returns:
            String representing the progress bar
        """
        filled_length = int(length * percent)
        empty_length = length - filled_length
        
        bar = '█' * filled_length + '░' * empty_length
        percent_text = f"{int(percent * 100)}%"
        
        return f"{bar} {percent_text}"

async def setup(bot):
    await bot.add_cog(Leveling(bot))