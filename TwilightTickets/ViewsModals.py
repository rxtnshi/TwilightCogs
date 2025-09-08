import discord
import datetime
import io
import re

from .Tickets import create_transcript, create_ticket
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⚠️ Discord Staff", description="Contact Discord staff"),
            discord.SelectOption(label="🎮 Game Staff", description="Contact SCP:SL staff")
        ]

        super().__init__(placeholder="Select a category...", options=options)

    async def callback(self, interaction = discord.Interaction):

        if not self.cog.tickets_enabled:
            await interaction.response.send_message("Ticket creation is currently disabled. Please contact staff if you believe this is an error", ephemeral=True)
            return
        
        if self.values[0] == "⚠️ Discord Staff":
            modal = DiscordModal()
        elif self.values[0] == "🎮 Game Staff":
            # modal = GameModal()
            await interaction.response.send_message("This option is currently disabled.", ephemeral=True)
            await interaction.message.edit(view=TicketView())

        await interaction.response.send_modal(modal)
        await interaction.message.edit(view=TicketView())

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class CloseTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        closing_user = interaction.user
        logs_channel_id = 1414397193934213140 #set whenever testing or active
        logs_channel = interaction.guild.get_channel(logs_channel_id)
        topic = interaction.channel.topic

        open_reason = None
        if topic and "Issue:" in topic:
            open_reason = topic.split("Issue:")[1].split("|")[0].strip()
        
        opening_user = None
        if topic:
            match = re.search(r"\((\d+)\)", topic)
            if match:
                opening_user = int(match.group(1))
        opener = channel.guild.get_member(opening_user) if opening_user else None

        await create_transcript(channel, open_reason, opener, closing_user, logs_channel)
        await interaction.response.send_message("Closing ticket...", ephemeral=True)

        try:
            await interaction.channel.delete()
        except Exception as e:
            await interaction.response.send_message(f"Failed to delete channel: {e}", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self, timeout=None):
        super().__init__(timeout=None)
        self.add_item(CloseTicket())

class DiscordModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Discord Help Request", timeout=None)
        self.discord_request_name = discord.ui.TextInput(label="What is your issue?", required=True, style=discord.TextStyle.short)
        self.discord_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.discord_request_name)
        self.add_item(self.discord_request)

    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            ticket_type="Discord",
            request_name=self.discord_request_name.value,
            request_description=self.discord_request.value,
            category_id=1349563765842247784, #set whenever testing or when active
            staff_role_id=1009509393609535548, #set whenever testing or when active
            embed_color=0xFF5733
        )

class GameModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Game Staff Help Request", timeout=None)
        self.discord_request_name = discord.ui.TextInput(label="What is your issue?", required=True, style=discord.TextStyle.short)
        self.discord_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.discord_request_name)
        self.add_item(self.discord_request)
    
    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            ticket_type="SCP:SL",
            request_name=self.game_request_name.value,
            request_description=self.game_request.value,
            category_id=1414397144370122833, #set whenever testing or when active
            staff_role_id=1009509393609535548, #set whenever testing or when active
            embed_color=0x3498db
        )