import discord
from discord import app_commands
from discord.ext import commands
import json
import re
from typing import Optional, Dict
import asyncio

from utils import has_mod_permissions, has_admin_permissions, random_color
from data_manager import DataManager

class EmbedModal(discord.ui.Modal, title="Create Embed"):
    """Modal for creating an embed"""
    
    title = discord.ui.TextInput(
        label="Embed Title",
        placeholder="Enter a title...",
        required=False,
        max_length=256
    )
    
    description = discord.ui.TextInput(
        label="Embed Description",
        placeholder="Enter a description...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000
    )
    
    color = discord.ui.TextInput(
        label="Embed Color (hex)",
        placeholder="e.g. #FF0000 for red (leave empty for random)",
        required=False,
        max_length=7
    )
    
    footer = discord.ui.TextInput(
        label="Footer Text",
        placeholder="Enter footer text...",
        required=False,
        max_length=2048
    )
    
    image_url = discord.ui.TextInput(
        label="Image URL",
        placeholder="Enter an image URL...",
        required=False
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        # Create the embed
        embed = discord.Embed()
        
        if self.title.value:
            embed.title = self.title.value
        
        if self.description.value:
            embed.description = self.description.value
        
        # Parse color
        if self.color.value:
            try:
                if self.color.value.startswith('#'):
                    color_hex = self.color.value[1:]
                else:
                    color_hex = self.color.value
                    
                color_int = int(color_hex, 16)
                embed.color = discord.Color(color_int)
            except ValueError:
                # Invalid color, use random one
                embed.color = random_color()
        else:
            # No color provided, use random one
            embed.color = random_color()
        
        if self.footer.value:
            embed.set_footer(text=self.footer.value)
        
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)
        
        # Set timestamp
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.response.send_message("Embed created!", ephemeral=True)
        await interaction.channel.send(embed=embed)

class EmbedFieldModal(discord.ui.Modal, title="Add Field to Embed"):
    """Modal for adding a field to an embed"""
    
    field_name = discord.ui.TextInput(
        label="Field Name",
        placeholder="Enter field name...",
        required=True,
        max_length=256
    )
    
    field_value = discord.ui.TextInput(
        label="Field Value",
        placeholder="Enter field value...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1024
    )
    
    inline = discord.ui.TextInput(
        label="Inline (true/false)",
        placeholder="true or false",
        required=False,
        max_length=5,
        default="true"
    )
    
    def __init__(self, message_id: int):
        super().__init__()
        self.message_id = message_id
    
    async def on_submit(self, interaction: discord.Interaction):
        # Determine if field should be inline
        inline_value = self.inline.value.lower()
        is_inline = inline_value != "false"
        
        try:
            # Get the message with the embed
            message = await interaction.channel.fetch_message(self.message_id)
            
            if not message.embeds:
                await interaction.response.send_message("No embed found in that message.", ephemeral=True)
                return
            
            # Get the embed and add the field
            embed = message.embeds[0].copy()
            embed.add_field(
                name=self.field_name.value,
                value=self.field_value.value,
                inline=is_inline
            )
            
            # Update the message
            await message.edit(embed=embed)
            await interaction.response.send_message("Field added to embed!", ephemeral=True)
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to edit that message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error editing message: {e}", ephemeral=True)

class EmbedEditModal(discord.ui.Modal, title="Edit Embed"):
    """Modal for editing an embed"""
    
    title = discord.ui.TextInput(
        label="Embed Title",
        placeholder="Enter a title... (leave empty to keep current)",
        required=False,
        max_length=256
    )
    
    description = discord.ui.TextInput(
        label="Embed Description",
        placeholder="Enter a description...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000
    )
    
    color = discord.ui.TextInput(
        label="Embed Color (hex)",
        placeholder="e.g. #FF0000 for red (leave empty to keep current)",
        required=False,
        max_length=7
    )
    
    footer = discord.ui.TextInput(
        label="Footer Text",
        placeholder="Enter footer text...",
        required=False,
        max_length=2048
    )
    
    image_url = discord.ui.TextInput(
        label="Image URL",
        placeholder="Enter an image URL...",
        required=False
    )
    
    def __init__(self, message_id: int, current_embed: discord.Embed):
        super().__init__()
        self.message_id = message_id
        
        # Pre-fill the form with current values
        if current_embed.title:
            self.title.default = current_embed.title
        
        if current_embed.description:
            self.description.default = current_embed.description
        
        if current_embed.color:
            self.color.default = f"#{current_embed.color.value:06x}"
        
        if current_embed.footer and current_embed.footer.text:
            self.footer.default = current_embed.footer.text
        
        if current_embed.image and current_embed.image.url:
            self.image_url.default = current_embed.image.url
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Get the message with the embed
            message = await interaction.channel.fetch_message(self.message_id)
            
            if not message.embeds:
                await interaction.response.send_message("No embed found in that message.", ephemeral=True)
                return
            
            # Get the embed and update it
            embed = message.embeds[0].copy()
            
            # Update title - explicitly set to empty string if user wants to remove it
            if self.title.value != "":
                embed.title = self.title.value
            
            # Update description - explicitly set to empty string if user wants to remove it
            if self.description.value != "":
                embed.description = self.description.value
            
            # Parse color if provided
            if self.color.value:
                try:
                    if self.color.value.startswith('#'):
                        color_hex = self.color.value[1:]
                    else:
                        color_hex = self.color.value
                        
                    color_int = int(color_hex, 16)
                    embed.color = discord.Color(color_int)
                except ValueError:
                    # Invalid color, ignore
                    pass
            
            if self.footer.value:
                embed.set_footer(text=self.footer.value)
            
            if self.image_url.value:
                embed.set_image(url=self.image_url.value)
            
            # Update the message
            await message.edit(embed=embed)
            await interaction.response.send_message("Embed updated!", ephemeral=True)
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to edit that message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error editing message: {e}", ephemeral=True)

class EmbedTools(commands.Cog):
    """Tools for creating and managing embeds"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
    
    @app_commands.command(name="embed", description="Create a custom embed")
    @has_mod_permissions()
    async def embed_command(self, interaction: discord.Interaction):
        # Show embed creation modal
        await interaction.response.send_modal(EmbedModal())
    
    @app_commands.command(name="embedjson", description="Create an embed from JSON")
    @app_commands.describe(
        json_data="JSON data for the embed"
    )
    @has_mod_permissions()
    async def embed_json_command(self, interaction: discord.Interaction, json_data: str):
        try:
            # Parse the JSON data
            embed_dict = json.loads(json_data)
            
            # Create the embed
            embed = discord.Embed.from_dict(embed_dict)
            
            await interaction.response.send_message("Embed created from JSON!", ephemeral=True)
            await interaction.channel.send(embed=embed)
            
        except json.JSONDecodeError:
            await interaction.response.send_message("Invalid JSON data.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error creating embed: {e}", ephemeral=True)
    
    @app_commands.command(name="editembed", description="Edit an existing embed")
    @app_commands.describe(
        message_id="ID of the message containing the embed"
    )
    @has_mod_permissions()
    async def edit_embed_command(self, interaction: discord.Interaction, message_id: str):
        # Validate message ID
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        
        try:
            # Get the message with the embed
            message = await interaction.channel.fetch_message(message_id)
            
            if not message.embeds:
                await interaction.response.send_message("No embed found in that message.", ephemeral=True)
                return
            
            # Create the edit modal with the current embed
            await interaction.response.send_modal(EmbedEditModal(message_id, message.embeds[0]))
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to view that message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error getting message: {e}", ephemeral=True)
    
    @app_commands.command(name="embedfield", description="Add a field to an existing embed")
    @app_commands.describe(
        message_id="ID of the message containing the embed"
    )
    @has_mod_permissions()
    async def embed_field_command(self, interaction: discord.Interaction, message_id: str):
        # Validate message ID
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        
        try:
            # Get the message with the embed
            message = await interaction.channel.fetch_message(message_id)
            
            if not message.embeds:
                await interaction.response.send_message("No embed found in that message.", ephemeral=True)
                return
            
            # Create the field modal
            await interaction.response.send_modal(EmbedFieldModal(message_id))
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to view that message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error getting message: {e}", ephemeral=True)
    
    @app_commands.command(name="embeddump", description="Get the JSON for an existing embed")
    @app_commands.describe(
        message_id="ID of the message containing the embed"
    )
    @has_mod_permissions()
    async def embed_dump_command(self, interaction: discord.Interaction, message_id: str):
        # Validate message ID
        try:
            message_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        
        try:
            # Get the message with the embed
            message = await interaction.channel.fetch_message(message_id)
            
            if not message.embeds:
                await interaction.response.send_message("No embed found in that message.", ephemeral=True)
                return
            
            # Get the embed as a dict
            embed_dict = message.embeds[0].to_dict()
            
            # Convert to formatted JSON
            json_data = json.dumps(embed_dict, indent=2)
            
            if len(json_data) > 2000:
                # JSON is too long for a message, send as a file
                await interaction.response.send_message(
                    "Embed JSON is too large for a message. Here's a file with the JSON:",
                    file=discord.File(
                        fp=discord.utils.to_bytes(json_data),
                        filename="embed.json"
                    ),
                    ephemeral=True
                )
            else:
                # Send the JSON in a code block
                await interaction.response.send_message(
                    f"```json\n{json_data}\n```",
                    ephemeral=True
                )
            
        except discord.NotFound:
            await interaction.response.send_message("Message not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to view that message.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Error getting message: {e}", ephemeral=True)
    
    @app_commands.command(name="embedsay", description="Send a message with an embed")
    @app_commands.describe(
        message="Message content to send with the embed"
    )
    @has_mod_permissions()
    async def embed_say_command(self, interaction: discord.Interaction, message: str):
        # Show a modal for embed creation that includes the message
        modal = EmbedModal()
        
        # Store the message to send
        modal._message = message
        
        # Override on_submit method to include the message
        original_on_submit = modal.on_submit
        
        async def new_on_submit(interaction):
            embed = discord.Embed()
            
            if modal.title.value:
                embed.title = modal.title.value
            
            if modal.description.value:
                embed.description = modal.description.value
            
            # Parse color
            if modal.color.value:
                try:
                    if modal.color.value.startswith('#'):
                        color_hex = modal.color.value[1:]
                    else:
                        color_hex = modal.color.value
                        
                    color_int = int(color_hex, 16)
                    embed.color = discord.Color(color_int)
                except ValueError:
                    # Invalid color, use random one
                    embed.color = random_color()
            else:
                # No color provided, use random one
                embed.color = random_color()
            
            if modal.footer.value:
                embed.set_footer(text=modal.footer.value)
            
            if modal.image_url.value:
                embed.set_image(url=modal.image_url.value)
            
            # Set timestamp
            embed.timestamp = discord.utils.utcnow()
            
            await interaction.response.send_message("Message with embed created!", ephemeral=True)
            await interaction.channel.send(content=message, embed=embed)
        
        modal.on_submit = new_on_submit
        
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(EmbedTools(bot))
