import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import json
import random
from datetime import datetime, timedelta
import typing
import config
from utils.embeds import success_embed, error_embed, info_embed
from utils.permissions import has_mod_perms, has_admin_perms, bot_has_permissions

logger = logging.getLogger(__name__)

class Tournament(commands.Cog):
    """Tournament and match fixture system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_tournaments = {}
    
    @app_commands.command(name="tournament", description="Create a tournament bracket")
    @app_commands.describe(
        name="The name of the tournament",
        type="The type of tournament (1v1, 2v2, or 4v4)",
        participants="Number of participants/teams (must be a power of 2: 4, 8, 16, 32)",
        channel="The channel to post the tournament bracket (defaults to current channel)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="1v1", value="1v1"),
        app_commands.Choice(name="2v2", value="2v2"),
        app_commands.Choice(name="4v4", value="4v4")
    ])
    @app_commands.checks.has_permissions(manage_events=True)
    async def tournament(self, 
                       interaction: discord.Interaction, 
                       name: str,
                       type: str,
                       participants: app_commands.Range[int, 4, 32],
                       channel: typing.Optional[discord.TextChannel] = None):
        """Create a tournament bracket"""
        # Validate participant count is a power of 2
        if not (participants & (participants - 1) == 0):
            await interaction.response.send_message(
                embed=error_embed("Invalid Participant Count", "The number of participants must be a power of 2 (4, 8, 16, 32)."),
                ephemeral=True
            )
            return
        
        # Get the channel to use (current channel if not specified)
        tournament_channel = channel or interaction.channel
        
        # Check if the bot can send messages in the target channel
        if not tournament_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I don't have permission to send messages in that channel."),
                ephemeral=True
            )
            return
        
        try:
            # Generate tournament ID
            tournament_id = f"tournament_{datetime.utcnow().timestamp()}"
            
            # Create tournament data
            tournament_data = {
                "id": tournament_id,
                "name": name,
                "type": type,
                "participants": participants,
                "created_by": str(interaction.user.id),
                "created_at": datetime.utcnow().isoformat(),
                "status": "signup",
                "channel_id": str(tournament_channel.id),
                "teams": {},
                "matches": []
            }
            
            # Add to active tournaments
            self.active_tournaments[tournament_id] = tournament_data
            
            # Create initial tournament embed
            embed = discord.Embed(
                title=f"🏆 {name}",
                description=f"A new {type} tournament has been created!\n\n"
                          f"**Type:** {type}\n"
                          f"**Participants:** 0/{participants}\n"
                          f"**Status:** Sign-up Phase\n\n"
                          "Click the button below to join the tournament.",
                color=config.COLORS["PRIMARY"],
                timestamp=datetime.utcnow()
            )
            
            embed.set_footer(text=f"Tournament ID: {tournament_id}")
            
            # Create tournament controls
            join_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Join Tournament",
                emoji="✅",
                custom_id=f"tournament_join_{tournament_id}"
            )
            
            leave_button = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Leave Tournament",
                emoji="❌",
                custom_id=f"tournament_leave_{tournament_id}"
            )
            
            start_button = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Start Tournament",
                emoji="🏁",
                custom_id=f"tournament_start_{tournament_id}"
            )
            
            view = discord.ui.View(timeout=None)
            view.add_item(join_button)
            view.add_item(leave_button)
            view.add_item(start_button)
            
            # Send the tournament announcement
            message = await tournament_channel.send(embed=embed, view=view)
            
            # Store message ID in tournament data
            tournament_data["message_id"] = str(message.id)
            
            # Respond to the interaction
            await interaction.response.send_message(
                embed=success_embed(
                    title="Tournament Created",
                    description=f"Tournament **{name}** has been created in {tournament_channel.mention}."
                )
            )
            
        except Exception as e:
            logger.error(f"Error creating tournament: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while creating the tournament: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="match", description="Create a match fixture")
    @app_commands.describe(
        team1="Name of the first team",
        team2="Name of the second team",
        type="The type of match (1v1, 2v2, or 4v4)",
        time="When the match will take place (optional)",
        channel="The channel to post the match fixture (defaults to current channel)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="1v1", value="1v1"),
        app_commands.Choice(name="2v2", value="2v2"),
        app_commands.Choice(name="4v4", value="4v4")
    ])
    @app_commands.checks.has_permissions(manage_events=True)
    async def match(self, 
                  interaction: discord.Interaction, 
                  team1: str,
                  team2: str,
                  type: str,
                  time: typing.Optional[str] = None,
                  channel: typing.Optional[discord.TextChannel] = None):
        """Create a match fixture"""
        # Get the channel to use (current channel if not specified)
        match_channel = channel or interaction.channel
        
        # Check if the bot can send messages in the target channel
        if not match_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I don't have permission to send messages in that channel."),
                ephemeral=True
            )
            return
        
        try:
            # Parse time if provided
            match_time = None
            time_display = "To be announced"
            
            if time:
                try:
                    # Try to parse time (format: YYYY-MM-DD HH:MM or MM/DD/YYYY HH:MM)
                    formats = ["%Y-%m-%d %H:%M", "%m/%d/%Y %H:%M"]
                    for fmt in formats:
                        try:
                            match_time = datetime.strptime(time, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if not match_time:
                        raise ValueError("Invalid time format")
                        
                    # Format for display
                    time_display = f"<t:{int(match_time.timestamp())}:F>"
                except ValueError:
                    await interaction.response.send_message(
                        embed=error_embed("Invalid Time Format", "Please use the format YYYY-MM-DD HH:MM or MM/DD/YYYY HH:MM"),
                        ephemeral=True
                    )
                    return
            
            # Generate match ID
            match_id = f"match_{datetime.utcnow().timestamp()}"
            
            # Create match data
            match_data = {
                "id": match_id,
                "team1": team1,
                "team2": team2,
                "type": type,
                "time": match_time.isoformat() if match_time else None,
                "created_by": str(interaction.user.id),
                "created_at": datetime.utcnow().isoformat(),
                "status": "scheduled",
                "channel_id": str(match_channel.id),
                "winner": None
            }
            
            # Create match embed
            embed = discord.Embed(
                title=f"⚔️ Match: {team1} vs {team2}",
                description=f"A {type} match has been scheduled!\n\n"
                          f"**Type:** {type}\n"
                          f"**Time:** {time_display}\n"
                          f"**Status:** Scheduled\n",
                color=config.COLORS["INFO"],
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name=team1, value="⏳ Ready", inline=True)
            embed.add_field(name=team2, value="⏳ Ready", inline=True)
            
            embed.set_footer(text=f"Match ID: {match_id}")
            
            # Create match controls
            team1_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"{team1} Won",
                custom_id=f"match_win_{match_id}_team1"
            )
            
            team2_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"{team2} Won",
                custom_id=f"match_win_{match_id}_team2"
            )
            
            cancel_button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Cancel Match",
                custom_id=f"match_cancel_{match_id}"
            )
            
            view = discord.ui.View(timeout=None)
            view.add_item(team1_button)
            view.add_item(team2_button)
            view.add_item(cancel_button)
            
            # Send the match fixture
            message = await match_channel.send(embed=embed, view=view)
            
            # Store message ID in match data
            match_data["message_id"] = str(message.id)
            
            # Respond to the interaction
            await interaction.response.send_message(
                embed=success_embed(
                    title="Match Created",
                    description=f"Match **{team1} vs {team2}** has been created in {match_channel.mention}."
                )
            )
            
        except Exception as e:
            logger.error(f"Error creating match: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while creating the match: {e}"),
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        """Handle button interactions for tournaments and matches"""
        if not interaction.type == discord.InteractionType.component:
            return
            
        custom_id = interaction.data.get("custom_id", "")
        
        # Handle tournament buttons
        if custom_id.startswith("tournament_join_"):
            # Join tournament button clicked
            tournament_id = custom_id.split("_")[2]
            await self.handle_tournament_join(interaction, tournament_id)
            
        elif custom_id.startswith("tournament_leave_"):
            # Leave tournament button clicked
            tournament_id = custom_id.split("_")[2]
            await self.handle_tournament_leave(interaction, tournament_id)
            
        elif custom_id.startswith("tournament_start_"):
            # Start tournament button clicked
            tournament_id = custom_id.split("_")[2]
            await self.handle_tournament_start(interaction, tournament_id)
            
        # Handle match buttons
        elif custom_id.startswith("match_win_"):
            # Match winner button clicked
            parts = custom_id.split("_")
            match_id = parts[2]
            winner = parts[3]  # team1 or team2
            await self.handle_match_winner(interaction, match_id, winner)
            
        elif custom_id.startswith("match_cancel_"):
            # Cancel match button clicked
            match_id = custom_id.split("_")[2]
            await self.handle_match_cancel(interaction, match_id)
    
    async def handle_tournament_join(self, interaction, tournament_id):
        """Handle a user joining a tournament"""
        # Check if tournament exists
        if tournament_id not in self.active_tournaments:
            await interaction.response.send_message(
                embed=error_embed("Tournament Not Found", "This tournament no longer exists."),
                ephemeral=True
            )
            return
        
        tournament = self.active_tournaments[tournament_id]
        
        # Check if tournament is still in signup phase
        if tournament["status"] != "signup":
            await interaction.response.send_message(
                embed=error_embed("Tournament Started", "This tournament has already started or ended."),
                ephemeral=True
            )
            return
        
        # Check if user is already in the tournament
        user_id = str(interaction.user.id)
        user_name = str(interaction.user)
        
        if user_id in tournament["teams"]:
            await interaction.response.send_message(
                embed=info_embed("Already Joined", "You have already joined this tournament."),
                ephemeral=True
            )
            return
        
        # Check if tournament is full
        if len(tournament["teams"]) >= tournament["participants"]:
            await interaction.response.send_message(
                embed=error_embed("Tournament Full", "This tournament is already full."),
                ephemeral=True
            )
            return
        
        # Add user to tournament
        tournament["teams"][user_id] = {
            "name": user_name,
            "joined_at": datetime.utcnow().isoformat()
        }
        
        # Update tournament message
        await self.update_tournament_message(interaction.guild, tournament)
        
        # Respond to the interaction
        await interaction.response.send_message(
            embed=success_embed(
                title="Tournament Joined",
                description=f"You have joined the tournament **{tournament['name']}**."
            ),
            ephemeral=True
        )
    
    async def handle_tournament_leave(self, interaction, tournament_id):
        """Handle a user leaving a tournament"""
        # Check if tournament exists
        if tournament_id not in self.active_tournaments:
            await interaction.response.send_message(
                embed=error_embed("Tournament Not Found", "This tournament no longer exists."),
                ephemeral=True
            )
            return
        
        tournament = self.active_tournaments[tournament_id]
        
        # Check if tournament is still in signup phase
        if tournament["status"] != "signup":
            await interaction.response.send_message(
                embed=error_embed("Tournament Started", "This tournament has already started or ended."),
                ephemeral=True
            )
            return
        
        # Check if user is in the tournament
        user_id = str(interaction.user.id)
        
        if user_id not in tournament["teams"]:
            await interaction.response.send_message(
                embed=info_embed("Not Joined", "You have not joined this tournament."),
                ephemeral=True
            )
            return
        
        # Remove user from tournament
        del tournament["teams"][user_id]
        
        # Update tournament message
        await self.update_tournament_message(interaction.guild, tournament)
        
        # Respond to the interaction
        await interaction.response.send_message(
            embed=success_embed(
                title="Tournament Left",
                description=f"You have left the tournament **{tournament['name']}**."
            ),
            ephemeral=True
        )
    
    async def handle_tournament_start(self, interaction, tournament_id):
        """Handle starting a tournament"""
        # Check if tournament exists
        if tournament_id not in self.active_tournaments:
            await interaction.response.send_message(
                embed=error_embed("Tournament Not Found", "This tournament no longer exists."),
                ephemeral=True
            )
            return
        
        tournament = self.active_tournaments[tournament_id]
        
        # Check if user has permission to start the tournament
        if str(interaction.user.id) != tournament["created_by"] and not interaction.user.guild_permissions.manage_events:
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "Only the tournament creator or staff can start the tournament."),
                ephemeral=True
            )
            return
        
        # Check if tournament is still in signup phase
        if tournament["status"] != "signup":
            await interaction.response.send_message(
                embed=error_embed("Already Started", "This tournament has already started or ended."),
                ephemeral=True
            )
            return
        
        # Check if there are enough participants
        if len(tournament["teams"]) < 2:
            await interaction.response.send_message(
                embed=error_embed("Not Enough Participants", "At least 2 participants are required to start the tournament."),
                ephemeral=True
            )
            return
        
        # Fill remaining slots with byes if necessary
        participants = len(tournament["teams"])
        target = tournament["participants"]
        
        if participants < target:
            await interaction.response.send_message(
                embed=info_embed(
                    title="Unfilled Tournament",
                    description=f"The tournament has {participants}/{target} participants. Empty slots will be filled with byes."
                ),
                ephemeral=True
            )
        
        # Generate the bracket
        await self.generate_tournament_bracket(tournament)
        
        # Update tournament status
        tournament["status"] = "active"
        
        # Update tournament message
        await self.update_tournament_message(interaction.guild, tournament)
        
        # Respond to the interaction
        await interaction.response.send_message(
            embed=success_embed(
                title="Tournament Started",
                description=f"The tournament **{tournament['name']}** has started with {participants} participants."
            )
        )
    
    async def handle_match_winner(self, interaction, match_id, winner_team):
        """Handle setting a match winner"""
        # TODO: Implement match winner handling for both standalone matches and tournament matches
        
        # For now, just acknowledge the interaction
        team_name = "Team 1" if winner_team == "team1" else "Team 2"
        
        await interaction.response.send_message(
            embed=success_embed(
                title="Match Result Recorded",
                description=f"{team_name} has been recorded as the winner."
            )
        )
    
    async def handle_match_cancel(self, interaction, match_id):
        """Handle canceling a match"""
        # TODO: Implement match cancellation
        
        # For now, just acknowledge the interaction
        await interaction.response.send_message(
            embed=info_embed(
                title="Match Cancelled",
                description="This match has been cancelled."
            )
        )
    
    async def update_tournament_message(self, guild, tournament):
        """Update the tournament message with current information"""
        try:
            # Get the channel and message
            channel_id = int(tournament["channel_id"])
            message_id = int(tournament["message_id"])
            
            channel = guild.get_channel(channel_id)
            if not channel:
                logger.warning(f"Could not find channel {channel_id} for tournament {tournament['id']}")
                return
            
            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                logger.warning(f"Could not find message {message_id} for tournament {tournament['id']}")
                return
            
            # Create updated embed
            if tournament["status"] == "signup":
                # Tournament in signup phase
                embed = discord.Embed(
                    title=f"🏆 {tournament['name']}",
                    description=f"A {tournament['type']} tournament is now open for sign-ups!\n\n"
                              f"**Type:** {tournament['type']}\n"
                              f"**Participants:** {len(tournament['teams'])}/{tournament['participants']}\n"
                              f"**Status:** Sign-up Phase\n\n"
                              "Click the button below to join the tournament.",
                    color=config.COLORS["PRIMARY"],
                    timestamp=datetime.utcnow()
                )
                
                # Add participant list
                if tournament["teams"]:
                    participants_text = "\n".join([f"{i+1}. {data['name']}" for i, (_, data) in enumerate(tournament["teams"].items())])
                    embed.add_field(
                        name="Participants",
                        value=participants_text,
                        inline=False
                    )
            else:
                # Tournament active or completed
                embed = discord.Embed(
                    title=f"🏆 {tournament['name']}",
                    description=f"A {tournament['type']} tournament is in progress!\n\n"
                              f"**Type:** {tournament['type']}\n"
                              f"**Participants:** {len(tournament['teams'])}\n"
                              f"**Status:** {tournament['status'].title()}\n\n",
                    color=config.COLORS["INFO"],
                    timestamp=datetime.utcnow()
                )
                
                # Add bracket information
                rounds = []
                for match in tournament["matches"]:
                    round_num = match["round"]
                    while len(rounds) <= round_num:
                        rounds.append([])
                    rounds[round_num].append(match)
                
                # Add each round as a field
                for i, round_matches in enumerate(rounds):
                    round_name = f"Round {i}" if i > 0 else "Quarterfinals"
                    if i == len(rounds) - 2:
                        round_name = "Semifinals"
                    elif i == len(rounds) - 1:
                        round_name = "Finals"
                    
                    matches_text = []
                    for match in round_matches:
                        team1 = match["team1"]
                        team2 = match["team2"]
                        
                        if team1 == "bye":
                            team1_display = "BYE"
                        else:
                            user1 = guild.get_member(int(team1))
                            team1_display = user1.display_name if user1 else "Unknown"
                        
                        if team2 == "bye":
                            team2_display = "BYE"
                        else:
                            user2 = guild.get_member(int(team2))
                            team2_display = user2.display_name if user2 else "Unknown"
                        
                        winner = match.get("winner")
                        if winner == "team1":
                            matches_text.append(f"**{team1_display}** vs {team2_display}")
                        elif winner == "team2":
                            matches_text.append(f"{team1_display} vs **{team2_display}**")
                        else:
                            matches_text.append(f"{team1_display} vs {team2_display}")
                    
                    if matches_text:
                        embed.add_field(
                            name=round_name,
                            value="\n".join(matches_text),
                            inline=True
                        )
            
            embed.set_footer(text=f"Tournament ID: {tournament['id']}")
            
            # Update the message
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error updating tournament message: {e}")
    
    async def generate_tournament_bracket(self, tournament):
        """Generate a tournament bracket based on participants"""
        participants = list(tournament["teams"].keys())
        random.shuffle(participants)  # Randomize the order
        
        # Add byes if needed to make participant count a power of 2
        target_count = tournament["participants"]
        while len(participants) < target_count:
            participants.append("bye")
        
        # Create the bracket rounds
        rounds = []
        round_matches = []
        
        # First round
        for i in range(0, len(participants), 2):
            team1 = participants[i]
            team2 = participants[i+1] if i+1 < len(participants) else "bye"
            
            match = {
                "round": 0,
                "match": i // 2,
                "team1": team1,
                "team2": team2,
                "winner": None,
                "next_match": i // 4
            }
            
            # Auto-advance if there's a bye
            if team1 == "bye" and team2 != "bye":
                match["winner"] = "team2"
            elif team2 == "bye" and team1 != "bye":
                match["winner"] = "team1"
            
            round_matches.append(match)
        
        tournament["matches"] = round_matches
        
        # Generate future rounds (we'll fill them in as matches are completed)
        rounds_needed = 0
        temp = target_count
        while temp > 1:
            temp //= 2
            rounds_needed += 1
        
        for r in range(1, rounds_needed):
            prev_matches = len(round_matches)
            round_matches = []
            
            for i in range(prev_matches // 2):
                match = {
                    "round": r,
                    "match": i,
                    "team1": None,  # To be determined
                    "team2": None,  # To be determined
                    "winner": None,
                    "next_match": i // 2 if r < rounds_needed - 1 else None
                }
                
                round_matches.append(match)
                tournament["matches"].extend(round_matches)

async def setup(bot):
    await bot.add_cog(Tournament(bot))
