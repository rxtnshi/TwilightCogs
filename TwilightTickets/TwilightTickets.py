import discord

from .TwilightTickets import Tickets
from datetime import datetime
from discord import app_commands
from discord.ext import commands


class TwilightTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot

	@commands.hybrid_command(name="initiatepanel", description="Sets up the panel used for the ticket option selection")
	@commands.has_any_role(1341958721793691669, 1398449212219457577, 1009509393609535548)
	@commands.guild_only()
	async def start_panel(self, ctx: commands.Context):
		"""Sets up the panel used for the ticket option selection"""
		
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

		view = Tickets.TicketView(self.bot)
		await ctx.send(embed=embed, view=view)