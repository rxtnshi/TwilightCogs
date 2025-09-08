import discord
import sqlite3

from . import ViewsModals
from datetime import datetime
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands
from redbot.core import commands

staff_roles = [1341958721793691669, 1398449212219457577, 1009509393609535548]
staff_roles_elevated = [1009509393609535548]
def role_check(member: discord.Member):
	return any(role.id in staff_roles for role in member.roles)

def role_check_elevated(member: discord.Member):
	return any(role.id in staff_roles_elevated for role in member.roles)

tickets_enabled = True

class TwilightTickets(commands.Cog):
	"""Ticketing system for the Twilight Zone"""

	def __init__(self, bot):
		self.bot = bot
		self.tickets_enabled = True
		self.ticket_statuses = {
			"discord": True,
			"game": True
		}
		
		self.conn = sqlite3.connect('tickets.db')
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
				close_time TEXT
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
	def cog_unload(self):
		self.conn.close()

	staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)

	@staff.command(name="panel", description="Sets up the panel used for the ticket option selection")
	async def start_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
		"""Sets up the panel used for the ticket option selection"""
		if not role_check(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
			return
		
		if channel is None:
			await interaction.response.send_message("You must specify which channel the panel is going to be posted in.", ephemeral=True)
			return
		
		embed = discord.Embed(title="Twilight Zone Support & Reporting",
                      description="So ya need help with something, right? Well you've come to the right place!\n\nHere's what I can help you with:",
                      color=0x7a2db9)
		embed.add_field(name="⚠️ Discord Help Request",
                value="Contact Discord staff!",
                inline=False)
		embed.add_field(name="🎮 Game Staff",
				  value="Contact SCP:SL server staff!",
				  inline=False)

		embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1341956884059521025/28cd7d2325f3b9b2704b99b7903877d2.png?size=1024")
		embed.set_footer(text="The Twilight Zone")
		embed.timestamp = datetime.now()

		view = ViewsModals.TicketView(self)
		await channel.send(embed=embed, view=view)
		await interaction.response.send_message(f"The panel has been sucessfully sent into {channel.mention}!", ephemeral=True)

	@staff.command(name="panic", description="Enables or disables panic mode")
	async def panic(self, interaction: discord.Interaction):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
			return
		log_channel_id = 1414397193934213140
		log_channel = interaction.guild.get_channel(log_channel_id)

		self.tickets_enabled = not self.tickets_enabled
		status = "enabled" if self.tickets_enabled else "disabled"

		await interaction.response.send_message(f"Ticket creation is now {status}")

	@staff.command(name="set", description="Enable/disable a specific ticket type")
	@app_commands.choices(
		ticket_type=[
			Choice(name="Discord Tickets", value="discord"),
			Choice(name="SCP:SL Tickets", value="game")
		],
		status=[
			Choice(name="Enable", value="enable"),
			Choice(name="Disable", value="disable")
		]
    )
	async def enable_disable_type(self, interaction: discord.Interaction, ticket_type: str, status: str):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
			return
		
		new_status = (status == "enable")
		self.ticket_statuses[ticket_type] = new_status

		await interaction.response.send_message(f"{ticket_type.capitalize()} tickets have been {status}d successfully.", ephemeral=True)

	@staff.command(name="blacklist", description="Blacklists a user")
	async def blacklist_user(self, interaction: discord.Interaction, user: discord.Member, reason: str):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
			return
		
		try:
			self.cursor.execute("""
				INSERT INTO blacklist(user_id, reason, staff_id, timestamp)
				VALUES(?, ?, ?, ?)
			""", (user.id, reason, interaction.user.id, datetime.now().isoformat()))
			self.conn.commit()
			await interaction.response.send_message(f"{user.mention} has been successfully blacklisted. Reason: {reason}")
		except sqlite3.IntegrityError:
			await interaction.response.send_message(f"{user.mention} has already been blacklisted.", ephemeral=True)
			return
	
	@staff.command(name="unblacklist", description="Removes a user from the blacklist")
	async def unblacklist_user(self, interaction: discord.Interaction, user: discord.Member):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
			return
		
		self.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (user.id,))
		if self.cursor.rowcount > 0:
			self.conn.commit()
			await interaction.response.send_message(f"{user.mention} has been successfully removed from the blacklist!", ephemeral=True)
		else:
			await interaction.response.send_message(f"{user.mention} was not found in the blacklist.", ephemeral=True)