import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
import string
import time
import re
from typing import Dict, Optional, List, Tuple, Set
from collections import defaultdict

from utils import has_admin_permissions, success_embed, error_embed

# List of Pokemon for the games
POKEMON = [
    "Pikachu", "Charizard", "Bulbasaur", "Squirtle", "Jigglypuff", "Eevee", "Mewtwo", "Snorlax", 
    "Gyarados", "Dragonite", "Gengar", "Lucario", "Garchomp", "Greninja", "Machamp", "Alakazam", 
    "Tyranitar", "Blaziken", "Gardevoir", "Metagross", "Salamence", "Swampert", "Infernape", 
    "Torterra", "Empoleon", "Zoroark", "Hydreigon", "Volcarona", "Sylveon", "Goodra", "Noivern", 
    "Mimikyu", "Toxtricity", "Corviknight", "Dragapult", "Urshifu", "Zarude", "Cinderace", 
    "Rillaboom", "Inteleon", "Zamazenta", "Zacian", "Eternatus", "Regieleki", "Glastrier", 
    "Spectrier", "Calyrex", "Baxcalibur", "Tinkaton", "Cetitan"
]

# Pokemon riddles list - pairs of (pokemon_name, riddle_text)
POKEMON_RIDDLES = [
    ("Pikachu", "I'm yellow, have red cheeks, and I'm the mascot of the franchise. Who am I?"),
    ("Charizard", "I'm the final evolution of a fire starter, and I can fly despite not being a Dragon type. Who am I?"),
    ("Squirtle", "I'm a tiny turtle who shoots water and evolves into a bigger turtle with cannons. Who am I?"),
    ("Bulbasaur", "I'm the first in the Pokedex, with a plant bulb on my back. Who am I?"),
    ("Mewtwo", "I was created by scientists from the DNA of Mew. Who am I?"),
    ("Jigglypuff", "I sing a song that makes people sleepy, then get angry when they fall asleep. Who am I?"),
    ("Gyarados", "I evolve from a weak fish but become a fearsome sea serpent. Who am I?"),
    ("Eevee", "I can evolve into many different types depending on various conditions. Who am I?"),
    ("Snorlax", "I'm big, I sleep a lot, and I'm known for blocking paths. Who am I?"),
    ("Gengar", "I'm a ghost/poison type that loves to hide in shadows. Who am I?"),
    ("Magikarp", "I'm known for being one of the weakest Pokémon, but I evolve into something amazing. Who am I?"),
    ("Dragonite", "I deliver mail, look friendly, and am the final evolution of a sea serpent. Who am I?"),
    ("Meowth", "I love shiny things, especially coins, and often appear with Team Rocket. Who am I?"),
    ("Ditto", "I can transform into any other Pokémon I see. Who am I?"),
    ("Mew", "I'm a mythical Pokémon said to contain the DNA of all Pokémon. Who am I?"),
    ("Celebi", "I'm a time-traveling forest guardian who resembles a fairy. Who am I?"),
    ("Wobbuffet", "I'm blue, blob-like, and I counter attacks rather than initiating them. Who am I?"),
    ("Mudkip", "I'm a water starter with a fin on my head that evolves into a water/ground type. Who am I?"),
    ("Rayquaza", "I'm a legendary dragon that lives in the ozone layer and stops Kyogre and Groudon from fighting. Who am I?"),
    ("Lucario", "I can sense and manipulate aura, and I'm a fighting/steel type. Who am I?")
]

# Fast type passages
TYPING_PASSAGES = [
    "The quick brown fox jumps over the lazy dog. This pangram contains every letter of the alphabet at least once. Typing quickly and accurately is a valuable skill for many jobs and activities. Practice makes perfect when it comes to typing speed and accuracy.",
    "In a world of technology, communication skills remain essential. Typing allows us to share ideas, connect with others, and express ourselves digitally. The faster and more accurately you can type, the more efficiently you can transform your thoughts into written words.",
    "Video games have evolved from simple pixelated adventures to complex virtual worlds with intricate storylines. Many gamers spend countless hours exploring these digital realms, completing quests, and building communities with fellow players across the globe.",
    "Pokemon trainers journey across regions collecting gym badges and capturing new creatures. Each Pokemon has unique abilities and types that make battles strategic and exciting. Legendary Pokemon are rare and powerful beings that often play important roles in the lore.",
    "Discord has become a popular platform for communities to gather, share, and communicate. Servers can be customized with various channels, roles, and permissions. Bots enhance the experience by providing additional features and automated responses to commands."
]

class GuessGame:
    """Class to manage a guess the number game instance"""
    def __init__(self, channel_id: int, owner_id: int, min_num: int, max_num: int):
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.min_num = min_num
        self.max_num = max_num
        self.number = random.randint(min_num, max_num)
        self.is_active = True
        self.guesses = {}  # Track user_id: number_of_guesses

    def guess(self, user_id: int, number: int) -> str:
        """Process a guess and return feedback"""
        if not self.is_active:
            return "This game is no longer active."

        # Increment or initialize the user's guess count
        self.guesses[user_id] = self.guesses.get(user_id, 0) + 1

        if number < self.number:
            return f"Too low! Try a higher number."
        elif number > self.number:
            return f"Too high! Try a lower number."
        else:
            self.is_active = False
            return "correct"  # Special return value for correct guesses

    def get_stats(self) -> Dict[int, int]:
        """Return stats about guesses made so far"""
        return self.guesses

class PokemonScrambleGame:
    """Class to manage a Pokemon Scramble game instance"""
    def __init__(self, channel_id: int, owner_id: int):
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.is_active = True
        self.current_round = 0
        self.max_rounds = 10
        self.scores = defaultdict(int)  # user_id: correct_answers
        self.used_pokemon = set()  # Track pokemon already used
        self.current_scramble = None
        self.current_answer = None
        self.message_id = None

    def get_random_pokemon(self) -> str:
        """Get a random pokemon that hasn't been used yet"""
        available_pokemon = [p for p in POKEMON if p not in self.used_pokemon]

        # If we've used all pokemon, reset the used list
        if not available_pokemon:
            self.used_pokemon.clear()
            available_pokemon = POKEMON

        pokemon = random.choice(available_pokemon)
        self.used_pokemon.add(pokemon)
        return pokemon

    def scramble_word(self, word: str) -> str:
        """Scramble the letters in a word"""
        word = word.lower()
        letters = list(word)
        random.shuffle(letters)
        scrambled = ''.join(letters)

        # Make sure the scrambled word is different from the original
        while scrambled == word.lower():
            random.shuffle(letters)
            scrambled = ''.join(letters)

        return scrambled

    def next_round(self) -> Tuple[str, str]:
        """Set up the next round and return (scrambled_word, original_word)"""
        if self.current_round >= self.max_rounds:
            self.is_active = False
            return None, None

        self.current_round += 1
        pokemon = self.get_random_pokemon()
        scrambled = self.scramble_word(pokemon)

        self.current_scramble = scrambled
        self.current_answer = pokemon.lower()

        return scrambled, pokemon

    def check_answer(self, user_id: int, answer: str) -> bool:
        """Check if an answer is correct and update scores"""
        if not self.is_active or not self.current_answer:
            return False

        if answer.lower() == self.current_answer:
            self.scores[user_id] += 1
            return True

        return False

    def get_winner(self) -> Tuple[int, int]:
        """Get the user_id with highest score and their score"""
        if not self.scores:
            return None, 0

        winner_id = max(self.scores, key=self.scores.get)
        return winner_id, self.scores[winner_id]


class PokemonRiddleGame:
    """Class to manage a Pokemon Riddle game instance"""
    def __init__(self, channel_id: int, owner_id: int):
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.is_active = True
        self.current_round = 0
        self.max_rounds = 10
        self.scores = defaultdict(int)  # user_id: correct_answers
        self.used_riddles = set()  # Track indices of riddles already used
        self.current_riddle = None
        self.current_answer = None
        self.message_id = None

    def get_random_riddle(self) -> Tuple[str, str]:
        """Get a random riddle that hasn't been used yet"""
        available_indices = [i for i in range(len(POKEMON_RIDDLES)) if i not in self.used_riddles]

        # If we've used all riddles, reset the used list
        if not available_indices:
            self.used_riddles.clear()
            available_indices = list(range(len(POKEMON_RIDDLES)))

        index = random.choice(available_indices)
        self.used_riddles.add(index)
        return POKEMON_RIDDLES[index]

    def next_round(self) -> Tuple[str, str]:
        """Set up the next round and return (riddle, answer)"""
        if self.current_round >= self.max_rounds:
            self.is_active = False
            return None, None

        self.current_round += 1
        pokemon, riddle = self.get_random_riddle()

        self.current_riddle = riddle
        self.current_answer = pokemon.lower()

        return riddle, pokemon

    def check_answer(self, user_id: int, answer: str) -> bool:
        """Check if an answer is correct and update scores"""
        if not self.is_active or not self.current_answer:
            return False

        if answer.lower() == self.current_answer:
            self.scores[user_id] += 1
            return True

        return False

    def get_winner(self) -> Tuple[int, int]:
        """Get the user_id with highest score and their score"""
        if not self.scores:
            return None, 0

        winner_id = max(self.scores, key=self.scores.get)
        return winner_id, self.scores[winner_id]


class FastTypeGame:
    """Class to manage a Fast Type game instance"""
    def __init__(self, channel_id: int, owner_id: int):
        self.channel_id = channel_id
        self.owner_id = owner_id
        self.is_active = True
        self.passage = None
        self.original_passage = None
        self.formatted_passage = None
        self.start_time = None
        self.players = {}  # user_id: {start_time, end_time, accuracy}
        self.message_id = None

    def start_game(self) -> str:
        """Start the game with a random passage and return formatted passage"""
        self.original_passage = random.choice(TYPING_PASSAGES)
        self.passage = self.original_passage.lower()

        # Format passage to make it harder to copy-paste
        formatted = ""
        for char in self.original_passage:
            if char.isalpha():
                # Use special unicode variants for letters to prevent easy copy-paste
                # These are "mathematical" variants of letters that look similar
                if char.isupper():
                    # Use italic uppercase letters instead of mathematical sans-serif
                    formatted += chr(ord('𝐴') + (ord(char) - ord('A')))
                else:
                    # Use italic lowercase letters instead of mathematical sans-serif
                    formatted += chr(ord('𝑎') + (ord(char) - ord('a')))
            else:
                formatted += char

        self.formatted_passage = formatted
        self.start_time = time.time()
        return self.formatted_passage

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate the similarity between two strings (simple implementation)"""
        text1 = text1.lower()
        text2 = text2.lower()

        # Simple character-by-character comparison
        errors = 0
        max_len = max(len(text1), len(text2))
        min_len = min(len(text1), len(text2))

        # Count character differences
        for i in range(min_len):
            if text1[i] != text2[i]:
                errors += 1

        # Add remaining characters as errors
        errors += max_len - min_len

        # Calculate accuracy percentage
        return max(0, 100 - (errors * 100 / max_len))

    def check_submission(self, user_id: int, text: str) -> Tuple[float, float]:
        """Check a user's submission and return (time_taken, accuracy)"""
        if not self.is_active or not self.passage:
            return 0, 0

        if user_id in self.players:
            return 0, 0  # User already submitted

        end_time = time.time()
        time_taken = end_time - self.start_time

        # Calculate accuracy
        text = text.lower()
        accuracy = self.calculate_similarity(self.passage, text)

        # Store player's result
        self.players[user_id] = {
            "time": time_taken,
            "accuracy": accuracy,
            "submission": text
        }

        return time_taken, accuracy

    def get_winner(self) -> Tuple[int, dict]:
        """Get the user_id with the fastest valid submission and their stats"""
        if not self.players:
            return None, {}

        # Only consider players with at least 90% accuracy
        qualified_players = {uid: stats for uid, stats in self.players.items() 
                            if stats["accuracy"] >= 90}

        if not qualified_players:
            return None, {}

        # Find the fastest qualified player
        winner_id = min(qualified_players, key=lambda uid: qualified_players[uid]["time"])
        return winner_id, qualified_players[winner_id]


class Games(commands.Cog):
    """Fun games for server members to play"""

    def __init__(self, bot):
        self.bot = bot
        self.guess_games = {}  # Dictionary of channel_id: GuessGame
        self.pokemon_scramble_games = {}  # Dictionary of channel_id: PokemonScrambleGame
        self.pokemon_riddle_games = {}  # Dictionary of channel_id: PokemonRiddleGame
        self.fast_type_games = {}  # Dictionary of channel_id: FastTypeGame

    @app_commands.command(name="guess_start", description="Start a Guess the Number game (Founder/Admin only)")
    @has_admin_permissions()
    async def guess_start(self, interaction: discord.Interaction, min_num: int = 1, max_num: int = 100):
        """Start a Guess the Number game (Founder/Admin only)"""
        # Check if user is founder or admin
        if not (interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only server founders and admins can start a Guess the Number game."),
                ephemeral=True
            )
            return

        # Check if a game is already active in this channel
        if interaction.channel.id in self.guess_games and self.guess_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("Game Already Active", "There's already a Guess the Number game running in this channel. Use `/guess_stop` to end it."),
                ephemeral=True
            )
            return

        # Create a new game
        self.guess_games[interaction.channel.id] = GuessGame(
            channel_id=interaction.channel.id,
            owner_id=interaction.user.id,
            min_num=min_num,
            max_num=max_num
        )

        # Send instructions
        embed = discord.Embed(
            title="🎮 Guess the Number Game Started!",
            description=f"I'm thinking of a number between {min_num} and {max_num}.\n\nType your guess in the chat to make a guess!\n\nThe first person to guess correctly wins!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Started by {interaction.user.display_name} • No time limit • No attempt limit")

        await interaction.response.send_message(embed=embed)

        # Send the correct number to the owner via DM
        try:
            correct_number = self.guess_games[interaction.channel.id].number
            await interaction.user.send(f"✅ You started a Guess the Number game in {interaction.channel.name}.\n**The correct number is: {correct_number}**")
        except discord.Forbidden:
            # Cannot DM the user
            await interaction.followup.send("Note: I couldn't send you a DM with the correct number. Please make sure your DMs are open.", ephemeral=True)

    @app_commands.command(name="guess_stop", description="Stop the active Guess the Number game (Founder/Admin only)")
    @has_admin_permissions()
    async def guess_stop(self, interaction: discord.Interaction):
        """Stop the active Guess the Number game (Founder/Admin only)"""
        # Check if a game is active in this channel
        if interaction.channel.id not in self.guess_games or not self.guess_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("No Active Game", "There's no active Guess the Number game in this channel."),
                ephemeral=True
            )
            return

        # Check if user is founder or admin
        if not (interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can stop a Guess the Number game."),
                ephemeral=True
            )
            return

        # End the game
        game = self.guess_games[interaction.channel.id]
        game.is_active = False

        embed = discord.Embed(
            title="🛑 Game Stopped",
            description=f"The Guess the Number game has been stopped by {interaction.user.display_name}.\nThe correct number was **{game.number}**.",
            color=discord.Color.red()
        )

        # Add stats about guesses
        stats = game.get_stats()
        total_guesses = sum(stats.values())
        participants = len(stats)

        embed.add_field(
            name="Game Stats",
            value=f"Total guesses: {total_guesses}\nParticipants: {participants}"
        )

        await interaction.response.send_message(embed=embed)

        # Unlock the channel
        try:
            overwrites = interaction.channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = None
                await interaction.channel.set_permissions(role, overwrite=overwrite)

            await interaction.channel.send("🔓 Channel has been unlocked.")
        except discord.Forbidden:
            await interaction.channel.send("⚠️ I don't have permissions to unlock the channel.")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for guesses in active games"""
        # Ignore bot messages
        if message.author.bot:
            return

        # Check if there's an active game in this channel
        if message.channel.id not in self.guess_games or not self.guess_games[message.channel.id].is_active:
            return

        # Try to convert message to number
        try:
            number = int(message.content)
        except ValueError:
            return

        # Process the guess
        game = self.guess_games[message.channel.id]
        result = game.guess(message.author.id, number)

        if result == "correct":
            # User guessed correctly!
            embed = discord.Embed(
                title="🎉 Correct Guess!",
                description=f"**{message.author.display_name}** guessed the number correctly! The number was **{game.number}**.",
                color=discord.Color.green()
            )

            # Add stats about guesses
            stats = game.get_stats()
            total_guesses = sum(stats.values())
            participants = len(stats)

            embed.add_field(
                name="Game Stats",
                value=f"Total guesses: {total_guesses}\nParticipants: {participants}\nYour guesses: {stats[message.author.id]}"
            )

            await message.channel.send(embed=embed)

            # Lock the channel to prevent further messages
            try:
                overwrites = message.channel.overwrites
                for role, overwrite in overwrites.items():
                    overwrite.send_messages = False
                    await message.channel.set_permissions(role, overwrite=overwrite)

                # Additional message about channel being locked
                await message.channel.send("🔒 This channel has been locked as the game has ended! The server owner can use `/guess_stop` to end the game.")
            except discord.Forbidden:
                await message.channel.send("⚠️ I don't have permissions to lock the channel.")

            # Send DM to the owner
            try:
                owner = await message.guild.fetch_member(game.owner_id)
                await owner.send(f"🎮 **Game Ended!** In {message.channel.name}, {message.author.display_name} correctly guessed the number **{game.number}**.")
            except:
                pass  # Silently fail if we can't DM the owner

        else:
            # User guessed incorrectly
            embed = discord.Embed(
                title="Guess Result",
                description=f"{result}",
                color=discord.Color.blue()
            )

            # Add hint about range
            if "higher" in result:
                embed.add_field(name="Hint", value=f"The number is between {number} and {game.max_num}")
            elif "lower" in result:
                embed.add_field(name="Hint", value=f"The number is between {game.min_num} and {number}")

            await message.channel.send(embed=embed)

    # Pokemon Scramble Game Commands

    @app_commands.command(name="pokemon_scramble_start", description="Start a Pokemon name scramble game (Founder/Admin only)")
    @has_admin_permissions()
    async def pokemon_scramble_start(self, interaction: discord.Interaction):
        """Start a Pokemon name scramble game (Founder/Admin only)"""
        # Check if user is founder or admin
        if not (interaction.user.id == interaction.guild.owner_id or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can start a Pokemon Scramble game."),
                ephemeral=True
            )
            return

        # Check if a game is already active in this channel
        if interaction.channel.id in self.pokemon_scramble_games and self.pokemon_scramble_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("Game Already Active", "There's already a Pokemon Scramble game running in this channel. Use `/pokemon_scramble_stop` to end it."),
                ephemeral=True
            )
            return

        # Create a new game
        self.pokemon_scramble_games[interaction.channel.id] = PokemonScrambleGame(
            channel_id=interaction.channel.id,
            owner_id=interaction.user.id
        )
        game = self.pokemon_scramble_games[interaction.channel.id]

        # Send game instructions
        embed = discord.Embed(
            title="🎮 Pokemon Scramble Game Started!",
            description="I'll show you 10 scrambled Pokemon names. Try to unscramble them and type the correct name in the chat!\n\nEach question will last for 20 seconds.\n\nThe player who answers the most questions correctly wins!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Started by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # Start the first round after a short delay
        await asyncio.sleep(3)
        await self.send_pokemon_scramble_question(interaction.channel, game)

    async def send_pokemon_scramble_question(self, channel, game):
        """Send a new Pokemon scramble question to the channel"""
        if not game.is_active:
            return

        # Get the next scrambled Pokemon
        scrambled, original = game.next_round()
        if not scrambled:  # No more rounds
            await self.end_pokemon_scramble_game(channel, game)
            return

        # Create and send the question embed
        embed = discord.Embed(
            title=f"Round {game.current_round}/10: Unscramble this Pokemon name!",
            description=f"**{scrambled.upper()}**",
            color=discord.Color.green()
        )
        embed.set_footer(text="Type your answer in the chat! You have 20 seconds.")

        message = await channel.send(embed=embed)
        game.message_id = message.id

        # Wait for correct answers
        def check(m):
            # Only accept messages in the correct channel
            if m.channel.id != channel.id:
                return False

            # Check if answer is correct (case insensitive)
            return m.content.lower() == game.current_answer

        try:
            # Wait for 20 seconds for a correct answer
            start_time = time.time()
            while time.time() - start_time < 20:
                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=20 - (time.time() - start_time))

                    # Someone got it right!
                    game.check_answer(msg.author.id, msg.content)

                    await channel.send(f"✅ {msg.author.mention} got it right! The answer was **{original}**.")

                    # Short break between questions
                    await asyncio.sleep(2)
                    break
                except asyncio.TimeoutError:
                    # No one got it right in time
                    break

            # Show the correct answer if no one got it
            if not any(user_id for user_id, score in game.scores.items() if score >= game.current_round):
                await channel.send(f"⏱️ Time's up! The correct answer was **{original}**.")
                await asyncio.sleep(2)

            # Continue to the next question or end the game
            if game.current_round < game.max_rounds and game.is_active:
                await self.send_pokemon_scramble_question(channel, game)
            else:
                await self.end_pokemon_scramble_game(channel, game)

        except Exception as e:
            await channel.send(f"An error occurred: {str(e)}")

    async def end_pokemon_scramble_game(self, channel, game):
        """End a Pokemon scramble game and announce the results"""
        if not game.is_active:
            return

        game.is_active = False

        # Get the winner
        winner_id, top_score = game.get_winner()

        embed = discord.Embed(
            title="🏆 Pokemon Scramble Game Finished!",
            color=discord.Color.gold()
        )

        # Format scores
        score_text = ""
        sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)

        for i, (user_id, score) in enumerate(sorted_scores, 1):
            try:
                user = await self.bot.fetch_user(user_id)
                score_text += f"{i}. {user.display_name}: {score} points\n"
            except:
                score_text += f"{i}. Unknown User: {score} points\n"

            # Only show top 10 players
            if i >= 10:
                break

        if score_text:
            embed.add_field(name="Final Scores", value=score_text, inline=False)
        else:
            embed.description = "No one scored any points!"

        # Announce the winner if there is one
        if winner_id:
            try:
                winner = await self.bot.fetch_user(winner_id)
                embed.description = f"🎉 **{winner.display_name}** won with **{top_score}** correct answers!"
            except:
                embed.description = "🎉 The winner couldn't be determined."

        await channel.send(embed=embed)

        # Lock the channel
        try:
            overwrites = channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = False
                await channel.set_permissions(role, overwrite=overwrite)

            await channel.send("🔒 This channel has been locked as the game has ended! The server owner can use `/pokemon_scramble_stop` to unlock it.")
        except discord.Forbidden:
            await channel.send("⚠️ I don't have permissions to lock the channel.")

    @app_commands.command(name="pokemon_scramble_stop", description="Stop the active Pokemon Scramble game (Server owner only)")
    async def pokemon_scramble_stop(self, interaction: discord.Interaction):
        """Stop the active Pokemon Scramble game (Server owner only)"""
        # Check if a game is active in this channel
        if interaction.channel.id not in self.pokemon_scramble_games or not self.pokemon_scramble_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("No Active Game", "There's no active Pokemon Scramble game in this channel."),
                ephemeral=True
            )
            return

        # Check if the user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can stop a Pokemon Scramble game."),
                ephemeral=True
            )
            return

        # End the game
        game = self.pokemon_scramble_games[interaction.channel.id]
        game.is_active = False

        embed = discord.Embed(
            title="🛑 Pokemon Scramble Game Stopped",
            description=f"The game has been stopped by {interaction.user.display_name}.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

        # Unlock the channel
        try:
            overwrites = interaction.channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = None
                await interaction.channel.set_permissions(role, overwrite=overwrite)

            await interaction.channel.send("🔓 Channel has been unlocked.")
        except discord.Forbidden:
            await interaction.channel.send("⚠️ I don't have permissions to unlock the channel.")

    # Pokemon Riddle Game Commands

    @app_commands.command(name="pokemon_riddle_start", description="Start a Pokemon riddle game (Server owner only)")
    async def pokemon_riddle_start(self, interaction: discord.Interaction):
        """Start a Pokemon riddle game (Server owner only)"""
        # Check if the user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can start a Pokemon Riddle game."),
                ephemeral=True
            )
            return

        # Check if a game is already active in this channel
        if interaction.channel.id in self.pokemon_riddle_games and self.pokemon_riddle_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("Game Already Active", "There's already a Pokemon Riddle game running in this channel. Use `/pokemon_riddle_stop` to end it."),
                ephemeral=True
            )
            return

        # Create a new game
        self.pokemon_riddle_games[interaction.channel.id] = PokemonRiddleGame(
            channel_id=interaction.channel.id,
            owner_id=interaction.user.id
        )
        game = self.pokemon_riddle_games[interaction.channel.id]

        # Send game instructions
        embed = discord.Embed(
            title="🎮 Pokemon Riddle Game Started!",
            description="I'll give you 10 riddles about Pokemon. Try to guess which Pokemon I'm describing!\n\nEach riddle will last for 20 seconds.\n\nThe player who answers the most riddles correctly wins!",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Started by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)

        # Start the first round after a short delay
        await asyncio.sleep(3)
        await self.send_pokemon_riddle_question(interaction.channel, game)

    async def send_pokemon_riddle_question(self, channel, game):
        """Send a new Pokemon riddle question to the channel"""
        if not game.is_active:
            return

        # Get the next riddle
        riddle, pokemon = game.next_round()
        if not riddle:  # No more rounds
            await self.end_pokemon_riddle_game(channel, game)
            return

        # Create and send the question embed
        embed = discord.Embed(
            title=f"Round {game.current_round}/10: Pokemon Riddle",
            description=f"**{riddle}**",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Type your answer in the chat! You have 20 seconds.")

        message = await channel.send(embed=embed)
        game.message_id = message.id

        # Wait for correct answers
        def check(m):
            # Only accept messages in the correct channel
            if m.channel.id != channel.id:
                return False

            # Check if answer is correct (case insensitive)
            return m.content.lower() == game.current_answer

        try:
            # Wait for 20 seconds for a correct answer
            start_time = time.time()
            while time.time() - start_time < 20:
                try:
                    msg = await self.bot.wait_for('message', check=check, timeout=20 - (time.time() - start_time))

                    # Someone got it right!
                    game.check_answer(msg.author.id, msg.content)

                    await channel.send(f"✅ {msg.author.mention} got it right! The answer was **{pokemon}**.")

                    # Short break between questions
                    await asyncio.sleep(2)
                    break
                except asyncio.TimeoutError:
                    # No one got it right in time
                    break

            # Show the correct answer if no one got it
            if not any(user_id for user_id, score in game.scores.items() if score >= game.current_round):
                await channel.send(f"⏱️ Time's up! The correct answer was **{pokemon}**.")
                await asyncio.sleep(2)

            # Continue to the next question or end the game
            if game.current_round < game.max_rounds and game.is_active:
                await self.send_pokemon_riddle_question(channel, game)
            else:
                await self.end_pokemon_riddle_game(channel, game)

        except Exception as e:
            await channel.send(f"An error occurred: {str(e)}")

    async def end_pokemon_riddle_game(self, channel, game):
        """End a Pokemon riddle game and announce the results"""
        if not game.is_active:
            return

        game.is_active = False

        # Get the winner
        winner_id, top_score = game.get_winner()

        embed = discord.Embed(
            title="🏆 Pokemon Riddle Game Finished!",
            color=discord.Color.gold()
        )

        # Format scores
        score_text = ""
        sorted_scores = sorted(game.scores.items(), key=lambda x: x[1], reverse=True)

        for i, (user_id, score) in enumerate(sorted_scores, 1):
            try:
                user = await self.bot.fetch_user(user_id)
                score_text += f"{i}. {user.display_name}: {score} points\n"
            except:
                score_text += f"{i}. Unknown User: {score} points\n"

            # Only show top 10 players
            if i >= 10:
                break

        if score_text:
            embed.add_field(name="Final Scores", value=score_text, inline=False)
        else:
            embed.description = "No one scored any points!"

        # Announce the winner if there is one
        if winner_id:
            try:
                winner = await self.bot.fetch_user(winner_id)
                embed.description = f"🎉 **{winner.display_name}** won with **{top_score}** correct answers!"
            except:
                embed.description = "🎉 The winner couldn't be determined."

        await channel.send(embed=embed)

        # Lock the channel
        try:
            overwrites = channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = False
                await channel.set_permissions(role, overwrite=overwrite)

            await channel.send("🔒 This channel has been locked as the game has ended! The server owner can use `/pokemon_riddle_stop` to unlock it.")
        except discord.Forbidden:
            await channel.send("⚠️ I don't have permissions to lock the channel.")

    @app_commands.command(name="pokemon_riddle_stop", description="Stop the active Pokemon Riddle game (Server owner only)")
    async def pokemon_riddle_stop(self, interaction: discord.Interaction):
        """Stop the active Pokemon Riddle game (Server owner only)"""
        # Check if a game is active in this channel
        if interaction.channel.id not in self.pokemon_riddle_games or not self.pokemon_riddle_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("No Active Game", "There's no active Pokemon Riddle game in this channel."),
                ephemeral=True
            )
            return

        # Check if the user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can stop a Pokemon Riddle game."),
                ephemeral=True
            )
            return

        # End the game
        game = self.pokemon_riddle_games[interaction.channel.id]
        game.is_active = False

        embed = discord.Embed(
            title="🛑 Pokemon Riddle Game Stopped",
            description=f"The game has been stopped by {interaction.user.display_name}.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

        # Unlock the channel
        try:
            overwrites = interaction.channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = None
                await interaction.channel.set_permissions(role, overwrite=overwrite)

            await interaction.channel.send("🔓 Channel has been unlocked.")
        except discord.Forbidden:
            await interaction.channel.send("⚠️ I don't have permissions to unlock the channel.")

    # Fast Type Game Commands

    @app_commands.command(name="fast_type_start", description="Start a fast typing game (Server owner only)")
    async def fast_type_start(self, interaction: discord.Interaction):
        """Start a fast typing game (Server owner only)"""
        # Check if the user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can start a Fast Type game."),
                ephemeral=True
            )
            return

        # Check if a game is already active in this channel
        if interaction.channel.id in self.fast_type_games and self.fast_type_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("Game Already Active", "There's already a Fast Type game running in this channel. Use `/fast_type_stop` to end it."),
                ephemeral=True
            )
            return

        # Create a new game
        self.fast_type_games[interaction.channel.id] = FastTypeGame(
            channel_id=interaction.channel.id,
            owner_id=interaction.user.id
        )
        game = self.fast_type_games[interaction.channel.id]

        # Start the game
        formatted_passage = game.start_game()

        # Split the passage into multiple messages if needed (due to Discord's message length limits)
        chunks = [formatted_passage[i:i+1900] for i in range(0, len(formatted_passage), 1900)]

        # Send game instructions first
        instructions_embed = discord.Embed(
            title="⌨️ Fast Type Game Started!",
            description="Type the following passage as quickly and accurately as possible.\n\nThe first person to type it correctly with at least 90% accuracy wins!\n\nCopy-pasting will not work due to the special formatting.",
            color=discord.Color.blue()
        )
        instructions_embed.set_footer(text=f"Started by {interaction.user.display_name}")

        await interaction.response.send_message(embed=instructions_embed)

        # Send the passage
        passage_embed = discord.Embed(
            title="📝 Type this passage:",
            description=chunks[0],
            color=discord.Color.green()
        )

        message = await interaction.channel.send(embed=passage_embed)
        game.message_id = message.id

        # Send additional chunks if any
        for chunk in chunks[1:]:
            chunk_embed = discord.Embed(description=chunk, color=discord.Color.green())
            await interaction.channel.send(embed=chunk_embed)

        # Information about submitting
        submit_embed = discord.Embed(
            title="🏁 How to submit",
            description="When you've finished typing, paste your answer in the chat. The fastest accurate typist wins!",
            color=discord.Color.gold()
        )
        await interaction.channel.send(embed=submit_embed)

        # Set up a listener for responses
        def check(m):
            # Only process messages in the correct channel
            if m.channel.id != interaction.channel.id:
                return False

            # Ignore bot messages
            if m.author.bot:
                return False

            # Message must be long enough to be a legitimate attempt
            return len(m.content) >= len(game.passage) * 0.5

        # Wait for a winner or until the game is stopped
        while game.is_active:
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=300)  # 5 minute timeout

                # Check the submission
                time_taken, accuracy = game.check_submission(msg.author.id, msg.content)

                if accuracy >= 90:
                    # This is a valid submission with good accuracy
                    embed = discord.Embed(
                        title="✅ Valid Submission!",
                        description=f"{msg.author.mention} has submitted with {accuracy:.1f}% accuracy in {time_taken:.2f} seconds.",
                        color=discord.Color.green()
                    )
                    await interaction.channel.send(embed=embed)

                    # Check if we have a winner
                    winner_id, stats = game.get_winner()
                    if winner_id and winner_id == msg.author.id:
                        await self.end_fast_type_game(interaction.channel, game, winner_id)
                        break
                else:
                    # Submission had poor accuracy
                    embed = discord.Embed(
                        title="⚠️ Low Accuracy Submission",
                        description=f"{msg.author.mention}'s submission had only {accuracy:.1f}% accuracy. At least 90% is required to win.",
                        color=discord.Color.orange()
                    )
                    await interaction.channel.send(embed=embed)

            except asyncio.TimeoutError:
                # No one submitted in 5 minutes
                await interaction.channel.send("⏱️ The Fast Type game timed out after 5 minutes with no valid submissions.")
                await self.end_fast_type_game(interaction.channel, game, None)
                break
            except Exception as e:
                await interaction.channel.send(f"An error occurred: {str(e)}")
                break

    async def end_fast_type_game(self, channel, game, winner_id):
        """End a Fast Type game and announce the results"""
        if not game.is_active:
            return

        game.is_active = False

        embed = discord.Embed(
            title="🏆 Fast Type Game Finished!",
            color=discord.Color.gold()
        )

        if winner_id:
            try:
                winner = await self.bot.fetch_user(winner_id)
                stats = game.players[winner_id]
                embed.description = f"🎉 **{winner.display_name}** won the Fast Type challenge!"
                embed.add_field(name="Time", value=f"{stats['time']:.2f} seconds", inline=True)
                embed.add_field(name="Accuracy", value=f"{stats['accuracy']:.1f}%", inline=True)
            except:
                embed.description = "🎉 The winner couldn't be determined."
        else:
            embed.description = "No one completed the challenge with sufficient accuracy."

        # Add all participants' stats
        if game.players:
            stats_text = ""
            sorted_players = sorted(game.players.items(), key=lambda x: x[1]['time'])

            for i, (user_id, stats) in enumerate(sorted_players, 1):
                if stats['accuracy'] >= 90:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        stats_text += f"{i}. {user.display_name}: {stats['time']:.2f}s ({stats['accuracy']:.1f}%)\n"
                    except:
                        stats_text += f"{i}. Unknown User: {stats['time']:.2f}s ({stats['accuracy']:.1f}%)\n"

                # Only show top 10 players
                if i >= 10:
                    break

            if stats_text:
                embed.add_field(name="Leaderboard", value=stats_text, inline=False)

        await channel.send(embed=embed)

        # Lock the channel
        try:
            overwrites = channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = False
                await channel.set_permissions(role, overwrite=overwrite)

            await channel.send("🔒 This channel has been locked as the game has ended! The server owner can use `/fast_type_stop` to unlock it.")
        except discord.Forbidden:
            await channel.send("⚠️ I don't have permissions to lock the channel.")

    @app_commands.command(name="fast_type_stop", description="Stop the active Fast Type game (Server owner only)")
    async def fast_type_stop(self, interaction: discord.Interaction):
        """Stop the active Fast Type game (Server owner only)"""
        # Check if a game is active in this channel
        if interaction.channel.id not in self.fast_type_games or not self.fast_type_games[interaction.channel.id].is_active:
            await interaction.response.send_message(
                embed=error_embed("No Active Game", "There's no active Fast Type game in this channel."),
                ephemeral=True
            )
            return

        # Check if the user is the server owner
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the server owner can stop a Fast Type game."),
                ephemeral=True
            )
            return

        # End the game
        game = self.fast_type_games[interaction.channel.id]
        game.is_active = False

        embed = discord.Embed(
            title="🛑 Fast Type Game Stopped",
            description=f"The game has been stopped by {interaction.user.display_name}.",
            color=discord.Color.red()
        )

        await interaction.response.send_message(embed=embed)

        # Unlock the channel
        try:
            overwrites = interaction.channel.overwrites
            for role, overwrite in overwrites.items():
                overwrite.send_messages = None
                await interaction.channel.set_permissions(role, overwrite=overwrite)

            await interaction.channel.send("🔓 Channel has been unlocked.")
        except discord.Forbidden:
            await interaction.channel.send("⚠️ I don't have permissions to unlock the channel.")

async def setup(bot):
    await bot.add_cog(Games(bot))