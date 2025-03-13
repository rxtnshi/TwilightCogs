import discord

from SchizoTickets import views
from redbot.core import commands, app_commands, Config
from datetime import datetime

class SchizoTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot

		self.config = Config.get_conf(self, identifier=1923892, force_registration=True)
		default_guild = {
			"blacklisted_users": {},
			"ticket_category": {},
			"support_roles": {},
			"admin_roles": {},
			"ticket_log_channel": {}
		}
		self.config.register_guild(**default_guild)

	@commands.hybrid_command(name="schizostart", description="Sets up the panel used for the ticket option selection")
	async def start_panel(self, ctx: commands.Context):
		"""Sets up the panel used for the ticket option selection"""
		embed = discord.Embed(title="Ghostz's Schizo Zone Support & Reporting",
                      description="So ya need help with something, right? Well you've come to the right place!\n\nHere's what I can help you with:",
                      colour=0x7a2db9,
                      timestamp=datetime.now())
		embed.add_field(name="🛠️ Bug Reports",
                value="You can open a ticket for bug reports related to our SCP:SL server. Issues such as game-breaking bugs with our plugins should be reported ASAP.",
                inline=False)
		embed.add_field(name="‼️ Player Reporting",
                value="Before opening a ticket, preferably report the player breaking the rules via the player list in-game. You can do that by pressing **N** and then clicking the ⚠️ next to their name.",
                inline=False)
		embed.add_field(name="⚠️ Discord Help Request",
                value="Please ping a mod in the respective channel you see a user breaking the rules of our Discord. Alternative, you can report them here instead but make sure to provide the message link of what the user sent that you believe broke our rules.",
                inline=False)

		embed.set_thumbnail(url="https://cdn.discordapp.com/icons/1341956884059521025/28cd7d2325f3b9b2704b99b7903877d2.png?size=1024")

		embed.set_footer(text="Ghostz's Schizo Zone")

		view = views.TicketView(self.bot)
		await ctx.send(embed=embed, view=view)