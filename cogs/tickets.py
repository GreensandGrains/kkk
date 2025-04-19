import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
import json
from datetime import datetime
import typing
import config
from utils.embeds import success_embed, error_embed, info_embed, ticket_embed
from utils.permissions import has_mod_perms, has_admin_perms, bot_has_permissions
from utils.data_manager import get_guild_data, update_guild_data, get_server_setting, set_server_setting

logger = logging.getLogger(__name__)

class TicketButton(discord.ui.Button):
    """Button for creating a ticket"""
    
    def __init__(self, label="Create Ticket", emoji="🎫", custom_id=None):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label,
            emoji=emoji,
            custom_id=custom_id or f"ticket_create_{datetime.utcnow().timestamp()}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Create a ticket when the button is clicked"""
        guild = interaction.guild
        user = interaction.user
        
        # Check if the bot has permission to manage channels
        if not guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "I don't have permission to create ticket channels.",
                ephemeral=True
            )
            return
        
        # Get ticket data
        ticket_data = await get_guild_data(config.TICKETS_FILE, guild.id)
        
        # Check if the user already has an open ticket
        user_id_str = str(user.id)
        if "active_tickets" in ticket_data and user_id_str in ticket_data["active_tickets"]:
            existing_channel_id = ticket_data["active_tickets"][user_id_str]
            channel = guild.get_channel(int(existing_channel_id))
            
            if channel:
                await interaction.response.send_message(
                    f"You already have an open ticket at {channel.mention}",
                    ephemeral=True
                )
                return
            else:
                # Channel doesn't exist anymore, remove it from active tickets
                del ticket_data["active_tickets"][user_id_str]
                await update_guild_data(config.TICKETS_FILE, guild.id, ticket_data)
        
        # Get support role
        support_role_id = await get_server_setting(guild.id, "ticket_support_role")
        support_role = None
        if support_role_id:
            support_role = guild.get_role(int(support_role_id))
        
        # Create permission overwrites
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Add support role permissions if it exists
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        try:
            # Create a ticket channel
            ticket_count = ticket_data.get("ticket_count", 0) + 1
            ticket_data["ticket_count"] = ticket_count
            
            # Get category from button custom id if available
            category_name = None
            custom_id_parts = self.custom_id.split("_")
            if len(custom_id_parts) > 2:
                category_name = custom_id_parts[2]
            
            # Get ticket category channel
            category_channel = None
            ticket_category_id = await get_server_setting(guild.id, "ticket_category")
            
            if ticket_category_id:
                category_channel = guild.get_channel(int(ticket_category_id))
            
            # Create channel name
            channel_name = f"ticket-{ticket_count:04d}-{user.name.lower()}"
            
            # Create the channel
            channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                category=category_channel,
                reason=f"Ticket created by {user}"
            )
            
            # Add to active tickets
            if "active_tickets" not in ticket_data:
                ticket_data["active_tickets"] = {}
                
            ticket_data["active_tickets"][user_id_str] = str(channel.id)
            
            # Save ticket data
            await update_guild_data(config.TICKETS_FILE, guild.id, ticket_data)
            
            # Create log entry
            if "ticket_logs" not in ticket_data:
                ticket_data["ticket_logs"] = []
                
            ticket_log = {
                "ticket_id": ticket_count,
                "channel_id": str(channel.id),
                "user_id": user_id_str,
                "created_at": datetime.utcnow().isoformat(),
                "status": "open",
                "category": category_name
            }
            
            ticket_data["ticket_logs"].append(ticket_log)
            await update_guild_data(config.TICKETS_FILE, guild.id, ticket_data)
            
            # Create welcome message
            embed = discord.Embed(
                title=f"Ticket #{ticket_count:04d}",
                description=f"Thank you for creating a ticket, {user.mention}!\n\n"
                          f"Please describe your issue and a staff member will assist you soon.",
                color=config.COLORS["INFO"],
                timestamp=datetime.utcnow()
            )
            
            if category_name:
                embed.add_field(name="Category", value=category_name, inline=True)
                
            # Add ticket controls
            close_button = discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="Close Ticket",
                emoji="🔒",
                custom_id=f"ticket_close_{ticket_count}"
            )
            
            claim_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="Claim Ticket",
                emoji="✋",
                custom_id=f"ticket_claim_{ticket_count}"
            )
            
            view = discord.ui.View(timeout=None)
            view.add_item(close_button)
            view.add_item(claim_button)
            
            await channel.send(f"{user.mention} {support_role.mention if support_role else ''}", embed=embed, view=view)
            
            # Respond to the interaction
            await interaction.response.send_message(
                f"Your ticket has been created at {channel.mention}",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.response.send_message(
                f"An error occurred while creating your ticket: {e}",
                ephemeral=True
            )

class TicketView(discord.ui.View):
    """View containing the ticket button"""
    
    def __init__(self, category=None):
        super().__init__(timeout=None)  # Persistent view
        
        # Create a custom ID that includes the category if provided
        custom_id = f"ticket_create_{category}" if category else "ticket_create"
        
        # Add the ticket button
        self.add_item(TicketButton(custom_id=custom_id))

class Tickets(commands.Cog):
    """Ticket system for support and help requests"""
    
    def __init__(self, bot):
        self.bot = bot
        self.views = {}  # Store ticket views by message ID
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Setup persistent views when bot starts"""
        # We would need to load all existing ticket panels and register their views
        # if we wanted them to persist through restarts
        pass
    
    @app_commands.command(name="ticket_panel", description="Create a ticket panel for users to open tickets")
    @app_commands.describe(
        channel="The channel to post the ticket panel in",
        title="The title of the ticket panel",
        description="The description of the ticket panel",
        category="The category for tickets created from this panel"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_panel(self, 
                          interaction: discord.Interaction, 
                          channel: discord.TextChannel,
                          title: str = "Support Tickets",
                          description: str = "Click the button below to create a support ticket.",
                          category: typing.Optional[str] = None):
        """Create a ticket panel for users to open tickets"""
        # Check if the bot can send messages in the target channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                embed=error_embed("Missing Permissions", "I don't have permission to send messages in that channel."),
                ephemeral=True
            )
            return
        
        try:
            # Create the ticket panel embed
            embed = ticket_embed(category or "Support")
            
            # Override title and description if provided
            if title != "Support Tickets":
                embed.title = title
            if description != "Click the button below to create a support ticket.":
                embed.description = description
            
            # Create and add the ticket view
            view = TicketView(category)
            
            # Send the panel
            message = await channel.send(embed=embed, view=view)
            
            # Store the view for persistence
            self.views[message.id] = view
            
            # Send confirmation
            await interaction.response.send_message(
                embed=success_embed(
                    title="Ticket Panel Created",
                    description=f"The ticket panel has been posted in {channel.mention}."
                )
            )
            
        except Exception as e:
            logger.error(f"Error creating ticket panel: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while creating the ticket panel: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="ticket_settings", description="Configure ticket system settings")
    @app_commands.describe(
        support_role="The role that can see and manage tickets",
        category="The category channel for ticket channels",
        log_channel="The channel where ticket logs will be sent when closed"
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def ticket_settings(self, 
                            interaction: discord.Interaction, 
                            support_role: typing.Optional[discord.Role] = None,
                            category: typing.Optional[discord.CategoryChannel] = None,
                            log_channel: typing.Optional[discord.TextChannel] = None):
        """Configure ticket system settings"""
        try:
            settings_changed = False
            
            # Update support role if provided
            if support_role:
                await set_server_setting(interaction.guild.id, "ticket_support_role", str(support_role.id))
                settings_changed = True
            
            # Update category if provided
            if category:
                await set_server_setting(interaction.guild.id, "ticket_category", str(category.id))
                settings_changed = True
            
            # Update log channel if provided
            if log_channel:
                # Check if bot can send messages to the channel
                if not log_channel.permissions_for(interaction.guild.me).send_messages:
                    await interaction.response.send_message(
                        embed=error_embed("Missing Permissions", "I don't have permission to send messages in the log channel."),
                        ephemeral=True
                    )
                    return
                
                await set_server_setting(interaction.guild.id, "ticket_log_channel", str(log_channel.id))
                settings_changed = True
            
            # If no settings were provided, show current settings
            if not settings_changed:
                support_role_id = await get_server_setting(interaction.guild.id, "ticket_support_role")
                category_id = await get_server_setting(interaction.guild.id, "ticket_category")
                log_channel_id = await get_server_setting(interaction.guild.id, "ticket_log_channel")
                
                support_role_text = f"<@&{support_role_id}>" if support_role_id else "Not set"
                category_text = f"<#{category_id}>" if category_id else "Not set"
                log_channel_text = f"<#{log_channel_id}>" if log_channel_id else "Not set"
                
                embed = discord.Embed(
                    title="Ticket System Settings",
                    description="Current ticket system settings:",
                    color=config.COLORS["INFO"]
                )
                
                embed.add_field(
                    name="Support Role",
                    value=support_role_text,
                    inline=True
                )
                
                embed.add_field(
                    name="Ticket Category",
                    value=category_text,
                    inline=True
                )
                
                embed.add_field(
                    name="Log Channel",
                    value=log_channel_text,
                    inline=True
                )
                
                await interaction.response.send_message(embed=embed)
                return
            
            # Send success message
            await interaction.response.send_message(
                embed=success_embed(
                    title="Settings Updated",
                    description="Ticket system settings have been updated."
                )
            )
            
        except Exception as e:
            logger.error(f"Error updating ticket settings: {e}")
            await interaction.response.send_message(
                embed=error_embed("Error", f"An error occurred while updating ticket settings: {e}"),
                ephemeral=True
            )
    
    @app_commands.command(name="close", description="Close the current ticket")
    @app_commands.describe(
        reason="The reason for closing the ticket"
    )
    async def close(self, interaction: discord.Interaction, reason: str = "No reason provided"):
        """Close the current ticket channel"""
        # Check if this is a ticket channel
        ticket_data = await get_guild_data(config.TICKETS_FILE, interaction.guild.id)
        
        if "active_tickets" not in ticket_data:
            await interaction.response.send_message(
                embed=error_embed("Not a Ticket", "This command can only be used in a ticket channel."),
                ephemeral=True
            )
            return
        
        # Find if this channel is a ticket
        channel_id_str = str(interaction.channel.id)
        user_id = None
        
        for user, channel in ticket_data["active_tickets"].items():
            if channel == channel_id_str:
                user_id = user
                break
        
        if not user_id:
            await interaction.response.send_message(
                embed=error_embed("Not a Ticket", "This channel is not an active ticket."),
                ephemeral=True
            )
            return
        
        # Check if user has permission to close the ticket
        if str(interaction.user.id) != user_id and not await self.can_manage_tickets(interaction.user):
            await interaction.response.send_message(
                embed=error_embed("Permission Denied", "You don't have permission to close this ticket."),
                ephemeral=True
            )
            return
        
        # Close the ticket
        await self.close_ticket(interaction, ticket_data, user_id, reason)
    
    async def close_ticket(self, interaction, ticket_data, user_id, reason):
        """Close a ticket and save transcript"""
        channel = interaction.channel
        guild = interaction.guild
        
        try:
            # First mark the ticket as closing
            await interaction.response.send_message(
                embed=info_embed(
                    title="Closing Ticket",
                    description=f"This ticket is being closed.\n**Reason:** {reason}"
                )
            )
            
            # Remove from active tickets
            channel_id = ticket_data["active_tickets"][user_id]
            del ticket_data["active_tickets"][user_id]
            
            # Update ticket log
            for log in ticket_data.get("ticket_logs", []):
                if log.get("channel_id") == channel_id:
                    log["status"] = "closed"
                    log["closed_at"] = datetime.utcnow().isoformat()
                    log["closed_by"] = str(interaction.user.id)
                    log["close_reason"] = reason
                    break
            
            # Save ticket data
            await update_guild_data(config.TICKETS_FILE, guild.id, ticket_data)
            
            # Get log channel if set
            log_channel_id = await get_server_setting(guild.id, "ticket_log_channel")
            log_channel = None
            
            if log_channel_id:
                log_channel = guild.get_channel(int(log_channel_id))
            
            # Create transcript and log if applicable
            if log_channel and log_channel.permissions_for(guild.me).send_messages:
                # Get messages from the channel (up to 100 for simplicity)
                messages = []
                async for message in channel.history(limit=100, oldest_first=True):
                    messages.append(message)
                
                # Create transcript embed
                transcript_embed = discord.Embed(
                    title=f"Ticket Transcript - {channel.name}",
                    description=f"Ticket closed by {interaction.user.mention}\n**Reason:** {reason}",
                    color=config.COLORS["INFO"],
                    timestamp=datetime.utcnow()
                )
                
                # Add user info if available
                ticket_user = guild.get_member(int(user_id))
                if ticket_user:
                    transcript_embed.set_author(name=f"{ticket_user}", icon_url=ticket_user.display_avatar.url)
                    transcript_embed.add_field(name="User", value=f"{ticket_user.mention} ({ticket_user.id})", inline=True)
                
                # Add metadata
                for log in ticket_data.get("ticket_logs", []):
                    if log.get("channel_id") == channel_id:
                        created_at = datetime.fromisoformat(log["created_at"])
                        transcript_embed.add_field(
                            name="Created",
                            value=f"<t:{int(created_at.timestamp())}:R>",
                            inline=True
                        )
                        
                        if "category" in log and log["category"]:
                            transcript_embed.add_field(
                                name="Category",
                                value=log["category"],
                                inline=True
                            )
                        
                        transcript_embed.add_field(
                            name="Ticket ID",
                            value=f"#{log.get('ticket_id', 'Unknown')}",
                            inline=True
                        )
                        break
                
                # Create transcript file
                transcript_text = f"Transcript of ticket {channel.name}\n"
                transcript_text += f"Created by: {ticket_user.name if ticket_user else 'Unknown'} ({user_id})\n"
                transcript_text += f"Closed by: {interaction.user.name} ({interaction.user.id})\n"
                transcript_text += f"Reason: {reason}\n\n"
                
                for msg in messages:
                    time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    transcript_text += f"[{time_str}] {msg.author.name}: {msg.content}\n"
                    
                    # Add attachments if any
                    for attachment in msg.attachments:
                        transcript_text += f"  Attachment: {attachment.url}\n"
                    
                    # Add embeds if any
                    for embed in msg.embeds:
                        transcript_text += f"  Embed: {embed.title or 'Untitled'}\n"
                
                # Save transcript to file
                transcript_file = discord.File(
                    fp=bytes(transcript_text, 'utf-8'),
                    filename=f"transcript-{channel.name}.txt"
                )
                
                # Send transcript to log channel
                await log_channel.send(embed=transcript_embed, file=transcript_file)
            
            # Wait a moment before deleting the channel
            await asyncio.sleep(3)
            
            # Delete the channel
            await channel.delete(reason=f"Ticket closed: {reason}")
            
        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            await interaction.followup.send(
                embed=error_embed("Error", f"An error occurred while closing the ticket: {e}")
            )
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        """Handle button interactions for tickets"""
        if not interaction.type == discord.InteractionType.component:
            return
            
        # Check if it's a ticket button
        custom_id = interaction.data.get("custom_id", "")
        
        if custom_id.startswith("ticket_close_"):
            # Close ticket button clicked
            ticket_id = custom_id.split("_")[2]
            
            # Get the modal for reason input
            modal = discord.ui.Modal(title="Close Ticket")
            
            reason_input = discord.ui.TextInput(
                label="Reason for closing the ticket",
                placeholder="Enter the reason for closing this ticket...",
                required=True,
                style=discord.TextStyle.paragraph
            )
            
            modal.add_item(reason_input)
            
            # Handle modal submission
            async def modal_callback(modal_interaction):
                reason = reason_input.value
                
                # Close the ticket with the provided reason
                ticket_data = await get_guild_data(config.TICKETS_FILE, interaction.guild.id)
                
                if "active_tickets" not in ticket_data:
                    await modal_interaction.response.send_message(
                        embed=error_embed("Error", "Ticket data not found."),
                        ephemeral=True
                    )
                    return
                
                # Find the user_id associated with this channel
                channel_id_str = str(interaction.channel.id)
                user_id = None
                
                for user, channel in ticket_data["active_tickets"].items():
                    if channel == channel_id_str:
                        user_id = user
                        break
                
                if not user_id:
                    await modal_interaction.response.send_message(
                        embed=error_embed("Not a Ticket", "This channel is not an active ticket."),
                        ephemeral=True
                    )
                    return
                
                # Close the ticket
                await self.close_ticket(modal_interaction, ticket_data, user_id, reason)
            
            modal.on_submit = modal_callback
            
            # Send the modal
            await interaction.response.send_modal(modal)
            
        elif custom_id.startswith("ticket_claim_"):
            # Claim ticket button clicked
            ticket_id = custom_id.split("_")[2]
            
            # Check if user can manage tickets
            if not await self.can_manage_tickets(interaction.user):
                await interaction.response.send_message(
                    embed=error_embed("Permission Denied", "You don't have permission to claim tickets."),
                    ephemeral=True
                )
                return
            
            # Claim the ticket
            await interaction.response.send_message(
                embed=success_embed(
                    title="Ticket Claimed",
                    description=f"{interaction.user.mention} has claimed this ticket and will assist you."
                )
            )
            
            # Update ticket data
            ticket_data = await get_guild_data(config.TICKETS_FILE, interaction.guild.id)
            
            # Find the ticket log for this channel
            channel_id_str = str(interaction.channel.id)
            
            for log in ticket_data.get("ticket_logs", []):
                if log.get("channel_id") == channel_id_str:
                    log["claimed_by"] = str(interaction.user.id)
                    log["claimed_at"] = datetime.utcnow().isoformat()
                    break
            
            # Save ticket data
            await update_guild_data(config.TICKETS_FILE, interaction.guild.id, ticket_data)
            
            # Edit channel permissions to add the claimer
            try:
                await interaction.channel.set_permissions(
                    interaction.user,
                    read_messages=True,
                    send_messages=True
                )
            except:
                # Not critical if this fails
                pass
    
    async def can_manage_tickets(self, user):
        """Check if a user can manage tickets"""
        # Server admins can always manage tickets
        if user.guild_permissions.administrator:
            return True
            
        # Check for support role
        support_role_id = await get_server_setting(user.guild.id, "ticket_support_role")
        if support_role_id:
            support_role = user.guild.get_role(int(support_role_id))
            if support_role and support_role in user.roles:
                return True
                
        return False

async def setup(bot):
    await bot.add_cog(Tickets(bot))
