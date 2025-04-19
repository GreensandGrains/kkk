import discord
from datetime import datetime
import config

def create_embed(
    title: str = None,
    description: str = None,
    color: int = config.COLORS["PRIMARY"],
    footer: str = config.DEFAULT_FOOTER,
    timestamp: bool = True,
    thumbnail: str = None,
    image: str = None,
    author: dict = None,
    fields: list = None,
    url: str = None
) -> discord.Embed:
    """
    Create a Discord embed with common styling.
    
    Args:
        title: Embed title
        description: Embed description
        color: Embed color (integer)
        footer: Footer text
        timestamp: Whether to include a timestamp
        thumbnail: URL for thumbnail image
        image: URL for main image
        author: Dict with author info (name, icon_url, url)
        fields: List of dicts with field info (name, value, inline)
        url: URL for embed title
        
    Returns:
        discord.Embed object
    """
    # Create the embed
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        url=url
    )
    
    # Add timestamp if requested
    if timestamp:
        embed.timestamp = datetime.utcnow()
    
    # Add footer
    if footer:
        embed.set_footer(text=footer)
    
    # Add thumbnail
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    # Add image
    if image:
        embed.set_image(url=image)
    
    # Add author
    if author:
        embed.set_author(
            name=author.get("name", ""),
            icon_url=author.get("icon_url", None),
            url=author.get("url", None)
        )
    
    # Add fields
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
    
    return embed

def success_embed(title: str, description: str = None) -> discord.Embed:
    """Create a success embed with green color."""
    return create_embed(
        title=f"{config.EMOJIS['SUCCESS']} {title}",
        description=description,
        color=config.COLORS["SUCCESS"]
    )

def error_embed(title: str, description: str = None) -> discord.Embed:
    """Create an error embed with red color."""
    return create_embed(
        title=f"{config.EMOJIS['ERROR']} {title}",
        description=description,
        color=config.COLORS["ERROR"]
    )

def warning_embed(title: str, description: str = None) -> discord.Embed:
    """Create a warning embed with yellow color."""
    return create_embed(
        title=f"{config.EMOJIS['WARNING']} {title}",
        description=description,
        color=config.COLORS["WARNING"]
    )

def info_embed(title: str, description: str = None) -> discord.Embed:
    """Create an info embed with blurple color."""
    return create_embed(
        title=title,
        description=description,
        color=config.COLORS["INFO"]
    )

def giveaway_embed(prize: str, host: discord.Member, end_time: datetime, winners: int) -> discord.Embed:
    """
    Create a giveaway embed.
    
    Args:
        prize: Prize name
        host: Member hosting the giveaway
        end_time: End time of the giveaway
        winners: Number of winners
        
    Returns:
        discord.Embed for the giveaway
    """
    timestamp = int(end_time.timestamp())
    time_left = f"<t:{timestamp}:R>"
    
    return create_embed(
        title=f"🎉 GIVEAWAY: {prize}",
        description=f"React with 🎉 to enter!\n\n"
                    f"**Time Remaining:** {time_left}\n"
                    f"**Hosted by:** {host.mention}\n"
                    f"**Winners:** {winners}",
        color=config.COLORS["GIVEAWAY"],
        footer="Ends at",
        timestamp=False
    )

def ticket_embed(category: str) -> discord.Embed:
    """
    Create a ticket system embed.
    
    Args:
        category: Ticket category
        
    Returns:
        discord.Embed for ticket panel
    """
    return create_embed(
        title="🎫 Support Ticket System",
        description="Click the button below to create a support ticket.\n\n"
                   f"**Category:** {category}\n\n"
                   "A staff member will assist you as soon as possible.",
        color=config.COLORS["PRIMARY"]
    )

def application_embed(title: str, description: str, questions: list) -> discord.Embed:
    """
    Create an application system embed.
    
    Args:
        title: Application title
        description: Application description
        questions: List of questions
        
    Returns:
        discord.Embed for application panel
    """
    question_list = "\n".join([f"**{i+1}.** {q}" for i, q in enumerate(questions)])
    
    return create_embed(
        title=f"📝 {title}",
        description=f"{description}\n\n**Questions:**\n{question_list}\n\n"
                  "Click the button below to apply!",
        color=config.COLORS["PRIMARY"]
    )

def help_embed(cog_name: str, commands: list) -> discord.Embed:
    """
    Create a help embed for a specific category.
    
    Args:
        cog_name: Name of the command category
        commands: List of command descriptions
        
    Returns:
        discord.Embed for help menu
    """
    command_list = "\n".join(commands)
    
    return create_embed(
        title=f"Help: {cog_name} Commands",
        description=command_list,
        color=config.COLORS["INFO"]
    )
