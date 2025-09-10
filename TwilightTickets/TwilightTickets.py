import discord
import sqlite3
import os

from . import ViewsModals
from datetime import datetime
from discord.app_commands import Choice
from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path

staff_roles = [1345963237316890776, 1345963295575769088]
staff_roles_elevated = [1341957856232210492, 1341958721793691669, 1341957864650047569, 1362917217611546705, 1342201478122704989, 1341961378100936735]
log_channel_id = 1414502972964212857 # 1414397193934213140 test channel
def role_check(member: discord.Member):
	return any(role.id in staff_roles for role in member.roles)

def role_check_elevated(member: discord.Member):
	return any(role.id in staff_roles_elevated for role in member.roles)

class TwilightTickets(commands.Cog):
	"""Ticketing system for the Twilight Zone"""

	def __init__(self, bot):
		self.bot = bot		

		self.config = Config.get_conf(self, identifier=99204742, force_registration=True)
		default_guild = {
			"tickets_enabled": True,
			"ticket_statuses": {
				"discord": True,
				"game": True,
				"appeals": True,
				"staffping": True
			}
		}
		self.config.register_guild(**default_guild)

		self.tickets_enabled = True
		self.ticket_statuses = {}

		db_path = cog_data_path(self) / "tickets.db"
		os.makedirs(os.path.dirname(db_path), exist_ok=True)

		self.conn = sqlite3.connect(db_path)
		self.cursor = self.conn.cursor()
		self.setup_db()

	def cog_check(self, ctx):
		guild_check = ctx.guild is not None and ctx.guild.id == 1341956884059521025 # TWILIGHT ZONE GUILDID
		if not guild_check:
			ctx.send("Sorry this cog is not available.")
			return

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

	staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)
	appeals = app_commands.Group(name="appeals", description="Appeal commands", guild_only=True)

	@staff.command(name="panel", description="Sets up the panel used for the ticket option selection")
	async def start_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
		"""Sets up the panel used for the ticket option selection"""
		if not role_check(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
			return
		
		if channel is None:
			await interaction.response.send_message("**`🛑 Error!`** You must specify which channel the panel is going to be posted in.", ephemeral=True)
			return
		
		embed = discord.Embed(title="Twilight Zone Support & Reporting",
                      description="So ya need help with something, right? Well you've come to the right place!\n\nHere's what I can help you with:",
                      color=0x7a2db9)
		embed.add_field(name="⚙️ Discord Staff", value="Contact Discord staff!", inline=False)
		embed.add_field(name="🎮 Game Staff", value="Contact SCP:SL server staff!", inline=False)
		embed.add_field(name="🔨 Ban Appeals", value="Request a ban appeal!", inline=False)

		embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1341956884059521025/28cd7d2325f3b9b2704b99b7903877d2.png?size=1024")
		embed.set_footer(text="Ghostz's Twilight Zone")
		embed.timestamp = datetime.now()

		view = ViewsModals.TicketView()
		await channel.send(embed=embed, view=view)
		await interaction.response.send_message(f"**`✅ Success!`** The panel has been sucessfully sent into {channel.mention}!", ephemeral=True)
		
	@staff.command(name="panic", description="Enables or disables panic mode")
	async def panic(self, interaction: discord.Interaction):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You do not have permission to use this command.", ephemeral=True)
			return
		
		self.tickets_enabled = not self.tickets_enabled
		await self.config.guild(interaction.guild).tickets_enabled.set(self.tickets_enabled)
		status = "enabled" if self.tickets_enabled else "disabled"

		await interaction.response.send_message(f"**`✅ Success!`** Ticket creation is now {status}.")

	@staff.command(name="set", description="Enable/disable a specific ticket type or ticket pings")
	@app_commands.choices(
		option=[
			Choice(name="Discord Tickets", value="discord"),
			Choice(name="SCP:SL Tickets", value="game"),
			Choice(name="Ban Appeals", value="appeals"),
			Choice(name="Staff Pings", value="staffping")
		],
		status=[
			Choice(name="Enable", value="enable"),
			Choice(name="Disable", value="disable")
		]
    )
	async def enable_disable_type(self, interaction: discord.Interaction, option: str, status: str):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
			return
		
		new_status = (status == "enable")
		self.ticket_statuses[option] = new_status

		await self.config.guild(interaction.guild).ticket_statuses.set(self.ticket_statuses)

		if option == "staffping":
			await interaction.response.send_message(f"**`✅ Success!`** Staff pings on tickets have been {status}d successfully.")
			return
			
		await interaction.response.send_message(f"**`✅ Success!`** {option.capitalize()} tickets have been {status}d successfully.")

	@staff.command(name="blacklist", description="Blacklists a user")
	async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, reason: str):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
			return
		
		try:
			self.cursor.execute("""
				INSERT INTO blacklist(user_id, reason, staff_id, timestamp)
				VALUES(?, ?, ?, ?)
			""", (user.id, reason, interaction.user.id, datetime.now().isoformat()))
			self.conn.commit()
			await interaction.response.send_message(f"**`✅ Success!`** {user.mention} has been successfully blacklisted. **Reason:** {reason}")
		except sqlite3.IntegrityError:
			await interaction.response.send_message(f"**`🛑 Error!`** {user.mention} has already been blacklisted.")
			return
	
	@staff.command(name="unblacklist", description="Removes a user from the blacklist")
	async def unblacklist_user(self, interaction: discord.Interaction, user: discord.Member):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
			return
		
		self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user.id,))
		if self.cursor.rowcount > 0:
			self.conn.commit()
			await interaction.response.send_message(f"**`✅ Success!`** {user.mention} has been successfully removed from the blacklist!")
		else:
			await interaction.response.send_message(f"**`🛑 Error!`** {user.mention} was not found in the blacklist.")

	@staff.command(name="history", description="Grabs the ticket history of a user")
	async def ticket_history(self, interaction: discord.Interaction, user: discord.Member):
		if not role_check(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
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
		
		logs_channel_id = 1414502972964212857 #1414397193934213140 # change whenever testing or active
		
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
		if not role_check(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
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
			"`panel <channel>`: Initiates the ticket panel used to create tickets and sends it into the specified channel.\n\n"
			"`panic`: Enables or disables ticket creation.\n __Warning:__ This will reset if the bot or cog is restarted.\n\n"
			"`set <ticket_type_or_pings> <status>`: Enables or disables a specific ticket type or staff pings in tickets.\n __Warning:__ This will reset if the bot or cog is restarted."
		)
		appeal_group = ""
		appeal_group += (
			"`status <appeal_id>`: Gets the appeal status for an appeal. This command is open to everyone as long they have an appeal id."
		)

		embed.add_field(name="/staff", value=staff_group, inline=False)
		embed.add_field(name="/appeal", value=appeal_group, inline=False)

		await interaction.response.send_message(embed=embed)

	@staff.command(name="getstatus", description="Display all ticket and ping statuses")
	async def get_type_status(self, interaction: discord.Interaction):
		if not role_check(interaction.user):
			await interaction.response.send_message("**`🚫 Prohibited!`** You don't have permission to use this command.", ephemeral=True)
			return

		tickets_enabled = self.tickets_enabled
		ticket_statuses = self.ticket_statuses

		embed = discord.Embed(
			title="⚙️ Current statuses",
			description="Showing all ticket and ping statuses below!",
			timestamp=datetime.now(),
			color=discord.Color.blue()
		)


		ticket_creation_status = "`✅ Enabled`" if tickets_enabled else "`🚫 Disabled`"
		embed.add_field(name="Overall Ticket Creation", value=f"The below categories will not matter if this is disabled.\n{ticket_creation_status}", inline=False)

		ticket_category_names = {
			"discord": "Discord Tickets",
			"game": "SCP:SL Tickets",
			"appeals": "Ban Appeals",
			"staffping": "Staff Ping in Tickets"
		}

		ticket_category_status = []
		for category, is_enabled in ticket_statuses.items():
			emoji = "✅" if is_enabled else "🚫"
			category_name = ticket_category_names.get(category, category.capitalize())
			ticket_category_status.append(f"{category_name}: `{emoji} {'Enabled' if is_enabled else 'Disabled'}`")
		embed.add_field(name="Ticket Categories", value="\n".join(ticket_category_status))

		await interaction.response.send_message(embed=embed)


	@appeals.command(name="status", description="Gets the status of an appeal")
	async def get_status_appeal(self, interaction: discord.Interaction, appeal_id: str):
    	# Get ban appeal status based on appeal id and discord user id
		self.cursor.execute("SELECT appeal_status, timestamp, user_id, ban_appeal_reason FROM appeals WHERE appeal_id = ?", (appeal_id))
		result = self.cursor.fetchone()

		if not result:
			await interaction.response.send_message(f"**`🛑 Error!`** There was no appeal matching ID: `{appeal_id}`. Please try again with a valid AID.", ephemeral=True)
			return
		
		# Hopefully it assigns the correct values if I'm doing it correctly
		appeal_status, timestamp_str, user_id, appeal_reason = result
		
		# Check status?
		if appeal_status == "pending":
			color = 0xffa500
			status = "📥 Appeal Received"
		elif appeal_status == "accepted":
			color = discord.Color.green()
			status = "✅ Appeal Accepted"
		else:
			color = discord.Color.red()
			status = "🚫 Appeal Rejected"

		time_sent = datetime.fromisoformat(timestamp_str)
		time_sent_ts = f"<t:{int(time_sent.timestamp())}:f>"

		# Create the base embed
		appeal_stat_embed = discord.Embed(
			title=f"Status for Appeal `{appeal_id}`",
			description=f"Appeal made by <@{user_id}>",
			timestamp=datetime.now(),
			color=color
		)

		appeal_stat_embed.add_field(name="Status:", value=status, inline=False)
		appeal_stat_embed.add_field(name="Time Sent:", value=time_sent_ts, inline=False)
		appeal_stat_embed.add_field(name="Appeal Reason:", value=appeal_reason, inline=False)

		await interaction.response.send_message(embed=appeal_stat_embed, ephemeral=True)