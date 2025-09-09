import discord
import sqlite3
import datetime
import io
import re

from .Tickets import create_transcript, create_ticket, close_ticket, create_ban_appeal, finalize_appeal
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

staff_roles = [1345963237316890776, 1345963295575769088, 1009509393609535548, 1009509393609535548]
staff_roles_elevated = [1398449212219457577, 1009509393609535548]
log_channel_id = 1414502972964212857 #1414397193934213140 test server

#
# Dropdowns and Buttons
# 

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⚠️ Discord Staff", description="Contact Discord staff", value="discord"),
            discord.SelectOption(label="🎮 Game Staff", description="Contact SCP:SL staff", value="game"),
            discord.SelectOption(label="🔨 Ban Appeals", description="Request a ban appeal", value="appeals")
        ]
        super().__init__(placeholder="Select a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog:
            await interaction.response.send_message("The ticket system is currently offline.", ephemeral=True)
            await interaction.message.edit(view=TicketView())
            return
        
        log_channel = interaction.guild.get_channel(log_channel_id)
        
        cog.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (interaction.user.id,))
        if result := cog.cursor.fetchone():
            await interaction.response.send_message(f"You are blacklisted from creating tickets. Reason: {result[0]}", ephemeral=True)
            await interaction.message.edit(view=TicketView())
            return

        if not cog.tickets_enabled:
            await interaction.response.send_message("Ticket creation is currently disabled.", ephemeral=True)
            await interaction.message.edit(view=TicketView())
            return
        
        selected_type = self.values[0]
        if not cog.ticket_statuses.get(selected_type, False):
            await interaction.response.send_message("This ticket category has been disabled.", ephemeral=True)
            await interaction.message.edit(view=TicketView())
            return

        if selected_type == "discord":
            category = discord.utils.get(interaction.guild.categories, id=1414502599293407324)
            if category:
                for channel in category.text_channels:
                    if channel.topic and f"({interaction.user.id})" in channel.topic:
                        await interaction.response.send_message(f"An existing ticket has been found: {channel.mention}", ephemeral=True)
                        await interaction.message.edit(view=TicketView())
                        return
            modal = DiscordModal()
        elif selected_type == "game":
            category = discord.utils.get(interaction.guild.categories, id=1414502707309314088)
            if category:
                for channel in category.text_channels:
                    if channel.topic and f"({interaction.user.id})" in channel.topic:
                        await interaction.response.send_message(f"An existing ticket has been found: {channel.mention}", ephemeral=True)
                        await interaction.message.edit(view=TicketView())
                        return
            modal = GameModal()
        elif selected_type == "appeals":

            cog.cursor.execute("SELECT appeal_id FROM appeals WHERE user_id = ? AND appeal_status = 'pending' ORDER BY timestamp DESC", (interaction.user.id,))
            if result := cog.cursor.fetchone():
                await interaction.response.send_message(f"You already have a pending appeal. Please wait for staff to review it.", ephemeral=True)
                await interaction.message.edit(view=TicketView())
                return
            modal = AppealModal()
        else:
            await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
            await interaction.message.edit(view=TicketView())
            return

        await interaction.response.send_modal(modal)
        await interaction.message.edit(view=TicketView())

class DecisionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="✅ Accept Appeal", value="accept"),
            discord.SelectOption(label="⛔ Deny Appeal", value="reject"),
        ]
        super().__init__(placeholder="Accept or Reject this Appeal", options=options)

    async def callback(self, interaction: discord.Interaction):
        decision = self.values[0]
        await interaction.response.send_modal(FinishAppealModal(decision))
        await interaction.message.edit(view=AppealView())
        
class CloseTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        if not any(role.id in staff_roles for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to close this ticket.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseTicketModal())

#
# Views
# 

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(CloseTicket())

class AppealView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DecisionSelect())

#
# Modals
# 

class CloseTicketModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Ticket Closure", timeout=None)
        self.close_reason = discord.ui.TextInput(label="Why are you closing the ticket?", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.close_reason)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog: return
        
        await interaction.response.send_message("⌛ Creating transcript and closing ticket...", ephemeral=True)

        channel = interaction.channel
        closer = interaction.user
        logs_channel = interaction.guild.get_channel(log_channel_id)
        topic = interaction.channel.topic
        open_reason = "N/A"
        opening_user_id = None
        if topic:
            if match := re.search(r"\((\d+)\)", topic):
                opening_user_id = int(match.group(1))
            try:
                open_reason = topic.split("Issue:")[1].split("|")[0].strip()
            except IndexError: pass
        opener = interaction.guild.get_member(opening_user_id) or "User Not Found"
        log_message = await create_transcript(channel, open_reason, opener, closer, logs_channel, self.close_reason.value, cog)
        await close_ticket(channel, closer, self.close_reason.value, log_message, cog)

class DiscordModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Discord Help Request", timeout=None)
        self.discord_request_name = discord.ui.TextInput(label="What is your issue?", required=True, style=discord.TextStyle.short)
        self.discord_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.discord_request_name)
        self.add_item(self.discord_request)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog: return

        await create_ticket(
            interaction, "Discord", self.discord_request_name.value, self.discord_request.value,
            1414502599293407324, 1345963295575769088, 0x5865f2, cog
        )

class GameModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Game Staff Help Request", timeout=None)
        self.game_request_name = discord.ui.TextInput(label="What is your issue?", required=True, style=discord.TextStyle.short)
        self.game_request = discord.ui.TextInput(label="Describe the issue", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.game_request_name)
        self.add_item(self.game_request)
    
    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog: return

        await create_ticket(
            interaction, "SCP:SL", self.game_request_name.value, self.game_request.value,
            1414502707309314088, 1345963237316890776, 0x3498db, cog
        )

class AppealModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Ban Appeal", timeout=None)
        self.appeal_user = discord.ui.TextInput(label="SteamID64 or Discord Username/ID", placeholder="Format: [Platform]: [ID]", required=True, style=discord.TextStyle.short)
        self.appeal_info = discord.ui.TextInput(label="Relevant Information/Evidence", placeholder="Provide evidence to support your appeal.", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.appeal_user)
        self.add_item(self.appeal_info)

    async def on_submit(self, interaction: discord.Interaction): 
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog: return

        await create_ban_appeal(interaction, self.appeal_user.value, self.appeal_info.value, cog)

class FinishAppealModal(discord.ui.Modal):
    def __init__(self, decision: str):
        super().__init__(title="Finalize Appeal Decision", timeout=None)
        self.decision = decision
        self.finish_appeal = discord.ui.TextInput(label=f"Reason for {decision.lower()}ing appeal", placeholder="Provide a detailed response.", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.finish_appeal)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog: return

        await interaction.response.send_message("⌛ Finalizing appeal and notifying user...", ephemeral=True)

        original_message = interaction.message
        original_embed = original_message.embeds[0]
        reason = self.finish_appeal.value
        staff_member = interaction.user
        footer_text = original_embed.footer.text
        try:
            user_id_part = footer_text.split("User ID: ")[1]
            opener_id = int(user_id_part.split(" | ")[0])
            appeal_id = footer_text.split("Appeal ID: ")[1]
        except (IndexError, ValueError):
            await interaction.followup.send("Error: Could not parse IDs from the embed.", ephemeral=True)
            return
        
        await finalize_appeal(opener_id, appeal_id, self.decision, reason, staff_member, cog)

        new_embed = original_embed.copy()
        if self.decision == "accept":
            new_embed.title = "✅ Appeal Accepted"
            new_embed.color = discord.Color.green()
        else:
            new_embed.title = "🚫 Appeal Rejected"
            new_embed.color = discord.Color.red()
        new_embed.add_field(name=f"Decision by:", value=f"{staff_member.mention}", inline=False)
        new_embed.add_field(name="Reason:", value=reason, inline=False)

        view = discord.ui.View.from_message(original_message)
        if view:
            for item in view.children:
                if isinstance(item, discord.ui.Select):
                    item.disabled = True
            await original_message.edit(embed=new_embed, view=view)
        else:
            await original_message.edit(embed=new_embed)

        await interaction.followup.send(f"✅ <@{opener_id}> has been successfully notified.", ephemeral=True)