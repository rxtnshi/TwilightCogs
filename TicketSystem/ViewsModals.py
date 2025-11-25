import discord
import sqlite3
import datetime
import io
import re

from redbot.core import Config
from .Handling import send_blocked, send_error, send_success, send_warning
from .Tickets import create_transcript, create_ticket, close_ticket, create_ban_appeal, finalize_appeal
from datetime import datetime
from discord import app_commands, utils
from discord.ext import commands

def parse_id(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip("'\""))
    except ValueError:
        return None

# - Dropdowns and Buttons -

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="👮 Discord Staff", description="Contact our Discord staff", value="discord"),
            discord.SelectOption(label="🎮 SCP:SL Staff", description="Contact our SCP:SL staff", value="scpsl"),
            discord.SelectOption(label="🔨 Appeals Requests", description="Request an appeal", value="appeals")
        ]
        super().__init__(placeholder="Select a Category", options=options, custom_id="persistent_ticket_select")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog:
            new_view = TicketView()
            await send_error(interaction, "TicketSystem not loaded.", True)
            await interaction.message.edit(view=new_view)
            return

        sconfg = cog.config.guild(interaction.guild)

        # Check for panic mode
        tickets_enabled = await sconfg.tickets_enabled()
        channels = await sconfg.ticket_channels()
        if not tickets_enabled:
            log_ch_id = channels.get("log_channel")
            log_ch = interaction.guild.get_channel(log_ch_id) if log_ch_id else None
            if log_ch:
                await log_ch.send(f"{interaction.user} ({interaction.user.id}) attempted to open ticket type `{self.values[0]}` during panic mode.")
            new_view = TicketView()
            await send_error(interaction, "Tickets are currently disabled.", True)
            await interaction.message.edit(view=new_view)
            return
        
        # Check for blacklist
        cog.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (interaction.user.id,))
        if result := cog.cursor.fetchone():
            new_view = TicketView()
            await send_blocked(interaction, "You are blacklisted from making tickets.", True)
            await interaction.message.edit(view=new_view)
            return

        # Check ticket type status
        ticket_statuses = await sconfg.ticket_statuses()
        selected_type = self.values[0]
        if not ticket_statuses.get(selected_type, True):
            new_view = TicketView()
            await interaction.response.send_message("**`🛑 Sorry!`** That ticket category is currently not active", ephemeral=True)
            await interaction.message.edit(view=new_view)
            return

        # Prevent duplicate ticket in same category
        cats = await sconfg.ticket_categories()
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
                        await send_blocked(interaction, f"You already have an open ticket in this category. You may access it here: {ch.mention}", True)
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
                await send_blocked(interaction, f"You already have an appeal open. Please wait for staff to review it. (Reference AID: `{existing_appeal_id}`)", True)
                await interaction.message.edit(view=new_view)
                return
            modal = AppealModal()
        else:
            new_view = TicketView()
            await send_error(interaction, "An unexpected error occurred. Please contact server staff.", True)
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
        cog = interaction.client.get_cog("TicketSystem")

        sconfg = cog.config.guild(guild)
        roles = await sconfg.ticket_roles()
        appeal_team_id = roles.get("appeal_team")

        appeal_team_role = guild.get_role(appeal_team_id)

        if not appeal_team_role or appeal_team_role not in interaction.user.roles:
            await send_blocked(interaction, "You are unable to make appeal decisions.", True)
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
        cog = interaction.client.get_cog("TicketSystem")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return

        sconfg = cog.config.guild(interaction.guild)
        roles = await sconfg.ticket_roles()
        mod_role_id = roles.get("modmail_access")
        mgmt_role_id = roles.get("modmail_mgmt")
        
        access_roles = {rid for rid in(mod_role_id, mgmt_role_id) if rid}
        is_allowed = bool(access_roles and any(r.id in access_roles for r in interaction.user.roles))

        if not is_allowed:
            new_view = CloseTicketView()
            await send_blocked(interaction, "Only the staff team can close tickets.", True)
            await interaction.message.edit(view=new_view)
            return

        new_view = CloseTicketView()
        await interaction.message.edit(view=new_view)
        await interaction.response.send_modal(CloseTicketModal())

class SetupChannelsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Channels", style=discord.ButtonStyle.primary, custom_id="setup_channels_button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return
        
        await interaction.response.send_modal(SetupChannelsModal(interaction.message))

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message

class SetupRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Roles", style=discord.ButtonStyle.primary, custom_id="setup_roles_button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return
        
        await interaction.response.send_modal(SetupRolesModal(interaction.message))

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message

class SetupResetButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚫 Reset Settings", style=discord.ButtonStyle.danger, custom_id="setup_reset_button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return
        
        await interaction.response.send_modal(SetupResetModal(interaction.message))

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message

class SetupSendPanelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="✈️ Send Panel", style=discord.ButtonStyle.success, custom_id="setup_send_panel_button")
    
    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog:
            await send_error(interaction, "TicketSystem not loaded.", True)
            return
        
        sconfg = cog.config.guild(interaction.guild)
        panel_cfg = await sconfg.panel_cfg()

        panel_ch_id = panel_cfg.get("channel")
        panel_message_id = panel_cfg.get("message_id")
        panel_ch = interaction.guild.get_channel(panel_ch_id)

        def make_embed():
            embed = discord.Embed(
				title=f"{interaction.guild.name} Support System",
				description="Welcome to our support system!\n\nPlease make sure to read our guidelines below before opening a help request. If you would like to open one, please interact with the dropdown menu below.\n\n Categories available for help are listed below:\n\n",
				color=0x7a2db9
			)
            
            embed.add_field(name="👮 Discord Staff", value="Contact our Discord staff to report users breaking our rules here. If you have a general question regarding this Discord server, you may open it under this category.", inline=False)
            embed.add_field(name="🎮 SCP:SL Staff", value="For player reports, preferably report them via the player list by pressing `N` and the `⚠️` icon. For general inquiries regarding our SCP:SL servers, you may open it under this category.", inline=False)
            embed.add_field(name="🔨 Appeals Requests", value="You may create an appeal request for our Discord or game servers here. Appeals will only be accepted if a moderator has made a mistake.", inline=False)
            embed.set_thumbnail(url="https://media.tenor.com/Vn_Bm9z2-4EAAAAM/a-hat-in-time-hat-in-time.gif")

            embed2 = discord.Embed(
                title="🚨 Help Request Guidelines",
                description="Before opening a support request, please make sure to **read** the guidelines below. These guidelines may change at any given time without notice.",
                timestamp=datetime.now(),
                color=discord.Color.red()
            )
            embed2.add_field(name="Duplicate Requests", value="Duplicate requests under the same user will be rejected automatically. Bypassing this with another account will result in that account getting blacklisted.", inline=False)
            embed2.add_field(name="Violations of our Rules or the Discord Terms of Service", value="Help requests will still fall under our server rules with some exceptions. We are obligated to report Discord ToS violations as well.", inline=False)
            embed2.add_field(name="Joke Requests", value="Opening a joke request will result in your request being closed and/or you being blacklisted from the request system indefinitely. Bypassing this would result in moderation of your account.", inline=False)
            embed2.add_field(name="Non-related Requests", value="Requests that are not related to our servers in any way may be closed based on staff discretion.", inline=False)
            embed2.set_footer(text="🎩 Hat Kid")
            embed2.set_thumbnail(url="https://media.tenor.com/HSPuoBtwg8UAAAAM/hat-in-time-run.gif")

            return [embed, embed2]
        
        panel_embeds = make_embed()

        if panel_message_id:
            try:
                panel_msg = await panel_ch.fetch_message(panel_message_id)
                await panel_msg.delete()
            except discord.NotFound:
                new_panel_message = await panel_ch.send(embeds=panel_embeds, view=TicketView())
                
                async with sconfg.panel_cfg() as panel:
                    panel["message_id"] = new_panel_message.id

                await send_error(interaction, "The previous panel was not found. A new one has been sent.")
            except discord.Forbidden:
                await send_error(interaction, "Unable to delete the panel due to missing permissions.")
            except Exception as e:
                cog.log.warning(f"**`⚠️ Error`**: Failed to delete old panel: {e}")

        try:
            new_panel_message = await panel_ch.send(embeds=panel_embeds, view=TicketView())

            async with sconfg.panel_cfg() as panel:
                panel["message_id"] = new_panel_message.id
                
            await send_success(interaction, "The panel has been successfully sent!")
        except Exception as e:
            await send_error(interaction, f"Unable to send the panel: `{e}`")

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message

# - Views -

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

class SetupView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member):
        super().__init__(timeout=60)
        self.message = None
        self.author_id = author.id
        self.add_item(SetupChannelsButton())
        self.add_item(SetupRolesButton())
        self.add_item(SetupSendPanelButton())
        self.add_item(SetupResetButton())

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await send_blocked(interaction, "Only the person who initiated this command can change the settings.", True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

# - Modals -

class CloseTicketModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Ticket Closure", timeout=None)
        self.close_reason = discord.ui.TextInput(label="Why are you closing the ticket?", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.close_reason)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog: 
            return
        
        await interaction.response.send_message("⌛ Creating transcript and closing ticket...", ephemeral=True)

        sconfg = cog.config.guild(interaction.guild)
        channel = interaction.channel
        channels = await sconfg.ticket_channels()
        closer = interaction.user

        logs_channel_id = channels.get("log_channel")
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
        self.request_type = discord.ui.Label(
            text="What type of request are you making today?",
            component=discord.ui.Select(
                required=True,
                placeholder="Select a Category",
                options=[
                    discord.SelectOption(label="User Report", description="Report a user in Discord server", value="User Report"),
                    discord.SelectOption(label="General Inquiry", description="General questions regarding our Discord server", value="General Inquiry")
                ]
            )
        )

        self.request_title = discord.ui.Label(
            text="What is your request?",
            description="Please describe your request in a few words.",
            component=discord.ui.TextInput(
                required=True,
                placeholder="What can we help with you today?",
                style=discord.TextStyle.short,
                min_length=10
            )
        )

        self.request_description = discord.ui.Label(
            text="Tell us more about your request!",
            description="Please provide us as much information so we're able to assist you better.",
            component=discord.ui.TextInput(
                required=True,
                placeholder="Describe your request here!",
                style=discord.TextStyle.paragraph,
                min_length=10,
                max_length=400
            )
        )

        self.add_item(self.request_type)
        self.add_item(self.request_title)
        self.add_item(self.request_description)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog: return

        sconfg = cog.config.guild(interaction.guild)
        categories = await sconfg.ticket_categories()
        roles = await sconfg.ticket_roles()
        category_id = categories.get("discord")
        staff_role_id = roles.get("discord_staff")

        await create_ticket(
            interaction, 
            "Discord",
            self.request_type.component.values[0],
            self.request_title.component.value, 
            self.request_description.component.value,
            category_id, # category id
            staff_role_id, # staff id
            0x5865f2, 
            cog
        )

class GameModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Game Staff Help Request", timeout=None)
        self.request_type = discord.ui.Label(
            text="What type of request are you making today?",
            component=discord.ui.Select(
                required=True,
                placeholder="Select a Category",
                options=[
                    discord.SelectOption(label="Connection Issues", description="Cannot connect to SCP:SL servers, VPN Block, etc.", value="Connection Issues"),
                    discord.SelectOption(label="Player Report", description="Report a player in our SCP:SL servers", value="Player Report"),
                    discord.SelectOption(label="General Inquiry", description="General questions regarding our SCP:SL servers", value="General Inquiry")
                ]
            )
        )

        self.request_title = discord.ui.Label(
            text="What is your request?",
            description="Please describe your request in a few words.",
            component=discord.ui.TextInput(
                required=True,
                placeholder="What can we help with you today?",
                style=discord.TextStyle.short,
                min_length=10
            )
        )

        self.request_description = discord.ui.Label(
            text="Tell us more about your request!",
            description="Please provide us as much information so we're able to assist you better.",
            component=discord.ui.TextInput(
                required=True,
                placeholder="Describe your request here!",
                style=discord.TextStyle.paragraph,
                min_length=10,
                max_length=400
            )
        )

        self.add_item(self.request_type)
        self.add_item(self.request_title)
        self.add_item(self.request_description)
    
    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
        if not cog: return

        sconfg = cog.config.guild(interaction.guild)
        categories = await sconfg.ticket_categories()
        roles = await sconfg.ticket_roles()
        category_id = categories.get("scpsl")
        staff_role_id = roles.get("game_staff")

        await create_ticket(
            interaction, 
            "SCP:SL",
            self.request_type.component.values[0],
            self.request_title.component.value, 
            self.request_description.component.value,
            category_id, # category id
            staff_role_id, # staff id
            0x3498db, 
            cog
        )

class AppealModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Appeal Request", timeout=None)
        self.appeal_platform = discord.ui.Label(
            text="What is the platform you were moderated on?",
            description="Please select the platform you were moderated on.",
            component=discord.ui.Select(
                required=True,
                placeholder="Select a Platform",
                options=[
                    discord.SelectOption(label="Steam", value="Steam"),
                    discord.SelectOption(label="Discord", value="Discord"),
                    discord.SelectOption(label="Other", value="Other Platform")
                ]
            )
        )

        self.appeal_user = discord.ui.Label(
            text="What is your Account ID (or User ID)?",
            description="Discord: Right click account → Copy ID | Steam: Paste profile URL in steamid.io → Copy SteamID64",
            component=discord.ui.TextInput(
                required=True,
                placeholder="ID of the account that was moderated",
                style=discord.TextStyle.short,
                min_length=15,
                max_length=22
            )
        )

        self.appeal_info = discord.ui.Label(
            text="Relevant Information",
            description="Provide details that support your appeal.",
            component=discord.ui.TextInput(
                required=True,
                placeholder="Please explain your case",
                style=discord.TextStyle.paragraph,
                min_length=40,
                max_length=400
            )
        )

        self.add_item(self.appeal_platform)
        self.add_item(self.appeal_user)
        self.add_item(self.appeal_info)

    async def on_submit(self, interaction: discord.Interaction): 
        cog = interaction.client.get_cog("TicketSystem")
        if not cog: return

        await create_ban_appeal(interaction, self.appeal_platform.component.values[0], self.appeal_user.component.value, self.appeal_info.component.value, cog)

class FinishAppealModal(discord.ui.Modal):
    def __init__(self, decision: str):
        super().__init__(title="Finalize Appeal Decision", timeout=None)
        self.decision = decision
        self.finish_appeal = discord.ui.TextInput(label=f"Reason for {decision.lower()}ing appeal", placeholder="Provide a detailed response.", required=True, style=discord.TextStyle.paragraph)
        self.add_item(self.finish_appeal)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("TicketSystem")
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
            new_embed.description = f"Appeal `{appeal_id}` has been accepted. The appeal is now finalized."
        else:
            new_embed.title = "🚫 Appeal Rejected"
            new_embed.color = discord.Color.red()
            new_embed.description = f"Appeal `{appeal_id}` has been denied. The appeal is now finalized."
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

        await interaction.edit_original_response(content=f"**`✅ Success`**: Appeal `{appeal_id}` has been finalized.")

class SetupChannelsModal(discord.ui.Modal):
    def __init__(self, setup_msg: discord.Message):
        super().__init__(title="Ticket System Channels Setup", timeout=None)
        self.setup_msg = setup_msg

        self.panel_channel = discord.ui.Label(
            text="Where should the ticket panel go?",
            description="Tickets will be created by users in this channel.",
            component= discord.ui.ChannelSelect(
                placeholder="Select a channel",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text]
            )
        )
        
        self.transcript_channel = discord.ui.Label(
            text="Where should the log channel be?",
            description="All transcripts and system logs will be sent here.",
            component= discord.ui.ChannelSelect(
                placeholder="Select a channel",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text]
            )
        )

        self.appeal_channel = discord.ui.Label(
            text="Where should appeals go?",
            description="All appeals will be sent here for staff to make a decision.",
            component= discord.ui.ChannelSelect(
                placeholder="Select a channel",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text]
            )
        )

        self.discord_ticket_category = discord.ui.Label(
            text="What category should Discord tickets be made?",
            description="New Discord tickets will open under this category.",
            component= discord.ui.ChannelSelect(
                placeholder="Select a category",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.category]
            )
        )

        self.scpsl_ticket_category = discord.ui.Label(
            text="What category should SCP:SL tickets be made?",
            description="New SCP:SL tickets will open under this category.",
            component= discord.ui.ChannelSelect(
                placeholder="Select a category",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.category]
            )
        )

        self.add_item(self.panel_channel)
        self.add_item(self.transcript_channel)
        self.add_item(self.appeal_channel)
        self.add_item(self.discord_ticket_category)
        self.add_item(self.scpsl_ticket_category)

    async def on_submit(self, interaction: discord.Interaction): 
        cog = interaction.client.get_cog("TicketSystem")
        if not cog: return

        sconfg = cog.config.guild(interaction.guild)
        transcript_channel = parse_id(self.transcript_channel.component.values[0])
        appeal_channel = parse_id(self.appeal_channel.component.values[0])
        panel_channel = parse_id(self.panel_channel.component.values[0])
        discord_cat = parse_id(self.discord_ticket_category.component.values[0])
        game_cat = parse_id(self.scpsl_ticket_category.component.values[0])

        try:
            async with sconfg.ticket_channels() as channels:
                channels["log_channel"] = transcript_channel
                channels["appeal_logs"] = appeal_channel
            
            async with sconfg.panel_cfg() as panel:
                panel["channel"] = panel_channel

            async with sconfg.ticket_categories() as categories:
                categories["discord"] = discord_cat
                categories["scpsl"] = game_cat

            cog.log.info("Channels were successfully set!")
            new_embed = await cog.get_setup_embed(interaction.guild)
            await self.setup_msg.edit(embed=new_embed)
            await send_success(interaction, "Channels configured successfully!")
        except Exception as e:
            cog.log.warning(f"Failed to set channels: {e}")
            await send_warning(interaction, f"Channels configured successfully but the setup embed wasn't updated: `{e}`")
            
class SetupRolesModal(discord.ui.Modal):
    def __init__(self, setup_msg: discord.Message):
        super().__init__(title="Ticket System Roles Setup", timeout=None)
        self.setup_msg = setup_msg

        self.modmail_access_role = discord.ui.Label(
            text="What role should have standard access?",
            description="This role will give basic permissions.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.modmail_mgmt_access_role = discord.ui.Label(
            text="What role should have management access?",
            description="This role will be given advanced permissions.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.discord_ping_role = discord.ui.Label(
            text="Who is responsible for Discord Tickets?",
            description="This role will be notified for these tickets.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.scpsl_ping_role = discord.ui.Label(
            text="Who is responsible for SCP:SL Tickets?",
            description="This role will be notified for these tickets.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.appeal_team_role = discord.ui.Label(
            text="Who is responsible for appeals?",
            description="This role will be notified as well as decide.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.add_item(self.modmail_access_role)
        self.add_item(self.modmail_mgmt_access_role)
        self.add_item(self.discord_ping_role)
        self.add_item(self.scpsl_ping_role)
        self.add_item(self.appeal_team_role)

    async def on_submit(self, interaction: discord.Interaction): 
        cog = interaction.client.get_cog("TicketSystem")
        if not cog: return

        sconfg = cog.config.guild(interaction.guild)
        modmail_role = parse_id(self.modmail_access_role.component.values[0])
        mgmt_role = parse_id(self.modmail_mgmt_access_role.component.values[0])
        discord_role = parse_id(self.discord_ping_role.component.values[0])
        scpsl_role = parse_id(self.scpsl_ping_role.component.values[0])
        appeal_role = parse_id(self.appeal_team_role.component.values[0])

        try:
            async with sconfg.ticket_roles() as roles:
                roles["modmail_access"] = modmail_role
                roles["modmail_mgmt"] = mgmt_role
                roles["discord_staff"] = discord_role
                roles["game_staff"] = scpsl_role
                roles["appeal_team"] = appeal_role

            cog.log.info("Roles were successfully set!")
            
            new_embed = await cog.get_setup_embed(interaction.guild)
            await self.setup_msg.edit(embed=new_embed)
            await send_success(interaction, "Roles configured successfully!")
        except Exception as e:
            cog.log.warning(f"Failed to set up roles: {e}")
            await send_warning(interaction, f"Roles configured successfully but the setup embed wasn't updated: `{e}`")

class SetupResetModal(discord.ui.Modal):
    def __init__(self, setup_msg: discord.Message):
        super().__init__(title="Resetting Config", timeout=None)
        self.setup_msg = setup_msg

        self.question = discord.ui.Label(
            text="Are you sure you want to reset?",
            description="Choose either yes or no.",
            component=discord.ui.Select(
                required=True,
                placeholder="Select an option",
                options=[
                    discord.SelectOption(label="✅ Yes", value="yes"),
                    discord.SelectOption(label="❌ No", value="no"),
                ]
            )
        )
        self.add_item(self.question)

    async def on_submit(self, interaction):
        cog = interaction.client.get_cog("TicketSystem")

        if self.question.component.values[0] == "yes":
            await cog.config.guild(interaction.guild).clear()
            cog.log.info("TicketSystem settings (config) was reset.")
        else:
            await interaction.response.send_message("❌ Reset aborted.")

        try:
            new_embed = await cog.get_setup_embed(interaction.guild)
            await self.setup_msg.edit(embed=new_embed)
            await send_success(interaction, "Settings reset successfully!")
        except Exception as e:
            await send_warning(interaction, f"Settings reset successfully but the setup embed wasn't updated: `{e}`")