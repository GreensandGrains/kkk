import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Optional, List, Dict
import datetime

from utils import has_mod_permissions, has_admin_permissions, create_confirmation_view
from data_manager import DataManager

class ApplicationDropdown(discord.ui.Select):
    """Dropdown menu for application selection"""
    
    def __init__(self, applications: Dict[str, dict]):
        options = [
            discord.SelectOption(
                label=name,
                description=f"Apply for {name}",
                value=name
            ) for name in applications.keys()
        ]
        
        super().__init__(
            placeholder="Select an application type...",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # The actual callback is handled in the parent view
        self.view.selected_application = self.values[0]
        await self.view.start_application(interaction)

class ApplicationView(discord.ui.View):
    """View containing the application dropdown and handling the application process"""
    
    def __init__(self, applications: Dict[str, dict], data_manager: DataManager):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(ApplicationDropdown(applications))
        self.selected_application = None
        self.applications = applications
        self.data_manager = data_manager
        self.user_application_channels = {}
    
    async def start_application(self, interaction: discord.Interaction):
        """Start the application process for the selected application"""
        if not self.selected_application:
            await interaction.response.send_message("Please select an application type.", ephemeral=True)
            return
        
        app_name = self.selected_application
        app_data = self.applications.get(app_name)
        
        if not app_data:
            await interaction.response.send_message("Application not found. Please try again.", ephemeral=True)
            return
        
        # Check if user already has an active application channel
        if interaction.user.id in self.user_application_channels:
            existing_channel_id = self.user_application_channels[interaction.user.id]
            channel = interaction.guild.get_channel(existing_channel_id)
            
            if channel:
                await interaction.response.send_message(
                    f"You already have an active application in {channel.mention}. "
                    f"Please complete that application first.",
                    ephemeral=True
                )
                return
            else:
                # Channel no longer exists, remove from tracking
                del self.user_application_channels[interaction.user.id]
        
        # Get the guild's application category
        category = None
        for cat in interaction.guild.categories:
            if cat.name.lower() == "applications":
                category = cat
                break
        
        # If no category exists, try to create one
        if not category:
            try:
                category = await interaction.guild.create_category(
                    "Applications",
                    reason="Created for application system"
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    "Error: I don't have permission to create a category. "
                    "Please give me the 'Manage Channels' permission.",
                    ephemeral=True
                )
                return
        
        # Create temporary channel for the application
        try:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Add access for users with the application's role_id if it exists
            if app_data.get("role_id"):
                role = interaction.guild.get_role(int(app_data["role_id"]))
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel_name = f"application-{interaction.user.name.lower()}"
            
            # Create the channel
            temp_channel = await category.create_text_channel(
                channel_name,
                overwrites=overwrites,
                reason=f"Application channel for {interaction.user.display_name} - {app_name}"
            )
            
            # Add channel to tracking
            self.user_application_channels[interaction.user.id] = temp_channel.id
            
            # Inform the user
            await interaction.response.send_message(
                f"Your application for **{app_name}** has been started in {temp_channel.mention}!",
                ephemeral=True
            )
            
            # Post welcome message in the temporary channel
            embed = discord.Embed(
                title=f"{app_name} Application",
                description=(
                    f"Welcome to your application for **{app_name}**, {interaction.user.mention}!\n\n"
                    f"I will ask you a series of questions. Please answer each question to the best of your ability.\n"
                    f"Take your time to provide thoughtful answers. The application will automatically "
                    f"proceed to the next question after you respond."
                ),
                color=discord.Color.blue()
            )
            
            await temp_channel.send(interaction.user.mention, embed=embed)
            
            # Start the application questions
            await self.ask_questions(app_name, app_data, interaction.user, temp_channel, interaction.guild)
            
        except discord.Forbidden:
            await interaction.followup.send(
                "Error: I don't have permission to create channels. "
                "Please give me the 'Manage Channels' permission.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"An error occurred while creating the application channel: {e}",
                ephemeral=True
            )
    
    async def ask_questions(self, app_name, app_data, user, channel, guild):
        """Ask application questions one by one"""
        questions = app_data.get("questions", [])
        responses = []
        
        for i, question in enumerate(questions, 1):
            # Send the question
            question_embed = discord.Embed(
                title=f"Question {i}/{len(questions)}",
                description=question,
                color=discord.Color.blue()
            )
            await channel.send(embed=question_embed)
            
            # Wait for user response
            try:
                def check(m):
                    return m.author.id == user.id and m.channel.id == channel.id
                
                response = await self.bot.wait_for('message', check=check, timeout=1800)  # 30 minutes timeout
                responses.append(response.content)
                
                # Send confirmation
                confirm_embed = discord.Embed(
                    description=f"Response recorded. ✅",
                    color=discord.Color.green()
                )
                await channel.send(embed=confirm_embed)
                
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="Application Timed Out",
                    description="You didn't respond in time. The application has been cancelled.",
                    color=discord.Color.red()
                )
                await channel.send(embed=timeout_embed)
                
                # Remove from tracking and delete channel after a delay
                if user.id in self.user_application_channels:
                    del self.user_application_channels[user.id]
                
                await asyncio.sleep(10)
                try:
                    await channel.delete(reason="Application timed out")
                except (discord.Forbidden, discord.HTTPException):
                    pass
                
                return
        
        # Application completed - prepare summary
        summary_embed = discord.Embed(
            title="Application Completed",
            description=f"Thank you for completing your application for **{app_name}**!",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add questions and answers to the summary
        for i, (question, answer) in enumerate(zip(questions, responses), 1):
            summary_embed.add_field(
                name=f"Question {i}: {question}",
                value=answer[:1024] if answer else "*No answer provided*",
                inline=False
            )
        
        # Send the summary to the application channel
        await channel.send(embed=summary_embed)
        
        # Send the application to the log channel
        log_channel_id = app_data.get("log_channel_id")
        if log_channel_id:
            log_channel = guild.get_channel(int(log_channel_id))
            if log_channel:
                log_embed = discord.Embed(
                    title=f"New {app_name} Application",
                    description=f"Application from {user.mention} ({user.name})",
                    color=discord.Color.blue(),
                    timestamp=discord.utils.utcnow()
                )
                
                # Add application responses
                for i, (question, answer) in enumerate(zip(questions, responses), 1):
                    log_embed.add_field(
                        name=f"Question {i}: {question}",
                        value=answer[:1024] if answer else "*No answer provided*",
                        inline=False
                    )
                
                # Add user information
                log_embed.add_field(
                    name="User Information",
                    value=(
                        f"**ID:** {user.id}\n"
                        f"**Created:** {discord.utils.format_dt(user.created_at)}\n"
                        f"**Joined:** {discord.utils.format_dt(user.joined_at) if hasattr(user, 'joined_at') else 'Unknown'}"
                    ),
                    inline=False
                )
                
                log_embed.set_thumbnail(url=user.display_avatar.url)
                
                # Add buttons for accept/deny
                view = ApplicationResponseView(app_name, user.id, channel.id, guild.id, self.data_manager)
                await log_channel.send(embed=log_embed, view=view)
        
        # Inform the user that their application has been submitted
        final_embed = discord.Embed(
            title="Application Submitted",
            description=(
                f"Your application has been submitted for review.\n"
                f"You will be notified when the staff team has made a decision.\n\n"
                f"This channel will be deleted in 1 minute."
            ),
            color=discord.Color.blue()
        )
        await channel.send(embed=final_embed)
        
        # Remove from tracking and delete channel after a delay
        if user.id in self.user_application_channels:
            del self.user_application_channels[user.id]
        
        await asyncio.sleep(60)
        try:
            await channel.delete(reason="Application completed")
        except (discord.Forbidden, discord.HTTPException):
            pass

class ApplicationResponseView(discord.ui.View):
    """View with buttons to accept or deny an application"""
    
    def __init__(self, app_name, user_id, channel_id, guild_id, data_manager):
        super().__init__(timeout=None)  # Persistent view
        self.app_name = app_name
        self.user_id = user_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.data_manager = data_manager
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Accept the application"""
        # Get the application data
        app_data = self.data_manager.get_application_system(self.guild_id, self.app_name)
        if not app_data:
            await interaction.response.send_message("Application system not found.", ephemeral=True)
            return
        
        # Disable buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(view=self)
        
        # Get the user
        user = interaction.guild.get_member(self.user_id)
        if not user:
            await interaction.followup.send(
                "User not found. They may have left the server.",
                ephemeral=True
            )
            return
        
        # Assign role if specified
        if app_data.get("role_id"):
            try:
                role = interaction.guild.get_role(int(app_data["role_id"]))
                if role:
                    await user.add_roles(role, reason=f"Application for {self.app_name} accepted")
                    await interaction.followup.send(
                        f"Application accepted and role {role.mention} assigned to {user.mention}.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"Application accepted but role not found.",
                        ephemeral=True
                    )
            except discord.Forbidden:
                await interaction.followup.send(
                    f"Application accepted but I don't have permission to assign roles.",
                    ephemeral=True
                )
        else:
            await interaction.followup.send(
                f"Application for {user.mention} accepted.",
                ephemeral=True
            )
        
        # Edit the message to show it was accepted
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = f"{embed.title} - ACCEPTED"
        embed.add_field(
            name="Decision",
            value=f"✅ Accepted by {interaction.user.mention} on {discord.utils.format_dt(discord.utils.utcnow())}",
            inline=False
        )
        
        await interaction.message.edit(embed=embed)
        
        # Notify the user
        try:
            user_embed = discord.Embed(
                title=f"Application Accepted",
                description=f"Your application for **{self.app_name}** has been accepted!",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            await user.send(embed=user_embed)
        except (discord.Forbidden, discord.HTTPException):
            # Could not DM the user
            pass
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Deny the application"""
        # Show modal for reason
        await interaction.response.send_modal(ApplicationDenyModal(self))

class ApplicationDenyModal(discord.ui.Modal, title="Deny Application"):
    """Modal for entering a reason when denying an application"""
    
    reason = discord.ui.TextInput(
        label="Reason for denial",
        placeholder="Enter the reason for denying this application...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )
    
    def __init__(self, view):
        super().__init__()
        self.parent_view = view
    
    async def on_submit(self, interaction: discord.Interaction):
        # Disable buttons in the parent view
        for child in self.parent_view.children:
            child.disabled = True
        
        await interaction.message.edit(view=self.parent_view)
        
        # Get the user
        user = interaction.guild.get_member(self.parent_view.user_id)
        
        # Edit the message to show it was denied
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = f"{embed.title} - DENIED"
        embed.add_field(
            name="Decision",
            value=(
                f"❌ Denied by {interaction.user.mention} on {discord.utils.format_dt(discord.utils.utcnow())}\n"
                f"**Reason:** {self.reason.value}"
            ),
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed)
        
        # Notify the user if they're still in the server
        if user:
            try:
                user_embed = discord.Embed(
                    title=f"Application Denied",
                    description=f"Your application for **{self.parent_view.app_name}** has been denied.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                user_embed.add_field(
                    name="Reason",
                    value=self.reason.value,
                    inline=False
                )
                await user.send(embed=user_embed)
            except (discord.Forbidden, discord.HTTPException):
                # Could not DM the user
                pass

class Application(commands.Cog):
    """Application commands for creating and managing application systems"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.application_views = {}
    
    async def cog_load(self):
        """Set up persistent views when the cog is loaded"""
        for guild in self.bot.guilds:
            await self.setup_application_view(guild.id)
    
    async def setup_application_view(self, guild_id):
        """Set up the application panel view for a guild"""
        application_systems = self.data_manager.get_application_systems(guild_id)
        
        if application_systems:
            # Create the view for this guild
            view = ApplicationView(application_systems, self.data_manager)
            view.bot = self.bot  # Give the view a reference to the bot for wait_for functionality
            self.application_views[guild_id] = view
    
    @app_commands.command(name="createapplication", description="Create a new application system")
    @app_commands.describe(
        name="Name of the application system",
        log_channel="Channel where applications will be sent for review",
        role="Role to assign when application is accepted (optional)"
    )
    @has_admin_permissions()
    async def create_application_command(
        self, 
        interaction: discord.Interaction, 
        name: str,
        log_channel: discord.TextChannel,
        role: Optional[discord.Role] = None
    ):
        # Check if the bot has required permissions
        if not (interaction.guild.me.guild_permissions.manage_channels and 
                interaction.guild.me.guild_permissions.manage_roles):
            await interaction.response.send_message(
                "I need the 'Manage Channels' and 'Manage Roles' permissions to set up application systems.",
                ephemeral=True
            )
            return
        
        # Check if an application with the same name already exists
        existing_apps = self.data_manager.get_application_systems(interaction.guild.id)
        if name in existing_apps:
            await interaction.response.send_message(
                f"An application system named '{name}' already exists.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_modal(
            ApplicationCreateModal(self, name, log_channel.id, role.id if role else None)
        )
    
    @app_commands.command(name="deleteapplication", description="Delete an application system")
    @app_commands.describe(
        name="Name of the application system to delete"
    )
    @has_admin_permissions()
    async def delete_application_command(
        self, 
        interaction: discord.Interaction, 
        name: str
    ):
        # Check if the application exists
        app_system = self.data_manager.get_application_system(interaction.guild.id, name)
        if not app_system:
            await interaction.response.send_message(
                f"Application system '{name}' not found.",
                ephemeral=True
            )
            return
        
        # Confirm deletion
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to delete the application system '{name}'? This cannot be undone."
        )
        
        if not confirm:
            await interaction.followup.send("Deletion cancelled.", ephemeral=True)
            return
        
        # Delete the application system
        success = self.data_manager.delete_application_system(interaction.guild.id, name)
        
        if success:
            await interaction.followup.send(
                f"Application system '{name}' has been deleted.",
                ephemeral=True
            )
            
            # Update the application view for this guild
            await self.setup_application_view(interaction.guild.id)
        else:
            await interaction.followup.send(
                f"Failed to delete application system '{name}'.",
                ephemeral=True
            )
    
    @app_commands.command(name="editapplication", description="Edit a question in an application system")
    @app_commands.describe(
        name="Name of the application system",
        question_index="Index of the question to edit (starting from 1)",
        new_question="New question text"
    )
    @has_admin_permissions()
    async def edit_application_question_command(
        self, 
        interaction: discord.Interaction, 
        name: str,
        question_index: app_commands.Range[int, 1, 20],
        new_question: str
    ):
        # Check if the application exists
        app_system = self.data_manager.get_application_system(interaction.guild.id, name)
        if not app_system:
            await interaction.response.send_message(
                f"Application system '{name}' not found.",
                ephemeral=True
            )
            return
        
        # Check if the question index is valid
        if not app_system.get("questions") or question_index > len(app_system["questions"]):
            await interaction.response.send_message(
                f"Question index {question_index} is out of range. The application has {len(app_system.get('questions', []))} questions.",
                ephemeral=True
            )
            return
        
        # Edit the question
        success = self.data_manager.edit_application_question(
            interaction.guild.id,
            name,
            question_index - 1,  # Convert to 0-based index
            new_question
        )
        
        if success:
            await interaction.response.send_message(
                f"Question {question_index} in application system '{name}' has been updated.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Failed to update question {question_index}.",
                ephemeral=True
            )
    
    @app_commands.command(name="applicationpanel", description="Create an application panel in the current channel")
    @app_commands.describe(
        title="Panel title",
        description="Panel description"
    )
    @has_admin_permissions()
    async def application_panel_command(
        self, 
        interaction: discord.Interaction, 
        title: str,
        description: str
    ):
        # Check if there are any application systems
        applications = self.data_manager.get_application_systems(interaction.guild.id)
        if not applications:
            await interaction.response.send_message(
                "No application systems found. Create one first using /createapplication.",
                ephemeral=True
            )
            return
        
        # Create the panel embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add application systems to the embed
        for name, app_data in applications.items():
            role_text = ""
            if app_data.get("role_id"):
                role = interaction.guild.get_role(int(app_data["role_id"]))
                role_text = f" - {role.mention}" if role else ""
            
            embed.add_field(
                name=name + role_text,
                value=f"{len(app_data.get('questions', []))} questions",
                inline=True
            )
        
        embed.set_footer(text="Select an application type from the dropdown below")
        
        # Get or create the view for this guild
        if interaction.guild.id not in self.application_views:
            await self.setup_application_view(interaction.guild.id)
        
        view = self.application_views.get(interaction.guild.id)
        if not view:
            await interaction.response.send_message(
                "Failed to create application panel view.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message("Application panel created!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    
    @app_commands.command(name="listapplications", description="List all application systems")
    @has_mod_permissions()
    async def list_applications_command(self, interaction: discord.Interaction):
        # Get all application systems
        applications = self.data_manager.get_application_systems(interaction.guild.id)
        
        if not applications:
            await interaction.response.send_message(
                "No application systems found.",
                ephemeral=True
            )
            return
        
        # Create the embed
        embed = discord.Embed(
            title="Application Systems",
            description=f"Found {len(applications)} application systems in this server.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add application systems to the embed
        for name, app_data in applications.items():
            log_channel = interaction.guild.get_channel(int(app_data.get("log_channel_id", 0)))
            log_channel_mention = log_channel.mention if log_channel else "Unknown channel"
            
            role_text = "None"
            if app_data.get("role_id"):
                role = interaction.guild.get_role(int(app_data["role_id"]))
                role_text = role.mention if role else "Unknown role"
            
            embed.add_field(
                name=name,
                value=(
                    f"**Questions:** {len(app_data.get('questions', []))}\n"
                    f"**Log Channel:** {log_channel_mention}\n"
                    f"**Role:** {role_text}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class ApplicationCreateModal(discord.ui.Modal, title="Create Application System"):
    """Modal for creating a new application system"""
    
    questions = discord.ui.TextInput(
        label="Questions (one per line)",
        style=discord.TextStyle.paragraph,
        placeholder="Enter your questions, one per line...",
        required=True,
        max_length=4000
    )
    
    def __init__(self, cog, name, log_channel_id, role_id=None):
        super().__init__()
        self.cog = cog
        self.name = name
        self.log_channel_id = log_channel_id
        self.role_id = role_id
    
    async def on_submit(self, interaction: discord.Interaction):
        # Split the questions by line
        question_list = [q.strip() for q in self.questions.value.split('\n') if q.strip()]
        
        if not question_list:
            await interaction.response.send_message(
                "Please provide at least one question.",
                ephemeral=True
            )
            return
        
        # Create the application system
        success = self.cog.data_manager.create_application_system(
            interaction.guild.id,
            self.name,
            question_list,
            self.log_channel_id,
            self.role_id
        )
        
        if success:
            # Update the application view for this guild
            await self.cog.setup_application_view(interaction.guild.id)
            
            await interaction.response.send_message(
                f"Application system '{self.name}' created with {len(question_list)} questions!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to create application system. Please try again.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Application(bot))
