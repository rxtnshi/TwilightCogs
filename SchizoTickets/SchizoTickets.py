import discord

from redbot.core import commands, app_commands
from datetime import datetime

class SchizoTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot 

	@app_commands.command(
		name = "startsystem",
		description = "Starts the ticket panel in a channel of your choosing"
	)
	async def start_panel(self, ctx):
		await ctx.send("This works!")