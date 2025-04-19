import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
from typing import Optional, Union

from utils import has_mod_permissions, has_admin_permissions, format_timestamp, parse_time, create_confirmation_view
from data_manager import DataManager

class Moderation(commands.Cog):
    """Moderation commands for managing server members and channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
    
    @app_commands.command(name="ban", description="Ban a user from the server")
    @app_commands.describe(
        user="The user to ban",
        reason="Reason for the ban",
        delete_days="Number of days of message history to delete (0-7)"
    )
    @has_mod_permissions()
    async def ban_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.User, 
        reason: Optional[str] = "No reason provided",
        delete_days: Optional[int] = 0
    ):
        # Check if the bot has permission to ban
        if not interaction.guild.me.guild_permissions.ban_members:
            await interaction.response.send_message("I don't have permission to ban members.", ephemeral=True)
            return
        
        # Check if the user is already banned
        try:
            await interaction.guild.fetch_ban(user)
            await interaction.response.send_message(f"{user.mention} is already banned from this server.", ephemeral=True)
            return
        except discord.NotFound:
            pass
        
        # Check if the member is in the guild and has higher role than the bot
        member = interaction.guild.get_member(user.id)
        if member:
            if member.top_role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "I cannot ban this user because their highest role is equal to or higher than mine.",
                    ephemeral=True
                )
                return
            
            # Check if the moderator is trying to ban someone with a higher role
            if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message(
                    "You cannot ban this user because their highest role is equal to or higher than yours.",
                    ephemeral=True
                )
                return
        
        # Clamp delete_days to valid range
        delete_days = max(0, min(7, delete_days))
        
        # Confirm the ban
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to ban {user.mention}?"
        )
        
        if not confirm:
            await interaction.followup.send("Ban cancelled.", ephemeral=True)
            return
        
        try:
            await interaction.guild.ban(user, reason=reason, delete_message_days=delete_days)
            
            # Create embed for success message
            embed = discord.Embed(
                title="User Banned",
                description=f"{user.mention} has been banned from the server.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_thumbnail(url=user.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
            # Try to DM the user
            try:
                embed = discord.Embed(
                    title=f"You have been banned from {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                await user.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                # Cannot DM the user, ignore
                pass
            
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to ban this user.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to ban the user: {e}", ephemeral=True)
    
    @app_commands.command(name="kick", description="Kick a user from the server")
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for the kick"
    )
    @has_mod_permissions()
    async def kick_command(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member, 
        reason: Optional[str] = "No reason provided"
    ):
        # Check if the bot has permission to kick
        if not interaction.guild.me.guild_permissions.kick_members:
            await interaction.response.send_message("I don't have permission to kick members.", ephemeral=True)
            return
        
        # Check if the member has higher role than the bot
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I cannot kick this user because their highest role is equal to or higher than mine.",
                ephemeral=True
            )
            return
        
        # Check if the moderator is trying to kick someone with a higher role
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "You cannot kick this user because their highest role is equal to or higher than yours.",
                ephemeral=True
            )
            return
        
        # Confirm the kick
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to kick {member.mention}?"
        )
        
        if not confirm:
            await interaction.followup.send("Kick cancelled.", ephemeral=True)
            return
        
        try:
            # Try to DM the user before kicking
            try:
                embed = discord.Embed(
                    title=f"You have been kicked from {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow()
                )
                embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                await member.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                # Cannot DM the user, ignore
                pass
            
            await member.kick(reason=reason)
            
            # Create embed for success message
            embed = discord.Embed(
                title="User Kicked",
                description=f"{member.mention} has been kicked from the server.",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to kick this user.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to kick the user: {e}", ephemeral=True)
    
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(
        member="The member to warn",
        reason="Reason for the warning"
    )
    @has_mod_permissions()
    async def warn_command(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member, 
        reason: str
    ):
        # Check if the member has higher role than the moderator
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "You cannot warn this user because their highest role is equal to or higher than yours.",
                ephemeral=True
            )
            return
        
        # Add warning to the database
        warn_count = await self.data_manager.add_warning(
            interaction.guild.id,
            member.id,
            reason,
            interaction.user.id
        )
        
        # Create embed for the warning
        embed = discord.Embed(
            title="User Warned",
            description=f"{member.mention} has been warned.",
            color=discord.Color.yellow(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Warning Count", value=str(warn_count), inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)
        
        # DM the user about the warning
        try:
            user_embed = discord.Embed(
                title=f"You have been warned in {interaction.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow()
            )
            user_embed.add_field(name="Warning Count", value=str(warn_count), inline=False)
            
            if warn_count >= 3:
                user_embed.add_field(
                    name="Notice",
                    value="You have received multiple warnings. Additional infractions may result in a kick or ban.",
                    inline=False
                )
            
            user_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
            await member.send(embed=user_embed)
        except (discord.Forbidden, discord.HTTPException):
            # Cannot DM the user, ignore
            pass
        
        # Take additional action if warn count is high
        if warn_count >= 3:
            auto_action_embed = discord.Embed(
                title="Automatic Moderation Notice",
                description=f"{member.mention} has received {warn_count} warnings.",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            auto_action_embed.add_field(
                name="Recommendation",
                value="Consider taking additional moderation action such as a timeout, kick, or ban.",
                inline=False
            )
            
            await interaction.followup.send(embed=auto_action_embed, ephemeral=True)
    
    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(
        member="The member to timeout",
        duration="Timeout duration (e.g., 1h30m, 1d, 2h)",
        reason="Reason for the timeout"
    )
    @has_mod_permissions()
    async def timeout_command(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member, 
        duration: str,
        reason: Optional[str] = "No reason provided"
    ):
        # Check if the bot has permission to timeout
        if not interaction.guild.me.guild_permissions.moderate_members:
            await interaction.response.send_message("I don't have permission to timeout members.", ephemeral=True)
            return
        
        # Check if the member has higher role than the bot
        if member.top_role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I cannot timeout this user because their highest role is equal to or higher than mine.",
                ephemeral=True
            )
            return
        
        # Check if the moderator is trying to timeout someone with a higher role
        if member.top_role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "You cannot timeout this user because their highest role is equal to or higher than yours.",
                ephemeral=True
            )
            return
        
        # Parse the duration
        time_delta = parse_time(duration)
        if not time_delta:
            await interaction.response.send_message(
                "Invalid duration format. Use a format like 1h30m, 1d, 2h, etc.",
                ephemeral=True
            )
            return
        
        # Check if duration is too long (max is 28 days)
        max_duration = datetime.timedelta(days=28)
        if time_delta > max_duration:
            await interaction.response.send_message(
                "Timeout duration cannot exceed 28 days.",
                ephemeral=True
            )
            return
        
        # Calculate the timeout end time
        timeout_until = discord.utils.utcnow() + time_delta
        
        try:
            # Apply the timeout
            await member.timeout(timeout_until, reason=reason)
            
            # Create embed for success message
            embed = discord.Embed(
                title="User Timed Out",
                description=f"{member.mention} has been timed out.",
                color=discord.Color.dark_orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=duration, inline=True)
            embed.add_field(name="Expires", value=format_timestamp(timeout_until, 'R'), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await interaction.response.send_message(embed=embed)
            
            # Try to DM the user
            try:
                user_embed = discord.Embed(
                    title=f"You have been timed out in {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=discord.Color.dark_orange(),
                    timestamp=discord.utils.utcnow()
                )
                user_embed.add_field(name="Duration", value=duration, inline=True)
                user_embed.add_field(name="Expires", value=format_timestamp(timeout_until, 'R'), inline=True)
                user_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
                await member.send(embed=user_embed)
            except (discord.Forbidden, discord.HTTPException):
                # Cannot DM the user, ignore
                pass
            
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to timeout this user.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to timeout the user: {e}", ephemeral=True)
    
    @app_commands.command(name="clear", description="Clear messages in a channel")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        user="Only delete messages from this user (optional)"
    )
    @has_mod_permissions()
    async def clear_command(
        self, 
        interaction: discord.Interaction, 
        amount: app_commands.Range[int, 1, 100],
        user: Optional[discord.User] = None
    ):
        # Check if the bot has permission to manage messages
        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message("I don't have permission to delete messages in this channel.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Delete messages
        if user:
            # Clear messages from specific user
            def check(message):
                return message.author.id == user.id
            
            deleted = await interaction.channel.purge(limit=amount, check=check)
            message = f"Deleted {len(deleted)} messages from {user.mention}."
        else:
            # Clear any messages
            deleted = await interaction.channel.purge(limit=amount)
            message = f"Deleted {len(deleted)} messages."
        
        await interaction.followup.send(message, ephemeral=True)
    
    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.describe(
        channel="The channel to lock (defaults to current channel)",
        reason="Reason for locking the channel"
    )
    @has_mod_permissions()
    async def lock_command(
        self, 
        interaction: discord.Interaction, 
        channel: Optional[Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel]] = None,
        reason: Optional[str] = "No reason provided"
    ):
        # Use current channel if none specified
        channel = channel or interaction.channel
        
        # Check if the bot has permission to manage roles
        if not channel.permissions_for(interaction.guild.me).manage_roles:
            await interaction.response.send_message("I don't have permission to manage roles in this channel.", ephemeral=True)
            return
        
        # Get default role (@everyone)
        default_role = interaction.guild.default_role
        
        # Check current permissions to avoid setting the same overwrites
        current_overwrites = channel.overwrites_for(default_role)
        if current_overwrites.send_messages is False:
            await interaction.response.send_message(f"{channel.mention} is already locked.", ephemeral=True)
            return
        
        # Update permission overwrites to deny sending messages
        await channel.set_permissions(
            default_role, 
            send_messages=False,
            reason=f"Locked by {interaction.user.display_name}: {reason}"
        )
        
        # Create embed for success message
        embed = discord.Embed(
            title="Channel Locked",
            description=f"{channel.mention} has been locked.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # Send a notification in the locked channel
        channel_embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"This channel has been locked by {interaction.user.mention}.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        if reason != "No reason provided":
            channel_embed.add_field(name="Reason", value=reason, inline=False)
        
        try:
            await channel.send(embed=channel_embed)
        except discord.Forbidden:
            # Cannot send to the channel, ignore
            pass
    
    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(
        channel="The channel to unlock (defaults to current channel)",
        reason="Reason for unlocking the channel"
    )
    @has_mod_permissions()
    async def unlock_command(
        self, 
        interaction: discord.Interaction, 
        channel: Optional[Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel]] = None,
        reason: Optional[str] = "No reason provided"
    ):
        # Use current channel if none specified
        channel = channel or interaction.channel
        
        # Check if the bot has permission to manage roles
        if not channel.permissions_for(interaction.guild.me).manage_roles:
            await interaction.response.send_message("I don't have permission to manage roles in this channel.", ephemeral=True)
            return
        
        # Get default role (@everyone)
        default_role = interaction.guild.default_role
        
        # Check current permissions to avoid setting the same overwrites
        current_overwrites = channel.overwrites_for(default_role)
        if current_overwrites.send_messages is None or current_overwrites.send_messages is True:
            await interaction.response.send_message(f"{channel.mention} is not locked.", ephemeral=True)
            return
        
        # Update permission overwrites to allow sending messages
        overwrite = channel.overwrites_for(default_role)
        overwrite.send_messages = None  # Reset to default
        await channel.set_permissions(
            default_role, 
            overwrite=overwrite,
            reason=f"Unlocked by {interaction.user.display_name}: {reason}"
        )
        
        # Create embed for success message
        embed = discord.Embed(
            title="Channel Unlocked",
            description=f"{channel.mention} has been unlocked.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # Send a notification in the unlocked channel
        channel_embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"This channel has been unlocked by {interaction.user.mention}.",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        if reason != "No reason provided":
            channel_embed.add_field(name="Reason", value=reason, inline=False)
        
        try:
            await channel.send(embed=channel_embed)
        except discord.Forbidden:
            # Cannot send to the channel, ignore
            pass
    
    @app_commands.command(name="slowmode", description="Set slowmode in a channel")
    @app_commands.describe(
        seconds="Slowmode delay in seconds (0 to disable, max 21600)",
        channel="The channel to set slowmode in (defaults to current channel)",
        reason="Reason for setting slowmode"
    )
    @has_mod_permissions()
    async def slowmode_command(
        self, 
        interaction: discord.Interaction, 
        seconds: app_commands.Range[int, 0, 21600],
        channel: Optional[discord.TextChannel] = None,
        reason: Optional[str] = "No reason provided"
    ):
        # Use current channel if none specified
        channel = channel or interaction.channel
        
        # Check if the bot has permission to manage channels
        if not channel.permissions_for(interaction.guild.me).manage_channels:
            await interaction.response.send_message("I don't have permission to manage this channel.", ephemeral=True)
            return
        
        # Set slowmode
        try:
            await channel.edit(slowmode_delay=seconds, reason=f"Slowmode set by {interaction.user.display_name}: {reason}")
            
            if seconds == 0:
                message = f"Slowmode has been disabled in {channel.mention}."
                color = discord.Color.green()
                title = "Slowmode Disabled"
            else:
                message = f"Slowmode has been set to {seconds} seconds in {channel.mention}."
                color = discord.Color.blue()
                title = "Slowmode Enabled"
            
            # Create embed for success message
            embed = discord.Embed(
                title=title,
                description=message,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            if seconds > 0:
                embed.add_field(name="Delay", value=f"{seconds} seconds", inline=True)
                
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to set slowmode in this channel.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to set slowmode: {e}", ephemeral=True)
    
    @app_commands.command(name="warnings", description="Check warnings for a user")
    @app_commands.describe(
        user="The user to check warnings for"
    )
    @has_mod_permissions()
    async def warnings_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.User
    ):
        # Get warnings from the database
        warnings = await self.data_manager.get_warnings(interaction.guild.id, user.id)
        
        if not warnings:
            await interaction.response.send_message(f"{user.mention} has no warnings.", ephemeral=True)
            return
        
        # Create embed with warning information
        embed = discord.Embed(
            title=f"Warnings for {user}",
            description=f"{user.mention} has {len(warnings)} warning(s).",
            color=discord.Color.yellow(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        
        for i, warning in enumerate(warnings, 1):
            warn_date = datetime.datetime.fromisoformat(warning["timestamp"])
            moderator = interaction.guild.get_member(int(warning["moderator_id"]))
            mod_mention = moderator.mention if moderator else f"Unknown moderator ({warning['moderator_id']})"
            
            embed.add_field(
                name=f"Warning #{i} - {warn_date.strftime('%Y-%m-%d %H:%M:%S')}",
                value=f"**Reason:** {warning['reason']}\n**Moderator:** {mod_mention}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="clearwarns", description="Clear warnings for a user")
    @app_commands.describe(
        user="The user to clear warnings for"
    )
    @has_mod_permissions()
    async def clearwarns_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.User
    ):
        # Check for warnings first
        warnings = await self.data_manager.get_warnings(interaction.guild.id, user.id)
        
        if not warnings:
            await interaction.response.send_message(f"{user.mention} has no warnings to clear.", ephemeral=True)
            return
        
        # Confirm the action
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to clear all {len(warnings)} warning(s) for {user.mention}?"
        )
        
        if not confirm:
            await interaction.followup.send("Action cancelled.", ephemeral=True)
            return
        
        # Clear warnings
        cleared = await self.data_manager.clear_warnings(interaction.guild.id, user.id)
        
        await interaction.followup.send(f"Cleared {cleared} warning(s) for {user.mention}.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
