import discord

from redbot.core import commands, app_commands
from datetime import datetime

class SchizoTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot 

	@commands.hybrid_command(name="schizostart")
	async def start_panel(self, interaction: discord.Interaction):
		await interaction.response.send_message("Hello World!", ephemeral=True)