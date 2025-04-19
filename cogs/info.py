import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime
import typing
import config
from utils.embeds import success_embed, error_embed, info_embed
from utils.permissions import bot_has_permissions

logger = logging.getLogger(__name__)

class Info(commands.Cog):
    """Information commands for server and users"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="serverinfo", description="Display information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Display information about the server"""
        guild = interaction.guild
        
        try:
            # Get basic server information
            created_at = int(guild.created_at.timestamp())
            
            # Get member counts
            total_members = guild.member_count
            humans = len([m for m in guild.members if not m.bot])
            bots = total_members - humans
            
            # Get online status counts
            online = len([m for m in guild.members if m.status == discord.Status.online])
            idle = len([m for m in guild.members if m.status == discord.Status.idle])
            dnd = len([m for m in guild.members if m.status == discord.Status.dnd])
            offline = len([m for m in guild.members if m.status == discord.Status.offline])
            
            # Get channel counts
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            
            # Get role count (excluding @everyone)
            roles = len(guild.roles) - 1
            
            # Create embed
            embed = discord.Embed(
                title=f"{guild.name} Information",
                description=f"{guild.description or 'No description set.'}",
                color=config.COLORS["INFO"],
                timestamp=datetime.utcnow()
            )
            
            # Set server icon as thumbnail
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # Add general information
            embed.add_field(
                name="General",
                value=f"**ID:** {guild.id}\n"
                      f"**Owner:** {guild.owner.mention}\n"
                      f"**Created:** <t:{created_at}:R>\n"
                      f"**Verification Level:** {str(guild.verification_level).title()}\n"
                      f"**Boost Tier:** {guild.premium_tier}\n"
                      f"**Boosts:** {guild.premium_subscription_count}",
                inline=True
            )
            
            # Add member information
            embed.add_field(
                name="Members",
                value=f"**Total:** {total_members}\n"
                      f"**Humans:** {humans}\n"
                      f"**Bots:** {bots}\n"
                      f"**Online:** {online}\n"
                      f"**Idle:** {idle}\n"
                      f"**DND:** {dnd}\n"
                      f"**Offline:** {offline}",
                inline=True
            )
            
            # Add channel information
            embed.add_field(
                name="Channels",
                value=f"**Text:** {text_channels}\n"
                      f"**Voice:** {voice_channels}\n"
                      f"**Categories:** {categories}\n"
                      f"**Roles:** {roles}",
                inline=True
            )
            
            # Add server features if any
            if guild.features:
                features = [f.replace('_', ' ').title() for f in guild.features]
                embed.add_field(
                    name="Features",
                    value=", ".join(features),
                    inline=False
                )
            
            # If server has a banner, add it
            if guild.banner:
                embed.set_image(url=guild.banner.url)
            
            # Send the embed
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting server info: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while getting server information: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="userinfo", description="Display information about a user")
    @app_commands.describe(
        user="The user to get information about (defaults to yourself)"
    )
    async def userinfo(self, interaction: discord.Interaction, user: typing.Optional[discord.Member] = None):
        """Display information about a user"""
        # Get the target user (command user if not specified)
        target = user or interaction.user
        
        try:
            # Get user information
            joined_at = int(target.joined_at.timestamp()) if target.joined_at else None
            created_at = int(target.created_at.timestamp())
            
            # Get roles (excluding @everyone)
            roles = [role.mention for role in target.roles if role.name != "@everyone"]
            roles.reverse()  # Show highest roles first
            
            if not roles:
                roles_str = "No roles"
            elif len(roles) > 10:
                roles_str = f"{', '.join(roles[:10])} and {len(roles) - 10} more"
            else:
                roles_str = ", ".join(roles)
            
            # Get permissions
            permissions = []
            if target.guild_permissions.administrator:
                permissions.append("Administrator")
            else:
                if target.guild_permissions.manage_guild:
                    permissions.append("Manage Server")
                if target.guild_permissions.ban_members:
                    permissions.append("Ban Members")
                if target.guild_permissions.kick_members:
                    permissions.append("Kick Members")
                if target.guild_permissions.manage_channels:
                    permissions.append("Manage Channels")
                if target.guild_permissions.manage_roles:
                    permissions.append("Manage Roles")
                if target.guild_permissions.moderate_members:
                    permissions.append("Timeout Members")
                if target.guild_permissions.manage_messages:
                    permissions.append("Manage Messages")
            
            # Try to get invite count if possible
            invite_count = None
            if interaction.guild.me.guild_permissions.manage_guild:
                try:
                    invites = await interaction.guild.invites()
                    user_invites = [inv for inv in invites if inv.inviter and inv.inviter.id == target.id]
                    invite_count = sum(inv.uses for inv in user_invites)
                except:
                    pass
            
            # Create embed
            embed = discord.Embed(
                title=f"{target} Information",
                color=target.color or config.COLORS["INFO"],
                timestamp=datetime.utcnow()
            )
            
            # Set user avatar as thumbnail
            embed.set_thumbnail(url=target.display_avatar.url)
            
            # Add general information
            embed.add_field(
                name="General",
                value=f"**ID:** {target.id}\n"
                      f"**Display Name:** {target.display_name}\n"
                      f"**Created:** <t:{created_at}:R>\n"
                      f"**Joined:** {f'<t:{joined_at}:R>' if joined_at else 'Unknown'}",
                inline=True
            )
            
            # Add status information
            status_emoji = {
                discord.Status.online: "🟢",
                discord.Status.idle: "🟡",
                discord.Status.dnd: "🔴",
                discord.Status.offline: "⚫"
            }
            
            status_text = f"{status_emoji.get(target.status, '⚫')} {str(target.status).title()}"
            
            # Get user's activities
            activities = []
            for activity in target.activities:
                if isinstance(activity, discord.CustomActivity) and activity.name:
                    # Custom status
                    emoji = activity.emoji or ""
                    activities.append(f"**Custom Status:** {emoji} {activity.name}")
                elif isinstance(activity, discord.Game):
                    # Playing a game
                    activities.append(f"**Playing:** {activity.name}")
                elif isinstance(activity, discord.Streaming):
                    # Streaming
                    activities.append(f"**Streaming:** [{activity.name}]({activity.url})")
                elif isinstance(activity, discord.Spotify):
                    # Listening to Spotify
                    activities.append(f"**Listening to:** {activity.title} by {activity.artist}")
                elif isinstance(activity, discord.Activity):
                    # Other activity
                    activities.append(f"**{activity.type.name.title()}:** {activity.name}")
            
            # Add status and activity information
            embed.add_field(
                name="Status",
                value=f"{status_text}\n" + "\n".join(activities) if activities else status_text,
                inline=True
            )
            
            # Add server-specific information
            server_info = []
            
            # Add invite count if available
            if invite_count is not None:
                server_info.append(f"**Invites:** {invite_count}")
            
            # Add key permissions
            if permissions:
                server_info.append(f"**Key Permissions:** {', '.join(permissions)}")
            
            # Add boosting status
            if target.premium_since:
                boost_since = int(target.premium_since.timestamp())
                server_info.append(f"**Boosting Since:** <t:{boost_since}:R>")
            
            if server_info:
                embed.add_field(
                    name="Server",
                    value="\n".join(server_info),
                    inline=False
                )
            
            # Add roles
            embed.add_field(
                name=f"Roles [{len(roles)}]",
                value=roles_str,
                inline=False
            )
            
            # Send the embed
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while getting user information: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="membercount", description="Display the current member count")
    async def membercount(self, interaction: discord.Interaction):
        """Display the current member count"""
        guild = interaction.guild
        
        try:
            # Get member counts
            total_members = guild.member_count
            humans = len([m for m in guild.members if not m.bot])
            bots = total_members - humans
            
            # Create embed
            embed = discord.Embed(
                title=f"{guild.name} Member Count",
                color=config.COLORS["INFO"],
                timestamp=datetime.utcnow()
            )
            
            # Set server icon as thumbnail
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # Add member counts
            embed.description = f"**Total Members:** {total_members}\n**Humans:** {humans}\n**Bots:** {bots}"
            
            # Send the embed
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error getting member count: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while getting member count: {e}"),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Info(bot))
