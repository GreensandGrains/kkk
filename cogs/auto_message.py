import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
from typing import Optional
import datetime

from utils import has_mod_permissions, has_admin_permissions, parse_time, create_confirmation_view
from data_manager import DataManager
import config

class AutoMessage(commands.Cog):
    """Commands for setting up automatic recurring messages"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.check_auto_messages.start()
    
    def cog_unload(self):
        self.check_auto_messages.cancel()
    
    @tasks.loop(seconds=30)
    async def check_auto_messages(self):
        """Check for auto messages that need to be sent"""
        now = datetime.datetime.utcnow()
        
        for guild in self.bot.guilds:
            # Get auto messages for this guild
            auto_messages = self.data_manager.get_auto_messages(guild.id)
            if not auto_messages:
                continue
            
            for message_id, message_data in auto_messages.items():
                # Skip inactive messages
                if not message_data.get("active", True):
                    continue
                
                # Get the channel
                channel_id = message_data.get("channel_id")
                if not channel_id:
                    continue
                
                channel = guild.get_channel(int(channel_id))
                if not channel:
                    continue
                
                # Check if it's time to send the message
                last_sent = datetime.datetime.fromisoformat(message_data.get("last_sent"))
                interval = message_data.get("interval", 3600)  # Default to 1 hour
                
                if (now - last_sent).total_seconds() >= interval:
                    # Send the message
                    try:
                        await channel.send(message_data.get("message", "Auto message"))
                        
                        # Update the last sent time
                        self.data_manager.update_auto_message_timestamp(guild.id, message_id)
                    except (discord.Forbidden, discord.HTTPException):
                        # Can't send to this channel, ignore
                        pass
    
    @check_auto_messages.before_loop
    async def before_check_auto_messages(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="automessage", description="Set up an automatic recurring message")
    @app_commands.describe(
        channel="Channel to send the message in",
        interval="Time between messages (e.g., 1h, 30m, 1d)",
        message="Message content to send"
    )
    @has_mod_permissions()
    async def auto_message_command(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        interval: str,
        message: str
    ):
        # Check if the bot has permission to send messages in the channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"I don't have permission to send messages in {channel.mention}.",
                ephemeral=True
            )
            return
        
        # Parse the interval
        time_delta = parse_time(interval)
        if not time_delta:
            await interaction.response.send_message(
                "Invalid interval format. Use a format like 1h30m, 1d, 2h, etc.",
                ephemeral=True
            )
            return
        
        # Convert to seconds
        interval_seconds = int(time_delta.total_seconds())
        
        # Check if interval is too short
        if interval_seconds < 60:
            await interaction.response.send_message(
                "Interval cannot be less than 1 minute.",
                ephemeral=True
            )
            return
        
        # Get existing auto messages for this guild
        auto_messages = self.data_manager.get_auto_messages(interaction.guild.id)
        
        # Check if we've reached the maximum number of auto messages
        max_auto_messages = config.MAX_AUTO_MESSAGES
        if auto_messages and len(auto_messages) >= max_auto_messages:
            await interaction.response.send_message(
                f"You have reached the maximum number of auto messages ({max_auto_messages}).\n"
                f"Use `/stopauto` to remove an existing auto message first.",
                ephemeral=True
            )
            return
        
        # Add the auto message
        success, message_id = self.data_manager.add_auto_message(
            interaction.guild.id,
            channel.id,
            message,
            interval_seconds
        )
        
        if success:
            embed = discord.Embed(
                title="Auto Message Created",
                description=f"Auto message will be sent in {channel.mention} every {interval}.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(name="Message", value=message[:1024], inline=False)
            embed.add_field(name="ID", value=f"`{message_id}`", inline=True)
            embed.add_field(name="Interval", value=interval, inline=True)
            
            embed.set_footer(text=f"Use /stopauto {message_id} to stop this auto message")
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "Failed to create auto message. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="listauto", description="List all automatic messages")
    @has_mod_permissions()
    async def list_auto_command(self, interaction: discord.Interaction):
        # Get auto messages for this guild
        auto_messages = self.data_manager.get_auto_messages(interaction.guild.id)
        
        if not auto_messages:
            await interaction.response.send_message("No automatic messages have been set up.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Automatic Messages",
            description=f"Found {len(auto_messages)} automatic messages in this server.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        for message_id, message_data in auto_messages.items():
            channel = interaction.guild.get_channel(int(message_data.get("channel_id", 0)))
            channel_mention = channel.mention if channel else "Unknown channel"
            
            interval = message_data.get("interval", 3600)
            hours = interval // 3600
            minutes = (interval % 3600) // 60
            interval_text = ""
            
            if hours > 0:
                interval_text += f"{hours}h"
            if minutes > 0:
                interval_text += f"{minutes}m"
            
            status = "✅ Active" if message_data.get("active", True) else "❌ Inactive"
            
            last_sent = datetime.datetime.fromisoformat(message_data.get("last_sent"))
            next_send = last_sent + datetime.timedelta(seconds=interval)
            
            embed.add_field(
                name=f"ID: {message_id} - {status}",
                value=(
                    f"**Channel:** {channel_mention}\n"
                    f"**Interval:** {interval_text}\n"
                    f"**Next Send:** <t:{int(next_send.timestamp())}:R>\n"
                    f"**Message:** {message_data.get('message', '')[:100]}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="stopauto", description="Stop an automatic message")
    @app_commands.describe(
        message_id="ID of the auto message to stop"
    )
    @has_mod_permissions()
    async def stop_auto_command(self, interaction: discord.Interaction, message_id: str):
        # Check if the auto message exists
        auto_messages = self.data_manager.get_auto_messages(interaction.guild.id)
        
        if not auto_messages or message_id not in auto_messages:
            await interaction.response.send_message(
                f"Auto message with ID `{message_id}` not found.",
                ephemeral=True
            )
            return
        
        # Confirm removal
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to stop and remove the auto message with ID `{message_id}`?"
        )
        
        if not confirm:
            await interaction.followup.send("Auto message removal cancelled.", ephemeral=True)
            return
        
        # Remove the auto message
        success = self.data_manager.remove_auto_message(interaction.guild.id, message_id)
        
        if success:
            await interaction.followup.send(f"Auto message with ID `{message_id}` has been stopped and removed.")
        else:
            await interaction.followup.send(f"Failed to remove auto message. Please try again.", ephemeral=True)
    
    @app_commands.command(name="toggleauto", description="Pause or resume an automatic message")
    @app_commands.describe(
        message_id="ID of the auto message to toggle"
    )
    @has_mod_permissions()
    async def toggle_auto_command(self, interaction: discord.Interaction, message_id: str):
        # Check if the auto message exists
        auto_messages = self.data_manager.get_auto_messages(interaction.guild.id)
        
        if not auto_messages or message_id not in auto_messages:
            await interaction.response.send_message(
                f"Auto message with ID `{message_id}` not found.",
                ephemeral=True
            )
            return
        
        # Get current status
        current_status = auto_messages[message_id].get("active", True)
        
        # Toggle the status
        success = self.data_manager.toggle_auto_message(interaction.guild.id, message_id, not current_status)
        
        if success:
            new_status = "resumed" if not current_status else "paused"
            await interaction.response.send_message(f"Auto message with ID `{message_id}` has been {new_status}.")
        else:
            await interaction.response.send_message(f"Failed to toggle auto message. Please try again.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoMessage(bot))
