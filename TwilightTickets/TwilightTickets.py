import discord

from . import ViewsModals
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from redbot.core import commands

staff_roles = [1341958721793691669, 1398449212219457577, 1009509393609535548]
staff_roles_elevated = []
def role_check(member: discord.Member):
	return any(role.id in staff_roles for role in member.roles)

def role_check_elevated(member: discord.Member):
	return any(role.id in staff_roles_elevated for role in member.roles)

tickets_enabled = True

class TwilightTickets(commands.Cog):
	"""Ticketing system for the Twilight Zone"""

	def __init__(self, bot):
		self.bot = bot
		
	staff = app_commands.Group(name="staff", description="Staff commands", guild_only=True)

	@staff.command(name="panel", description="Sets up the panel used for the ticket option selection")
	async def start_panel(self, interaction: discord.Interaction):
		"""Sets up the panel used for the ticket option selection"""
		if not role_check(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
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

		view = ViewsModals.TicketView()
		await interaction.send(embed=embed, view=view)

	@staff.command(name="panic", description="Enables or disables creation of new tickets.")
	async def panic(self, interaction: discord.Interaction):
		if not role_check_elevated(interaction.user):
			await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
			return
		
		global tickets_enabled

		tickets_enabled = not tickets_enabled
		status = "enabled" if tickets_enabled else "disabled"

		await interaction.response.send_message(f"Ticket creation is now {status}.")