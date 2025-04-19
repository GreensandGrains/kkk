import asyncio
import logging
import sys
import os
import traceback
import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_cogs")

# Define intents similar to the main bot
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

class TestBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('!'),
            intents=intents,
            help_command=None
        )

async def test_cog_import(cog_name):
    """Test if a specific cog can be imported and loaded"""
    try:
        # Try direct import
        logger.info(f"Testing import for: {cog_name}")
        module_name = f"cogs.{cog_name}"
        __import__(module_name)
        logger.info(f"Successfully imported: {module_name}")
        return True
    except Exception as e:
        logger.error(f"Error importing {module_name}: {e}")
        logger.error(traceback.format_exc())
        return False

async def test_cog_load(bot, cog_name):
    """Test if a specific cog can be loaded by the bot"""
    try:
        logger.info(f"Testing loading cog: {cog_name}")
        await bot.load_extension(f"cogs.{cog_name}")
        logger.info(f"Successfully loaded: cogs.{cog_name}")
        return True
    except Exception as e:
        logger.error(f"Error loading cogs.{cog_name}: {e}")
        logger.error(traceback.format_exc())
        return False

async def main():
    """Test importing and loading problematic cogs"""
    problem_cogs = ["invite_tracker", "tournament", "games"]
    
    # First test importing
    for cog in problem_cogs:
        result = await test_cog_import(cog)
        print(f"Cog {cog} import: {'Success' if result else 'Failed'}")
    
    # Then test loading
    bot = TestBot()
    for cog in problem_cogs:
        result = await test_cog_load(bot, cog)
        print(f"Cog {cog} load: {'Success' if result else 'Failed'}")

if __name__ == "__main__":
    asyncio.run(main())