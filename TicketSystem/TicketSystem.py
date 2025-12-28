import discord
import sqlite3
import asyncio
import os
import re
import logging

from . import ViewsModals
from .Handling import send_blocked, send_error, send_success, send_warning
from datetime import datetime
from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path

""" 
TO-DO List:
	- Add comments to explain thought process
	- Rewrite history command to display all tickets rather than just 5
"""

class TicketSystem(commands.Cog):
	"""Ticketing system for the Twilight Zone"""

	def __init__(self, bot):
		self.bot = bot
		self.log = logging.getLogger("twilightcogs.tickets")

		# Setup Redbot config (guild config since I don't want these settings to be global)
		self.config = Config.get_conf(self, identifier=99204742, force_registration=True)
		default_guild = {
			"tickets_enabled": True,
			"ticket_statuses": {
				"discord": True,
				"scpsl": True,
				"appeals": True,
				"staffping": True,
			},
			"ticket_roles": {
				"modmail_access": None,
				"modmail_mgmt": None,
				"appeal_team": None,
				"discord_staff": None,
				"game_staff": None
			},
			"ticket_categories": {
				"discord": None,
				"scpsl": None,
			},
			"ticket_channels": {
				"log_channel": None,
				"appeal_logs": None,
			},
			"panel_cfg": {
				"channel": None,
				"message_id": None,
			}
			#"modmail_access_role": None,
			#"management_access_role": None,
			#"appeal_team_role": None,
			#"ticket_log_channel": None,
			#"appeal_log_channel": None,
			#"panel_channel": None,
			#"panel_message_id": None,
			# "discord_staff_role": None,
			# "scpsl_staff_role": None
		}
		self.config.register_guild(**default_guild)

		# Temporarily assign the self values and then have Config load it later on
		self.tickets_enabled = True
		self.ticket_statuses = {
			"discord": True,
			"scpsl": True,
			"appeals": True,
			"staffping": True,
		}
		self.ticket_categories = {
			"discord": None,
			"scpsl": None,
		}
		self.ticket_roles = {
			"modmail_access": None,
			"modmail_mgmt": None,
			"appeal_team": None,
			"discord_staff": None,
			"game_staff": None,
		}

		self.panel_cfg = {
			"channel": None,
			"message_id": None,
		}
		# self.modmail_access_role = None
		# self.management_access_role = None
		# self.appeal_team_role = None
		# self.discord_staff_team_role = None
		# self.scpsl_staff_team_role = None
		# self.ticket_log_channel = None
		# self.appeal_log_channel = None
		# self.panel_channel = None
		# self.panel_message_id = None

		# DB setup
		db_path = cog_data_path(self) / "tickets.db"
		os.makedirs(os.path.dirname(db_path), exist_ok=True)

		self.conn = sqlite3.connect(db_path)
		self.cursor = self.conn.cursor()
		self.setup_db()

	def setup_db(self):
		"""Creates DB for stats, history, whatnot"""
		self.cursor.execute("""
			CREATE TABLE IF NOT EXISTS tickets (
				ticket_id TEXT PRIMARY KEY,
				channel_id INTEGER NOT NULL,
				opener_id INTEGER NOT NULL,
				closer_id INTEGER,
				open_time TEXT NOT NULL,
				close_time TEXT,
				log_message_id INTEGER,
				ticket_type TEXT,
				close_reason TEXT
			)
		""")
		
		self.cursor.execute("""
			CREATE TABLE IF NOT EXISTS blacklist (
				user_id INTEGER PRIMARY KEY,
				reason TEXT,
				staff_id INTEGER NOT NULL,
				timestamp TEXT NOT NULL
			)
		""")

		self.cursor.execute("""
			CREATE TABLE IF NOT EXISTS appeals (
				appeal_id TEXT PRIMARY KEY,
				user_id INTEGER NOT NULL,
				ban_platform TEXT,
				ban_appeal_reason TEXT,
				appeal_status TEXT NOT NULL,
				timestamp TEXT NOT NULL
			)
		""")

	def cog_unload(self):
		"""Close the local database connection once this cog unloads"""
		self.conn.close()

	# Bool function to check for standard level access to the system
	async def has_staff(self, interaction: discord.Interaction):
		sconfg = self.config.guild(interaction.guild)

		roles = await sconfg.ticket_roles()
		staff_role = roles.get("modmail_access")
		mgmt_role = roles.get("modmail_mgmt")

		check = {rid for rid in (staff_role, mgmt_role) if rid}
		if not check:
			return False

		user_role_ids = {r.id for r in interaction.user.roles}
		return not user_role_ids.isdisjoint(check)
	
	# Bool function to check for elevated level access to the system
	async def has_management(self, interaction: discord.Interaction):
		sconfg = self.config.guild(interaction.guild)
		
		roles = await sconfg.ticket_roles()
		role_id = roles.get("modmail_mgmt")

		if interaction.user.guild_permissions.administrator:
			return True
		
		return bool(role_id and any(r.id == role_id for r in interaction.user.roles))
	
	# Bool function to check if a user is a protected user (ticket staff or management or has administrator permission enabled)
	async def check_protected_status(self, guild: discord.Guild, member: discord.Member) -> bool:
		if member.guild_permissions.administrator:
			return True
		sconfg = self.config.guild(guild)
		roles = await sconfg.ticket_roles()
		protected_role_ids =[
			roles.get("modmail_access"),
			roles.get("modmail_mgmt"),
			roles.get("discord_staff"),
			roles.get("game_staff")
		]
		role_ids = [rid for rid in protected_role_ids if rid]
		return any(r.id in role_ids for r in member.roles)
	
	async def get_setup_embed(self, guild: discord.Guild):
		# Helper for channels/roles
		def format_mention(item_id, item_type):
			if not item_id: return "`Not Set`"
			if item_type == "role": return f"<@&{item_id}>"
			if item_type == "channel": return f"<#{item_id}>"
			return f"`{item_id}`"
		
		# Get the server config and assign the necessary values
		sconfg = self.config.guild(guild)
		roles = await sconfg.ticket_roles()
		channels = await sconfg.ticket_channels()
		panel = await sconfg.panel_cfg()
		categories = await sconfg.ticket_categories()

		# Get IDs
		modmail_access_role = roles.get("modmail_access")
		management_role_id = roles.get("modmail_mgmt")
		appeal_team_role_id = roles.get("appeal_team")
		discord_staff_role_id = roles.get("discord_staff")
		game_staff_role_id = roles.get("game_staff")

		panel_channel_id = panel.get("channel")
		ticket_log_channel_id = channels.get("log_channel")
		appeal_log_channel_id = channels.get("appeal_logs")

		# Gather into list!
		channel_list = [panel_channel_id, ticket_log_channel_id, appeal_log_channel_id]		
		role_list = [modmail_access_role, management_role_id, appeal_team_role_id, discord_staff_role_id, game_staff_role_id]
		
		# Embeds and whatnot
		setup_embed = discord.Embed(
			title="⚙️ Ticket System Setup",
			description="You are currently setting up your panel. To see your current settings, please run `/staff settings`.",
			color=discord.Color.blurple(),
			timestamp=datetime.now()
		)

		is_setup = False
		if all(not item for item in channel_list and role_list):
			is_setup = False
		else:
			is_setup = True
		
		setup_embed_status = "`✅ System Configured`" if is_setup else "`❌ Not Configured`"
		setup_embed.add_field(name="Setup Status", value=setup_embed_status)

		roles_text = (
			f"Staff Access: {format_mention(modmail_access_role, 'role')}\n"
			f"Management Access: {format_mention(management_role_id, 'role')}\n"
			f"Appeals: {format_mention(appeal_team_role_id, 'role')}\n"
			f"Discord Staff: {format_mention(discord_staff_role_id, 'role')}\n"
			f"SCP:SL Staff: {format_mention(game_staff_role_id, 'role')}"
		)
		setup_embed.add_field(name="Role Configuration", value=roles_text, inline=False)

		discord_cat_id = categories.get("discord")
		scpsl_cat_id = categories.get("scpsl")
		channels_text = (
			f"Ticket Logs: {format_mention(ticket_log_channel_id, 'channel')}\n"
			f"Appeal Logs: {format_mention(appeal_log_channel_id, 'channel')}\n"
			f"Panel Channel: {format_mention(panel_channel_id, 'channel')}\n"
			f"Discord Ticket Category: {format_mention(discord_cat_id, 'channel')}\n"
			f"SCP:SL Ticket Category: {format_mention(scpsl_cat_id, 'channel')}"
		)
		setup_embed.add_field(name="Channel & Category Configuration", value=channels_text, inline=False)

		return setup_embed

	# Assign the command groups so I don't have to make several disorganized commands
	staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)
	appeals = app_commands.Group(name="appeals", description="Appeal commands", guild_only=True)
		
	@staff.command(name="setup", description="Starts the setup process for the ticketing system. Sends the panel if setup has been done.")
	async def setup_tool(self, interaction: discord.Interaction):
		# Permission check
		if not await self.has_management(interaction):
			await send_blocked(interaction, "You need Administrator or the configured management role.", True)
			return
		
		setup_embed = await self.get_setup_embed(interaction.guild)

		view = ViewsModals.SetupView(interaction.user)
		await interaction.response.send_message(view=view, embed=setup_embed)
		view.message = await interaction.original_response()

	@staff.command(name="panic", description="Enables or disables panic mode")
	async def panic(self, interaction: discord.Interaction):
		"""This will set the status for overall ticket creation."""
		allowed = await self.has_management(interaction)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		 
		sconfg = self.config.guild(interaction.guild)
		current = await sconfg.tickets_enabled()
		new = not current
		await sconfg.tickets_enabled.set(new)
		await send_success(interaction, f"Ticket creation is now {'enabled' if new else 'disabled'}.")

	@staff.command(name="set", description="Enable/disable a specific ticket type or ticket pings")
	@app_commands.choices(
		option=[
			app_commands.Choice(name="Discord Tickets", value="discord"),
			app_commands.Choice(name="SCP:SL Tickets", value="scpsl"),
			app_commands.Choice(name="Ban Appeals", value="appeals"),
			app_commands.Choice(name="Staff Pings", value="staffping")
		],
		status=[
			app_commands.Choice(name="Enable", value="enable"),
			app_commands.Choice(name="Disable", value="disable")
		]
	)
	async def enable_disable_type(self, interaction: discord.Interaction, option: str, status: str):
		"""This will enable or disable specific ticket categories as an alternative to panic mode."""
		allowed = await self.has_management(interaction)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		 
		sconfg = self.config.guild(interaction.guild)
		ticket_statuses = await sconfg.ticket_statuses()
		ticket_statuses[option] = (status == "enable")

		await sconfg.ticket_statuses.set(ticket_statuses)
		if option == "staffping":
			await send_success(interaction, f"Staff pings have been {status}d.")
		else:
			await send_success(interaction, f"{option.capitalize()} tickets have been {status}d.")

	@staff.command(name="blacklist", description="Blacklists a user")
	async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, reason: str):
		"""Blacklists a user from the ticket system if they're misusing the system"""
		allowed = await self.has_management(interaction)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		 

		if await self.check_protected_status(interaction.guild, user):
			await send_blocked(interaction, "This is a protected user.", True)
			return
		
		try:
			self.cursor.execute("""
				INSERT INTO blacklist(user_id, reason, staff_id, timestamp)
				VALUES(?, ?, ?, ?)
			""", (user.id, reason, interaction.user.id, datetime.now().isoformat()))
			self.conn.commit()
			await send_success(interaction, f"{user.mention} has been successfully blacklisted. **Reason:** {reason}")
		except sqlite3.IntegrityError:
			await send_error(interaction, f"{user.mention} has already been blacklisted.")
	
	@staff.command(name="unblacklist", description="Removes a user from the blacklist")
	async def unblacklist_user(self, interaction: discord.Interaction, user: discord.Member):
		"""Removes a user from the blacklist."""
		allowed = await self.has_management(interaction)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		 
		
		self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user.id,))
		if self.cursor.rowcount > 0:
			self.conn.commit()
			await send_success(interaction, f"{user.mention} has been successfully removed from the blacklist!")
		else:
			await send_error(interaction, f"{user.mention} was not found in the blacklist.")

	@staff.command(name="history", description="Grabs the ticket history of a user")
	async def ticket_history(self, interaction: discord.Interaction, user: discord.Member):
		"""Get the ticket history for a user"""
		allowed = await self.has_staff(interaction)
		sconfg = self.config.guild(interaction.guild)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		 
		# Get the history for local DB
		self.cursor.execute(
			"SELECT ticket_id, closer_id, open_time, close_time, log_message_id FROM tickets WHERE opener_id = ? ORDER BY open_time DESC",
			(user.id,)
		)
		tickets = self.cursor.fetchall()

		# If no history is found, then this would be sent
		if not tickets:
			no_history_embed = discord.Embed(
				title=f"📋 Ticket History for {user.display_name}",
				description=f"No ticket history found for {user.mention}.",
				color=0x808080
			)
			no_history_embed.set_thumbnail(url=user.display_avatar.url)
			await interaction.response.send_message(embed=no_history_embed)
			return
		
		channels = await sconfg.ticket_channels()
		logs_channel_id = channels.get("log_channel")

		history_embed = discord.Embed(
				title=f"📋 Ticket History for {user.display_name}",
				color=0x808080,
				timestamp=datetime.now()
			)
		history_embed.set_thumbnail(url=user.display_avatar.url)

		history_text = ""
		for ticket in tickets[:5]:
			ticket_id, closer_id, open_time_str, close_time_str, log_message_id = ticket
			
			open_dt = datetime.fromisoformat(open_time_str)
			open_ts = f"<t:{int(open_dt.timestamp())}:f>"

			ticket_line = f"**Ticket ID:** `{ticket_id}`\n"
			status_line = f"Status: `Open`\n"

			if close_time_str:
				close_dt = datetime.fromisoformat(close_time_str)
				close_ts = f"<t:{int(close_dt.timestamp())}:f>"
				closer = interaction.guild.get_member(closer_id) or f"ID: {closer_id}"
				status_line = f"Status: `Closed`\nClosed at: {close_ts} by {closer.mention}\n"

				if log_message_id:
					log_link = f"https://discord.com/channels/{interaction.guild.id}/{logs_channel_id}/{log_message_id}"
					ticket_line = f"**Ticket ID:** [`{ticket_id}`]({log_link})\n"

			history_text += (
				f"{ticket_line}"
				f"Opened: {open_ts}\n"
				f"{status_line}"
				f"---\n"
			)
		
		history_embed.description = history_text
		history_embed.set_footer(text=f"Displaying the last 5 tickets made")

		await interaction.response.send_message(embed=history_embed)

	@staff.command(name="commands", description="Display all commands for the ticket system")
	async def help_menu(self, interaction: discord.Interaction):
		"""
		Show all commands for the ticket system
		"""
		allowed = self.has_staff(interaction)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		
		embed = discord.Embed(
			description="Here is a list of all commands used for the ticket system! Keep in mind these are all slash commands.",
			timestamp=datetime.now(),
			color=discord.Color.orange()
		)
		staff_group = ""
		staff_group += (
			"`setup`: Starts the setup process for TicketSystem.\n\n"
			"`register`: Registers access to the ticket system. Users with Administrator privileges will gain elevated access to the ticket system.\n\n"
			"`blacklist <user> <reason>`: Blacklists a user from the ticketing system.\n\n"
			"`unblacklist <user> <reason>`: Removes a user the blacklist.\n\n"
			"`panic`: Enables or disables ticket creation.\n\n"
			"`set <ticket_type_or_pings> <status>`: Enables or disables a specific ticket type or staff pings in tickets.\n\n"
			"`settings`: Displays all ticket statuses.\n\n"
			"`history <user>`: Gets the ticket history for a user. Currently, the last 5 tickets are displayed.\n\n"
			"`list`: Gets the list of all ticket staff\n\n"
		)
		appeal_group = ""
		appeal_group += (
			"`status <appeal_id>`: Gets the appeal status for an appeal. This command is open to everyone as long they have an appeal id."
		)

		embed.add_field(name="/staff", value=staff_group, inline=False)
		embed.add_field(name="/appeal", value=appeal_group, inline=False)

		await interaction.response.send_message(embed=embed)

	@staff.command(name="statuses", description="Display ticket statuses")
	async def get_type_status(self, interaction: discord.Interaction):
		"""
		Renamed to statuses command. Settings moved to setup command.
		"""
		allowed = await self.has_management(interaction)

		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		
		sconfg = self.config.guild(interaction.guild)

		tickets_enabled = await sconfg.tickets_enabled()
		ticket_statuses = await sconfg.ticket_statuses()

		embed = discord.Embed(
			title="⚙️ Current Ticket Statuses",
			description="Showing all ticket statuses.",
			timestamp=datetime.now(),
			color=discord.Color.blue()
		)

		embed.add_field(
			name="Overall Ticket Creation",
			value=f"The below categories will not matter if this is disabled.\n{'`✅ Enabled`' if tickets_enabled else '`🚫 Disabled`'}",
			inline=False
		)
		name_map = {
			"discord": "Discord Tickets", 
			"scpsl": "SCP:SL Tickets", 
			"appeals": "Appeals", 
			"staffping": "Staff Ping in Tickets"
		}
		lines = []
		for key, enabled in ticket_statuses.items():
			emoji = "✅" if enabled else "🚫"
			lines.append(f"{name_map.get(key, key.capitalize())}: `{emoji} {'Enabled' if enabled else 'Disabled'}`")

		embed.add_field(name="Ticket Categories", value="\n".join(lines) or "`Not Set`", inline=False)

		await interaction.response.send_message(embed=embed)

	@staff.command(name="register", description="Registers access to the ticket system")
	async def register_access(self, interaction: discord.Interaction):
		"""
		Lets users with the staff roles register themselves to the ticket system for access
		"""
		sconfg = self.config.guild(interaction.guild)
		user = interaction.user
		roles = await sconfg.ticket_roles()

		discord_staff_id = roles.get("discord_staff")
		scpsl_staff_id = roles.get("game_staff")
		modmail_access_id = roles.get("modmail_access")
		mgmt_access_id = roles.get("modmail_mgmt")

		modmail_access_role = interaction.guild.get_role(modmail_access_id)
		mgmt_access_role = interaction.guild.get_role(mgmt_access_id)

		staff_role_ids = {rid for rid in (discord_staff_id, scpsl_staff_id) if rid}
		access_roles = {rid for rid in (modmail_access_id, mgmt_access_id) if rid}
		
		check_staff = bool(staff_role_ids and any(r.id in staff_role_ids for r in user.roles))
		check_modmail = bool(access_roles and any(r.id in access_roles for r in user.roles))


		if not check_staff:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return
		
		if check_modmail:
			await send_blocked(interaction, "You already have access to the ticket system.", True)
			return
		
		try:
			if user.guild_permissions.administrator:
				if check_modmail:
					await send_blocked(interaction, "You already have access to the ticket system.", True)
					return
				await user.add_roles(mgmt_access_role, reason="Registered user to ticket staff team")
				await send_success(interaction, f"You were successfully registered. Assigned {mgmt_access_role.mention} to you since you have Administrator privileges in this server.", True)
				return
			
			await user.add_roles(modmail_access_role, reason="Registered user to ticket staff team")
			await send_success(interaction, f"You were successfully registered. Assigned {modmail_access_role.mention} to you. If you are a server administrator that needs management level access, you may add {mgmt_access_role.mention} manually.", True)
		except Exception as e:
			await send_error(interaction, f"Unable to register properly: `{e}`")
	
	@staff.command(name="list", description="Gets a list of all ticket system staff that are registered")
	async def get_ticket_staff_list(self, interaction: discord.Interaction):
		"""
		Get list of all staff registered to the ticket system
		"""
		allowed = await self.has_management(interaction)
		if not allowed:
			await send_blocked(interaction, "You do not have permission to run this command.", True)
			return

		guild = interaction.guild
		sconfg = self.config.guild(guild)
		roles = await sconfg.ticket_roles()
		allowed = await self.has_staff(interaction) or await self.has_management(interaction)

		modmail_id = roles.get("modmail_access")
		mgmt_id = roles.get("modmail_mgmt")

		mgmt_role = guild.get_role(mgmt_id) if mgmt_id else None
		modmail_role = guild.get_role(modmail_id) if modmail_id else None

		mgmt_members = mgmt_role.members if mgmt_role else []
		modmail_members = modmail_role.members if modmail_role else []

		mgmt_team = "\n".join(m.mention for m in mgmt_members) or "`No staff`"
		modmail_team = "\n".join(m.mention for m in modmail_members) or "`No staff`"

		embed = discord.Embed(
			title="🛠️ Ticket System Staff",
			description="Here is a list of all staff with ticket system access!",
			color=discord.Color.blue(),
			timestamp=datetime.now()
		)
		embed.add_field(name="Ticket Management", value=mgmt_team, inline=False)
		embed.add_field(name="Ticket Staff", value=modmail_team, inline=False)

		await interaction.response.send_message(embed=embed)

	@appeals.command(name="status", description="Gets the status of an appeal")
	async def get_status_appeal(self, interaction: discord.Interaction, appeal_id: str):
		"""
		If a user has an appeal id, they can check it via this command. Set to ephemeral to protect user privacy.
		"""
		# Get appeal status based on appeal id and discord user id
		self.cursor.execute("SELECT appeal_status, timestamp, user_id, ban_appeal_reason FROM appeals WHERE appeal_id = ?", (appeal_id,))
		result = self.cursor.fetchone()

		if not result:
			await send_error(interaction, f"There was no appeal matching ID: `{appeal_id}`. Please try again with a valid appeal ID.", True)
			return
		
		# Hopefully it assigns the correct values if I'm doing it correctly
		appeal_status, timestamp_str, user_id, appeal_reason = result
		
		# Check status?
		if appeal_status == "pending":
			color = 0xffa500
			status_text = "📥 Appeal Received"
		elif appeal_status == "accepted":
			color = discord.Color.green()
			status_text = "✅ Appeal Accepted"
		else:
			color = discord.Color.red()
			status_text = "🚫 Appeal Rejected"

		time_sent = datetime.fromisoformat(timestamp_str)
		time_sent_ts = f"<t:{int(time_sent.timestamp())}:f>"

		# Create the base embed
		appeal_stat_embed = discord.Embed(
			title=f"Status for Appeal `{appeal_id}`",
			description=f"Appeal made by <@{user_id}>",
			timestamp=datetime.now(),
			color=color
		)

		appeal_stat_embed.add_field(name="Status", value=status_text, inline=False)
		appeal_stat_embed.add_field(name="Time Sent", value=time_sent_ts, inline=False)
		appeal_stat_embed.add_field(name="Appeal Reason", value=appeal_reason, inline=False)

		await interaction.response.send_message(embed=appeal_stat_embed, ephemeral=True)