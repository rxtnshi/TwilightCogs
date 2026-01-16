import discord
import aiosqlite
import re
import logging

from .error_handling import send_blocked, send_success
from .databases import TicketDB
from datetime import datetime
from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path

class tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.log = logging.getLogger("twilightcogs.tickets_rewrite")
        self.path = cog_data_path(self)
        self.db = TicketDB(self.path) # in case if need to make db entries/searches

        self.config = Config.get_conf(self, identifier=1, force_registration=True)
        default_guild = {
			"tickets_enabled": True,
			"ticket_roles": {
				"modmail_access": None,
				"modmail_mgmt": None,
				"appeals_access": None,
                "staff_roles": []
			},
			"ticket_channels": {
				"log_channel": None,
				"appeal_logs": None,
			},
			"panel_cfg": {
				"channel": None,
				"message_id": None,
			},
            "file_scans": {
                "vt_key": None,
                "enabled": False
            }
		}
        self.config.register_guild(**default_guild)

    async def staff_check(self, interaction):
        confg = self.config.guild(interaction.guild)
        ticket_roles = await confg.ticket_roles()
        modmail_access = ticket_roles["modmail_access"]
        modmail_mgmt = ticket_roles["modmail_mgmt"]

        check = {rid for rid in (modmail_access, modmail_mgmt) if rid}
        if not check:
            return False
        
        return any(role.id in check for role in interaction.user.roles)

    async def elevated_check(self, interaction):
        confg = self.config.guild(interaction.guild)
        ticket_roles = await confg.ticket_roles()
        modmail_mgmt = ticket_roles["modmail_mgmt"]

        if interaction.user.guild_permissions.administrator:
            return True
        
        if not modmail_mgmt:
            return False
        
        return any(role.id == modmail_mgmt for role in interaction.user.roles) 

    async def blacklist_check(self, interaction, user: discord.Member):
        return await TicketDB.existing_blacklist_check(self, user.id)

    staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)
    ticket = app_commands.Group(name="ticket", description="Ticket commands", guild_only=True)
    appeal = app_commands.Group(name="appeal", description="Appeal commands", guild_only=True)

    @staff.command(name="setup", description="Set up the ticket system for your server.")
    async def setup_tickets(self, interaction):
        if not await self.elevated_check(interaction):
            await send_blocked("You cannot run this command!", True)
            return
        
        await interaction.response.send_message("hello")
        
    @staff.command(name="register", description="Allows your staff to gain access to use the ticket system.")
    async def register_staff(self, interaction):
        pass

    @staff.command(name="deregister", description="Remove a staff member from being able to access the ticket system.")
    @app_commands.describe(member="The staff member you want to deregister from the system.")
    async def deregister_staff(self, interaction, member: discord.Member):
        pass

    @staff.command(name="blacklist", description="Blacklist server members from using the ticket system.")
    @app_commands.describe(member="The member you want to blacklist from using the ticket system.")
    async def blacklist_member(self, interaction, member: discord.Member):
        pass

    @staff.command(name="unblacklist", description="Remove server members from the blacklist.")
    @app_commands.describe(member="The member you want to unblacklist.")
    async def blacklist_member(self, interaction, member: discord.Member):
        pass

    @staff.command(name="panic", description="Enables/disables panic (ticket creation)")
    async def panic_mode(self, interaction):
        pass

    @ticket.command(name="close", description="Close a ticket channel or a specified channel")
    @app_commands.describe(ticket_id="The ticket you want to close.")
    async def close_ticket(self, interaction, ticket_id: str):
        pass

    @ticket.command(name="help", description="Display all commands and their usage.")
    async def commands_help(self, interaction):
        is_staff = False
        pass

    @appeal.command(name="status", description="Get the status of an appeal made with the ticket system.")
    @app_commands.describe(id="The appeal id given to you after an appeal has been made.")
    async def commands_help(self, interaction, id: str):
        pass