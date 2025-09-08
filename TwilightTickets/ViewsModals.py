import discord
import sqlite3
import datetime
import io
import re

from .Tickets import create_transcript, create_ticket
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

class TicketSelect(discord.ui.Select):
    def __init__(self, cog: commands.Cog):
        options = [
            discord.SelectOption(label="⚠️ Discord Staff", description="Contact Discord staff", value="discord"),
            discord.SelectOption(label="🎮 Game Staff", description="Contact SCP:SL staff", value="game")
        ]

        super().__init__(placeholder="Select a category...", options=options)
        self.cog = cog

    async def callback(self, interaction = discord.Interaction):
        log_channel_id = 1414397193934213140
        log_channel = interaction.guild.get_channel(log_channel_id)

        # blacklist check
        self.cog.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (interaction.user.id,))
        result = self.cog.cursor.fetchone()
        if result:
            await interaction.response.send_message(f"You are blacklisted from creating tickets. Reason: {result[0]}", ephemeral=True)

        # check for panic mode
        if not self.cog.tickets_enabled:
            await interaction.response.send_message("Ticket creation is currently disabled. Please contact staff if you believe this is an error!", ephemeral=True)
            await log_channel.send(f"{interaction.user.mention} tried to open a ticket while panic mode was active.")
            return
        
        # check for ticket type statuses
        selected_type = self.values[0]
        if not self.cog.ticket_statuses.get(selected_type, False):
            await interaction.response.send_message("This ticket category has been disabled! Please contact staff if you believe this is an error.", ephemeral=True)
            return

        if selected_type == "discord":
            category_id = 1349563765842247784 # change when testing or active
            category = discord.utils.get(interaction.guild.categories, id=category_id)

            if category:
                for channel in category.text_channels:
                    if channel.topic and f"({interaction.user.id})" in channel.topic:
                        await interaction.response.send_message(f"An existing ticket has been found in this category. You can access it here: {channel.mention}", ephemeral=True)
                        await interaction.message.edit(view=TicketView(self.cog))
                        return
            modal = DiscordModal(self.cog)
        elif selected_type == "game":
            category_id = 1414397144370122833 # change when testing or active
            category = discord.utils.get(interaction.guild.categories, id=category_id)

            if category:
                for channel in category.text_channels:
                    if channel.topic and f"({interaction.user.id})" in channel.topic:
                        await interaction.response.send_message(f"An existing ticket has been found in this category. You can access it here: {channel.mention}", ephemeral=True)
                        await interaction.message.edit(view=TicketView(self.cog))
                        return
            modal = GameModal(self.cog)
        else:
            await interaction.response.send_message("An unexpected error occurred upon trying to show a modal.", ephemeral=True)
            await interaction.message.edit(view=TicketView(self.cog))
            return

        await interaction.response.send_modal(modal)
        await interaction.message.edit(view=TicketView(self.cog))

class TicketView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(cog))

class CloseTicket(discord.ui.Button):
    def __init__(self, cog: commands.Cog):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger)

        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        staff_roles = [1341958721793691669, 1398449212219457577, 1009509393609535548]
        channel = interaction.channel
        closing_user = interaction.user
        logs_channel_id = 1414397193934213140 #set whenever testing or active
        logs_channel = interaction.guild.get_channel(logs_channel_id)
        topic = interaction.channel.topic

        has_permission = any(role.id in staff_roles for role in interaction.user.roles)
        if not has_permission:
            await interaction.response.send_message("Sorry, only modmail staff have access to close this ticket. Please ping a staff if you would like to close this ticket.")
            return

        open_reason = None
        if topic and "Issue:" in topic:
            open_reason = topic.split("Issue:")[1].split("|")[0].strip()
        
        opening_user = None
        if topic:
            match = re.search(r"\((\d+)\)", topic)
            if match:
                opening_user = int(match.group(1))
        opener = channel.guild.get_member(opening_user) if opening_user else None

        await create_transcript(channel, open_reason, opener, closing_user, logs_channel, cog=self.cog)
        await interaction.response.send_message("Closing ticket...", ephemeral=True)

        try:
            await interaction.channel.delete()
        except Exception as e:
            await interaction.response.send_message(f"Failed to delete channel: {e}", ephemeral=True)

class CloseTicketView(discord.ui.View):
    def __init__(self, cog: commands.Cog, timeout=None):
        super().__init__(timeout=None)
        self.add_item(CloseTicket(cog))

class DiscordModal(discord.ui.Modal):
    def __init__(self, cog: commands.Cog):
        super().__init__(title="Discord Help Request", timeout=None)
        self.cog = cog
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
            embed_color=0x5865f2,
            cog=self.cog
        )

class GameModal(discord.ui.Modal):
    def __init__(self, cog: commands.Cog):
        super().__init__(title="Game Staff Help Request", timeout=None)
        self.cog = cog
        self.game_request_name = discord.ui.TextInput(label="What is your issue?", required=True, style=discord.TextStyle.short)
        self.game_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.game_request_name)
        self.add_item(self.game_request)
    
    async def on_submit(self, interaction: discord.Interaction):
        await create_ticket(
            interaction,
            ticket_type="SCP:SL",
            request_name=self.game_request_name.value,
            request_description=self.game_request.value,
            category_id=1414397144370122833, #set whenever testing or when active
            staff_role_id=1009509393609535548, #set whenever testing or when active
            embed_color=0x3498db,
            cog=self.cog
        )