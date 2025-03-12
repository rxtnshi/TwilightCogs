from redbot.core import commands
from discord import app_commands
from datetime import datetime

class SchizoTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot 

	@tree.command(
		name = "startsystem",
		description = "Starts the ticket panel in a channel of your choosing"
	)
	async def start_panel(self, ctx):
		await ctx.send("This works!")