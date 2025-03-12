import discord

from redbot.core import commands, app_commands
from datetime import datetime

#class MySelect(discord.ui.Select):
#	def __init__(self):
#		options = [
#			discord.SelectOption(label="Option 1", description="Opens Modal 1"),
#			discord.SelectOption(label="Option 2", description="Opens Modal 2"),
#       ]
#		super().__init__(placeholder="Choose an option...", options=options)
#	
#	async def callback(self, interaction: discord.Interaction):
#		if self.values[0] == "Option 1":
#			modal = MyModal(title="Modal 1")
#		elif self.values[0] == "Option 2":
#			modal = MyModal(title="Modal 2")
#
#		await interaction.response.send_modal(modal)

#class MyModal(discord.ui.Modal):
#	def __init__(self, title: str):
#		super().__init__(title=title)
#
#		self.add_item(discord.ui.TextInput(label="Enter something:", required=True))
#
#	async def on_submit(self, interaction: discord.Interaction):
#		await interaction.response.send_message(f"You entered: {self.children[0].value}", ephemeral=True)

#class MyView(discord.ui.View):
#	def __init__(self):
#		super().__init__()
#		self.add_item(MySelect())

class SchizoTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot 

	@commands.hybrid_group(name="setup")
	@setup.command(name="schizostart", description="Sets up the panel used for the ticket option selection")
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

		await ctx.send(embed=embed)

	#@commands.command()
	#async def dropdown(self, ctx: commands.Context):
	#	view = MyView()
	#	await ctx.send("Choose an option:", view=view)