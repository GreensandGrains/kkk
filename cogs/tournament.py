import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict
import asyncio
import datetime
import random
import math

from utils import has_mod_permissions, has_admin_permissions, create_confirmation_view
from data_manager import DataManager

class TournamentMatchModal(discord.ui.Modal, title="Set Match Result"):
    """Modal for setting a tournament match result"""
    
    winner = discord.ui.TextInput(
        label="Winning Team Name",
        placeholder="Enter the exact name of the winning team...",
        required=True
    )
    
    score = discord.ui.TextInput(
        label="Score (Optional)",
        placeholder="e.g., 3-1",
        required=False
    )
    
    def __init__(self, match_id, team1, team2, tournament_name, cog):
        super().__init__()
        self.match_id = match_id
        self.team1 = team1
        self.team2 = team2
        self.tournament_name = tournament_name
        self.cog = cog
    
    async def on_submit(self, interaction: discord.Interaction):
        winner_name = self.winner.value.strip()
        
        # Validate winner
        if winner_name != self.team1 and winner_name != self.team2:
            await interaction.response.send_message(
                f"Error: Winner must be either '{self.team1}' or '{self.team2}'.",
                ephemeral=True
            )
            return
        
        # Set the match winner
        success = self.cog.data_manager.set_match_winner(
            interaction.guild.id,
            self.tournament_name,
            self.match_id,
            winner_name
        )
        
        if success:
            score_text = f" with a score of {self.score.value}" if self.score.value else ""
            await interaction.response.send_message(
                f"Match result recorded! {winner_name} wins{score_text}.",
                ephemeral=True
            )
            
            # Send a match result notification to the channel
            embed = discord.Embed(
                title="Match Result",
                description=f"**{self.team1}** vs **{self.team2}**",
                color=discord.Color.gold(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="Winner",
                value=winner_name,
                inline=True
            )
            
            if self.score.value:
                embed.add_field(
                    name="Score",
                    value=self.score.value,
                    inline=True
                )
            
            embed.add_field(
                name="Recorded By",
                value=interaction.user.mention,
                inline=True
            )
            
            await interaction.channel.send(embed=embed)
            
            # Check if tournament is now complete
            tournament = self.cog.data_manager.get_tournament(interaction.guild.id, self.tournament_name)
            if tournament and tournament.get("status") == "completed":
                # Find the team with the highest score
                teams = tournament.get("teams", {})
                if teams:
                    winner = max(teams.items(), key=lambda x: x[1].get("score", 0))
                    winner_name, winner_data = winner
                    
                    # Create champion announcement
                    champion_embed = discord.Embed(
                        title="Tournament Champion!",
                        description=f"The **{self.tournament_name}** tournament has concluded!",
                        color=discord.Color.gold(),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    champion_embed.add_field(
                        name="Champion",
                        value=f"**{winner_name}**",
                        inline=False
                    )
                    
                    champion_embed.add_field(
                        name="Score",
                        value=f"{winner_data.get('score', 0)} wins",
                        inline=True
                    )
                    
                    # Add team members
                    members_text = ""
                    for member_id in winner_data.get("members", []):
                        member = interaction.guild.get_member(int(member_id))
                        if member:
                            members_text += f"{member.mention} "
                    
                    if members_text:
                        champion_embed.add_field(
                            name="Team Members",
                            value=members_text,
                            inline=False
                        )
                    
                    await interaction.channel.send(embed=champion_embed)
        else:
            await interaction.response.send_message(
                "Failed to record match result. Please try again.",
                ephemeral=True
            )

class Tournament(commands.Cog):
    """Tournament commands for managing competitive events"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
    
    @app_commands.command(name="createtournament", description="Create a new tournament")
    @app_commands.describe(
        name="Name of the tournament",
        team_size="Number of players per team (1, 2, or 4)",
        team_count="Maximum number of teams allowed",
        channel="Channel for tournament announcements"
    )
    @has_mod_permissions()
    async def create_tournament_command(
        self, 
        interaction: discord.Interaction, 
        name: str,
        team_size: app_commands.Range[int, 1, 4],
        team_count: app_commands.Range[int, 2, 32],
        channel: discord.TextChannel
    ):
        # Validate team size (only 1, 2, or 4 allowed)
        if team_size not in [1, 2, 4]:
            await interaction.response.send_message(
                "Team size must be 1 (1v1), 2 (2v2), or 4 (4v4).",
                ephemeral=True
            )
            return
        
        # Check if a tournament with the same name already exists
        existing_tournament = self.data_manager.get_tournament(interaction.guild.id, name)
        if existing_tournament:
            await interaction.response.send_message(
                f"A tournament named '{name}' already exists.",
                ephemeral=True
            )
            return
        
        # Create the tournament
        success = self.data_manager.create_tournament(
            interaction.guild.id,
            name,
            team_size,
            team_count,
            channel.id
        )
        
        if success:
            # Create announcement embed
            embed = discord.Embed(
                title=f"New Tournament: {name}",
                description=f"A new {team_size}v{team_size} tournament has been created!",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="Team Size",
                value=f"{team_size} players per team",
                inline=True
            )
            
            embed.add_field(
                name="Team Limit",
                value=f"{team_count} teams maximum",
                inline=True
            )
            
            embed.add_field(
                name="Status",
                value="Registration open",
                inline=True
            )
            
            embed.add_field(
                name="How to Join",
                value=f"Use `/jointournament {name} [team name]` to register your team.",
                inline=False
            )
            
            # Send announcement
            await channel.send(embed=embed)
            
            await interaction.response.send_message(
                f"Tournament '{name}' created successfully. Announcement sent to {channel.mention}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to create tournament. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="jointournament", description="Join a tournament with your team")
    @app_commands.describe(
        tournament_name="Name of the tournament to join",
        team_name="Name for your team",
        member1="First team member (optional)",
        member2="Second team member (optional)",
        member3="Third team member (optional)"
    )
    async def join_tournament_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str,
        team_name: str,
        member1: Optional[discord.Member] = None,
        member2: Optional[discord.Member] = None,
        member3: Optional[discord.Member] = None
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Check if tournament is still in registration phase
        if tournament.get("status") != "registration":
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' is no longer accepting registrations.",
                ephemeral=True
            )
            return
        
        # Check if team name is valid
        if not team_name or len(team_name) > 32:
            await interaction.response.send_message(
                "Team name must be between 1 and 32 characters.",
                ephemeral=True
            )
            return
        
        # Get team size from tournament
        team_size = tournament.get("team_size", 1)
        
        # Compile team members based on team size
        team_members = [interaction.user.id]  # User creating the team is always first member
        
        if team_size >= 2 and member1:
            team_members.append(member1.id)
        
        if team_size >= 2 and member2:
            team_members.append(member2.id)
        
        if team_size == 4 and member3:
            team_members.append(member3.id)
        
        # Check if we have enough members
        if len(team_members) < team_size:
            await interaction.response.send_message(
                f"You need {team_size} members for this tournament. Please specify all team members.",
                ephemeral=True
            )
            return
        
        # Add the team to the tournament
        success = self.data_manager.add_team_to_tournament(
            interaction.guild.id,
            tournament_name,
            team_name,
            team_members
        )
        
        if success:
            # Get the channel for announcements
            channel_id = tournament.get("channel_id")
            channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
            
            # Create team registration embed
            embed = discord.Embed(
                title="Team Registered",
                description=f"Team **{team_name}** has registered for **{tournament_name}**!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add team members
            members_text = ""
            for member_id in team_members:
                member = interaction.guild.get_member(int(member_id))
                if member:
                    members_text += f"{member.mention} "
            
            embed.add_field(
                name="Team Members",
                value=members_text,
                inline=False
            )
            
            # Send announcement if channel exists
            if channel:
                await channel.send(embed=embed)
            
            # Get team count for the response
            teams = tournament.get("teams", {})
            team_count = len(teams) + 1  # Include the team we just added
            max_teams = tournament.get("team_count", 0)
            
            await interaction.response.send_message(
                f"Your team '{team_name}' has been registered for the tournament! ({team_count}/{max_teams} teams)"
            )
        else:
            await interaction.response.send_message(
                "Failed to register your team. This may be because:\n"
                "• The team name is already taken\n"
                "• One or more team members are already in another team\n"
                "• The tournament is full",
                ephemeral=True
            )
    
    @app_commands.command(name="starttournament", description="Start a tournament and generate matches")
    @app_commands.describe(
        tournament_name="Name of the tournament to start"
    )
    @has_mod_permissions()
    async def start_tournament_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Check if tournament is in registration phase
        if tournament.get("status") != "registration":
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' is already started or completed.",
                ephemeral=True
            )
            return
        
        # Get team count
        teams = tournament.get("teams", {})
        team_count = len(teams)
        
        if team_count < 2:
            await interaction.response.send_message(
                "Cannot start tournament with fewer than 2 teams.",
                ephemeral=True
            )
            return
        
        # Confirm start
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to start the tournament '{tournament_name}' with {team_count} teams? "
            f"Team registration will be closed."
        )
        
        if not confirm:
            await interaction.followup.send("Tournament start cancelled.", ephemeral=True)
            return
        
        # Start the tournament
        success = self.data_manager.start_tournament(interaction.guild.id, tournament_name)
        
        if success:
            # Get updated tournament data with matches
            tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
            
            # Get the channel for announcements
            channel_id = tournament.get("channel_id")
            channel = interaction.guild.get_channel(int(channel_id)) if channel_id else None
            
            if not channel:
                await interaction.followup.send(
                    "Tournament started, but announcement channel not found.",
                    ephemeral=True
                )
                return
            
            # Create tournament start announcement
            embed = discord.Embed(
                title=f"Tournament Started: {tournament_name}",
                description="The tournament has officially begun! Below are the matches for this tournament.",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # Add match information
            matches = tournament.get("matches", [])
            
            if not matches:
                await interaction.followup.send(
                    "Tournament started, but no matches were generated.",
                    ephemeral=True
                )
                return
            
            # Create match list embed fields
            for i, match in enumerate(matches):
                embed.add_field(
                    name=f"Match #{match.get('match_id', i+1)}",
                    value=f"**{match.get('team1')}** vs **{match.get('team2')}**",
                    inline=True
                )
            
            embed.add_field(
                name="Reporting Results",
                value="Moderators can use `/setmatchresult` to report match outcomes.",
                inline=False
            )
            
            await channel.send(embed=embed)
            
            await interaction.followup.send(
                f"Tournament '{tournament_name}' has been started successfully! "
                f"{len(matches)} matches have been generated.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Failed to start tournament. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="setmatchresult", description="Set the result of a tournament match")
    @app_commands.describe(
        tournament_name="Name of the tournament",
        match_id="ID of the match to set result for"
    )
    @has_mod_permissions()
    async def set_match_result_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str,
        match_id: int
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Check if tournament is ongoing
        if tournament.get("status") != "ongoing":
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' is not currently ongoing.",
                ephemeral=True
            )
            return
        
        # Find the match
        matches = tournament.get("matches", [])
        match = None
        
        for m in matches:
            if m.get("match_id") == match_id:
                match = m
                break
        
        if not match:
            await interaction.response.send_message(
                f"Match #{match_id} not found in tournament '{tournament_name}'.",
                ephemeral=True
            )
            return
        
        # Check if match is already completed
        if match.get("completed"):
            await interaction.response.send_message(
                f"Match #{match_id} has already been completed. Use `/editmatchresult` to change the result.",
                ephemeral=True
            )
            return
        
        # Show modal to enter match result
        await interaction.response.send_modal(
            TournamentMatchModal(
                match_id,
                match.get("team1"),
                match.get("team2"),
                tournament_name,
                self
            )
        )
    
    @app_commands.command(name="tournamentstatus", description="Check the status of a tournament")
    @app_commands.describe(
        tournament_name="Name of the tournament to check"
    )
    async def tournament_status_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Create status embed
        embed = discord.Embed(
            title=f"Tournament Status: {tournament_name}",
            description=f"Current status: **{tournament.get('status', 'Unknown').title()}**",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add basic information
        embed.add_field(
            name="Team Size",
            value=f"{tournament.get('team_size')}v{tournament.get('team_size')}",
            inline=True
        )
        
        embed.add_field(
            name="Teams",
            value=f"{len(tournament.get('teams', {}))} / {tournament.get('team_count')}",
            inline=True
        )
        
        # Add teams information
        teams = tournament.get("teams", {})
        if teams:
            teams_text = ""
            
            # For tournaments with many teams, just show count
            if len(teams) > 10:
                embed.add_field(
                    name=f"Registered Teams ({len(teams)})",
                    value="Too many teams to display. Use `/tournamentteams` to see all teams.",
                    inline=False
                )
            else:
                # Sort teams by score if tournament is ongoing or completed
                if tournament.get("status") in ["ongoing", "completed"]:
                    sorted_teams = sorted(teams.items(), key=lambda x: x[1].get("score", 0), reverse=True)
                    
                    for team_name, team_data in sorted_teams:
                        teams_text += f"**{team_name}** - {team_data.get('score', 0)} wins\n"
                else:
                    for team_name in teams:
                        teams_text += f"**{team_name}**\n"
                
                embed.add_field(
                    name=f"Registered Teams ({len(teams)})",
                    value=teams_text or "No teams registered yet.",
                    inline=False
                )
        
        # Add matches information if tournament is ongoing or completed
        if tournament.get("status") in ["ongoing", "completed"]:
            matches = tournament.get("matches", [])
            
            if matches:
                # Count completed matches
                completed_matches = sum(1 for match in matches if match.get("completed"))
                embed.add_field(
                    name="Matches",
                    value=f"{completed_matches} completed, {len(matches) - completed_matches} remaining",
                    inline=True
                )
                
                # Show next few upcoming matches
                upcoming_matches = [match for match in matches if not match.get("completed")]
                
                if upcoming_matches:
                    upcoming_text = ""
                    for i, match in enumerate(upcoming_matches[:5]):
                        upcoming_text += f"Match #{match.get('match_id')}: " \
                                        f"**{match.get('team1')}** vs **{match.get('team2')}**\n"
                    
                    embed.add_field(
                        name=f"Upcoming Matches ({len(upcoming_matches)})",
                        value=upcoming_text,
                        inline=False
                    )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="tournamentteams", description="List all teams in a tournament")
    @app_commands.describe(
        tournament_name="Name of the tournament"
    )
    async def tournament_teams_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Create teams embed
        embed = discord.Embed(
            title=f"Tournament Teams: {tournament_name}",
            description=f"Current status: **{tournament.get('status', 'Unknown').title()}**",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add teams information
        teams = tournament.get("teams", {})
        if not teams:
            embed.description += "\n\nNo teams have registered yet."
            await interaction.response.send_message(embed=embed)
            return
        
        # Sort teams by score if tournament is ongoing or completed
        if tournament.get("status") in ["ongoing", "completed"]:
            teams_list = sorted(teams.items(), key=lambda x: x[1].get("score", 0), reverse=True)
        else:
            teams_list = list(teams.items())
        
        # Create team fields
        for team_name, team_data in teams_list:
            # Get team members
            members_text = ""
            for member_id in team_data.get("members", []):
                member = interaction.guild.get_member(int(member_id))
                if member:
                    members_text += f"{member.mention} "
                else:
                    members_text += f"Unknown Member ({member_id}) "
            
            # Create field value with score if tournament has started
            field_value = members_text
            if tournament.get("status") in ["ongoing", "completed"]:
                field_value = f"**Score:** {team_data.get('score', 0)} wins\n**Members:** {members_text}"
            
            embed.add_field(
                name=team_name,
                value=field_value,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="tournamentmatches", description="List all matches in a tournament")
    @app_commands.describe(
        tournament_name="Name of the tournament"
    )
    async def tournament_matches_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Check if tournament has matches
        matches = tournament.get("matches", [])
        if not matches:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' has no matches yet. The tournament might not have started.",
                ephemeral=True
            )
            return
        
        # Create matches embed
        embed = discord.Embed(
            title=f"Tournament Matches: {tournament_name}",
            description=f"Current status: **{tournament.get('status', 'Unknown').title()}**",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Split matches into completed and upcoming
        completed_matches = [match for match in matches if match.get("completed")]
        upcoming_matches = [match for match in matches if not match.get("completed")]
        
        # Add upcoming matches
        if upcoming_matches:
            upcoming_text = ""
            for i, match in enumerate(upcoming_matches):
                upcoming_text += f"Match #{match.get('match_id')}: " \
                                f"**{match.get('team1')}** vs **{match.get('team2')}**\n"
            
            embed.add_field(
                name=f"Upcoming Matches ({len(upcoming_matches)})",
                value=upcoming_text,
                inline=False
            )
        
        # Add completed matches
        if completed_matches:
            completed_text = ""
            for i, match in enumerate(completed_matches):
                winner = match.get("winner", "Unknown")
                completed_text += f"Match #{match.get('match_id')}: " \
                                 f"**{match.get('team1')}** vs **{match.get('team2')}** - " \
                                 f"Winner: **{winner}**\n"
            
            embed.add_field(
                name=f"Completed Matches ({len(completed_matches)})",
                value=completed_text,
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="deletetournament", description="Delete a tournament")
    @app_commands.describe(
        tournament_name="Name of the tournament to delete"
    )
    @has_admin_permissions()
    async def delete_tournament_command(
        self, 
        interaction: discord.Interaction, 
        tournament_name: str
    ):
        # Get the tournament
        tournament = self.data_manager.get_tournament(interaction.guild.id, tournament_name)
        if not tournament:
            await interaction.response.send_message(
                f"Tournament '{tournament_name}' not found.",
                ephemeral=True
            )
            return
        
        # Confirm deletion
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to delete the tournament '{tournament_name}'? "
            f"This will permanently remove all tournament data including teams and match results."
        )
        
        if not confirm:
            await interaction.followup.send("Tournament deletion cancelled.", ephemeral=True)
            return
        
        # Delete the tournament from the database
        # Note: Since we don't have a delete_tournament method in the DataManager,
        # we'll update the tournament systems with the tournament removed
        tournaments = self.data_manager.get_tournaments(interaction.guild.id)
        if tournament_name in tournaments:
            del tournaments[tournament_name]
            
            # Update config with tournaments
            config_data = self.data_manager.config.load_guild_config(interaction.guild.id)
            config_data["tournament_systems"][str(interaction.guild.id)] = tournaments
            
            success = self.data_manager.config.save_guild_config(interaction.guild.id, config_data)
            
            if success:
                await interaction.followup.send(f"Tournament '{tournament_name}' has been deleted.")
            else:
                await interaction.followup.send("Failed to delete tournament. Please try again.", ephemeral=True)
        else:
            await interaction.followup.send(f"Tournament '{tournament_name}' not found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tournament(bot))
