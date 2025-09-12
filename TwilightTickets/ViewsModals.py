import discord
import sqlite3
import datetime
import io
import re

from .Tickets import create_transcript, create_ticket, close_ticket, create_ban_appeal, finalize_appeal
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

#
# Dropdowns and Buttons
# 

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="👮 Discord Staff", description="Open a ticket for reports/inquiries", value="discord"),
            discord.SelectOption(label="🎮 SCP:SL Staff", description="Open a ticket for reports/inquiries", value="scpsl"),
            discord.SelectOption(label="🔨 Appeals Requests", description="Request an appeal for a punishment", value="appeals")
        ]
        super().__init__(placeholder="Select a category...", options=options, custom_id="persistent_ticket_select")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog:
            new_view = TicketView()
            await interaction.response.send_message("**`⚠️ Error!`** Ticket system not loaded.", ephemeral=True)
            await interaction.message.edit(view=new_view)
            return

        gconf = cog.config.guild(interaction.guild)

        # Check for panic mode
        tickets_enabled = await gconf.tickets_enabled()
        if not tickets_enabled:
            log_ch_id = await gconf.ticket_log_channel()
            log_ch = interaction.guild.get_channel(log_ch_id) if log_ch_id else None
            if log_ch:
                await log_ch.send(f"{interaction.user} ({interaction.user.id}) attempted to open `{self.values[0]}` tickets during panic mode.")
            new_view = TicketView()
            await interaction.response.send_message("**`⚠️ Error!`** Tickets are currently disabled.", ephemeral=True)
            await interaction.message.edit(view=new_view)
            return
        
        # Check for blacklist
        cog.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (interaction.user.id,))
        if result := cog.cursor.fetchone():
            new_view = TicketView()
            await interaction.response.send_message(f"**`🚫 Prohibited!`** You are blacklisted from creating tickets.", ephemeral=True)
            await interaction.message.edit(view=new_view)
            return

        # Check ticket type status
        ticket_statuses = await gconf.ticket_statuses()
        selected_type = self.values[0]
        if not ticket_statuses.get(selected_type, True):
            new_view = TicketView()
            await interaction.response.send_message("**`🛑 Sorry!`** That ticket category is currently not active", ephemeral=True)
            await interaction.message.edit(view=new_view)
            return

        # Prevent duplicate ticket in same category
        cats = await gconf.ticket_categories()
        if selected_type == "discord":
            cat_id = cats.get("discord")
        elif selected_type == "scpsl":
            cat_id = cats.get("scpsl")
        else:
            cat_id = None

        if cat_id:
            category = discord.utils.get(interaction.guild.categories, id=cat_id)
            if category:
                for ch in category.text_channels:
                    if ch.topic and f"({interaction.user.id})" in ch.topic:
                        new_view = TicketView()
                        await interaction.response.send_message(f"**`🚫 Prohibited!`** You already have an open ticket in this category. You may access it here {ch.mention}", ephemeral=True)
                        await interaction.message.edit(view=new_view)
                        return

        if selected_type == "discord":
            modal = DiscordModal()
        elif selected_type == "scpsl":
            modal = GameModal()
        elif selected_type == "appeals":
            user = interaction.user
            cog.cursor.execute("SELECT appeal_id FROM appeals WHERE user_id = ? AND appeal_status = 'pending'", (user.id,))
            result = cog.cursor.fetchone()

            if result:
                existing_appeal_id = result[0]
                new_view = TicketView()
                await interaction.response.send_message(f"**`🚫 Prohibited!`** You already have an appeal open. Please wait for staff to review it. (Reference AID: `{existing_appeal_id}`)", ephemeral=True)
                await interaction.message.edit(view=new_view)
                return
            modal = AppealModal()
        else:
            new_view = TicketView()
            await interaction.response.send_message("**`⚠️ Error!`** An unexpected error occurred.", ephemeral=True)
            await interaction.message.edit(view=new_view)
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
        cog = interaction.client.get_cog("TwilightTickets")

        sconfg = cog.config.guild(guild)
        appeal_team_id = await sconfg.appeal_team_role()
        appeal_team_role = guild.get_role(appeal_team_id)

        if not appeal_team_role or appeal_team_role not in interaction.user.roles:
            await interaction.response.send_message("**`🚫 Prohibited!`** You do not have permission to make appeal decisions.", ephemeral=True)
            new_view = AppealView()
            await interaction.message.edit(view=new_view)
            return
        
        decision = self.values[0]
        await interaction.response.send_modal(FinishAppealModal(decision))
        new_view = AppealView()
        await interaction.message.edit(view=new_view)
        
class CloseTicket(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="persistent_close_ticket")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TwilightTickets")
        if not cog:
            await interaction.response.send_message("`🛑` Ticket system not loaded.", ephemeral=True)
            return

        gconf = cog.config.guild(interaction.guild)
        mod_role_id = await gconf.modmail_access_role()
        is_allowed = interaction.user.guild_permissions.administrator or (
            mod_role_id and any(r.id == mod_role_id for r in interaction.user.roles)
        )
        if not is_allowed:
            new_view = CloseTicketView()
            await interaction.response.send_message("**`🚫 Prohibited!`** You do not have permission to close this ticket.", ephemeral=True)
            await interaction.message.edit(view=new_view)
            return

        new_view = CloseTicketView()
        await interaction.message.edit(view=new_view)
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


        sconfg = cog.config.guild(interaction.guild)
        channel = interaction.channel
        closer = interaction.user

        logs_channel_id = await sconfg.ticket_log_channel()
        logs_channel = interaction.guild.get_channel(logs_channel_id)
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

        sconfg = cog.config.guild(interaction.guild)
        categories = await sconfg.ticket_categories()
        category_id = categories.get("discord")
        staff_role_id = await sconfg.discord_staff_role()

        await create_ticket(
            interaction, "Discord", 
            self.discord_request_name.value, 
            self.discord_request.value,
            category_id, # category id
            staff_role_id, # staff id
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

        sconfg = cog.config.guild(interaction.guild)
        categories = await sconfg.ticket_categories()
        category_id = categories.get("scpsl")
        staff_role_id = await sconfg.scpsl_staff_role()

        await create_ticket(
            interaction, 
            "SCP:SL", 
            self.game_request_name.value, 
            self.game_request.value,
            category_id, # category id
            staff_role_id, # staff id
            0x3498db, 
            cog
        )

class AppealModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Appeal Request", timeout=None)
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

        await interaction.response.send_message("⌛ Finalizing appeal and notifying user...")

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
            await interaction.followup.send("`⚠️ Error:` Could not parse IDs from the embed.", ephemeral=True)
            return
        
        await finalize_appeal(opener_id, appeal_id, self.decision, reason, staff_member, cog)

        new_embed = original_embed.copy()
        if self.decision == "accept":
            new_embed.title = "✅ Appeal Accepted"
            new_embed.color = discord.Color.green()
            new_embed.description = f"Appeal `{appeal_id} has been accepted. The appeal is now finalized."
        else:
            new_embed.title = "🚫 Appeal Rejected"
            new_embed.color = discord.Color.red()
            new_embed.description = f"Appeal `{appeal_id} has been denied. The appeal is now finalized."
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

        await interaction.edit_original_response(content=f"**`✅ Success!`** Appeal `{appeal_id}` has been finalized.")