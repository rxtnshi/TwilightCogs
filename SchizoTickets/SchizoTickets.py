import discord

from redbot.core import commands, app_commands
from datetime import datetime

class MySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Option 1", description="Opens Modal 1"),
            discord.SelectOption(label="Option 2", description="Opens Modal 2"),
        ]
        super().__init__(placeholder="Choose an option...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "Option 1":
            modal = MyModal(title="Modal 1")
        elif self.values[0] == "Option 2":
            modal = MyModal(title="Modal 2")
        
        await interaction.response.send_modal(modal)

class MyModal(discord.ui.Modal):
    def __init__(self, title: str):
        super().__init__(title=title)
        self.add_item(discord.ui.TextInput(label="Enter something:", required=True))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"You entered: {self.children[0].value}", ephemeral=True)

class MyView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(MySelect())

class SchizoTickets(commands.Cog):
	"""very schizo attempt at making this please excuse my braincells"""

	def __init__(self, bot):
		self.bot = bot 

	@commands.hybrid_command(name="schizostart")
	async def start_panel(self, ctx: commands.Context):
		await ctx.send("Hello World!")

	@commands.command()
    async def dropdown(self, ctx: commands.Context):
		view = MyView()
        await ctx.send("Choose an option:", view=view)