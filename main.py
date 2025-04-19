"""
This file serves dual purposes:
1. Contains the Discord bot code when run directly (python main.py)
2. Contains a small Flask app serving an import redirect for the gunicorn "main:app" import
"""

import os
import logging
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import config
from bot import setup_bot # Assuming setup_bot is in bot.py


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("discord_bot")

# Define intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True
intents.guilds = True #Added from edited code


# Initialize bot
class FeatureRichBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('!'),
            intents=intents,
            help_command=None
        )
        self.initial_extensions = [
            'cogs.moderation',
            'cogs.utility',
            'cogs.giveaway',
            'cogs.application',
            'cogs.ticket',
            'cogs.role_management',
            'cogs.auto_message',
            'cogs.embed_tools',
            'cogs.invite_tracker',
            'cogs.tournament',
            'cogs.games',
            'cogs.leveling',
            'cogs.economy',
            'cogs.welcome',
            'cogs.gym'
        ]

    async def setup_hook(self):
        # Load extensions
        for extension in self.initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded extension: {extension}")
            except Exception as e:
                logger.error(f"Failed to load extension {extension}: {e}")
                import traceback
                logger.error(traceback.format_exc())

        # We'll sync commands once we connect to the gateway
        logger.info("Will sync application commands after connecting to gateway")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")

        # Set a custom status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="/help for commands"
            )
        )

        # Now we can sync commands with correct application ID
        try:
            command_count = len(await self.tree.sync())
            logger.info(f"Synced {command_count} application commands")
        except Exception as e:
            logger.error(f"Failed to sync application commands: {e}")

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have permission to use this command.")
            return

        logger.error(f"Command error: {error}")
        await ctx.send(f"An error occurred: {error}")

bot = FeatureRichBot()

async def main():
    async with bot:
        await setup_bot(bot) # Use the imported setup_bot function
        from dotenv import load_dotenv
        load_dotenv()
        TOKEN = os.getenv("DISCORD_TOKEN")
        if not TOKEN:
            logger.critical("No Discord token found. Set the DISCORD_TOKEN environment variable.")
            exit(1)
        await bot.start(TOKEN)


@bot.tree.command(name="help", description="Shows the help menu")
async def help_command(interaction: discord.Interaction):
    """Display help information about bot commands"""
    embed = discord.Embed(
        title="Bot Commands Help",
        description="Here are the available command categories. Use `/help <category>` for more details.",
        color=discord.Color.blue()
    )

    categories = [
        ("🛡️ Moderation", "Ban, kick, warn, timeout, lock/unlock channel, clear messages"),
        ("🔧 Utility", "Ping, avatar, server info, user info, slowmode, timer"),
        ("🎉 Giveaway", "Start, end, and reroll giveaways"),
        ("📝 Application", "Create and manage application systems"),
        ("🎫 Tickets", "Create and manage support tickets"),
        ("👥 Role Management", "Add, remove, set admin/mod roles"),
        ("📢 Auto Message", "Set up automatic messages with intervals"),
        ("🖼️ Embed Tools", "Create and edit custom embeds"),
        ("📨 Invite Tracker", "Track server invites and their users"),
        ("🏆 Tournament", "Manage tournament fixtures for 1v1, 2v2, or 4v4"),
        ("🎮 Games", "Fun games like Guess the Number, Pokemon Scramble, Pokemon Riddle, and Fast Type"),
        ("📊 Leveling", "Level up by chatting, earn roles at specific levels, view leaderboard"),
        ("💰 Economy", "Earn and spend Chari Coins, shop with multiple categories, trade items"),
        ("👋 Welcome", "Customizable welcome and goodbye messages for new/leaving members"),
        ("🏋️ Gym", "Create and challenge Pokémon-style gyms, earn badges, track progress")
    ]

    for name, description in categories:
        embed.add_field(name=name, value=description, inline=False)

    embed.set_footer(text="Use /help <category> for more information about specific commands")

    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    asyncio.run(main())

# Flask app for the gunicorn "main:app" import
# This is imported by gunicorn when started with the Start application workflow
from flask import Flask, redirect
app = Flask(__name__)

@app.route('/')
def index():
    # Redirect to the app.py route
    from app import app as flask_app
    return flask_app.dispatch_request()
