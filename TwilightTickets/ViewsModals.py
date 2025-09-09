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
    def __init__(self, cog: commands.Cog):
        options = [
            discord.SelectOption(label="⚠️ Discord Staff", description="Contact Discord staff", value="discord"),
            discord.SelectOption(label="🎮 Game Staff", description="Contact SCP:SL staff", value="game"),
            discord.SelectOption(label="🔨 Ban Appeals", description="Request a ban appeal", value="appeals")
        ]

        super().__init__(placeholder="Select a category...", options=options)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog:
            await interaction.response.send_message("The ticket system is currently offline. Please try again later.", ephemeral=True)
            return

        user = interaction.user

        # Blacklist check
        cog.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (user.id,))
        if (row := cog.cursor.fetchone()):
            await interaction.response.send_message(f"You are blacklisted from creating tickets.", ephemeral=True)
            return

        if not cog.tickets_enabled:
            await interaction.response.send_message("Ticket creation is currently disabled.", ephemeral=True)
            return

        selected_type = self.values[0]  # e.g. 'discord', 'game', maybe 'ban_appeal'

        # Map selection to category & staff role
        TYPE_MAP = {
            "discord": {
                "category_id": 1349563765842247784,
                "staff_role_id": 1341958721793691669,
                "modal": DiscordModal
            },
            "game": {
                "category_id": 1414397144370122833,
                "staff_role_id": 1009509393609535548,
                "modal": GameModal
            },
            "ban_appeal": {
                "category_id": 1414770277782392993,
                "staff_role_id": 1398449212219457577,
                "modal": AppealModal
            }
        }

        if selected_type not in TYPE_MAP:
            await interaction.response.send_message("Invalid selection.", ephemeral=True)
            return

        cfg = TYPE_MAP[selected_type]
        category = discord.utils.get(interaction.guild.categories, id=cfg["category_id"])

        if category:
            # Prevent duplicate open ticket of same type
            for ch in category.text_channels:
                if ch.topic and f"({user.id})" in ch.topic:
                    await interaction.response.send_message(
                        f"You already have an open ticket here: {ch.mention}",
                        ephemeral=True
                    )
                    return
        else:
            await interaction.response.send_message("Configuration error: category not found.", ephemeral=True)
            return

        # Show the proper modal
        await interaction.response.send_modal(cfg["modal"](cog))
        # (Optional) refresh panel view
        try:
            await interaction.message.edit(view=TicketView(cog))
        except Exception:
            pass

class DecisionSelect(discord.ui.Select):
    def __init__(self, cog: commands.Cog):
        options = [
            discord.SelectOption(label="✅ Accept Appeal", description="Bans related to this Discord", value="accept"),
            discord.SelectOption(label="⛔ Deny Appeal", description="Bans related to SCP:SL or other games", value="reject"),
        ]
        self.cog = cog

        super().__init__(placeholder="Accept or Reject this Appeal", options=options)

    async def callback(self, interaction: discord.Interaction):
        decision = self.values[0]

        await interaction.response.send_modal(FinishAppealModal(self.cog, decision))
        
class CloseTicket(discord.ui.Button):
    def __init__(self, cog: commands.Cog):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        has_permission = any(role.id in staff_roles for role in interaction.user.roles)
        
        if not has_permission:
            await interaction.response.send_message("You do not have permission to close this ticket. Please contact a staff member if you would like to close this.", ephemeral=True)
            return

        await interaction.response.send_modal(CloseTicketModal(self.cog))

#
# Views
# 

class TicketView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.add_item(TicketSelect(cog))


class CloseTicketView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.add_item(CloseTicket(cog))

class AppealView(discord.ui.View):
    def __init__(self, cog: commands.Cog):
        super().__init__(timeout=None)
        self.add_item(DecisionSelect(cog))

#
# Modals
# 

class CloseTicketModal(discord.ui.Modal):
    def __init__(self, cog: commands.Cog):
        super().__init__(title="Ticket Closure", timeout=None)
        self.cog = cog
        self.close_reason = discord.ui.TextInput(label="Why are you closing the ticket?", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.close_reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⌛ Creating transcript and closing ticket...", ephemeral=True)

        channel = interaction.channel
        closer = interaction.user
        logs_channel = interaction.guild.get_channel(log_channel_id)
        topic = interaction.channel.topic

        open_reason = "N/A"
        opening_user_id = None
        if topic:
            match = re.search(r"\((\d+)\)", topic)
            if match:
                opening_user_id = int(match.group(1))
            try:
                open_reason = topic.split("Issue:")[1].split("|")[0].strip()
            except IndexError:
                pass
        
        opener = interaction.guild.get_member(opening_user_id) if opening_user_id else "User Not Found (Left/Unknown User)"
        
        close_reason_value = self.close_reason.value

        log_message = await create_transcript(channel, open_reason, opener, closer, logs_channel, close_reason_value, self.cog)

        await close_ticket(channel, closer, close_reason_value, log_message, self.cog)

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
            category_id=1414502599293407324, #1349563765842247784, #set whenever testing or when active
            staff_role_id=1345963295575769088, #1009509393609535548, #set whenever testing or when active
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
            category_id=1414502707309314088, #1414397144370122833, #set whenever testing or when active
            staff_role_id=1345963237316890776, #1009509393609535548, #set whenever testing or when active
            embed_color=0x3498db,
            cog=self.cog
        )

class AppealModal(discord.ui.Modal):
    def __init__(self, cog: commands.Cog):
        super().__init__(title="Ban Appeal", timeout=None)
        self.cog = cog
        self.appeal_user = discord.ui.TextInput(
            label="SteamID64 or Discord Username/UserID",
            placeholder="Please provide the ID of the user on the platform they were banned from.",
            required=True, 
            style=discord.TextStyle.short
        )
        self.appeal_info = discord.ui.TextInput(
            label="Relevent Information/Evidence", 
            placeholder="Please provide evidence that supports your appeal to help us investigate it further.",
            required=True, 
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.appeal_user)
        self.add_item(self.appeal_info)

    async def on_submit(self, interaction: discord.Interaction): 
        await create_ban_appeal(
            interaction=interaction,
            banned_user=self.appeal_user.value,
            appeal_request=self.appeal_info.value,
            cog=self.cog
        )

class FinishAppealModal(discord.ui.Modal):
    def __init__(self, cog: commands.Cog, decision: str):
        super().__init__(title="Finalize Appeal Decision", timeout=None)
        self.cog = cog
        self.decision = decision
        self.finish_appeal = discord.ui.TextInput(
            label=f"Reason for {decision.lower()}ing appeal?",
            placeholder="Provide a detailed response to the user.",
            required=True, 
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.finish_appeal)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⌛ Finalizing appeal and notifying user...", ephemeral=True)

        original_message = interaction.message
        original_embed = original_message.embeds[0]
        reason = self.finish_appeal.value

        footer_user_id = original_embed.footer.text
        try:
            opener_id = int(footer_user_id.split("Discord User ID: ")[1])
        except (IndexError, ValueError):
            await interaction.followup.send("Error: Could not parse the original User ID from the embed.", ephemeral=True)
            return
        
        await finalize_appeal(
            interaction=interaction,
            opener_id=opener_id,
            decision=self.decision,
            reason=reason,
        )

        new_embed = original_embed.copy()
        if self.decision == "accept":
            new_embed.title = "✅ Appeal Accepted"
            new_embed.color = discord.Color.green()
        else:
            new_embed.title = "🚫 Appeal Rejected"
            new_embed.color = discord.Color.red()

        new_embed.add_field(name=f"Decision by: {interaction.user}")

        view = self.view
        for item in view.children:
            if isinstance(item, discord.ui.Select):
                item.disabled = True

        await original_message.edit(embed=new_embed, view=view)