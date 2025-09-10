import discord
import sqlite3
import datetime
import io
import re

from .Tickets import create_transcript, create_ticket, close_ticket, create_ban_appeal, finalize_appeal
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

staff_roles = [1345963237316890776, 1345963295575769088]
staff_roles_elevated = [1341957856232210492, 1341958721793691669, 1341957864650047569, 1362917217611546705, 1342201478122704989, 1341961378100936735]
log_channel_id = 1414502972964212857 #1414397193934213140 test server

#
# Dropdowns and Buttons
# 

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="⚙️ Discord Staff", description="Contact Discord staff", value="discord"),
            discord.SelectOption(label="🎮 Game Staff", description="Contact SCP:SL staff", value="game"),
            discord.SelectOption(label="🔨 Ban Appeals", description="Request a ban appeal", value="appeals")
        ]
        super().__init__(placeholder="Select a category...", options=options, custom_id="persistent_ticket_select")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog:
            await interaction.response.send_message("`**🛑 Error!**` The ticket system is currently offline.", ephemeral=True)
            new_view = TicketView()
            await interaction.message.edit(view=new_view)
            return
        
        log_channel = interaction.guild.get_channel(log_channel_id)
        selected_type = self.values[0]
        
        cog.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (interaction.user.id,))
        if result := cog.cursor.fetchone():
            await interaction.response.send_message(f"`**🚫 Prohibited!**` You are blacklisted from creating tickets.", ephemeral=True)
            new_view = TicketView()
            await interaction.message.edit(view=new_view)
            return

        if not cog.tickets_enabled:
            await interaction.response.send_message("``**🛑 Error!**` Ticket creation is currently disabled.", ephemeral=True)
            new_view = TicketView()
            await interaction.message.edit(view=new_view)
            if log_channel:
                await log_channel.send(f"{interaction.user} ({interaction.user.id}) tried opening `{selected_type}` tickets during panic mode.")
                return
        
        if not cog.ticket_statuses.get(selected_type, False):
            await interaction.response.send_message("``**🛑 Error!**` This ticket category has been disabled.", ephemeral=True)
            new_view = TicketView()
            await interaction.message.edit(view=new_view)
            return

        if selected_type == "discord":
            category = discord.utils.get(interaction.guild.categories, id=1414502599293407324)
            if category:
                for channel in category.text_channels:
                    if channel.topic and f"({interaction.user.id})" in channel.topic:
                        await interaction.response.send_message(f"`**🚫 Prohibited!**` An existing ticket has been found: {channel.mention}", ephemeral=True)
                        new_view = TicketView()
                        await interaction.message.edit(view=new_view)
                        return
            modal = DiscordModal()
        elif selected_type == "game":
            category = discord.utils.get(interaction.guild.categories, id=1414502707309314088)
            if category:
                for channel in category.text_channels:
                    if channel.topic and f"({interaction.user.id})" in channel.topic:
                        await interaction.response.send_message(f"`**🚫 Prohibited!**` An existing ticket has been found: {channel.mention}", ephemeral=True)
                        new_view = TicketView()
                        await interaction.message.edit(view=new_view)
                        return
            modal = GameModal()
        elif selected_type == "appeals":
            user = interaction.user
            cog.cursor.execute("SELECT appeal_id FROM appeals WHERE user_id = ? AND appeal_status = 'pending'", (user.id,))
            result = cog.cursor.fetchone()

            if result:
                existing_appeal_id = result[0]
                await interaction.response.send_message(f"`**🚫 Prohibited!**` You already have an appeal open. Please wait for staff to review it. (Reference AID: `{existing_appeal_id}`)", ephemeral=True)
                new_view = TicketView()
                await interaction.message.edit(view=new_view)
            modal = AppealModal()
        else:
            await interaction.response.send_message("`**🛑 Error!**` An unexpected error occurred.", ephemeral=True)
            return

        await interaction.response.send_modal(modal)
        new_view = TicketView()
        await interaction.message.edit(view=new_view)

class DecisionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="✅ Accept Appeal", value="accept"),
            discord.SelectOption(label="⛔ Deny Appeal", value="reject"),
        ]
        super().__init__(placeholder="Accept or Reject this Appeal", options=options, custom_id="persistent_appeal_decision")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        appeal_team_id = 1415179872241975368
        appeal_team_role = guild.get_role(appeal_team_id)

        if not appeal_team_role or appeal_team_role not in interaction.user.roles:
            await interaction.response.send_message("`**🚫 Prohibited!**` You do not have permission to make appeal decisions.", ephemeral=True)
            return
        
        decision = self.values[0]
        await interaction.response.send_modal(FinishAppealModal(decision))
        new_view = AppealView()
        await interaction.message.edit(view=new_view)
        
class CloseTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="persistent_close_ticket")

    async def callback(self, interaction: discord.Interaction):
        if not any(role.id in staff_roles for role in interaction.user.roles):
            await interaction.response.send_message("`**🚫 Prohibited!**` You do not have permission to close this ticket.", ephemeral=True)
            return
        await interaction.response.send_modal(CloseTicketModal())
        new_view = CloseTicketView()
        await interaction.message.edit(view=new_view)

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
            interaction, "Discord", 
            self.discord_request_name.value, 
            self.discord_request.value,
            1414502599293407324, # category id
            1345963295575769088, # staff id
            0x5865f2, 
            cog
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
            interaction, 
            "SCP:SL", 
            self.game_request_name.value, 
            self.game_request.value,
            1414502707309314088, # category id
            1345963237316890776, # staff id
            0x3498db, 
            cog
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

        await interaction.response.send_message("⌛ Finalizing appeal and notifying user...", ephemeral=False)

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
            await interaction.followup.send("`🛑 Error:` Could not parse IDs from the embed.", ephemeral=True)
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

        await interaction.edit_original_response(content=f"`**✅ Success!**` <@{opener_id}> has been successfully notified. Appeal status has been updated.")