import discord
from discord import app_commands
import re
import asyncio
from datetime import datetime, timedelta
import random

def format_timestamp(dt, style='f'):
    """Format a datetime object into a Discord timestamp string
    Styles:
    - f: Full Date Time (e.g., "January 1, 2023 12:00 AM")
    - R: Relative Time (e.g., "2 hours ago", "in 3 days")
    - t: Short Time (e.g., "12:00 AM")
    - d: Short Date (e.g., "01/01/2023")
    """
    timestamp = int(dt.timestamp())
    return f"<t:{timestamp}:{style}>"

def parse_time(time_str):
    """Parse a time string like 1d2h3m4s and return timedelta
    Returns None if the format is invalid
    """
    if not time_str:
        return None
        
    pattern = r'(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?'
    match = re.fullmatch(pattern, time_str)
    
    if not match or not any(match.groups()):
        return None
        
    days = int(match.group(1) or 0)
    hours = int(match.group(2) or 0)
    minutes = int(match.group(3) or 0)
    seconds = int(match.group(4) or 0)
    
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

async def create_confirmation_view(interaction, message):
    """Create a confirmation view with yes/no buttons
    Returns True if confirmed, False otherwise
    """
    view = discord.ui.View(timeout=60)
    result = [None]
    
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def yes_button(button_interaction: discord.Interaction, button: discord.ui.Button):
        result[0] = True
        for item in view.children:
            item.disabled = True
        await button_interaction.response.edit_message(view=view)
        view.stop()
    
    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def no_button(button_interaction: discord.Interaction, button: discord.ui.Button):
        result[0] = False
        for item in view.children:
            item.disabled = True
        await button_interaction.response.edit_message(view=view)
        view.stop()
    
    view.add_item(yes_button)
    view.add_item(no_button)
    
    await interaction.response.send_message(message, view=view, ephemeral=True)
    
    # Wait for the view to stop
    await view.wait()
    return result[0]

def has_mod_permissions():
    """Check if the user has moderation permissions"""
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
            
        from data_manager import DataManager
        dm = DataManager()
        
        # Check if user has admin or mod role
        admin_roles = dm.get_admin_roles(interaction.guild.id) or []
        mod_roles = dm.get_mod_roles(interaction.guild.id) or []
        
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in user_roles for role_id in admin_roles + mod_roles)
    
    return app_commands.check(predicate)

def has_admin_permissions():
    """Check if the user has administrator permissions"""
    async def predicate(interaction: discord.Interaction):
        if interaction.user.guild_permissions.administrator:
            return True
            
        from data_manager import DataManager
        dm = DataManager()
        
        # Check if user has admin role
        admin_roles = dm.get_admin_roles(interaction.guild.id) or []
        
        user_roles = [role.id for role in interaction.user.roles]
        return any(role_id in user_roles for role_id in admin_roles)
    
    return app_commands.check(predicate)

def generate_embed(title=None, description=None, color=0x5865F2, fields=None, author=None, footer=None, timestamp=None, thumbnail=None, image=None):
    """Create a discord Embed with the given parameters"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=timestamp or discord.utils.utcnow()
    )
    
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    
    if author:
        embed.set_author(name=author.get('name'), icon_url=author.get('icon_url'))
    
    if footer:
        embed.set_footer(text=footer.get('text'), icon_url=footer.get('icon_url'))
    
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    if image:
        embed.set_image(url=image)
    
    return embed

def truncate_text(text, max_length=1024):
    """Truncate text to fit in Discord embed fields"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

def error_embed(title, description):
    """Create an error embed"""
    return generate_embed(
        title=title,
        description=description,
        color=discord.Color.red()
    )

def success_embed(title, description):
    """Create a success embed"""
    return generate_embed(
        title=title,
        description=description,
        color=discord.Color.green()
    )

async def paginate_embeds(interaction, embeds, timeout=180):
    """Display paginated embeds with next/previous buttons"""
    if not embeds:
        return
    
    current_page = 0
    
    # Create the view with pagination buttons
    view = discord.ui.View(timeout=timeout)
    
    # Add page counter to all embeds
    for i, embed in enumerate(embeds):
        embed.set_footer(text=f"Page {i+1}/{len(embeds)}")
    
    async def update_message():
        await interaction.edit_original_response(embed=embeds[current_page], view=view)
    
    @discord.ui.button(label="Previous", style=discord.ButtonStyle.gray, disabled=True)
    async def previous_button(button_interaction: discord.Interaction, button: discord.ui.Button):
        nonlocal current_page
        
        # Check if the user who clicked is the same as the one who initiated
        if button_interaction.user != interaction.user:
            await button_interaction.response.send_message("You cannot use these controls.", ephemeral=True)
            return
            
        current_page -= 1
        
        # Update button states
        next_button.disabled = current_page >= len(embeds) - 1
        button.disabled = current_page <= 0
        
        await button_interaction.response.defer()
        await update_message()
    
    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray)
    async def next_button(button_interaction: discord.Interaction, button: discord.ui.Button):
        nonlocal current_page
        
        # Check if the user who clicked is the same as the one who initiated
        if button_interaction.user != interaction.user:
            await button_interaction.response.send_message("You cannot use these controls.", ephemeral=True)
            return
            
        current_page += 1
        
        # Update button states
        button.disabled = current_page >= len(embeds) - 1
        previous_button.disabled = current_page <= 0
        
        await button_interaction.response.defer()
        await update_message()
    
    # Add buttons to view
    view.add_item(previous_button)
    view.add_item(next_button)
    
    # Send initial message
    await interaction.response.send_message(embed=embeds[0], view=view)
    
    # Wait for the view to time out
    await view.wait()
    
    # Disable all buttons once timed out
    for button in view.children:
        button.disabled = True
    
    await interaction.edit_original_response(view=view)

def create_progressbar(value, max_value, size=10):
    """Create a text-based progress bar
    
    Args:
        value: Current value
        max_value: Maximum value
        size: Number of characters in the progress bar
        
    Returns:
        String representing the progress bar
    """
    percentage = value / max_value
    filled = int(size * percentage)
    empty = size - filled
    return '█' * filled + '░' * empty

def random_color():
    """Generate a random Discord color"""
    return discord.Color.from_rgb(
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    )
