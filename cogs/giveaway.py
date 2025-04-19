import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncio
import datetime
import random
from typing import Optional

from utils import has_mod_permissions, format_timestamp, parse_time, create_confirmation_view
from data_manager import DataManager

class Giveaway(commands.Cog):
    """Giveaway commands for creating and managing giveaways"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.check_giveaways.start()
    
    def cog_unload(self):
        self.check_giveaways.cancel()
    
    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        """Check for giveaways that have ended"""
        for guild in self.bot.guilds:
            # Get all giveaways for this guild
            giveaways = self.data_manager.get_giveaways(guild.id)
            if not giveaways:
                continue
            
            current_time = datetime.datetime.utcnow()
            
            for message_id, giveaway_data in giveaways.items():
                if not giveaway_data.get("active", True):
                    continue
                
                # Parse end time
                end_time = datetime.datetime.fromisoformat(giveaway_data["end_time"])
                
                # Check if giveaway has ended
                if current_time >= end_time:
                    # Mark giveaway as ended
                    self.data_manager.end_giveaway(guild.id, message_id)
                    
                    # Get channel and message
                    channel_id = int(giveaway_data["channel_id"])
                    message_id = int(message_id)
                    
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue
                    
                    try:
                        message = await channel.fetch_message(message_id)
                        
                        # Get participants from reactions
                        participants = []
                        for reaction in message.reactions:
                            if str(reaction.emoji) == "🎉":
                                users = [user async for user in reaction.users() if not user.bot]
                                participants.extend(users)
                        
                        # Update embed
                        embed = message.embeds[0]
                        embed.color = discord.Color.red()
                        
                        # Check if there are participants
                        if participants:
                            # Pick a winner
                            winner = random.choice(participants)
                            
                            embed.description = f"🎉 Winner: {winner.mention}\n\n" + embed.description
                            embed.set_footer(text=f"Giveaway ended at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')} | Winner selected from {len(participants)} participants")
                            
                            # Send winner announcement
                            await channel.send(
                                f"🎊 Congratulations {winner.mention}! You won the **{giveaway_data['prize']}** giveaway!"
                            )
                        else:
                            embed.description = "🎉 Giveaway ended but no one participated.\n\n" + embed.description
                            embed.set_footer(text=f"Giveaway ended at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')} | No participants")
                            
                            await channel.send(
                                f"🎊 The giveaway for **{giveaway_data['prize']}** has ended, but no one participated."
                            )
                        
                        await message.edit(embed=embed)
                        
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        # Message not found or can't access, ignore
                        pass
    
    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="gstart", description="Start a giveaway")
    @app_commands.describe(
        duration="Giveaway duration (e.g., 1h30m, 1d, 2h)",
        prize="The prize for the giveaway",
        winners="Number of winners (default: 1)",
        channel="Channel to host the giveaway in (default: current channel)"
    )
    @has_mod_permissions()
    async def gstart_command(
        self, 
        interaction: discord.Interaction, 
        duration: str,
        prize: str,
        winners: Optional[app_commands.Range[int, 1, 10]] = 1,
        channel: Optional[discord.TextChannel] = None
    ):
        # Use current channel if none specified
        channel = channel or interaction.channel
        
        # Check if the bot has permission to send messages and add reactions in the channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(f"I don't have permission to send messages in {channel.mention}.", ephemeral=True)
            return
        
        if not channel.permissions_for(interaction.guild.me).add_reactions:
            await interaction.response.send_message(f"I don't have permission to add reactions in {channel.mention}.", ephemeral=True)
            return
        
        # Parse the duration
        time_delta = parse_time(duration)
        if not time_delta:
            await interaction.response.send_message(
                "Invalid duration format. Use a format like 1h30m, 1d, 2h, etc.",
                ephemeral=True
            )
            return
        
        # Calculate the end time
        end_time = discord.utils.utcnow() + time_delta
        
        # Create the giveaway embed
        embed = discord.Embed(
            title=prize,
            description=(
                f"React with 🎉 to enter!\n\n"
                f"Hosted by: {interaction.user.mention}\n"
                f"Ends: {format_timestamp(end_time, 'R')}\n"
                f"Winners: {winners}"
            ),
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Giveaway ends at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        await interaction.response.send_message(f"Giveaway started in {channel.mention}!", ephemeral=True)
        
        # Send the giveaway message
        giveaway_message = await channel.send(embed=embed)
        await giveaway_message.add_reaction("🎉")
        
        # Save giveaway information
        self.data_manager.add_giveaway(
            interaction.guild.id, 
            channel.id, 
            giveaway_message.id, 
            prize, 
            end_time,
            interaction.user.id
        )
    
    @app_commands.command(name="gend", description="End a giveaway early")
    @app_commands.describe(
        message_id="ID of the giveaway message to end"
    )
    @has_mod_permissions()
    async def gend_command(
        self, 
        interaction: discord.Interaction, 
        message_id: str
    ):
        await interaction.response.defer(ephemeral=True)
        
        # Validate message ID
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.followup.send("Invalid message ID. Please provide a valid message ID.", ephemeral=True)
            return
        
        # Get giveaways for this guild
        giveaways = self.data_manager.get_giveaways(interaction.guild.id)
        
        # Check if giveaway exists
        if not giveaways or str(message_id) not in giveaways:
            await interaction.followup.send("Giveaway not found. Please check the message ID and try again.", ephemeral=True)
            return
        
        giveaway_data = giveaways.get(str(message_id))
        
        # Check if giveaway is still active
        if not giveaway_data.get("active", True):
            await interaction.followup.send("This giveaway has already ended.", ephemeral=True)
            return
        
        # Get channel and message
        channel_id = int(giveaway_data["channel_id"])
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("Cannot find the channel for this giveaway.", ephemeral=True)
            return
        
        try:
            message = await channel.fetch_message(message_id)
            
            # Mark giveaway as ended
            self.data_manager.end_giveaway(interaction.guild.id, message_id)
            
            # Get participants from reactions
            participants = []
            for reaction in message.reactions:
                if str(reaction.emoji) == "🎉":
                    users = [user async for user in reaction.users() if not user.bot]
                    participants.extend(users)
            
            # Update embed
            embed = message.embeds[0]
            embed.color = discord.Color.red()
            
            # Check if there are participants
            if participants:
                # Pick a winner
                winner = random.choice(participants)
                
                embed.description = f"🎉 Winner: {winner.mention}\n\n" + embed.description
                embed.set_footer(text=f"Giveaway ended early | Winner selected from {len(participants)} participants")
                
                # Send winner announcement
                await channel.send(
                    f"🎊 Congratulations {winner.mention}! You won the **{giveaway_data['prize']}** giveaway!"
                )
                
                await interaction.followup.send(
                    f"Giveaway ended. Winner: {winner.mention}",
                    ephemeral=True
                )
            else:
                embed.description = "🎉 Giveaway ended but no one participated.\n\n" + embed.description
                embed.set_footer(text=f"Giveaway ended early | No participants")
                
                await channel.send(
                    f"🎊 The giveaway for **{giveaway_data['prize']}** has ended, but no one participated."
                )
                
                await interaction.followup.send(
                    "Giveaway ended. No participants found.",
                    ephemeral=True
                )
            
            await message.edit(embed=embed)
            
        except discord.NotFound:
            await interaction.followup.send("Cannot find the giveaway message. It may have been deleted.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to access or edit the giveaway message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred while ending the giveaway: {e}", ephemeral=True)
    
    @app_commands.command(name="greroll", description="Reroll a giveaway winner")
    @app_commands.describe(
        message_id="ID of the giveaway message to reroll"
    )
    @has_mod_permissions()
    async def greroll_command(
        self, 
        interaction: discord.Interaction, 
        message_id: str
    ):
        await interaction.response.defer(ephemeral=True)
        
        # Validate message ID
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.followup.send("Invalid message ID. Please provide a valid message ID.", ephemeral=True)
            return
        
        # Get giveaways for this guild
        giveaways = self.data_manager.get_giveaways(interaction.guild.id)
        
        # Check if giveaway exists
        if not giveaways or str(message_id) not in giveaways:
            await interaction.followup.send("Giveaway not found. Please check the message ID and try again.", ephemeral=True)
            return
        
        giveaway_data = giveaways.get(str(message_id))
        
        # Check if giveaway has ended
        if giveaway_data.get("active", True):
            await interaction.followup.send("This giveaway is still active. You can only reroll ended giveaways.", ephemeral=True)
            return
        
        # Get channel and message
        channel_id = int(giveaway_data["channel_id"])
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.followup.send("Cannot find the channel for this giveaway.", ephemeral=True)
            return
        
        try:
            message = await channel.fetch_message(message_id)
            
            # Get participants from reactions
            participants = []
            for reaction in message.reactions:
                if str(reaction.emoji) == "🎉":
                    users = [user async for user in reaction.users() if not user.bot]
                    participants.extend(users)
            
            # Check if there are participants
            if not participants:
                await interaction.followup.send("Cannot reroll the giveaway winner because there were no participants.", ephemeral=True)
                return
            
            # Pick a new winner
            winner = random.choice(participants)
            
            # Update embed
            embed = message.embeds[0]
            
            # Extract the prize from the embed title
            prize = embed.title
            
            # Get previous description and update with new winner
            description_lines = embed.description.split('\n\n')
            if len(description_lines) > 1:
                # Replace first line (winner line)
                description_lines[0] = f"🎉 Winner: {winner.mention}"
                embed.description = '\n\n'.join(description_lines)
            else:
                # Add winner line at the beginning
                embed.description = f"🎉 Winner: {winner.mention}\n\n" + embed.description
            
            embed.set_footer(text=f"Giveaway rerolled at {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await message.edit(embed=embed)
            
            # Send winner announcement
            await channel.send(
                f"🎊 The giveaway for **{prize}** has been rerolled!\n"
                f"New winner: {winner.mention}! Congratulations!"
            )
            
            await interaction.followup.send(
                f"Giveaway rerolled. New winner: {winner.mention}",
                ephemeral=True
            )
            
        except discord.NotFound:
            await interaction.followup.send("Cannot find the giveaway message. It may have been deleted.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to access or edit the giveaway message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred while rerolling the giveaway: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
