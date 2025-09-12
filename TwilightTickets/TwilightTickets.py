import discord
import sqlite3
import asyncio
import os
from . import ViewsModals
from datetime import datetime
from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path

class TwilightTickets(commands.Cog):
	"""Ticketing system for the Twilight Zone"""

	def __init__(self, bot):
		self.bot = bot		

		self.config = Config.get_conf(self, identifier=99204742, force_registration=True)
		default_guild = {
			"tickets_enabled": True,
			"ticket_statuses": {
				"discord": True,
				"scpsl": True,
				"appeals": True,
				"staffping": True
			},
			"modmail_access_role": None,
			"management_access_role": None,
			"appeal_team_role": None,
			"ticket_log_channel": None,
			"appeal_log_channel": None,
			"panel_channel": None,
			"panel_message_id": None,
			"ticket_categories": {
				"discord": None,
				"scpsl": None,
			},
			"discord_staff_role": None,
			"scpsl_staff_role": None
		}
		self.config.register_guild(**default_guild)

		self.tickets_enabled = True
		self.ticket_statuses = {
			"discord": True,
			"scpsl": True,
			"appeals": True,
			"staffping": True
		}
		self.modmail_access_role = None
		self.management_access_role = None
		self.appeal_team_role = None
		self.discord_staff_team_role = None
		self.scpsl_staff_team_role = None
		self.ticket_log_channel = None
		self.appeal_log_channel = None
		self.panel_channel = None
		self.panel_message_id = None
		self.ticket_categories = {
			"discord": None,
			"scpsl": None,
		}

		self.settings_loaded = False

		db_path = cog_data_path(self) / "tickets.db"
		os.makedirs(os.path.dirname(db_path), exist_ok=True)

		self.conn = sqlite3.connect(db_path)
		self.cursor = self.conn.cursor()
		self.setup_db()

	def role_check(self, member: discord.Member):
		if not self.modmail_access_role:
			return False
		return any(role.id == self.modmail_access_role for role in member.roles)
	
	def role_check_elevated(self, member: discord.Member):
		if not self.management_access_role:
			return False
		return any(role.id == self.management_access_role for role in member.roles)

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
				ban_appeal_reason TEXT,
				appeal_status TEXT NOT NULL,
				timestamp TEXT NOT NULL
			)
		""")
	def cog_unload(self):
		self.conn.close()

	async def has_staff(self, interaction: discord.Interaction) -> bool:
		role_id = await self.config.guild(interaction.guild).modmail_access_role()
		return bool(role_id and any(r.id == role_id for r in interaction.user.roles))
	
	async def has_management(self, interaction: discord.Interaction) -> bool:
		role_id = await self.config.guild(interaction.guild).management_access_role()
		return bool(role_id and any(r.id == role_id for r in interaction.user.roles))
	
	async def check_protected_status(self, guild: discord.Guild, member: discord.Member) -> bool:
		if member.guild_permissions.administrator:
			return True
		sconfg = self.config.guild(guild)
		protected_role_ids =[
			await sconfg.modmail_access_role(),
			await sconfg.management_access_role(),
			await sconfg.discord_staff_role(),
			await sconfg.scpsl_staff_role()
		]
		role_ids = [rid for rid in protected_role_ids if rid]
		return any(r.id in role_ids for r in member.roles)

	staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)
	appeals = app_commands.Group(name="appeals", description="Appeal commands", guild_only=True)
		
	@staff.command(name="initiate", description="Starts the setup process for the ticketing system. Sends the panel if setup has been done.")
	async def setup_tool(self, interaction: discord.Interaction, refresh_panel: bool = False, reset: bool = False):
		if not (interaction.user.guild_permissions.administrator or await self.has_management(interaction)):
			await interaction.response.send_message("**`🚫 Prohibited!`** You need Administrator or the configured management role.", ephemeral=True)
			return
		
		if not interaction.response.is_done():
			await interaction.response.defer()

		sconfg = self.config.guild(interaction.guild)
		ticket_log_ch = await sconfg.ticket_log_channel()
		panel_channel_id = await sconfg.panel_channel()
		panel_message_id = await sconfg.panel_message_id()

		def make_embed():
			embed = discord.Embed(
			title=f"{interaction.guild.name} Support & Reports",
			description="Need to contact staff? Select a category below.",
			timestamp=datetime.now(),
			color=0x7a2db9
		)
			embed.add_field(name="👮 Discord Staff", value="Report users or general inquiries", inline=False)
			embed.add_field(name="🎮 SCP:SL Staff", value="Report users or general inquiries", inline=False)
			embed.add_field(name="🔨 Appeals Requests", value="Appeal Discord or SCP:SL punishments", inline=False)
			embed.set_thumbnail(url="https://images.steamusercontent.com/ugc/961973556172351165/A41A548899E427C540698909FF523F4E7558EBAF/?imw=5000")

			return embed
		
		embed = make_embed()
		panel_ch = interaction.guild.get_channel(panel_channel_id) if panel_channel_id else None

		# Resend panel method
		if refresh_panel and not reset:
			if (ticket_log_ch and panel_channel_id):
				if panel_message_id:
					try:
						msg = await panel_ch.fetch_message(panel_message_id)
						await msg.edit(embed=embed, view=ViewsModals.TicketView())
						await interaction.followup.send("**`✅ Success!`**: Panel refreshed.")
						return
					except Exception:
						pass
				new_msg = await panel_ch.send(embed=embed, view=ViewsModals.TicketView())
				await sconfg.panel_message_id.set(new_msg.id)
				panel_ch = interaction.guild.get_channel(panel_channel_id)
				await interaction.followup.send("**`✅ Success!`**: Panel was deleted so it was resent.")
				return
			# Check if setup was configured
			if not (ticket_log_ch and panel_channel_id):
				await interaction.followup.send("**`⚠️ Error`**: Setup incomplete. Please re-run `/staff initiate reset:true` to reconfigure the ticket system.")
				return
			if not panel_ch:
				await interaction.followup.send("**`⚠️ Error`**: Panel channel no longer exists. Please re-run `/staff initiate reset:true` to reconfigure the ticket system.")
				return
			
		if reset and not refresh_panel:
			pass

		# If ticket system configured and not resetting?
		if ticket_log_ch and not reset:
			location = "`Not Set`"
			if panel_channel_id:
				channel = interaction.guild.get_channel(panel_channel_id)
				location = channel.mention if channel else "`Deleted Channel (No Longer Exists)`"
			await interaction.followup.send(f"**`⚠️ Warning`**: Panel found in {location}. Please run `/staff initiate refresh_panel:true` to resend/refresh the panel.")
			return
		
		# Start the interactive setup process
		await interaction.followup.send("**`⚙️ First Time Setup`**: Hello! Please answer the following questions in order to start the ticket system!")

		async def ask_for(item_type: str, prompt: str):
			await interaction.followup.send(prompt)
			while True:
				try:
					def check(m): return m.author == interaction.user and m.channel == interaction.channel
					msg = await self.bot.wait_for("message", check=check, timeout=180.0)

					if item_type in ("channel", "category"):
						if not msg.channel_mentions:
							await interaction.followup.send(f"**`⚠️ Invalid`** No {item_type} mentioned. Try again.")
							continue
						ref = msg.channel_mentions[0]
						if item_type == "channel" and not isinstance(ref, discord.TextChannel):
							await interaction.followup.send("**`⚠️ Invalid`** Not a text channel. Try again.")
							continue
						if item_type == "category" and not isinstance(ref, discord.CategoryChannel):
							await interaction.followup.send("**`⚠️ Invalid`** Not a category. Try again.")
							continue
						return ref
					elif item_type == "role":
						if not msg.role_mentions:
							await interaction.followup.send("**`⚠️ Invalid`** No role mentioned. Try again.")
							continue
						return msg.role_mentions[0]
					elif item_type == "question":
						answer = msg.content.strip().lower()
						if answer in ("yes"):
							return True
						if answer in ("no"):
							return False
						await interaction.followup.send("**`⚠️ Invalid`** Must be `yes` or `no`. Try again.")
				except asyncio.TimeoutError:
					await interaction.followup.send("**`🛑 Canceled`** Timed out.")
					return None

		# Questions
		if not await ask_for("question", "Before continuing, do you wish to continue? Type `'yes'` or `'no'`."):
			await interaction.followup.send("**`🛑 Canceled`** Setup process canceled. Rerun `/staff initiate` if you wish to start over.")
			return
		
		ticket_log_channel = await ask_for("channel", "**`Q1/10`**: Where should ticket logs (transcripts) go?")
		if not ticket_log_channel: return
		appeal_log_channel = await ask_for("channel", "**`Q2/10`**: Where should appeal logs go?")
		if not appeal_log_channel: return
		discord_category = await ask_for("category", "**`Q3/10`**: Category for Discord tickets?")
		if not discord_category: return
		scpsl_category = await ask_for("category", "**`Q4/10`**: Category for SCP:SL tickets?")
		if not scpsl_category: return
		staff_access = await ask_for("role", "**`Q5/10`**: Staff access role?")
		if not staff_access: return
		management_access = await ask_for("role", "**`Q6/10`**: Management role?")
		if not management_access: return
		discord_staff = await ask_for("role", "**`Q7/10`**: Discord staff ping role?")
		if not discord_staff: return
		scpsl_staff = await ask_for("role", "**`Q8/10`**: SCP:SL staff ping role?")
		if not scpsl_staff: return
		appeal_staff = await ask_for("role", "**`Q9/10`**: Appeal team role?")
		if not appeal_staff: return
		panel_channel = await ask_for("channel", "**`Q10/10`**: Channel to post the ticket panel?")
		if not panel_channel: return

		# Save to Config (persists across reloads)
		await sconfg.ticket_log_channel.set(ticket_log_channel.id)
		await sconfg.appeal_log_channel.set(appeal_log_channel.id)
		await sconfg.ticket_categories.set({"discord": discord_category.id, "scpsl": scpsl_category.id})
		await sconfg.modmail_access_role.set(staff_access.id)
		await sconfg.management_access_role.set(management_access.id)
		await sconfg.discord_staff_role.set(discord_staff.id)
		await sconfg.scpsl_staff_role.set(scpsl_staff.id)
		await sconfg.appeal_team_role.set(appeal_staff.id)
		await sconfg.panel_channel.set(panel_channel.id)

		await panel_channel.send(embed=embed, view=ViewsModals.TicketView())
		await interaction.followup.send(f"**`✅ Success!`**: Panel sent to {panel_channel.mention}.")

	@staff.command(name="panic", description="Enables or disables panic mode")
	async def panic(self, interaction: discord.Interaction):
		allowed = (
			await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		 
		sconfg = self.config.guild(interaction.guild)
		current = await sconfg.tickets_enabled()
		new = not current
		await sconfg.tickets_enabled.set(new)
		await interaction.response.send_message(f"**`✅ Success!`**: Ticket creation is now {'enabled' if new else 'disabled'}.")

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
		allowed = (
			await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		 
		sconfg = self.config.guild(interaction.guild)
		ticket_statuses = await sconfg.ticket_statuses()
		ticket_statuses[option] = (status == "enable")
		await sconfg.ticket_statuses.set(ticket_statuses)
		if option == "staffping":
			await interaction.response.send_message(f"**`✅ Success!`**: Staff pings have been {status}d.")
		else:
			await interaction.response.send_message(f"**`✅ Success!`**: {option.capitalize()} tickets have been {status}d.")

	@staff.command(name="blacklist", description="Blacklists a user")
	async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, reason: str):
		allowed = (
			await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		 

		if await self.check_protected_status(interaction.guild, user):
			await interaction.response.send_message("**`🚫 Prohibited!`** This is a protected user. You cannot blacklist them.")
			return
		
		try:
			self.cursor.execute("""
				INSERT INTO blacklist(user_id, reason, staff_id, timestamp)
				VALUES(?, ?, ?, ?)
			""", (user.id, reason, interaction.user.id, datetime.now().isoformat()))
			self.conn.commit()
			await interaction.response.send_message(f"**`✅ Success!`**: {user.mention} has been successfully blacklisted. **Reason:** {reason}")
		except sqlite3.IntegrityError:
			await interaction.response.send_message(f"**`⚠️ Error!`** {user.mention} has already been blacklisted.")
			return
	
	@staff.command(name="unblacklist", description="Removes a user from the blacklist")
	async def unblacklist_user(self, interaction: discord.Interaction, user: discord.Member):
		allowed = (
			await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		 
		
		self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user.id,))
		if self.cursor.rowcount > 0:
			self.conn.commit()
			await interaction.response.send_message(f"**`✅ Success!`**: {user.mention} has been successfully removed from the blacklist!")
		else:
			await interaction.response.send_message(f"**`⚠️ Error!`** {user.mention} was not found in the blacklist.")

	@staff.command(name="history", description="Grabs the ticket history of a user")
	async def ticket_history(self, interaction: discord.Interaction, user: discord.Member):
		allowed = (
			await self.has_staff(interaction)
			or await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		 

		self.cursor.execute(
			"SELECT ticket_id, closer_id, open_time, close_time, log_message_id FROM tickets WHERE opener_id = ? ORDER BY open_time DESC",
			(user.id,)
		)
		tickets = self.cursor.fetchall()

		if not tickets:
			no_history_embed = discord.Embed(
				title=f"📋 Ticket History for {user.display_name}",
				description=f"No ticket history found for {user.mention}.",
				color=0x808080
			)
			no_history_embed.set_thumbnail(url=user.display_avatar.url)
			await interaction.response.send_message(embed=no_history_embed)
			return
		
		logs_channel_id = await self.config.guild(interaction.guild).ticket_log_channel()

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
			status_line = f"**Status:** Open\n"

			if close_time_str:
				close_dt = datetime.fromisoformat(close_time_str)
				close_ts = f"<t:{int(close_dt.timestamp())}:f>"
				closer = interaction.guild.get_member(closer_id) or f"ID: {closer_id}"
				status_line = f"**Status:** Closed\n**Closed at:** {close_ts} by {closer.mention}\n"

				if log_message_id:
					log_link = f"https://discord.com/channels/{interaction.guild.id}/{logs_channel_id}/{log_message_id}"
					ticket_line = f"**Ticket ID:** [`{ticket_id}`]({log_link})\n"

			history_text += (
				f"{ticket_line}"
				f"**Opened:** {open_ts}\n"
				f"{status_line}"
				f"---\n"
			)
		
		history_embed.description = history_text
		history_embed.set_footer(text=f"Displaying the last 5 tickets made")

		await interaction.response.send_message(embed=history_embed)

	@staff.command(name="commands", description="Display all commands for the ticket system")
	async def help_menu(self, interaction: discord.Interaction):
		allowed = (
			await self.has_staff(interaction)
			or await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		
		embed = discord.Embed(
			title="Ticket System Command List",
			description="Here is a list of all commands used for the ticket system! Keep in mind these are all slash commands.",
			timestamp=datetime.now(),
			color=discord.Color.orange()
		)
		staff_group = ""
		staff_group += (
			"`blacklist <user> <reason>`: Blacklists a user from the ticketing system.\n\n"
			"`unblacklist <user> <reason>`: Removes a user the blacklist.\n\n"
			"`history <user>`: Gets the ticket history for a user. Currently, the last 5 tickets are displayed.\n\n"
			"`initiate`: Starts the interactive setup for the ticket system.\n\n"
			"`panic`: Enables or disables ticket creation.\n\n"
			"`set <ticket_type_or_pings> <status>`: Enables or disables a specific ticket type or staff pings in tickets.\n\n"
			"`settings`: Displays all current settings and ticket statuses."
		)
		appeal_group = ""
		appeal_group += (
			"`status <appeal_id>`: Gets the appeal status for an appeal. This command is open to everyone as long they have an appeal id."
		)

		embed.add_field(name="/staff", value=staff_group, inline=False)
		embed.add_field(name="/appeal", value=appeal_group, inline=False)

		await interaction.response.send_message(embed=embed)

	@staff.command(name="settings", description="Display all current settings and ticket statuses")
	async def get_type_status(self, interaction: discord.Interaction):
		allowed = (
			await self.has_staff(interaction)
			or await self.has_management(interaction)
		)

		if not allowed:
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission.", ephemeral=True)
			return
		
		sconfg = self.config.guild(interaction.guild)

		tickets_enabled = await sconfg.tickets_enabled()
		ticket_statuses = await sconfg.ticket_statuses()
		modmail_access_role = await sconfg.modmail_access_role()
		management_role_id = await sconfg.management_access_role()
		appeal_team_role_id = await sconfg.appeal_team_role()
		discord_staff_role_id = await sconfg.discord_staff_role()
		scpsl_staff_role_id = await sconfg.scpsl_staff_role()
		ticket_log_channel_id = await sconfg.ticket_log_channel()
		appeal_log_channel_id = await sconfg.appeal_log_channel()
		panel_channel_id = await sconfg.panel_channel()
		ticket_categories = await sconfg.ticket_categories()

		embed = discord.Embed(
			title="⚙️ Current Settings",
			description="Showing all ticket statuses and settings for this cog",
			timestamp=datetime.now(),
			color=discord.Color.blue()
		)

		def format_mention(item_id, item_type):
			if not item_id: return "`Not Set`"
			if item_type == "role": return f"<@&{item_id}>"
			if item_type == "channel": return f"<#{item_id}>"
			return f"`{item_id}`"

		embed.add_field(
			name="Overall Ticket Creation",
			value=f"The below categories will not matter if this is disabled.\n{'`✅ Enabled`' if tickets_enabled else '`🚫 Disabled`'}",
			inline=False
		)

		name_map = {"discord": "Discord Tickets", "scpsl": "SCP:SL Tickets", "appeals": "Ban Appeals", "staffping": "Staff Ping in Tickets"}
		lines = []
		for key, enabled in ticket_statuses.items():
			emoji = "✅" if enabled else "🚫"
			lines.append(f"{name_map.get(key, key.capitalize())}: `{emoji} {'Enabled' if enabled else 'Disabled'}`")
		embed.add_field(name="Ticket Categories", value="\n".join(lines) or "`Not Set`", inline=False)

		roles_text = (
			f"Staff Access: {format_mention(modmail_access_role, 'role')}\n"
			f"Management Access: {format_mention(management_role_id, 'role')}\n"
			f"Appeals: {format_mention(appeal_team_role_id, 'role')}\n"
			f"Discord Staff: {format_mention(discord_staff_role_id, 'role')}\n"
			f"SCP:SL Staff: {format_mention(scpsl_staff_role_id, 'role')}"
		)
		embed.add_field(name="Role Configuration", value=roles_text, inline=False)

		discord_cat_id = ticket_categories.get("discord")
		scpsl_cat_id = ticket_categories.get("scpsl")
		channels_text = (
			f"Ticket Logs: {format_mention(ticket_log_channel_id, 'channel')}\n"
			f"Appeal Logs: {format_mention(appeal_log_channel_id, 'channel')}\n"
			f"Panel Channel: {format_mention(panel_channel_id, 'channel')}\n"
			f"Discord Ticket Category: {format_mention(discord_cat_id, 'channel')}\n"
			f"SCP:SL Ticket Category: {format_mention(scpsl_cat_id, 'channel')}"
		)
		embed.add_field(name="Channel & Category Configuration", value=channels_text, inline=False)

		await interaction.response.send_message(embed=embed)

	@appeals.command(name="status", description="Gets the status of an appeal")
	async def get_status_appeal(self, interaction: discord.Interaction, appeal_id: str):
		# Get ban appeal status based on appeal id and discord user id
		self.cursor.execute("SELECT appeal_status, timestamp, user_id, ban_appeal_reason FROM appeals WHERE appeal_id = ?", (appeal_id,))
		result = self.cursor.fetchone()

		if not result:
			await interaction.response.send_message(f"**`⚠️ Error!`** There was no appeal matching ID: `{appeal_id}`. Please try again with a valid AID.", ephemeral=True)
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