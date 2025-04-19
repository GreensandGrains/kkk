import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import datetime
import random
import json
import os

from utils import has_mod_permissions, has_admin_permissions
from data_manager import DataManager

class Welcome(commands.Cog):
    """Welcome and goodbye message management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.welcome_messages = {}
        self.goodbye_messages = {}
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Load welcome/goodbye settings when bot is ready"""
        # Load settings for each guild
        for guild in self.bot.guilds:
            welcome_config = self.data_manager.get_welcome_config(guild.id)
            self.welcome_messages[guild.id] = welcome_config.get("enabled", False)
            
            goodbye_config = self.data_manager.get_goodbye_config(guild.id)
            self.goodbye_messages[guild.id] = goodbye_config.get("enabled", False)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Send welcome message when a new member joins"""
        if member.bot:
            return
            
        # Check if welcome messages are enabled
        if not self.welcome_messages.get(member.guild.id, False):
            return
            
        # Get welcome configuration
        welcome_config = self.data_manager.get_welcome_config(member.guild.id)
        if not welcome_config:
            return
            
        channel_id = welcome_config.get("channel_id")
        if not channel_id:
            return
            
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
            
        # Get welcome message (or use default)
        message = welcome_config.get("message", "Welcome to the server, {user}!")
        
        # Replace placeholders
        message = message.replace("{user}", member.mention)
        message = message.replace("{username}", member.display_name)
        message = message.replace("{server}", member.guild.name)
        message = message.replace("{count}", str(member.guild.member_count))
        
        # Create welcome embed
        embed = discord.Embed(
            title=f"👋 Welcome to {member.guild.name}!",
            description=message,
            color=0x47B0FF  # Blue
        )
        
        # Add member info
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(member.created_at.timestamp())}:R>",
            inline=True
        )
        
        embed.add_field(
            name="Member Count",
            value=f"#{member.guild.member_count}",
            inline=True
        )
        
        # Random welcome messages for the footer
        welcome_footers = [
            "We're glad you're here!",
            "Hope you enjoy your stay!",
            "Thanks for joining us!",
            "Don't forget to check the rules!",
            "Make yourself at home!"
        ]
        
        embed.set_footer(text=random.choice(welcome_footers))
        embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            # Failed to send, ignore
            pass
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Send goodbye message when a member leaves"""
        if member.bot:
            return
            
        # Check if goodbye messages are enabled
        if not self.goodbye_messages.get(member.guild.id, False):
            return
            
        # Get goodbye configuration
        goodbye_config = self.data_manager.get_goodbye_config(member.guild.id)
        if not goodbye_config:
            return
            
        channel_id = goodbye_config.get("channel_id")
        if not channel_id:
            return
            
        channel = member.guild.get_channel(int(channel_id))
        if not channel:
            return
            
        # Get goodbye message (or use default)
        message = goodbye_config.get("message", "Goodbye, {username}. We'll miss you!")
        
        # Replace placeholders
        message = message.replace("{user}", member.mention)
        message = message.replace("{username}", member.display_name)
        message = message.replace("{server}", member.guild.name)
        message = message.replace("{count}", str(member.guild.member_count))
        
        # Create goodbye embed
        embed = discord.Embed(
            title=f"👋 Goodbye!",
            description=message,
            color=0xE74C3C  # Red
        )
        
        # Add member info
        joined_days_ago = (datetime.datetime.utcnow() - member.joined_at.replace(tzinfo=None)).days if member.joined_at else 0
        
        embed.add_field(
            name="Joined",
            value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown",
            inline=True
        )
        
        embed.add_field(
            name="Time in Server",
            value=f"{joined_days_ago} days" if joined_days_ago > 0 else "Less than a day",
            inline=True
        )
        
        embed.add_field(
            name="Member Count",
            value=f"#{member.guild.member_count}",
            inline=True
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await channel.send(embed=embed)
        except discord.HTTPException:
            # Failed to send, ignore
            pass
    
    @app_commands.command(name="welcome", description="Configure welcome messages")
    @app_commands.describe(
        set_channel="Set the channel for welcome messages",
        enable="Enable or disable welcome messages",
        message="Set a custom welcome message (use {user}, {username}, {server}, {count} as placeholders)"
    )
    @has_admin_permissions()
    async def welcome_command(
        self, 
        interaction: discord.Interaction, 
        set_channel: Optional[discord.TextChannel] = None,
        enable: Optional[bool] = None,
        message: Optional[str] = None
    ):
        # Get current configuration
        welcome_config = self.data_manager.get_welcome_config(interaction.guild.id)
        
        # Update configuration based on parameters
        updated = False
        
        if set_channel is not None:
            welcome_config["channel_id"] = set_channel.id
            updated = True
        
        if enable is not None:
            welcome_config["enabled"] = enable
            self.welcome_messages[interaction.guild.id] = enable
            updated = True
        
        if message is not None:
            welcome_config["message"] = message
            updated = True
        
        if updated:
            # Save updated configuration
            success = self.data_manager.save_welcome_config(interaction.guild.id, welcome_config)
            
            if success:
                # Show preview of welcome message
                channel_id = welcome_config.get("channel_id")
                channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
                
                status = "enabled" if welcome_config.get("enabled", False) else "disabled"
                channel_text = channel.mention if channel else "not set"
                
                embed = discord.Embed(
                    title="Welcome Messages Configuration",
                    description="Configuration updated successfully!",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Channel", value=channel_text, inline=True)
                
                # Show message preview
                if welcome_config.get("message"):
                    preview = welcome_config["message"]
                    preview = preview.replace("{user}", interaction.user.mention)
                    preview = preview.replace("{username}", interaction.user.display_name)
                    preview = preview.replace("{server}", interaction.guild.name)
                    preview = preview.replace("{count}", str(interaction.guild.member_count))
                    
                    embed.add_field(name="Message Preview", value=preview, inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Failed to update welcome configuration. Please try again.",
                    ephemeral=True
                )
        else:
            # Show current configuration
            channel_id = welcome_config.get("channel_id")
            channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
            
            status = "enabled" if welcome_config.get("enabled", False) else "disabled"
            channel_text = channel.mention if channel else "not set"
            
            embed = discord.Embed(
                title="Welcome Messages Configuration",
                description="Current welcome message settings:",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Channel", value=channel_text, inline=True)
            
            # Show message preview
            if welcome_config.get("message"):
                preview = welcome_config["message"]
                preview = preview.replace("{user}", interaction.user.mention)
                preview = preview.replace("{username}", interaction.user.display_name)
                preview = preview.replace("{server}", interaction.guild.name)
                preview = preview.replace("{count}", str(interaction.guild.member_count))
                
                embed.add_field(name="Message Preview", value=preview, inline=False)
            
            embed.add_field(
                name="Usage",
                value="Use `/welcome parameter:value` to change settings.\n"
                "For example: `/welcome enable:True set_channel:#welcome`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="goodbye", description="Configure goodbye messages")
    @app_commands.describe(
        set_channel="Set the channel for goodbye messages",
        enable="Enable or disable goodbye messages",
        message="Set a custom goodbye message (use {user}, {username}, {server}, {count} as placeholders)"
    )
    @has_admin_permissions()
    async def goodbye_command(
        self, 
        interaction: discord.Interaction, 
        set_channel: Optional[discord.TextChannel] = None,
        enable: Optional[bool] = None,
        message: Optional[str] = None
    ):
        # Get current configuration
        goodbye_config = self.data_manager.get_goodbye_config(interaction.guild.id)
        
        # Update configuration based on parameters
        updated = False
        
        if set_channel is not None:
            goodbye_config["channel_id"] = set_channel.id
            updated = True
        
        if enable is not None:
            goodbye_config["enabled"] = enable
            self.goodbye_messages[interaction.guild.id] = enable
            updated = True
        
        if message is not None:
            goodbye_config["message"] = message
            updated = True
        
        if updated:
            # Save updated configuration
            success = self.data_manager.save_goodbye_config(interaction.guild.id, goodbye_config)
            
            if success:
                # Show preview of goodbye message
                channel_id = goodbye_config.get("channel_id")
                channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
                
                status = "enabled" if goodbye_config.get("enabled", False) else "disabled"
                channel_text = channel.mention if channel else "not set"
                
                embed = discord.Embed(
                    title="Goodbye Messages Configuration",
                    description="Configuration updated successfully!",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Channel", value=channel_text, inline=True)
                
                # Show message preview
                if goodbye_config.get("message"):
                    preview = goodbye_config["message"]
                    preview = preview.replace("{user}", interaction.user.mention)
                    preview = preview.replace("{username}", interaction.user.display_name)
                    preview = preview.replace("{server}", interaction.guild.name)
                    preview = preview.replace("{count}", str(interaction.guild.member_count))
                    
                    embed.add_field(name="Message Preview", value=preview, inline=False)
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "Failed to update goodbye configuration. Please try again.",
                    ephemeral=True
                )
        else:
            # Show current configuration
            channel_id = goodbye_config.get("channel_id")
            channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
            
            status = "enabled" if goodbye_config.get("enabled", False) else "disabled"
            channel_text = channel.mention if channel else "not set"
            
            embed = discord.Embed(
                title="Goodbye Messages Configuration",
                description="Current goodbye message settings:",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="Status", value=status, inline=True)
            embed.add_field(name="Channel", value=channel_text, inline=True)
            
            # Show message preview
            if goodbye_config.get("message"):
                preview = goodbye_config["message"]
                preview = preview.replace("{user}", interaction.user.mention)
                preview = preview.replace("{username}", interaction.user.display_name)
                preview = preview.replace("{server}", interaction.guild.name)
                preview = preview.replace("{count}", str(interaction.guild.member_count))
                
                embed.add_field(name="Message Preview", value=preview, inline=False)
            
            embed.add_field(
                name="Usage",
                value="Use `/goodbye parameter:value` to change settings.\n"
                "For example: `/goodbye enable:True set_channel:#goodbye`",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="testwelcome", description="Test the welcome message (Admin only)")
    @has_admin_permissions()
    async def test_welcome_command(self, interaction: discord.Interaction):
        # Get welcome configuration
        welcome_config = self.data_manager.get_welcome_config(interaction.guild.id)
        
        channel_id = welcome_config.get("channel_id")
        if not channel_id:
            await interaction.response.send_message(
                "Welcome channel not set. Configure it with `/welcome set_channel:#channel`",
                ephemeral=True
            )
            return
            
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Welcome channel not found. It may have been deleted.",
                ephemeral=True
            )
            return
        
        # Get welcome message (or use default)
        message = welcome_config.get("message", "Welcome to the server, {user}!")
        
        # Replace placeholders
        message = message.replace("{user}", interaction.user.mention)
        message = message.replace("{username}", interaction.user.display_name)
        message = message.replace("{server}", interaction.guild.name)
        message = message.replace("{count}", str(interaction.guild.member_count))
        
        # Create welcome embed
        embed = discord.Embed(
            title=f"👋 Welcome to {interaction.guild.name}!",
            description=message,
            color=0x47B0FF  # Blue
        )
        
        # Add member info
        embed.add_field(
            name="Account Created",
            value=f"<t:{int(interaction.user.created_at.timestamp())}:R>",
            inline=True
        )
        
        embed.add_field(
            name="Member Count",
            value=f"#{interaction.guild.member_count}",
            inline=True
        )
        
        # Random welcome messages for the footer
        welcome_footers = [
            "We're glad you're here!",
            "Hope you enjoy your stay!",
            "Thanks for joining us!",
            "Don't forget to check the rules!",
            "Make yourself at home!"
        ]
        
        embed.set_footer(text=f"TEST MESSAGE: {random.choice(welcome_footers)}")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(
                f"Test welcome message sent to {channel.mention}!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to send test message: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="testgoodbye", description="Test the goodbye message (Admin only)")
    @has_admin_permissions()
    async def test_goodbye_command(self, interaction: discord.Interaction):
        # Get goodbye configuration
        goodbye_config = self.data_manager.get_goodbye_config(interaction.guild.id)
        
        channel_id = goodbye_config.get("channel_id")
        if not channel_id:
            await interaction.response.send_message(
                "Goodbye channel not set. Configure it with `/goodbye set_channel:#channel`",
                ephemeral=True
            )
            return
            
        channel = interaction.guild.get_channel(int(channel_id))
        if not channel:
            await interaction.response.send_message(
                "Goodbye channel not found. It may have been deleted.",
                ephemeral=True
            )
            return
        
        # Get goodbye message (or use default)
        message = goodbye_config.get("message", "Goodbye, {username}. We'll miss you!")
        
        # Replace placeholders
        message = message.replace("{user}", interaction.user.mention)
        message = message.replace("{username}", interaction.user.display_name)
        message = message.replace("{server}", interaction.guild.name)
        message = message.replace("{count}", str(interaction.guild.member_count))
        
        # Create goodbye embed
        embed = discord.Embed(
            title=f"👋 Goodbye!",
            description=message,
            color=0xE74C3C  # Red
        )
        
        # Add member info
        joined_days_ago = (datetime.datetime.utcnow() - interaction.user.joined_at.replace(tzinfo=None)).days
        
        embed.add_field(
            name="Joined",
            value=f"<t:{int(interaction.user.joined_at.timestamp())}:R>",
            inline=True
        )
        
        embed.add_field(
            name="Time in Server",
            value=f"{joined_days_ago} days" if joined_days_ago > 0 else "Less than a day",
            inline=True
        )
        
        embed.add_field(
            name="Member Count",
            value=f"#{interaction.guild.member_count}",
            inline=True
        )
        
        embed.set_footer(text="TEST MESSAGE")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(
                f"Test goodbye message sent to {channel.mention}!",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to send test message: {e}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Welcome(bot))