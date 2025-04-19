import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Optional, Dict
import datetime
import io

from utils import has_mod_permissions, has_admin_permissions, create_confirmation_view
from data_manager import DataManager

class TicketButton(discord.ui.Button):
    """Button that opens a ticket when clicked"""
    
    def __init__(self, ticket_system_name: str, emoji: str = "📩"):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Open Ticket",
            emoji=emoji,
            custom_id=f"ticket_button_{ticket_system_name}"
        )
        self.ticket_system_name = ticket_system_name
    
    async def callback(self, interaction: discord.Interaction):
        # The actual callback is handled in the parent view
        await self.view.open_ticket(interaction, self.ticket_system_name)

class TicketView(discord.ui.View):
    """View containing the ticket button and handling the ticket creation process"""
    
    def __init__(self, ticket_systems: Dict[str, dict], data_manager: DataManager):
        super().__init__(timeout=None)  # Persistent view
        self.ticket_systems = ticket_systems
        self.data_manager = data_manager
        
        # Add buttons for each ticket system
        for name in ticket_systems:
            self.add_item(TicketButton(name))
    
    async def open_ticket(self, interaction: discord.Interaction, system_name: str):
        """Open a ticket for the user"""
        system_data = self.ticket_systems.get(system_name)
        if not system_data:
            await interaction.response.send_message("Ticket system not found. Please try again.", ephemeral=True)
            return
        
        # Check if ticket category exists
        category_id = system_data.get("category_id")
        category = interaction.guild.get_channel(int(category_id)) if category_id else None
        
        if not category:
            await interaction.response.send_message(
                "Ticket category not found. Please contact an administrator.",
                ephemeral=True
            )
            return
        
        # Check if the user already has an open ticket in this system
        user_has_ticket = False
        for channel in category.channels:
            if isinstance(channel, discord.TextChannel) and channel.topic and f"Ticket Owner: {interaction.user.id}" in channel.topic:
                user_has_ticket = True
                await interaction.response.send_message(
                    f"You already have an open ticket in {channel.mention}",
                    ephemeral=True
                )
                break
        
        if user_has_ticket:
            return
        
        # Get support role
        support_role = None
        if system_data.get("support_role_id"):
            support_role = interaction.guild.get_role(int(system_data["support_role_id"]))
        
        # Create ticket channel
        try:
            # Increment ticket count
            ticket_number = self.data_manager.increment_ticket_count(interaction.guild.id, system_name)
            if ticket_number is None:
                ticket_number = 1
            
            # Set up channel permissions
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            
            # Add support role permissions if it exists
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            # Create the ticket channel
            channel_name = f"ticket-{ticket_number}-{interaction.user.name}"
            if len(channel_name) > 100:  # Discord channel name limit is 100 characters
                channel_name = f"ticket-{ticket_number}"
            
            ticket_channel = await category.create_text_channel(
                channel_name,
                topic=f"Ticket Owner: {interaction.user.id} | System: {system_name}",
                overwrites=overwrites,
                reason=f"Ticket opened by {interaction.user.display_name}"
            )
            
            # Send success message to user
            await interaction.response.send_message(
                f"Your ticket has been created: {ticket_channel.mention}",
                ephemeral=True
            )
            
            # Send initial message in ticket channel
            embed = discord.Embed(
                title=f"Ticket #{ticket_number} - {system_name}",
                description=system_data.get("description", "Welcome to your ticket!"),
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="User",
                value=f"{interaction.user.mention} ({interaction.user.id})",
                inline=True
            )
            
            embed.add_field(
                name="Created",
                value=discord.utils.format_dt(discord.utils.utcnow(), "F"),
                inline=True
            )
            
            if support_role:
                embed.add_field(
                    name="Support Team",
                    value=support_role.mention,
                    inline=True
                )
            
            embed.set_footer(text="Use the buttons below to manage this ticket")
            
            # Add ticket control buttons
            ticket_controls = TicketControlView(interaction.user.id, system_name, self.data_manager)
            
            await ticket_channel.send(
                f"{interaction.user.mention} {support_role.mention if support_role else ''}",
                embed=embed,
                view=ticket_controls
            )
            
            # Log the ticket creation
            log_channel_id = system_data.get("log_channel_id")
            if log_channel_id:
                log_channel = interaction.guild.get_channel(int(log_channel_id))
                if log_channel:
                    log_embed = discord.Embed(
                        title="Ticket Created",
                        description=f"Ticket #{ticket_number} has been created.",
                        color=discord.Color.green(),
                        timestamp=discord.utils.utcnow()
                    )
                    
                    log_embed.add_field(
                        name="User",
                        value=f"{interaction.user.mention} ({interaction.user.id})",
                        inline=True
                    )
                    
                    log_embed.add_field(
                        name="Channel",
                        value=ticket_channel.mention,
                        inline=True
                    )
                    
                    log_embed.add_field(
                        name="System",
                        value=system_name,
                        inline=True
                    )
                    
                    await log_channel.send(embed=log_embed)
        
        except discord.Forbidden:
            await interaction.followup.send(
                "I don't have permission to create the ticket channel. Please contact an administrator.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"An error occurred while creating the ticket: {e}",
                ephemeral=True
            )

class TicketControlView(discord.ui.View):
    """View with buttons to control a ticket"""
    
    def __init__(self, owner_id: int, system_name: str, data_manager: DataManager):
        super().__init__(timeout=None)  # Persistent view
        self.owner_id = owner_id
        self.system_name = system_name
        self.data_manager = data_manager
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket"""
        # Check if user is moderator or ticket owner
        is_owner = interaction.user.id == self.owner_id
        is_mod = interaction.user.guild_permissions.manage_channels
        
        if not (is_owner or is_mod):
            await interaction.response.send_message(
                "You don't have permission to close this ticket.",
                ephemeral=True
            )
            return
        
        # Ask for confirmation
        confirm = await create_confirmation_view(
            interaction,
            "Are you sure you want to close this ticket? A transcript will be saved."
        )
        
        if not confirm:
            await interaction.followup.send("Ticket closure cancelled.", ephemeral=True)
            return
        
        # Get the system data for log channel
        system_data = self.data_manager.get_ticket_system(interaction.guild.id, self.system_name)
        log_channel = None
        
        if system_data and system_data.get("log_channel_id"):
            log_channel = interaction.guild.get_channel(int(system_data["log_channel_id"]))
        
        # Get the ticket owner
        ticket_owner = interaction.guild.get_member(self.owner_id)
        
        # Create transcript
        transcript = await self.create_transcript(interaction.channel)
        
        # Send transcript to log channel if it exists
        if log_channel and transcript:
            # Create log embed
            log_embed = discord.Embed(
                title="Ticket Closed",
                description=f"Ticket closed by {interaction.user.mention}",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            
            log_embed.add_field(
                name="Ticket",
                value=f"#{interaction.channel.name}",
                inline=True
            )
            
            log_embed.add_field(
                name="Owner",
                value=f"{ticket_owner.mention if ticket_owner else f'User ID: {self.owner_id}'} ",
                inline=True
            )
            
            log_embed.add_field(
                name="Closed by",
                value=interaction.user.mention,
                inline=True
            )
            
            # Send transcript file
            await log_channel.send(
                embed=log_embed,
                file=discord.File(
                    fp=io.BytesIO(transcript.encode()),
                    filename=f"transcript-{interaction.channel.name}.txt"
                )
            )
        
        # Send closing message
        closing_embed = discord.Embed(
            title="Ticket Closing",
            description="This ticket is now closed and will be deleted in 5 seconds.",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        
        await interaction.followup.send(embed=closing_embed)
        
        # Wait before deleting the channel
        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user.display_name}")
        except (discord.Forbidden, discord.HTTPException) as e:
            # If we can't delete, just let the user know
            await interaction.followup.send(
                f"Could not delete the channel: {e}",
                ephemeral=True
            )
    
    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📑", custom_id="ticket_transcript")
    async def transcript_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Generate a transcript of the ticket"""
        # Check if user is moderator or ticket owner
        is_owner = interaction.user.id == self.owner_id
        is_mod = interaction.user.guild_permissions.manage_channels
        
        if not (is_owner or is_mod):
            await interaction.response.send_message(
                "You don't have permission to generate a transcript.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        # Create transcript
        transcript = await self.create_transcript(interaction.channel)
        
        if transcript:
            # Send the transcript to the user
            await interaction.followup.send(
                "Here is the transcript for this ticket:",
                file=discord.File(
                    fp=io.BytesIO(transcript.encode()),
                    filename=f"transcript-{interaction.channel.name}.txt"
                ),
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Failed to generate transcript.",
                ephemeral=True
            )
    
    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="ticket_add_user")
    async def add_user_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a user to the ticket"""
        # Check if user is moderator
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "You don't have permission to add users to this ticket.",
                ephemeral=True
            )
            return
        
        # Show modal to enter user ID
        await interaction.response.send_modal(AddUserModal(interaction.channel))
    
    async def create_transcript(self, channel):
        """Create a text transcript of the channel"""
        try:
            messages = []
            async for message in channel.history(limit=None, oldest_first=True):
                # Format timestamp
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                # Format message content
                content = message.content or "*No content*"
                
                # Add embeds
                if message.embeds:
                    for i, embed in enumerate(message.embeds):
                        content += f"\n[Embed {i+1}]"
                        if embed.title:
                            content += f"\nTitle: {embed.title}"
                        if embed.description:
                            content += f"\nDescription: {embed.description}"
                        for field in embed.fields:
                            content += f"\n{field.name}: {field.value}"
                
                # Add attachments
                if message.attachments:
                    content += "\nAttachments: " + ", ".join(a.url for a in message.attachments)
                
                # Format the message
                formatted_message = f"[{timestamp}] {message.author.display_name} ({message.author.id}): {content}"
                messages.append(formatted_message)
            
            # Join all messages with newlines
            transcript = "\n\n".join(messages)
            
            # Add header
            header = (
                f"Transcript for {channel.name}\n"
                f"Created: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Guild: {channel.guild.name} ({channel.guild.id})\n"
                f"------------------------\n\n"
            )
            
            return header + transcript
            
        except Exception as e:
            print(f"Error creating transcript: {e}")
            return None

class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    """Modal for adding a user to a ticket"""
    
    user_id = discord.ui.TextInput(
        label="User ID or Mention",
        placeholder="Enter the user ID or @mention...",
        required=True
    )
    
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    async def on_submit(self, interaction: discord.Interaction):
        # Parse the user ID
        user_input = self.user_id.value.strip()
        
        # Check if it's a mention
        if user_input.startswith("<@") and user_input.endswith(">"):
            # Extract ID from mention
            user_id = "".join(c for c in user_input if c.isdigit())
        else:
            # Assume it's just an ID
            user_id = "".join(c for c in user_input if c.isdigit())
        
        if not user_id:
            await interaction.response.send_message(
                "Invalid user ID or mention.",
                ephemeral=True
            )
            return
        
        # Get the user
        try:
            user_id = int(user_id)
            user = interaction.guild.get_member(user_id)
            
            if not user:
                await interaction.response.send_message(
                    "User not found in this server.",
                    ephemeral=True
                )
                return
            
            # Add user to the ticket
            await self.channel.set_permissions(
                user,
                read_messages=True,
                send_messages=True,
                reason=f"Added to ticket by {interaction.user.display_name}"
            )
            
            await interaction.response.send_message(
                f"Added {user.mention} to the ticket.",
                ephemeral=True
            )
            
            # Send notification in the channel
            await self.channel.send(f"{user.mention} has been added to the ticket by {interaction.user.mention}.")
            
        except ValueError:
            await interaction.response.send_message(
                "Invalid user ID.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to modify channel permissions.",
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"An error occurred: {e}",
                ephemeral=True
            )

class Ticket(commands.Cog):
    """Ticket commands for creating and managing support tickets"""
    
    def __init__(self, bot):
        self.bot = bot
        self.data_manager = DataManager()
        self.ticket_views = {}
    
    async def cog_load(self):
        """Set up persistent views when the cog is loaded"""
        for guild in self.bot.guilds:
            await self.setup_ticket_view(guild.id)
    
    async def setup_ticket_view(self, guild_id):
        """Set up the ticket panel view for a guild"""
        ticket_systems = self.data_manager.get_ticket_systems(guild_id)
        
        if ticket_systems:
            # Create the view for this guild
            view = TicketView(ticket_systems, self.data_manager)
            self.ticket_views[guild_id] = view
    
    @app_commands.command(name="createticket", description="Create a new ticket system")
    @app_commands.describe(
        name="Name of the ticket system",
        category="Category for ticket channels",
        log_channel="Channel for ticket logs",
        support_role="Role for support staff (optional)",
        description="Description for the ticket panel"
    )
    @has_admin_permissions()
    async def create_ticket_command(
        self, 
        interaction: discord.Interaction, 
        name: str,
        category: discord.CategoryChannel,
        log_channel: discord.TextChannel,
        support_role: Optional[discord.Role] = None,
        description: Optional[str] = "Click the button below to open a ticket"
    ):
        # Check if the bot has required permissions
        if not (interaction.guild.me.guild_permissions.manage_channels and 
                interaction.guild.me.guild_permissions.manage_roles):
            await interaction.response.send_message(
                "I need the 'Manage Channels' and 'Manage Roles' permissions to set up ticket systems.",
                ephemeral=True
            )
            return
        
        # Check if a ticket system with the same name already exists
        existing_tickets = self.data_manager.get_ticket_systems(interaction.guild.id)
        if name in existing_tickets:
            await interaction.response.send_message(
                f"A ticket system named '{name}' already exists.",
                ephemeral=True
            )
            return
        
        # Create the ticket system
        success = self.data_manager.create_ticket_system(
            interaction.guild.id,
            name,
            description,
            category.id,
            log_channel.id,
            support_role.id if support_role else None
        )
        
        if success:
            await interaction.response.send_message(
                f"Ticket system '{name}' created successfully!",
                ephemeral=True
            )
            
            # Update the ticket view for this guild
            await self.setup_ticket_view(interaction.guild.id)
        else:
            await interaction.response.send_message(
                "Failed to create ticket system. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(name="deleteticket", description="Delete a ticket system")
    @app_commands.describe(
        name="Name of the ticket system to delete"
    )
    @has_admin_permissions()
    async def delete_ticket_command(
        self, 
        interaction: discord.Interaction, 
        name: str
    ):
        # Check if the ticket system exists
        ticket_system = self.data_manager.get_ticket_system(interaction.guild.id, name)
        if not ticket_system:
            await interaction.response.send_message(
                f"Ticket system '{name}' not found.",
                ephemeral=True
            )
            return
        
        # Confirm deletion
        confirm = await create_confirmation_view(
            interaction,
            f"Are you sure you want to delete the ticket system '{name}'? This cannot be undone."
        )
        
        if not confirm:
            await interaction.followup.send("Deletion cancelled.", ephemeral=True)
            return
        
        # Delete the ticket system
        success = self.data_manager.delete_ticket_system(interaction.guild.id, name)
        
        if success:
            await interaction.followup.send(
                f"Ticket system '{name}' has been deleted.",
                ephemeral=True
            )
            
            # Update the ticket view for this guild
            await self.setup_ticket_view(interaction.guild.id)
        else:
            await interaction.followup.send(
                f"Failed to delete ticket system '{name}'.",
                ephemeral=True
            )
    
    @app_commands.command(name="ticketpanel", description="Create a ticket panel in the current channel")
    @app_commands.describe(
        title="Panel title",
        description="Panel description"
    )
    @has_admin_permissions()
    async def ticket_panel_command(
        self, 
        interaction: discord.Interaction, 
        title: str,
        description: str
    ):
        # Check if there are any ticket systems
        ticket_systems = self.data_manager.get_ticket_systems(interaction.guild.id)
        if not ticket_systems:
            await interaction.response.send_message(
                "No ticket systems found. Create one first using /createticket.",
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
        
        # Add ticket systems to the embed
        for name, ticket_data in ticket_systems.items():
            embed.add_field(
                name=name,
                value=ticket_data.get("description", "Click the button below to create a ticket"),
                inline=False
            )
        
        # Get or create the view for this guild
        if interaction.guild.id not in self.ticket_views:
            await self.setup_ticket_view(interaction.guild.id)
        
        view = self.ticket_views.get(interaction.guild.id)
        if not view:
            await interaction.response.send_message(
                "Failed to create ticket panel view.",
                ephemeral=True
            )
            return
        
        await interaction.response.send_message("Ticket panel created!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    
    @app_commands.command(name="listtickets", description="List all ticket systems")
    @has_mod_permissions()
    async def list_tickets_command(self, interaction: discord.Interaction):
        # Get all ticket systems
        ticket_systems = self.data_manager.get_ticket_systems(interaction.guild.id)
        
        if not ticket_systems:
            await interaction.response.send_message(
                "No ticket systems found.",
                ephemeral=True
            )
            return
        
        # Create the embed
        embed = discord.Embed(
            title="Ticket Systems",
            description=f"Found {len(ticket_systems)} ticket systems in this server.",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add ticket systems to the embed
        for name, ticket_data in ticket_systems.items():
            category = interaction.guild.get_channel(int(ticket_data.get("category_id", 0)))
            category_name = category.name if category else "Unknown category"
            
            log_channel = interaction.guild.get_channel(int(ticket_data.get("log_channel_id", 0)))
            log_channel_mention = log_channel.mention if log_channel else "Unknown channel"
            
            support_role_text = "None"
            if ticket_data.get("support_role_id"):
                role = interaction.guild.get_role(int(ticket_data["support_role_id"]))
                support_role_text = role.mention if role else "Unknown role"
            
            embed.add_field(
                name=name,
                value=(
                    f"**Category:** {category_name}\n"
                    f"**Log Channel:** {log_channel_mention}\n"
                    f"**Support Role:** {support_role_text}\n"
                    f"**Tickets Created:** {ticket_data.get('ticket_count', 0)}"
                ),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Ticket(bot))
