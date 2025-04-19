import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import datetime
from typing import Optional, Union
import time

from utils import has_mod_permissions, format_timestamp, parse_time, generate_embed
from data_manager import DataManager

class Utility(commands.Cog):
    """Utility commands for general server functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.timers = {}
    
    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping_command(self, interaction: discord.Interaction):
        start_time = time.time()
        await interaction.response.defer(ephemeral=True)
        
        # Calculate API latency
        api_latency = round((time.time() - start_time) * 1000)
        
        # Get websocket latency
        websocket_latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description="Bot latency information",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="API Latency", value=f"{api_latency}ms", inline=True)
        embed.add_field(name="WebSocket Latency", value=f"{websocket_latency}ms", inline=True)
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="avatar", description="Get a user's avatar")
    @app_commands.describe(
        user="The user to get the avatar of (defaults to yourself)"
    )
    async def avatar_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.User] = None
    ):
        # Use the command user if no user is specified
        target_user = user or interaction.user
        
        embed = discord.Embed(
            title=f"{target_user.name}'s Avatar",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add the avatar to the embed
        embed.set_image(url=target_user.display_avatar.url)
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Open in Browser",
            url=target_user.display_avatar.url,
            style=discord.ButtonStyle.link
        ))
        
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="userinfo", description="Get information about a user")
    @app_commands.describe(
        user="The user to get information about (defaults to yourself)"
    )
    async def userinfo_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.User] = None
    ):
        # Use the command user if no user is specified
        target_user = user or interaction.user
        
        embed = discord.Embed(
            title=f"User Information",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add user basic information
        embed.add_field(name="Username", value=target_user.name, inline=True)
        embed.add_field(name="User ID", value=target_user.id, inline=True)
        embed.add_field(name="Created", value=format_timestamp(target_user.created_at, 'f'), inline=True)
        
        # Get member information if the user is in the guild
        member = interaction.guild.get_member(target_user.id)
        if member:
            # Add member information
            joined_at = format_timestamp(member.joined_at, 'f') if member.joined_at else "Unknown"
            embed.add_field(name="Joined Server", value=joined_at, inline=True)
            
            # Get top role
            top_role = member.top_role
            if top_role and top_role != interaction.guild.default_role:
                embed.add_field(name="Highest Role", value=top_role.mention, inline=True)
            
            # Get status and activity if available
            if member.status:
                embed.add_field(name="Status", value=str(member.status).title(), inline=True)
            
            if member.activity:
                activity_type = str(member.activity.type).split('.')[-1].title()
                embed.add_field(name=f"{activity_type}", value=member.activity.name, inline=True)
            
            # Check how many warnings the user has
            warnings = await self.data_manager.get_warnings(interaction.guild.id, target_user.id)
            if warnings:
                embed.add_field(name="Warnings", value=str(len(warnings)), inline=True)
        
        # Add user avatar
        embed.set_thumbnail(url=target_user.display_avatar.url)
        
        # Get member roles if available
        if member and len(member.roles) > 1:  # More than just @everyone
            role_mentions = [role.mention for role in reversed(member.roles) if role != interaction.guild.default_role]
            if len(role_mentions) > 0:
                roles_value = ", ".join(role_mentions)
                if len(roles_value) > 1024:  # Discord field value length limit
                    roles_value = f"{len(role_mentions)} roles"
                embed.add_field(name="Roles", value=roles_value, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="Get information about the server")
    async def serverinfo_command(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        embed = discord.Embed(
            title=f"{guild.name} Information",
            description=guild.description or "No description",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Basic server info
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Created", value=format_timestamp(guild.created_at, 'f'), inline=True)
        
        # Member counts
        total_members = guild.member_count
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        
        embed.add_field(name="Members", value=f"{human_count} humans, {bot_count} bots", inline=True)
        
        # Channel counts
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed.add_field(name="Channels", value=f"{text_channels} text, {voice_channels} voice, {categories} categories", inline=True)
        
        # Role count
        embed.add_field(name="Roles", value=str(len(guild.roles) - 1), inline=True)  # Subtract @everyone
        
        # Emoji count
        emoji_count = len(guild.emojis)
        if guild.premium_tier >= 1:
            emoji_limit = 100 if guild.premium_tier == 1 else (200 if guild.premium_tier == 2 else 500)
            embed.add_field(name="Emojis", value=f"{emoji_count}/{emoji_limit}", inline=True)
        else:
            embed.add_field(name="Emojis", value=str(emoji_count), inline=True)
        
        # Boost status
        embed.add_field(name="Boost Tier", value=f"Level {guild.premium_tier}", inline=True)
        embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)
        
        # Verification level
        embed.add_field(name="Verification", value=str(guild.verification_level).title(), inline=True)
        
        # Server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Server banner
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="timer", description="Set a timer")
    @app_commands.describe(
        duration="Timer duration (e.g., 1h30m, 1d, 2h)",
        reminder="What to remind you about (optional)"
    )
    async def timer_command(
        self, 
        interaction: discord.Interaction, 
        duration: str,
        reminder: Optional[str] = None
    ):
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
        
        embed = discord.Embed(
            title="⏰ Timer Set",
            description=f"Timer set for {duration}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Ends", value=format_timestamp(end_time, 'R'), inline=True)
        
        if reminder:
            embed.add_field(name="Reminder", value=reminder, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Convert to seconds for asyncio.sleep
        seconds = time_delta.total_seconds()
        
        # Check if duration is reasonable
        if seconds > 60 * 60 * 24 * 7:  # 1 week
            return  # Don't actually create very long timers
        
        # Create a unique ID for this timer
        timer_id = f"{interaction.user.id}-{int(time.time())}"
        
        # Store the timer
        self.timers[timer_id] = {
            "user_id": interaction.user.id,
            "end_time": end_time,
            "reminder": reminder,
            "channel_id": interaction.channel.id
        }
        
        # Start the timer
        asyncio.create_task(self._run_timer(timer_id, seconds))
    
    async def _run_timer(self, timer_id, seconds):
        """Run a timer and notify the user when it's complete"""
        try:
            await asyncio.sleep(seconds)
            
            # Get the timer information
            timer_info = self.timers.pop(timer_id, None)
            if not timer_info:
                return  # Timer was removed
            
            user = self.bot.get_user(timer_info["user_id"])
            if not user:
                return  # User not found
            
            # Create the timer complete message
            embed = discord.Embed(
                title="⏰ Timer Complete",
                description="Your timer has ended!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            if timer_info["reminder"]:
                embed.add_field(name="Reminder", value=timer_info["reminder"], inline=False)
            
            # Try to DM the user
            try:
                await user.send(embed=embed)
            except (discord.Forbidden, discord.HTTPException):
                # If DM fails, try to send in the original channel
                channel = self.bot.get_channel(timer_info["channel_id"])
                if channel:
                    await channel.send(f"{user.mention}", embed=embed)
        
        except asyncio.CancelledError:
            # Timer was cancelled
            self.timers.pop(timer_id, None)
        except Exception as e:
            print(f"Error in timer: {e}")
    
    @app_commands.command(name="membercount", description="Display member count information")
    async def membercount_command(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        # Calculate counts
        total_members = guild.member_count
        online_count = sum(1 for member in guild.members if member.status and member.status != discord.Status.offline)
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        
        embed = discord.Embed(
            title=f"{guild.name} Member Count",
            description=f"Total Members: **{total_members}**",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(name="Humans", value=str(human_count), inline=True)
        embed.add_field(name="Bots", value=str(bot_count), inline=True)
        
        if online_count > 0:
            embed.add_field(name="Online", value=str(online_count), inline=True)
        
        # Set server icon as thumbnail
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="invite", description="Get invite links for the bot and server")
    async def invite_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Invite Links",
            description="Here are the invite links for the bot and this server.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Create bot invite URL with necessary permissions
        permissions = discord.Permissions(
            manage_channels=True,
            manage_roles=True,
            manage_messages=True,
            kick_members=True,
            ban_members=True,
            moderate_members=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            use_external_emojis=True,
            external_emojis=True,
            manage_webhooks=True
        )
        
        bot_invite = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands")
        )
        
        # Try to create a server invite
        server_invite = None
        try:
            # Check if the bot has permission to create invites
            if interaction.guild.me.guild_permissions.create_instant_invite:
                # Find a suitable channel for the invite
                invite_channel = next(
                    (c for c in interaction.guild.text_channels 
                     if c.permissions_for(interaction.guild.me).create_instant_invite),
                    None
                )
                
                if invite_channel:
                    invite = await invite_channel.create_invite(
                        max_age=86400,  # 24 hours
                        max_uses=0,     # Unlimited uses
                        unique=True
                    )
                    server_invite = invite.url
        except discord.Forbidden:
            pass
        
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Invite Bot",
            url=bot_invite,
            style=discord.ButtonStyle.link
        ))
        
        if server_invite:
            embed.add_field(name="Server Invite", value=f"[Click here to join the server]({server_invite})", inline=False)
            view.add_item(discord.ui.Button(
                label="Join Server",
                url=server_invite,
                style=discord.ButtonStyle.link
            ))
        else:
            embed.add_field(name="Server Invite", value="I don't have permission to create a server invite.", inline=False)
        
        await interaction.response.send_message(embed=embed, view=view)
    
    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
        option5="Fifth option (optional)"
    )
    async def poll_command(
        self, 
        interaction: discord.Interaction, 
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        option5: Optional[str] = None
    ):
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
        if option5:
            options.append(option5)
        
        # Create the poll embed
        embed = discord.Embed(
            title="📊 " + question,
            description="React with the emoji to vote!",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add options to the embed
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        
        for i, option in enumerate(options):
            embed.add_field(
                name=f"{emojis[i]} Option {i+1}",
                value=option,
                inline=False
            )
        
        embed.set_footer(text=f"Poll created by {interaction.user}")
        
        # Send the poll
        await interaction.response.send_message("Poll created!")
        poll_message = await interaction.channel.send(embed=embed)
        
        # Add reaction options
        for i in range(len(options)):
            await poll_message.add_reaction(emojis[i])

async def setup(bot):
    await bot.add_cog(Utility(bot))
