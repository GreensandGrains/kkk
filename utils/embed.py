"""
Utility functions for creating and managing embeds.
"""
import discord
from typing import Optional, List, Dict, Any

class EmbedManager:
    """A class to handle creation and modification of embeds."""
    
    @staticmethod
    def create_embed(
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[discord.Color] = discord.Color.blue(),
        fields: Optional[List[Dict[str, Any]]] = None,
        footer: Optional[str] = None,
        thumbnail: Optional[str] = None,
        image: Optional[str] = None,
        author: Optional[Dict[str, Any]] = None,
        timestamp: bool = False
    ) -> discord.Embed:
        """
        Create a Discord embed with the given parameters.
        
        Args:
            title: The title of the embed
            description: The description of the embed
            color: The color of the embed
            fields: List of dicts with name, value, and inline keys
            footer: Footer text
            thumbnail: URL for the thumbnail
            image: URL for the main image
            author: Dict with name, url, and icon_url keys
            timestamp: Whether to add current timestamp
            
        Returns:
            discord.Embed: The created embed
        """
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        # Add fields if provided
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', 'Field'),
                    value=field.get('value', 'Value'),
                    inline=field.get('inline', True)
                )
        
        # Add footer if provided
        if footer:
            embed.set_footer(text=footer)
        
        # Add thumbnail if provided
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        # Add image if provided
        if image:
            embed.set_image(url=image)
        
        # Add author if provided
        if author:
            embed.set_author(
                name=author.get('name', ''),
                url=author.get('url', discord.Embed.Empty),
                icon_url=author.get('icon_url', discord.Embed.Empty)
            )
        
        # Add timestamp if requested
        if timestamp:
            embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    @staticmethod
    def success_embed(message: str, title: Optional[str] = "Success") -> discord.Embed:
        """Create a success embed."""
        return EmbedManager.create_embed(
            title=title,
            description=message,
            color=discord.Color.green(),
            timestamp=True
        )
    
    @staticmethod
    def error_embed(message: str, title: Optional[str] = "Error") -> discord.Embed:
        """Create an error embed."""
        return EmbedManager.create_embed(
            title=title,
            description=message,
            color=discord.Color.red(),
            timestamp=True
        )
    
    @staticmethod
    def warning_embed(message: str, title: Optional[str] = "Warning") -> discord.Embed:
        """Create a warning embed."""
        return EmbedManager.create_embed(
            title=title,
            description=message,
            color=discord.Color.yellow(),
            timestamp=True
        )
    
    @staticmethod
    def info_embed(message: str, title: Optional[str] = "Information") -> discord.Embed:
        """Create an informational embed."""
        return EmbedManager.create_embed(
            title=title,
            description=message,
            color=discord.Color.blue(),
            timestamp=True
        )
    
    @staticmethod
    def create_command_help(
        command_name: str,
        description: str,
        usage: str,
        examples: List[str],
        required_permissions: Optional[List[str]] = None
    ) -> discord.Embed:
        """Create a help embed for a specific command."""
        embed = EmbedManager.create_embed(
            title=f"Command Help: /{command_name}",
            description=description,
            color=discord.Color.blue(),
            timestamp=True
        )
        
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
        
        if examples:
            embed.add_field(
                name="Examples",
                value="\n".join([f"`{example}`" for example in examples]),
                inline=False
            )
        
        if required_permissions:
            embed.add_field(
                name="Required Permissions",
                value=", ".join(required_permissions),
                inline=False
            )
        
        return embed
