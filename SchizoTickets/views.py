import discord, os, config
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

class TicketDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛠️ Bug Report", description="Report a plugin bug."),
            discord.SelectOption(label="‼️ Player Report", description="Report a player breaking the rules."),
            discord.SelectOption(label="⚠️ Discord Help", description="Request help for Discord-related issues."),
        ]
        super().__init__(placeholder="Select a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        """Handles the dropdown selection."""
        if self.values[0] == "🛠️ Bug Report":
            modal = BugReportModal()
        elif self.values[0] == "‼️ Player Report":
            modal = PlayerReportModal()
        elif self.values[0] == "⚠️ Discord Help":
            modal = DiscordHelpModal()
        
        await interaction.response.send_modal(modal)

class BugReportModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Bug Report")
        self.add_item(discord.ui.TextInput(label="Describe the bug in a few sentences", required=True, style=discord.TextStyle.short))
        self.add_item(discord.ui.TextInput(label="Reproduction Steps", required=True, style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Bug report submitted!", ephemeral=True)

class PlayerReportModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Player Report")
        self.add_item(discord.ui.TextInput(label="Player Name", required=True))
        self.add_item(discord.ui.TextInput(label="What did they do?", required=True, style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Player report submitted!", ephemeral=True)

class DiscordHelpModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Discord Help Request")
        self.add_item(discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("Help request submitted!", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(TicketDropdown(self.bot))