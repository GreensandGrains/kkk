"""
Main bot functionality and setup.
"""
import os
import json
import logging
import discord
from discord.ext import commands
from discord import app_commands

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup intents (permissions)
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True
intents.guilds = True

# Create bot instance with slash commands
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

# Create data directories if they don't exist
os.makedirs('data', exist_ok=True)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord."""
    logging.info(f'Logged in as {bot.user.name} ({bot.user.id})')

    # Load all cogs
    cog_list = [
        'cogs.moderation',
        'cogs.utility',
        'cogs.giveaway',
        'cogs.application',
        'cogs.ticket',
        'cogs.tournament',
        'cogs.bump'
    ]

    for cog in cog_list:
        try:
            await bot.load_extension(cog)
            logging.info(f'Loaded extension: {cog}')
        except Exception as e:
            logging.error(f'Failed to load extension {cog}: {e}')

    # Set bot activity
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening,
        name="/help"
    ))

@bot.tree.command(name="invite", description="Get bot invite link and support server link")
async def invite(interaction: discord.Interaction):
    """Provides invite links for the bot and support server."""
    embed = discord.Embed(
        title="🔗 Invite Links",
        description="Add the bot to your server or join our support server!",
        color=discord.Color.blue()
    )

    bot_invite = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
    support_invite = "https://discord.gg/supportserver"  # Replace with actual support server invite

    embed.add_field(name="Bot Invite", value=f"[Click Here]({bot_invite})", inline=False)
    embed.add_field(name="Support Server", value=f"[Click Here]({support_invite})", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show list of available commands")
async def help_command(interaction: discord.Interaction):
    """Display help information for all commands."""
    embed = discord.Embed(
        title="📚 Bot Help",
        description="Here's a list of available command categories. Use `/help [category]` for detailed information.",
        color=discord.Color.blue()
    )

    categories = {
        "Moderation": "Ban, kick, warn, timeout, lock/unlock channels, clear messages",
        "Utility": "Auto message, server info, user info, ping, avatar, slow mode, etc.",
        "Giveaway": "Start, end, and reroll giveaways",
        "Application": "Create and manage application systems",
        "Ticket": "Set up and manage support tickets",
        "Tournament": "Create tournament fixtures for 1v1, 2v2, or 4v4",
        "Bump": "Server bump system with banner management"
    }

    for category, description in categories.items():
        embed.add_field(name=category, value=description, inline=False)

    embed.set_footer(text="Use /help [category] for more details on specific commands")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    """Show the bot's current latency."""
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: {latency}ms")

@bot.event
async def on_application_command_error(interaction, error):
    """Handle errors from slash commands."""
    if isinstance(error, commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏰ Command on cooldown. Try again in {error.retry_after:.2f} seconds.", ephemeral=True)
        return

    if isinstance(error, commands.MissingPermissions):
        await interaction.response.send_message("❌ You don't have the required permissions to use this command.", ephemeral=True)
        return

    if isinstance(error, commands.BotMissingPermissions):
        missing_perms = ', '.join(error.missing_permissions)
        await interaction.response.send_message(f"❌ I need the following permissions to run this command: {missing_perms}", ephemeral=True)
        return

    logging.error(f"Command error: {error}")
    await interaction.response.send_message("❌ An error occurred while processing your command. Please try again later.", ephemeral=True)


async def setup_bot(bot_instance):
    """Setup function to be called from main.py"""
    # Sync commands
    try:
        await bot_instance.tree.sync()
        logging.info("Synced application commands")
    except Exception as e:
        logging.error(f"Failed to sync commands: {e}")