import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict
import asyncio
import datetime

from utils import has_mod_permissions, has_admin_permissions
from data_manager import DataManager

class InviteTracker(commands.Cog):
    """Track server invites and their usage"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.invite_cache = {}
    
    async def cog_load(self):
        """Initialize invite cache when the cog is loaded"""
        # We'll initialize the cache when the bot is ready instead of waiting here
        pass
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize invite cache when the bot is ready"""
        await self.update_invite_cache()
    
    async def update_invite_cache(self):
        """Update the cache of all guild invites"""
        for guild in self.bot.guilds:
            try:
                # Skip if bot doesn't have permission to manage guild
                if not guild.me.guild_permissions.manage_guild:
                    continue
                
                # Get all invites for the guild
                invites = await guild.invites()
                
                # Store in cache
                self.invite_cache[guild.id] = {
                    invite.code: invite.uses for invite in invites
                }
            except (discord.Forbidden, discord.HTTPException):
                # Bot doesn't have permission or another error occurred
                continue
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Update invite cache when the bot joins a new guild"""
        try:
            if guild.me.guild_permissions.manage_guild:
                invites = await guild.invites()
                self.invite_cache[guild.id] = {
                    invite.code: invite.uses for invite in invites
                }
        except (discord.Forbidden, discord.HTTPException):
            pass
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """Update invite cache when a new invite is created"""
        if invite.guild.id not in self.invite_cache:
            self.invite_cache[invite.guild.id] = {}
        
        self.invite_cache[invite.guild.id][invite.code] = invite.uses
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """Update invite cache when an invite is deleted"""
        if invite.guild.id in self.invite_cache and invite.code in self.invite_cache[invite.guild.id]:
            del self.invite_cache[invite.guild.id][invite.code]
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Track which invite was used when a member joins"""
        guild = member.guild
        
        # Skip if bot doesn't have manage guild permission
        if not guild.me.guild_permissions.manage_guild:
            return
        
        # Check if invite tracking is enabled for this guild
        invite_tracking = self.data_manager.get_invite_tracking(guild.id)
        if not invite_tracking or not invite_tracking.get("enabled", False):
            return
        
        # Get the channel for invite notifications
        channel_id = invite_tracking.get("channel_id")
        if not channel_id:
            return
        
        channel = guild.get_channel(int(channel_id))
        if not channel:
            return
        
        try:
            # Get the current invites
            invites_before = self.invite_cache.get(guild.id, {})
            invites_after = {}
            
            # Get new invite counts
            current_invites = await guild.invites()
            for invite in current_invites:
                invites_after[invite.code] = invite.uses
            
            # Update the cache
            self.invite_cache[guild.id] = invites_after
            
            # Find which invite was used
            used_invite = None
            inviter = None
            
            for invite_code, uses in invites_after.items():
                # Check if this invite's uses increased
                if invite_code in invites_before and uses > invites_before[invite_code]:
                    # Find the actual invite object for more information
                    for invite in current_invites:
                        if invite.code == invite_code:
                            used_invite = invite
                            inviter = invite.inviter
                            break
                    break
            
            # Create embed for the notification
            embed = discord.Embed(
                title="Member Joined",
                description=f"{member.mention} has joined the server!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="Account Created",
                value=f"<t:{int(member.created_at.timestamp())}:R>",
                inline=True
            )
            
            # Add inviter information if found
            if used_invite:
                embed.add_field(
                    name="Invited By",
                    value=f"{inviter.mention if inviter else 'Unknown'} using code `{used_invite.code}`",
                    inline=True
                )
                
                if used_invite.max_uses:
                    embed.add_field(
                        name="Invite Uses",
                        value=f"{used_invite.uses}/{used_invite.max_uses}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="Invite Uses",
                        value=str(used_invite.uses),
                        inline=True
                    )
            else:
                embed.add_field(
                    name="Invite",
                    value="Could not determine which invite was used.",
                    inline=True
                )
            
            embed.set_thumbnail(url=member.display_avatar.url)
            
            # Send the notification
            await channel.send(embed=embed)
            
        except (discord.Forbidden, discord.HTTPException):
            # Bot doesn't have permission or another error occurred
            pass
    
    @app_commands.command(name="invitetracking", description="Enable or disable invite tracking")
    @app_commands.describe(
        channel="Channel to send invite notifications",
        enabled="Whether invite tracking should be enabled"
    )
    @has_admin_permissions()
    async def invite_tracking_command(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel,
        enabled: bool = True
    ):
        # Check if the bot has required permissions
        if not interaction.guild.me.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "I need the 'Manage Server' permission to track invites.",
                ephemeral=True
            )
            return
        
        # Set up invite tracking
        success = self.data_manager.set_invite_tracking(
            interaction.guild.id,
            channel.id,
            enabled
        )
        
        if success:
            status = "enabled" if enabled else "disabled"
            await interaction.response.send_message(
                f"Invite tracking has been {status}. "
                f"Notifications will be sent to {channel.mention}."
            )
            
            # Update invite cache
            try:
                invites = await interaction.guild.invites()
                self.invite_cache[interaction.guild.id] = {
                    invite.code: invite.uses for invite in invites
                }
            except (discord.Forbidden, discord.HTTPException):
                pass
        else:
            await interaction.response.send_message(
                "Failed to update invite tracking settings. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="invites", description="Check how many invites a user has")
    @app_commands.describe(
        user="The user to check invites for (defaults to yourself)"
    )
    async def invites_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.User] = None
    ):
        # Use the command user if no user is specified
        target_user = user or interaction.user
        
        # Check if the bot has manage guild permission
        if not interaction.guild.me.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "I need the 'Manage Server' permission to check invites.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Get all invites
            invites = await interaction.guild.invites()
            
            # Filter invites created by the target user
            user_invites = [invite for invite in invites if invite.inviter and invite.inviter.id == target_user.id]
            
            if not user_invites:
                await interaction.followup.send(
                    f"{target_user.mention} has no active invites in this server."
                )
                return
            
            # Count total uses
            total_uses = sum(invite.uses for invite in user_invites)
            
            # Create the embed
            embed = discord.Embed(
                title=f"Invites for {target_user.display_name}",
                description=f"{target_user.mention} has **{total_uses}** total invites from **{len(user_invites)}** active invite links.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.set_thumbnail(url=target_user.display_avatar.url)
            
            # Add invites to the embed (up to 25 to avoid embed field limit)
            for i, invite in enumerate(sorted(user_invites, key=lambda i: i.uses, reverse=True)):
                if i >= 25:
                    break
                
                # Create expiration text
                expires = "Never"
                if invite.max_age > 0:
                    created_at = invite.created_at
                    expires_at = created_at + datetime.timedelta(seconds=invite.max_age)
                    expires = f"<t:{int(expires_at.timestamp())}:R>"
                
                # Create uses text
                uses_text = f"{invite.uses}"
                if invite.max_uses:
                    uses_text += f"/{invite.max_uses}"
                
                embed.add_field(
                    name=f"Invite Code: {invite.code}",
                    value=(
                        f"**Uses:** {uses_text}\n"
                        f"**Channel:** {invite.channel.mention}\n"
                        f"**Expires:** {expires}"
                    ),
                    inline=True
                )
            
            await interaction.followup.send(embed=embed)
            
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to view invites.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"An error occurred: {e}",
                ephemeral=True
            )
    
    @app_commands.command(name="clearinvites", description="Clear all invites for a user")
    @app_commands.describe(
        user="The user to clear invites for"
    )
    @has_admin_permissions()
    async def clear_invites_command(
        self, 
        interaction: discord.Interaction, 
        user: discord.User
    ):
        # Check if the bot has manage guild permission
        if not interaction.guild.me.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "I need the 'Manage Server' permission to clear invites.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Get all invites
            invites = await interaction.guild.invites()
            
            # Filter invites created by the target user
            user_invites = [invite for invite in invites if invite.inviter and invite.inviter.id == user.id]
            
            if not user_invites:
                await interaction.followup.send(
                    f"{user.mention} has no active invites to clear.",
                    ephemeral=True
                )
                return
            
            # Delete each invite
            deleted_count = 0
            for invite in user_invites:
                try:
                    await invite.delete(reason=f"Cleared by {interaction.user.display_name}")
                    deleted_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    # Skip invites that can't be deleted
                    continue
            
            await interaction.followup.send(
                f"Deleted {deleted_count} invites created by {user.mention}.",
                ephemeral=True
            )
            
            # Update the invite cache
            new_invites = await interaction.guild.invites()
            self.invite_cache[interaction.guild.id] = {
                invite.code: invite.uses for invite in new_invites
            }
            
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to manage invites.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"An error occurred: {e}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(InviteTracker(bot))
