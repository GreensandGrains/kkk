import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import json
from datetime import datetime, timedelta
import typing
import config
from utils.embeds import success_embed, error_embed, info_embed
from utils.permissions import has_mod_perms, has_admin_perms, bot_has_permissions
from utils.data_manager import get_guild_data, update_guild_data, get_server_setting, set_server_setting

logger = logging.getLogger(__name__)

class Bump(commands.Cog):
    """Server bump system with cooldowns and reminders"""
    
    def __init__(self, bot):
        self.bot = bot
        self.remind_tasks = {}  # Store bump reminder tasks
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Set up any active bump reminders when the bot starts"""
        await self.load_bump_reminders()
    
    async def load_bump_reminders(self):
        """Load active bump reminders and set up tasks"""
        try:
            # Load all server bump data
            bump_data = json.loads(open(config.BUMP_FILE, 'r').read())
            
            for guild_id, guild_data in bump_data.items():
                # Check if there's an active reminder
                last_bump = guild_data.get("last_bump")
                if not last_bump:
                    continue
                
                # Calculate when the next bump is available
                last_bump_time = datetime.fromisoformat(last_bump)
                next_bump_time = last_bump_time + timedelta(seconds=config.BUMP_COOLDOWN)
                
                # Only set a reminder if the next bump is in the future
                now = datetime.utcnow()
                if next_bump_time > now:
                    # Calculate seconds until the reminder should trigger
                    seconds_until_reminder = (next_bump_time - now).total_seconds()
                    
                    # Set up the reminder task
                    self.create_reminder_task(int(guild_id), seconds_until_reminder)
                    logger.info(f"Set up bump reminder for guild {guild_id} in {seconds_until_reminder} seconds")
                
        except Exception as e:
            logger.error(f"Error loading bump reminders: {e}")
    
    def create_reminder_task(self, guild_id, delay):
        """Create a task to send a bump reminder after the delay"""
        async def reminder_task():
            await asyncio.sleep(delay)
            
            try:
                # Get the guild
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    logger.warning(f"Could not find guild {guild_id} for bump reminder")
                    return
                
                # Get the bump channel
                bump_channel_id = await get_server_setting(guild_id, "bump_channel")
                if not bump_channel_id:
                    return
                
                bump_channel = guild.get_channel(int(bump_channel_id))
                if not bump_channel:
                    logger.warning(f"Could not find bump channel {bump_channel_id} for guild {guild_id}")
                    return
                
                # Get the bump role if set
                bump_role_id = await get_server_setting(guild_id, "bump_role")
                bump_role = None
                if bump_role_id:
                    bump_role = guild.get_role(int(bump_role_id))
                
                # Create the reminder message
                embed = discord.Embed(
                    title="Bump Available!",
                    description="The server can be bumped again! Use `/bump` to bump the server.",
                    color=config.COLORS["SUCCESS"],
                    timestamp=datetime.utcnow()
                )
                
                # Add bump statistics
                bump_data = await get_guild_data(config.BUMP_FILE, guild_id)
                bump_count = bump_data.get("bump_count", 0)
                top_bumper_id = bump_data.get("top_bumper")
                
                embed.add_field(
                    name="Bump Statistics",
                    value=f"**Total Bumps:** {bump_count}\n"
                         f"**Top Bumper:** {f'<@{top_bumper_id}>' if top_bumper_id else 'No one yet'}"
                )
                
                # Send the reminder
                mention = bump_role.mention if bump_role else ""
                await bump_channel.send(mention, embed=embed)
                
            except Exception as e:
                logger.error(f"Error sending bump reminder: {e}")
            
            # Remove the task from active tasks
            if guild_id in self.remind_tasks:
                del self.remind_tasks[guild_id]
        
        # Create and store the task
        task = asyncio.create_task(reminder_task())
        self.remind_tasks[guild_id] = task
        
        return task
    
    @app_commands.command(name="bump", description="Bump the server to increase its visibility")
    async def bump(self, interaction: discord.Interaction):
        """Bump the server to increase its visibility"""
        try:
            # Get bump data for this server
            bump_data = await get_guild_data(config.BUMP_FILE, interaction.guild.id)
            
            # Check if there's a bump channel set
            bump_channel_id = await get_server_setting(interaction.guild.id, "bump_channel")
            if not bump_channel_id:
                await interaction.response.send_message(
                    embed=error_embed(
                        "No Bump Channel",
                        "The bump channel hasn't been set up yet. Ask an admin to use `/bump_settings`."
                    ),
                    ephemeral=True
                )
                return
            
            # Check if bump is on cooldown
            last_bump = bump_data.get("last_bump")
            if last_bump:
                last_bump_time = datetime.fromisoformat(last_bump)
                next_bump_time = last_bump_time + timedelta(seconds=config.BUMP_COOLDOWN)
                
                now = datetime.utcnow()
                if next_bump_time > now:
                    # Bump is on cooldown
                    cooldown_remaining = int((next_bump_time - now).total_seconds())
                    hours, remainder = divmod(cooldown_remaining, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    cooldown_str = ""
                    if hours:
                        cooldown_str += f"{hours}h "
                    if minutes:
                        cooldown_str += f"{minutes}m "
                    cooldown_str += f"{seconds}s"
                    
                    await interaction.response.send_message(
                        embed=error_embed(
                            "Bump on Cooldown",
                            f"The server was recently bumped. You can bump again <t:{int(next_bump_time.timestamp())}:R>.\n"
                            f"Time remaining: **{cooldown_str}**"
                        ),
                        ephemeral=True
                    )
                    return
            
            # Update bump data
            bump_count = bump_data.get("bump_count", 0) + 1
            bump_data["bump_count"] = bump_count
            bump_data["last_bump"] = datetime.utcnow().isoformat()
            
            # Update user's bump count
            user_id = str(interaction.user.id)
            if "user_bumps" not in bump_data:
                bump_data["user_bumps"] = {}
            
            if user_id not in bump_data["user_bumps"]:
                bump_data["user_bumps"][user_id] = 0
            
            bump_data["user_bumps"][user_id] += 1
            
            # Update top bumper if needed
            top_bumper_id = bump_data.get("top_bumper")
            top_bumper_count = 0
            
            if top_bumper_id:
                top_bumper_count = bump_data["user_bumps"].get(top_bumper_id, 0)
            
            if bump_data["user_bumps"][user_id] > top_bumper_count:
                bump_data["top_bumper"] = user_id
            
            # Save the bump data
            await update_guild_data(config.BUMP_FILE, interaction.guild.id, bump_data)
            
            # Create bump success message
            embed = discord.Embed(
                title="Server Bumped! 🚀",
                description=f"Thanks for bumping the server, {interaction.user.mention}!\n\n"
                          f"**Bump Count:** {bump_count}\n"
                          f"**Your Bumps:** {bump_data['user_bumps'][user_id]}\n"
                          f"**Next Bump:** <t:{int((datetime.utcnow() + timedelta(seconds=config.BUMP_COOLDOWN)).timestamp())}:R>",
                color=config.COLORS["SUCCESS"],
                timestamp=datetime.utcnow()
            )
            
            # Add banner if set
            banner_url = await get_server_setting(interaction.guild.id, "bump_banner")
            if banner_url:
                embed.set_image(url=banner_url)
            
            # Send to bump channel
            bump_channel = interaction.guild.get_channel(int(bump_channel_id))
            if bump_channel and bump_channel.permissions_for(interaction.guild.me).send_messages:
                await bump_channel.send(embed=embed)
                
                # Set up a reminder for when the bump cooldown expires
                if interaction.guild.id in self.remind_tasks:
                    self.remind_tasks[interaction.guild.id].cancel()
                
                self.create_reminder_task(interaction.guild.id, config.BUMP_COOLDOWN)
            
            # Respond to the interaction
            await interaction.response.send_message(
                embed=success_embed(
                    title="Server Bumped!",
                    description="Thank you for bumping the server! The bump has been recorded."
                )
            )
            
        except Exception as e:
            logger.error(f"Error bumping server: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while bumping the server: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="bump_settings", description="Configure the server bump system")
    @app_commands.describe(
        channel="The channel where bump messages will be sent",
        role="The role to ping when bump is available (optional)",
        banner="URL to an image/banner to show in bump messages (optional)"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def bump_settings(self, 
                          interaction: discord.Interaction, 
                          channel: typing.Optional[discord.TextChannel] = None,
                          role: typing.Optional[discord.Role] = None,
                          banner: typing.Optional[str] = None):
        """Configure the server bump system"""
        try:
            settings_changed = False
            
            # Update bump channel if provided
            if channel:
                # Check if bot can send messages to the channel
                if not channel.permissions_for(interaction.guild.me).send_messages:
                    await interaction.response.send_message(
                        embed=error_embed("Missing Permissions", "I don't have permission to send messages in that channel."),
                        ephemeral=True
                    )
                    return
                
                await set_server_setting(interaction.guild.id, "bump_channel", str(channel.id))
                settings_changed = True
            
            # Update bump role if provided
            if role:
                await set_server_setting(interaction.guild.id, "bump_role", str(role.id))
                settings_changed = True
            
            # Update bump banner if provided
            if banner:
                # Basic URL validation
                if not (banner.startswith("http://") or banner.startswith("https://")):
                    await interaction.response.send_message(
                        embed=error_embed("Invalid URL", "Please provide a valid URL starting with http:// or https://"),
                        ephemeral=True
                    )
                    return
                
                await set_server_setting(interaction.guild.id, "bump_banner", banner)
                settings_changed = True
            
            # If no settings were provided, show current settings
            if not settings_changed:
                bump_channel_id = await get_server_setting(interaction.guild.id, "bump_channel")
                bump_role_id = await get_server_setting(interaction.guild.id, "bump_role")
                bump_banner = await get_server_setting(interaction.guild.id, "bump_banner")
                
                bump_channel_text = f"<#{bump_channel_id}>" if bump_channel_id else "Not set"
                bump_role_text = f"<@&{bump_role_id}>" if bump_role_id else "Not set"
                
                embed = discord.Embed(
                    title="Bump System Settings",
                    description="Current bump system settings:",
                    color=config.COLORS["INFO"]
                )
                
                embed.add_field(
                    name="Bump Channel",
                    value=bump_channel_text,
                    inline=True
                )
                
                embed.add_field(
                    name="Bump Role",
                    value=bump_role_text,
                    inline=True
                )
                
                embed.add_field(
                    name="Bump Banner",
                    value=bump_banner or "Not set",
                    inline=False
                )
                
                if bump_banner:
                    embed.set_image(url=bump_banner)
                
                await interaction.response.send_message(embed=embed)
                return
            
            # Send success message
            await interaction.response.send_message(
                embed=success_embed(
                    title="Settings Updated",
                    description="Bump system settings have been updated."
                )
            )
            
        except Exception as e:
            logger.error(f"Error updating bump settings: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while updating bump settings: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="bumps", description="Show bump statistics for the server or a user")
    @app_commands.describe(
        user="The user to show bump statistics for (optional)"
    )
    async def bumps(self, interaction: discord.Interaction, user: typing.Optional[discord.User] = None):
        """Show bump statistics for the server or a user"""
        try:
            # Get bump data
            bump_data = await get_guild_data(config.BUMP_FILE, interaction.guild.id)
            bump_count = bump_data.get("bump_count", 0)
            
            if not user:
                # Show server stats
                embed = discord.Embed(
                    title="Server Bump Statistics",
                    description=f"This server has been bumped **{bump_count}** times.",
                    color=config.COLORS["INFO"],
                    timestamp=datetime.utcnow()
                )
                
                # Add last bump time if available
                last_bump = bump_data.get("last_bump")
                if last_bump:
                    last_bump_time = datetime.fromisoformat(last_bump)
                    next_bump_time = last_bump_time + timedelta(seconds=config.BUMP_COOLDOWN)
                    
                    now = datetime.utcnow()
                    if next_bump_time > now:
                        embed.add_field(
                            name="Next Bump",
                            value=f"<t:{int(next_bump_time.timestamp())}:R>",
                            inline=True
                        )
                    else:
                        embed.add_field(
                            name="Status",
                            value="Ready to Bump!",
                            inline=True
                        )
                    
                    embed.add_field(
                        name="Last Bumped",
                        value=f"<t:{int(last_bump_time.timestamp())}:R>",
                        inline=True
                    )
                
                # Add top bumpers if any
                if "user_bumps" in bump_data and bump_data["user_bumps"]:
                    # Sort users by bump count
                    top_users = sorted(
                        bump_data["user_bumps"].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:5]  # Top 5
                    
                    top_text = []
                    for i, (user_id, count) in enumerate(top_users, 1):
                        top_text.append(f"{i}. <@{user_id}> - **{count}** bumps")
                    
                    embed.add_field(
                        name="Top Bumpers",
                        value="\n".join(top_text) if top_text else "No bumps recorded yet",
                        inline=False
                    )
            else:
                # Show user stats
                user_id = str(user.id)
                user_bumps = bump_data.get("user_bumps", {}).get(user_id, 0)
                
                embed = discord.Embed(
                    title=f"Bump Statistics for {user.display_name}",
                    description=f"{user.mention} has bumped this server **{user_bumps}** times.",
                    color=config.COLORS["INFO"],
                    timestamp=datetime.utcnow()
                )
                
                # Add user avatar as thumbnail
                embed.set_thumbnail(url=user.display_avatar.url)
                
                # Show ranking if possible
                if "user_bumps" in bump_data and bump_data["user_bumps"]:
                    # Sort users by bump count
                    ranked_users = sorted(
                        bump_data["user_bumps"].items(),
                        key=lambda x: x[1],
                        reverse=True
                    )
                    
                    # Find user's rank
                    for i, (u_id, _) in enumerate(ranked_users, 1):
                        if u_id == user_id:
                            embed.add_field(
                                name="Rank",
                                value=f"#{i} of {len(ranked_users)} bumpers",
                                inline=True
                            )
                            break
                
                # Show percentage of total bumps
                if bump_count > 0:
                    percentage = (user_bumps / bump_count) * 100
                    embed.add_field(
                        name="Contribution",
                        value=f"{percentage:.1f}% of all bumps",
                        inline=True
                    )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing bump statistics: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while showing bump statistics: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="clear_bumps", description="Reset bump statistics")
    @app_commands.describe(
        target="What to reset: 'all' for complete reset, 'cooldown' to reset cooldown, or 'user' for specific user",
        user="The user to reset bumps for (only used if target is 'user')"
    )
    @app_commands.choices(target=[
        app_commands.Choice(name="All Bump Data", value="all"),
        app_commands.Choice(name="Bump Cooldown", value="cooldown"),
        app_commands.Choice(name="Specific User", value="user")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_bumps(self, 
                         interaction: discord.Interaction, 
                         target: str,
                         user: typing.Optional[discord.User] = None):
        """Reset bump statistics"""
        try:
            # Get bump data
            bump_data = await get_guild_data(config.BUMP_FILE, interaction.guild.id)
            
            if target == "all":
                # Reset everything
                bump_data = {
                    "bump_count": 0,
                    "user_bumps": {},
                    "top_bumper": None
                }
                
                # Save data
                await update_guild_data(config.BUMP_FILE, interaction.guild.id, bump_data)
                
                # Cancel any active reminder
                if interaction.guild.id in self.remind_tasks:
                    self.remind_tasks[interaction.guild.id].cancel()
                    del self.remind_tasks[interaction.guild.id]
                
                await interaction.response.send_message(
                    embed=success_embed(
                        title="Bump Data Reset",
                        description="All bump statistics have been reset."
                    )
                )
                
            elif target == "cooldown":
                # Just reset the cooldown
                if "last_bump" in bump_data:
                    del bump_data["last_bump"]
                
                # Save data
                await update_guild_data(config.BUMP_FILE, interaction.guild.id, bump_data)
                
                # Cancel any active reminder
                if interaction.guild.id in self.remind_tasks:
                    self.remind_tasks[interaction.guild.id].cancel()
                    del self.remind_tasks[interaction.guild.id]
                
                await interaction.response.send_message(
                    embed=success_embed(
                        title="Bump Cooldown Reset",
                        description="The bump cooldown has been reset. The server can be bumped immediately."
                    )
                )
                
            elif target == "user":
                # Reset bumps for a specific user
                if not user:
                    await interaction.response.send_message(
                        embed=error_embed("User Required", "Please specify a user when using the 'user' target."),
                        ephemeral=True
                    )
                    return
                
                user_id = str(user.id)
                
                # Remove user from bump data
                if "user_bumps" in bump_data and user_id in bump_data["user_bumps"]:
                    del bump_data["user_bumps"][user_id]
                
                # Update top bumper if necessary
                if bump_data.get("top_bumper") == user_id:
                    # Find new top bumper
                    if "user_bumps" in bump_data and bump_data["user_bumps"]:
                        top_user = max(bump_data["user_bumps"].items(), key=lambda x: x[1])
                        bump_data["top_bumper"] = top_user[0]
                    else:
                        bump_data["top_bumper"] = None
                
                # Save data
                await update_guild_data(config.BUMP_FILE, interaction.guild.id, bump_data)
                
                await interaction.response.send_message(
                    embed=success_embed(
                        title="User Bumps Reset",
                        description=f"Bump statistics for {user.mention} have been reset."
                    )
                )
                
        except Exception as e:
            logger.error(f"Error clearing bump statistics: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while clearing bump statistics: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="ad_banner", description="Set a custom bump advertisement banner")
    @app_commands.describe(
        banner_url="URL to the banner image to use for bumps"
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def ad_banner(self, interaction: discord.Interaction, banner_url: str):
        """Set a custom bump advertisement banner"""
        # Basic URL validation
        if not (banner_url.startswith("http://") or banner_url.startswith("https://")):
            await interaction.response.send_message(
                embed=error_embed("Invalid URL", "Please provide a valid URL starting with http:// or https://"),
                ephemeral=True
            )
            return
        
        try:
            # Save the banner URL
            await set_server_setting(interaction.guild.id, "bump_banner", banner_url)
            
            # Create a preview embed
            embed = discord.Embed(
                title="Banner Preview",
                description="This banner will be displayed in bump messages.",
                color=config.COLORS["SUCCESS"]
            )
            
            embed.set_image(url=banner_url)
            
            await interaction.response.send_message(
                embed=success_embed(
                    title="Banner Set",
                    description="The bump advertisement banner has been set."
                ),
                ephemeral=False
            )
            
            # Send the preview as a followup
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error setting bump banner: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while setting the bump banner: {e}"),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Bump(bot))
