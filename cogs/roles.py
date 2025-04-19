import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import json
import typing
import config
from utils.embeds import success_embed, error_embed, info_embed
from utils.permissions import has_mod_perms, has_admin_perms, bot_has_permissions
from utils.data_manager import get_server_setting, set_server_setting

logger = logging.getLogger(__name__)

class ReactionRoleButton(discord.ui.Button):
    """Button for reaction roles"""
    def __init__(self, role_id, emoji, custom_id=None):
        self.role_id = role_id
        
        # Determine if emoji is custom or unicode
        try:
            # Try to convert to emoji
            discord_emoji = discord.PartialEmoji.from_str(emoji)
            if discord_emoji.id:
                # It's a custom emoji
                super().__init__(style=discord.ButtonStyle.secondary, emoji=discord_emoji, custom_id=custom_id)
            else:
                # It's a unicode emoji
                super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=custom_id)
        except:
            # Fallback to just using the string
            super().__init__(style=discord.ButtonStyle.secondary, emoji="🔄", label=emoji, custom_id=custom_id)
    
    async def callback(self, interaction):
        """Handle button click to toggle role"""
        # Get the role from the server
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message(
                "This role no longer exists on the server.", 
                ephemeral=True
            )
            return
        
        # Check if bot can manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "I don't have permission to manage roles.", 
                ephemeral=True
            )
            return
            
        # Check if role is too high for bot to manage
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message(
                "I can't assign this role because it's higher than or equal to my highest role.", 
                ephemeral=True
            )
            return
        
        # Toggle role
        member = interaction.user
        if role in member.roles:
            # Remove role
            await member.remove_roles(role, reason="Reaction role button")
            await interaction.response.send_message(
                f"Removed the {role.mention} role.", 
                ephemeral=True
            )
        else:
            # Add role
            await member.add_roles(role, reason="Reaction role button")
            await interaction.response.send_message(
                f"Added the {role.mention} role.", 
                ephemeral=True
            )

class ReactionRoleView(discord.ui.View):
    """View containing role buttons"""
    def __init__(self, roles_data):
        super().__init__(timeout=None)  # Persistent view
        
        # Add buttons for each role
        for i, (role_id, emoji) in enumerate(roles_data.items()):
            self.add_item(ReactionRoleButton(
                int(role_id), 
                emoji,
                custom_id=f"reaction_role_{role_id}"
            ))

class Roles(commands.Cog):
    """Role management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Register persistent view when bot starts"""
        # This would need to load all existing reaction role messages
        # and register their views if we wanted them to persist through restarts
        pass
        
    @app_commands.command(name="add_role", description="Add a role to a member")
    @app_commands.describe(
        member="The member to add the role to",
        role="The role to add"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Add a role to a member"""
        # Check if the bot can manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I don't have permission to manage roles."),
                ephemeral=True
            )
            return
        
        # Check if the role is higher than the bot's highest role
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message(
                embed=error_embed("Role Too High", "I can't assign a role that's higher than or equal to my highest role."),
                ephemeral=True
            )
            return
        
        # Check if the role is higher than the command user's highest role
        if role.position >= interaction.user.top_role.position and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Role Too High", "You can't assign a role that's higher than or equal to your highest role."),
                ephemeral=True
            )
            return
        
        try:
            # Check if member already has the role
            if role in member.roles:
                await interaction.response.send_message(
                    embed=info_embed("Role Already Assigned", f"{member.mention} already has the {role.mention} role."),
                    ephemeral=True
                )
                return
            
            # Add the role
            await member.add_roles(role, reason=f"Role added by {interaction.user}")
            
            # Send success message
            await interaction.response.send_message(
                embed=success_embed(
                    title="Role Added",
                    description=f"Added {role.mention} to {member.mention}."
                )
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Forbidden", "I don't have permission to add that role."),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error adding role: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while adding the role: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="remove_role", description="Remove a role from a member")
    @app_commands.describe(
        member="The member to remove the role from",
        role="The role to remove"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        """Remove a role from a member"""
        # Check if the bot can manage roles
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I don't have permission to manage roles."),
                ephemeral=True
            )
            return
        
        # Check if the role is higher than the bot's highest role
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message(
                embed=error_embed("Role Too High", "I can't remove a role that's higher than or equal to my highest role."),
                ephemeral=True
            )
            return
        
        # Check if the role is higher than the command user's highest role
        if role.position >= interaction.user.top_role.position and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Role Too High", "You can't remove a role that's higher than or equal to your highest role."),
                ephemeral=True
            )
            return
        
        try:
            # Check if member has the role
            if role not in member.roles:
                await interaction.response.send_message(
                    embed=info_embed("No Role", f"{member.mention} doesn't have the {role.mention} role."),
                    ephemeral=True
                )
                return
            
            # Remove the role
            await member.remove_roles(role, reason=f"Role removed by {interaction.user}")
            
            # Send success message
            await interaction.response.send_message(
                embed=success_embed(
                    title="Role Removed",
                    description=f"Removed {role.mention} from {member.mention}."
                )
            )
            
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("Forbidden", "I don't have permission to remove that role."),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error removing role: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while removing the role: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="admin_role", description="Set the admin role for bot commands")
    @app_commands.describe(
        role="The role to set as admin"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set the admin role for bot commands"""
        try:
            # Save the admin role ID to server settings
            await set_server_setting(interaction.guild.id, "admin_role", str(role.id))
            
            # Send success message
            await interaction.response.send_message(
                embed=success_embed(
                    title="Admin Role Set",
                    description=f"{role.mention} has been set as the admin role for bot commands."
                )
            )
            
        except Exception as e:
            logger.error(f"Error setting admin role: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while setting the admin role: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="mod_role", description="Set the moderator role for bot commands")
    @app_commands.describe(
        role="The role to set as moderator"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def mod_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set the moderator role for bot commands"""
        try:
            # Save the mod role ID to server settings
            await set_server_setting(interaction.guild.id, "mod_role", str(role.id))
            
            # Send success message
            await interaction.response.send_message(
                embed=success_embed(
                    title="Moderator Role Set",
                    description=f"{role.mention} has been set as the moderator role for bot commands."
                )
            )
            
        except Exception as e:
            logger.error(f"Error setting mod role: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while setting the moderator role: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="reaction_role", description="Create a reaction role message with buttons")
    @app_commands.describe(
        channel="The channel to send the reaction role message to",
        title="The title of the reaction role message",
        description="The description of the reaction role message",
        color="The color of the embed in hex format (e.g., #FF0000 for red)"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reaction_role(self, 
                          interaction: discord.Interaction, 
                          channel: discord.TextChannel,
                          title: str,
                          description: str,
                          color: str = "#2F3136"):
        """Create a reaction role message with buttons"""
        # Check if the bot has required permissions
        bot_permissions = channel.permissions_for(interaction.guild.me)
        if not bot_permissions.send_messages or not bot_permissions.embed_links:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I need permissions to send messages and embed links in the target channel."),
                ephemeral=True
            )
            return
        
        # Also check manage roles permission
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I don't have permission to manage roles."),
                ephemeral=True
            )
            return
        
        try:
            # Parse color
            if color.startswith('#'):
                color = color[1:]
            try:
                color_int = int(color, 16)
            except ValueError:
                await interaction.response.send_message(
                    embed=error_embed("Invalid Color", "Please provide a valid hex color (e.g., #FF0000 for red)."),
                    ephemeral=True
                )
                return
            
            # Start a role collection session
            await interaction.response.send_message(
                embed=info_embed(
                    title="Reaction Role Setup",
                    description="Please send the roles and emojis in the following format:\n"
                               "`@Role1 emoji1, @Role2 emoji2, @Role3 emoji3`\n\n"
                               "Example: `@Member 👍, @VIP 🌟, @Gamer 🎮`\n\n"
                               "You can use up to 5 roles. Type `cancel` to cancel setup."
                ),
                ephemeral=True
            )
            
            # Wait for the user's response
            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id
            
            try:
                response = await self.bot.wait_for('message', check=check, timeout=120.0)
                
                # Check for cancellation
                if response.content.lower() == 'cancel':
                    await interaction.followup.send(
                        embed=info_embed("Setup Cancelled", "Reaction role setup has been cancelled."),
                        ephemeral=True
                    )
                    # Try to delete the user's message
                    try:
                        await response.delete()
                    except:
                        pass
                    return
                
                # Parse the roles and emojis
                parts = response.content.split(',')
                roles_data = {}
                
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    
                    # Split the role mention and emoji
                    role_emoji = part.split(' ', 1)
                    if len(role_emoji) != 2:
                        await interaction.followup.send(
                            embed=error_embed("Invalid Format", f"Invalid format in `{part}`. Please use the format `@Role emoji`."),
                            ephemeral=True
                        )
                        return
                    
                    role_mention, emoji = role_emoji
                    
                    # Extract role ID from mention
                    role_id_match = discord.utils.get(response.role_mentions, mention=role_mention)
                    if not role_id_match:
                        # Try again with a different approach
                        role_id_str = role_mention.replace('<@&', '').replace('>', '')
                        try:
                            role_id = int(role_id_str)
                            role = interaction.guild.get_role(role_id)
                            if not role:
                                await interaction.followup.send(
                                    embed=error_embed("Invalid Role", f"Could not find role `{role_mention}`."),
                                    ephemeral=True
                                )
                                return
                        except ValueError:
                            await interaction.followup.send(
                                embed=error_embed("Invalid Role", f"Invalid role mention `{role_mention}`."),
                                ephemeral=True
                            )
                            return
                    else:
                        role = role_id_match
                    
                    # Check if role is manageable
                    if role.position >= interaction.guild.me.top_role.position:
                        await interaction.followup.send(
                            embed=error_embed("Role Too High", f"I can't assign the role {role.mention} because it's higher than or equal to my highest role."),
                            ephemeral=True
                        )
                        return
                    
                    # Add to roles data
                    roles_data[str(role.id)] = emoji.strip()
                
                # Check if we have at least one role
                if not roles_data:
                    await interaction.followup.send(
                        embed=error_embed("No Roles", "No valid roles were provided."),
                        ephemeral=True
                    )
                    return
                
                # Check if we have too many roles
                if len(roles_data) > 5:
                    await interaction.followup.send(
                        embed=error_embed("Too Many Roles", "You can only have up to 5 roles in a reaction role message."),
                        ephemeral=True
                    )
                    return
                
                # Try to delete the user's message
                try:
                    await response.delete()
                except:
                    pass
                
                # Create the reaction role embed
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=color_int
                )
                
                # Add roles to the embed
                roles_text = []
                for role_id, emoji in roles_data.items():
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        roles_text.append(f"{emoji} - {role.mention}")
                
                if roles_text:
                    embed.add_field(
                        name="Available Roles",
                        value="\n".join(roles_text),
                        inline=False
                    )
                
                # Create and add the view with buttons
                view = ReactionRoleView(roles_data)
                
                # Send the reaction role message
                reaction_message = await channel.send(embed=embed, view=view)
                
                # Send confirmation
                await interaction.followup.send(
                    embed=success_embed(
                        title="Reaction Role Created",
                        description=f"Reaction role message has been created in {channel.mention}."
                    ),
                    ephemeral=True
                )
                
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    embed=error_embed("Timeout", "Reaction role setup timed out."),
                    ephemeral=True
                )
                return
            
        except Exception as e:
            logger.error(f"Error creating reaction role: {e}")
            await interaction.followup.send(
                embed=error_embed("Error", f"An error occurred while creating the reaction role: {e}"),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Roles(bot))
