import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Union, List
import asyncio

from utils import has_mod_permissions, has_admin_permissions, create_confirmation_view
from data_manager import DataManager

class RoleManagement(commands.Cog):
    """Role management commands for adding, removing, and setting roles"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.reaction_role_messages = {}
    
    async def cog_load(self):
        """Setup reaction roles when the cog is loaded"""
        self.bot.add_listener(self.on_raw_reaction_add, "on_raw_reaction_add")
        self.bot.add_listener(self.on_raw_reaction_remove, "on_raw_reaction_remove")
    
    @app_commands.command(name="addrole", description="Add a role to a user")
    @app_commands.describe(
        member="The member to add the role to",
        role="The role to add",
        reason="Reason for adding the role"
    )
    @has_mod_permissions()
    async def add_role_command(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member, 
        role: discord.Role,
        reason: Optional[str] = "No reason provided"
    ):
        # Check if the bot has the Manage Roles permission
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("I don't have permission to manage roles.", ephemeral=True)
            return
        
        # Check if the role is higher than the bot's highest role
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I can't assign that role because it's higher than or equal to my highest role.",
                ephemeral=True
            )
            return
        
        # Check if the moderator's highest role is higher than the role being added
        if role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "You can't assign a role that is higher than or equal to your highest role.",
                ephemeral=True
            )
            return
        
        # Check if the user already has the role
        if role in member.roles:
            await interaction.response.send_message(f"{member.mention} already has the {role.mention} role.", ephemeral=True)
            return
        
        try:
            await member.add_roles(role, reason=f"Added by {interaction.user.display_name}: {reason}")
            
            # Create embed for success message
            embed = discord.Embed(
                title="Role Added",
                description=f"Added {role.mention} to {member.mention}",
                color=role.color,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            if reason != "No reason provided":
                embed.add_field(name="Reason", value=reason, inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to add that role.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
    
    @app_commands.command(name="removerole", description="Remove a role from a user")
    @app_commands.describe(
        member="The member to remove the role from",
        role="The role to remove",
        reason="Reason for removing the role"
    )
    @has_mod_permissions()
    async def remove_role_command(
        self, 
        interaction: discord.Interaction, 
        member: discord.Member, 
        role: discord.Role,
        reason: Optional[str] = "No reason provided"
    ):
        # Check if the bot has the Manage Roles permission
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("I don't have permission to manage roles.", ephemeral=True)
            return
        
        # Check if the role is higher than the bot's highest role
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "I can't remove that role because it's higher than or equal to my highest role.",
                ephemeral=True
            )
            return
        
        # Check if the moderator's highest role is higher than the role being removed
        if role >= interaction.user.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "You can't remove a role that is higher than or equal to your highest role.",
                ephemeral=True
            )
            return
        
        # Check if the user has the role
        if role not in member.roles:
            await interaction.response.send_message(f"{member.mention} doesn't have the {role.mention} role.", ephemeral=True)
            return
        
        try:
            await member.remove_roles(role, reason=f"Removed by {interaction.user.display_name}: {reason}")
            
            # Create embed for success message
            embed = discord.Embed(
                title="Role Removed",
                description=f"Removed {role.mention} from {member.mention}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            
            if reason != "No reason provided":
                embed.add_field(name="Reason", value=reason, inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to remove that role.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
    
    @app_commands.command(name="setadminrole", description="Set a role as an admin role")
    @app_commands.describe(
        role="The role to set as an admin role"
    )
    @has_admin_permissions()
    async def set_admin_role_command(self, interaction: discord.Interaction, role: discord.Role):
        # Only server administrators or the owner can use this command
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message("Only server administrators can use this command.", ephemeral=True)
            return
        
        # Get current admin roles
        admin_roles = self.data_manager.get_admin_roles(interaction.guild.id)
        
        # Check if role is already set as admin
        if admin_roles and role.id in admin_roles:
            await interaction.response.send_message(f"{role.mention} is already set as an admin role.", ephemeral=True)
            return
        
        # Set the role as admin
        success = self.data_manager.set_admin_role(interaction.guild.id, role.id)
        
        if success:
            await interaction.response.send_message(f"{role.mention} has been set as an admin role.")
        else:
            await interaction.response.send_message("Failed to set admin role. Please try again.", ephemeral=True)
    
    @app_commands.command(name="setmodrole", description="Set a role as a moderator role")
    @app_commands.describe(
        role="The role to set as a moderator role"
    )
    @has_admin_permissions()
    async def set_mod_role_command(self, interaction: discord.Interaction, role: discord.Role):
        # Only administrators can use this command
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message("Only server administrators can use this command.", ephemeral=True)
            return
        
        # Get current mod roles
        mod_roles = self.data_manager.get_mod_roles(interaction.guild.id)
        
        # Check if role is already set as mod
        if mod_roles and role.id in mod_roles:
            await interaction.response.send_message(f"{role.mention} is already set as a moderator role.", ephemeral=True)
            return
        
        # Set the role as mod
        success = self.data_manager.set_mod_role(interaction.guild.id, role.id)
        
        if success:
            await interaction.response.send_message(f"{role.mention} has been set as a moderator role.")
        else:
            await interaction.response.send_message("Failed to set moderator role. Please try again.", ephemeral=True)
    
    @app_commands.command(name="removeadminrole", description="Remove a role from being an admin role")
    @app_commands.describe(
        role="The role to remove from admin roles"
    )
    @has_admin_permissions()
    async def remove_admin_role_command(self, interaction: discord.Interaction, role: discord.Role):
        # Only server administrators or the owner can use this command
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message("Only server administrators can use this command.", ephemeral=True)
            return
        
        # Get current admin roles
        admin_roles = self.data_manager.get_admin_roles(interaction.guild.id)
        
        # Check if role is set as admin
        if not admin_roles or role.id not in admin_roles:
            await interaction.response.send_message(f"{role.mention} is not set as an admin role.", ephemeral=True)
            return
        
        # Remove the role as admin
        success = self.data_manager.remove_admin_role(interaction.guild.id, role.id)
        
        if success:
            await interaction.response.send_message(f"{role.mention} has been removed from admin roles.")
        else:
            await interaction.response.send_message("Failed to remove admin role. Please try again.", ephemeral=True)
    
    @app_commands.command(name="removemodrole", description="Remove a role from being a moderator role")
    @app_commands.describe(
        role="The role to remove from moderator roles"
    )
    @has_admin_permissions()
    async def remove_mod_role_command(self, interaction: discord.Interaction, role: discord.Role):
        # Only administrators can use this command
        if not (interaction.user.guild_permissions.administrator or interaction.user.id == interaction.guild.owner_id):
            await interaction.response.send_message("Only server administrators can use this command.", ephemeral=True)
            return
        
        # Get current mod roles
        mod_roles = self.data_manager.get_mod_roles(interaction.guild.id)
        
        # Check if role is set as mod
        if not mod_roles or role.id not in mod_roles:
            await interaction.response.send_message(f"{role.mention} is not set as a moderator role.", ephemeral=True)
            return
        
        # Remove the role as mod
        success = self.data_manager.remove_mod_role(interaction.guild.id, role.id)
        
        if success:
            await interaction.response.send_message(f"{role.mention} has been removed from moderator roles.")
        else:
            await interaction.response.send_message("Failed to remove moderator role. Please try again.", ephemeral=True)
    
    @app_commands.command(name="reactionrole", description="Create a reaction role message")
    @app_commands.describe(
        title="Title for the reaction role embed",
        description="Description for the reaction role embed"
    )
    @has_mod_permissions()
    async def reaction_role_command(
        self, 
        interaction: discord.Interaction, 
        title: str,
        description: str
    ):
        # Check if the bot has the required permissions
        if not (interaction.guild.me.guild_permissions.manage_roles and 
                interaction.guild.me.guild_permissions.add_reactions):
            await interaction.response.send_message(
                "I need the 'Manage Roles' and 'Add Reactions' permissions to create reaction roles.",
                ephemeral=True
            )
            return
        
        # Create initial embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.response.send_message(
            "Reaction role message created! Use the `/editreactionrole` command to add roles.",
            ephemeral=True
        )
        
        # Send the message
        message = await interaction.channel.send(embed=embed)
        
        # Store the message ID in reaction_role_messages
        if interaction.guild.id not in self.reaction_role_messages:
            self.reaction_role_messages[interaction.guild.id] = {}
        
        self.reaction_role_messages[interaction.guild.id][message.id] = {
            "roles": {}
        }
    
    @app_commands.command(name="editreactionrole", description="Edit a reaction role message")
    @app_commands.describe(
        message_id="ID of the reaction role message to edit",
        role="Role to add",
        emoji="Emoji to use for the role",
        title="New title for the embed (optional)",
        description="New description for the embed (optional)",
        color="New color for the embed (hex format, e.g., #FF0000) (optional)"
    )
    @has_mod_permissions()
    async def edit_reaction_role_command(
        self, 
        interaction: discord.Interaction, 
        message_id: str,
        role: discord.Role,
        emoji: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None
    ):
        await interaction.response.defer(ephemeral=True)
        
        # Check if the role is higher than the bot's highest role
        if role >= interaction.guild.me.top_role:
            await interaction.followup.send(
                "I can't assign that role because it's higher than or equal to my highest role.",
                ephemeral=True
            )
            return
        
        # Validate message ID
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.followup.send("Invalid message ID. Please provide a valid message ID.", ephemeral=True)
            return
        
        # Try to get the message
        try:
            channel = interaction.channel
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.followup.send("Message not found in this channel.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to see that message.", ephemeral=True)
            return
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            return
        
        # Check if the message is from the bot
        if message.author.id != self.bot.user.id:
            await interaction.followup.send("I can only edit reaction role messages that I sent.", ephemeral=True)
            return
        
        # Ensure we're using a valid emoji
        try:
            # Try to add the reaction to make sure it's valid
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await interaction.followup.send(
                "Invalid emoji. Please use a standard emoji or a custom emoji from this server.",
                ephemeral=True
            )
            return
        
        # Get or create the reaction role data for this message
        if interaction.guild.id not in self.reaction_role_messages:
            self.reaction_role_messages[interaction.guild.id] = {}
        
        if message_id not in self.reaction_role_messages[interaction.guild.id]:
            self.reaction_role_messages[interaction.guild.id][message_id] = {
                "roles": {}
            }
        
        # Add the role to the message
        self.reaction_role_messages[interaction.guild.id][message_id]["roles"][emoji] = role.id
        
        # Get the current embed
        if message.embeds:
            embed = message.embeds[0]
        else:
            embed = discord.Embed(
                title="Reaction Roles",
                description="React to get roles",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
        
        # Update the embed if needed
        if title:
            embed.title = title
        
        if description:
            embed.description = description
        
        if color:
            # Parse hex color
            try:
                if color.startswith('#'):
                    color = color[1:]
                
                color_int = int(color, 16)
                embed.color = discord.Color(color_int)
            except ValueError:
                await interaction.followup.send(
                    "Invalid color format. Please use hex format (e.g., #FF0000).",
                    ephemeral=True
                )
                return
        
        # Update the roles field
        roles_text = ""
        for e, role_id in self.reaction_role_messages[interaction.guild.id][message_id]["roles"].items():
            r = interaction.guild.get_role(role_id)
            if r:
                roles_text += f"{e} - {r.mention}\n"
        
        # Clear existing fields and add updated roles field
        embed.clear_fields()
        
        if roles_text:
            embed.add_field(name="Roles", value=roles_text, inline=False)
        
        # Update the message
        try:
            await message.edit(embed=embed)
            await interaction.followup.send(
                f"Reaction role message updated! Added {role.mention} with emoji {emoji}",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(f"Failed to update the message: {e}", ephemeral=True)
    
    @app_commands.command(name="listroles", description="List all roles in the server")
    async def list_roles_command(self, interaction: discord.Interaction):
        guild = interaction.guild
        roles = sorted(guild.roles, key=lambda r: r.position, reverse=True)
        
        # Remove @everyone role
        roles = [r for r in roles if r.id != guild.id]
        
        if not roles:
            await interaction.response.send_message("This server has no roles other than @everyone.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Roles in {guild.name}",
            description=f"Total: {len(roles)} roles",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Split roles into chunks for fields
        chunks = [roles[i:i + 15] for i in range(0, len(roles), 15)]
        
        for i, chunk in enumerate(chunks):
            roles_text = "\n".join([f"{r.mention} (ID: {r.id})" for r in chunk])
            embed.add_field(name=f"Roles {i+1}", value=roles_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def on_raw_reaction_add(self, payload):
        """Handler for reaction role addition"""
        # Ignore bot reactions
        if payload.user_id == self.bot.user.id:
            return
        
        guild_id = payload.guild_id
        if not guild_id:
            return
        
        # Check if this is a reaction role message
        if (guild_id in self.reaction_role_messages and 
            payload.message_id in self.reaction_role_messages[guild_id]):
            
            emoji = str(payload.emoji)
            role_data = self.reaction_role_messages[guild_id][payload.message_id]
            
            # Check if this emoji is associated with a role
            if emoji in role_data["roles"]:
                role_id = role_data["roles"][emoji]
                
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    return
                
                member = guild.get_member(payload.user_id)
                if not member:
                    return
                
                role = guild.get_role(role_id)
                if not role:
                    return
                
                try:
                    await member.add_roles(role, reason="Reaction role")
                except (discord.Forbidden, discord.HTTPException):
                    # Failed to add role, ignore
                    pass
    
    async def on_raw_reaction_remove(self, payload):
        """Handler for reaction role removal"""
        guild_id = payload.guild_id
        if not guild_id:
            return
        
        # Check if this is a reaction role message
        if (guild_id in self.reaction_role_messages and 
            payload.message_id in self.reaction_role_messages[guild_id]):
            
            emoji = str(payload.emoji)
            role_data = self.reaction_role_messages[guild_id][payload.message_id]
            
            # Check if this emoji is associated with a role
            if emoji in role_data["roles"]:
                role_id = role_data["roles"][emoji]
                
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    return
                
                member = guild.get_member(payload.user_id)
                if not member:
                    return
                
                role = guild.get_role(role_id)
                if not role:
                    return
                
                try:
                    await member.remove_roles(role, reason="Reaction role removed")
                except (discord.Forbidden, discord.HTTPException):
                    # Failed to remove role, ignore
                    pass

async def setup(bot):
    await bot.add_cog(RoleManagement(bot))
