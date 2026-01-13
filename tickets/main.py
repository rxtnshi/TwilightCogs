import discord
import aiosqlite
import re
import logging

from .databases import TicketDB
from datetime import datetime
from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path

class tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.log = logging.getLogger("twilightcogs.tickets_rewrite")
        self.path = cog_data_path(self)
        self.db = TicketDB(self.path)

        self.config = Config.get_conf(self, identifier=1, force_registration=True)
        default_guild = {
			"tickets_enabled": True,
			"ticket_roles": {
				"modmail_access": None,
				"modmail_mgmt": None,
				"appeals_access": None,
			},
			"ticket_channels": {
				"log_channel": None,
				"appeal_logs": None,
			},
			"panel_cfg": {
				"channel": None,
				"message_id": None,
			}
		}
        self.config.register_guild(**default_guild)

    async def staff_check(self, interaction):
        pass

    async def elevated_check(self, interaction):
        pass

    async def blacklist_check(self, interaction):
        pass

    ticket = app_commands.Group(name="ticket", description="Ticket commands", guild_only=True)
    staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)
    appeal = app_commands.Group(name="appeal", description="Appeal commands", guild_only=True)

    