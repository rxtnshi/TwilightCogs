import discord
import logging

from datetime import datetime
from .db_handler import db
from discord import ui
from .creation_handler import Ticket, Appeal, Category, Blacklist
from .error_handler import send_blocked, send_error, send_success

log = logging.getLogger("twilightcogs.ticketsv2")
def disable_all(item): # not my code, since idk how to disable buttons in containers
            if isinstance(item, ui.ActionRow): # understand this code since a container has children within them, then check for an ActionRow
                for sub in item.children: # for every item in the actionrow, if it is a button have it disabled
                    if isinstance(sub, (ui.Button)):
                        sub.disabled = True
            if hasattr(item, "children"): # recursive method to disable every child
                for sub in item.children:
                    disable_all(sub)

# -- Views/LayoutViews -- #
class TicketInfo(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.display = ui.TextDisplay("⌛ Generating panel...")

        self.add_item(self.display)

    def set_data(self, author: discord.Member | discord.User, title: str, description: str, ticket_id: str):
        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🛈 Request Information"),
                ui.TextDisplay(f"{author.mention} ({author.id}) has created a support ticket.\n\n"),
                ui.TextDisplay(f"-# Thank you for contacting us. A member of our staff team will get to you shortly."),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/hat-kid-wave.gif")
            ),
            ui.TextDisplay("## Title"),
            ui.TextDisplay(f"{title}\n\n"),
            ui.TextDisplay("## Description"),
            ui.TextDisplay(f"{description}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(f"### Action Center"),
            ui.ActionRow(CloseTicket(ticket_id))
        )
        self.add_item(container)
        self.remove_item(self.display)
        return self

class LogInfo(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.display = ui.TextDisplay("⌛ Generating panel...")

        self.add_item(self.display)
    
    def set_data(self, author: discord.Member | discord.User, type: str, title: str, description: str, ticket_channel: discord.TextChannel):
        self.author = author
        self.type = type
        self.title = title
        self.description = description
        self.channel = ticket_channel

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🚨 New Support Request!"),
                ui.TextDisplay(f"A new `{self.type}` request was opened by {self.author.mention}. Please review it as soon as possible and notify appropriate staff if needed."),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/clipboard.png")
            ),
            ui.TextDisplay("### Request Title"),
            ui.TextDisplay(f"{self.title}"),
            ui.TextDisplay("### Request Description"),
            ui.TextDisplay(f"{self.description}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(
                ui.Button(
                    label="Access Ticket",
                    style=discord.ButtonStyle.link,
                    url=self.channel.jump_url
                )
            )
        )

        self.add_item(container)
        self.remove_item(self.display)
        return self

class AppealPanel(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.display = ui.TextDisplay("⌛ Generating panel...")

        self.add_item(self.display)

    def generate(self, type: str, appeal_id: str, user: discord.Member, moderated_account: str, platform: str, moderated_reason: str, appeal_info: str):
        self.appeal_id = appeal_id
        self.user = user
        self.platform = platform
        self.moderated_account = moderated_account
        self.moderated_reason = moderated_reason
        self.appeal_info = appeal_info
        
        match type:
            case 'log':
                container = ui.Container(
                    ui.Section(
                        ui.TextDisplay(f"## 🚨 Appeal `{self.appeal_id}`Submitted"),
                        ui.TextDisplay(f"An appeal was submitted by {self.user.mention}. The information below has been provided and review any available evidence to process this appeal."),
                        accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/pending.png")
                    ),
                    ui.TextDisplay("### Moderated Account Info"),
                    ui.TextDisplay(f"**Platform**: {self.platform}\n**Account ID**: {self.moderated_account}"),
                    ui.TextDisplay("### Appeal Info"),
                    ui.TextDisplay(f"{self.moderated_reason} - {self.appeal_info}"),
                    ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
                    ui.ActionRow(AcceptAppeal(self.appeal_id, self.user), DenyAppeal(self.appeal_id, self.user)),
                    accent_color=discord.Color.yellow(),
                    id="3"
                )
            case 'receipt':
                container = ui.Container(
                    ui.Section(
                        ui.TextDisplay(f"## 🚨 Appeal `{self.appeal_id}`Submitted"),
                        ui.TextDisplay(f"Your appeal has been submitted to staff and is now in review. Please allow up to **3-5 business days** for the server staff to process your appeal. Attempts to make several appeals will result in a blacklist from the system and your appeal will be rejected."),
                        accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/pending.png")
                    ),
                    ui.TextDisplay("### Moderated Account Info"),
                    ui.TextDisplay(f"**Platform**: {self.platform}\n**Account ID**: {self.moderated_account}"),
                    ui.TextDisplay("### Appeal Info"),
                    ui.TextDisplay(f"{self.moderated_reason} - {self.appeal_info}"),
                    accent_color=discord.Color.yellow()
                )

        self.add_item(container)
        self.remove_item(self.display)
        return self

class DecisionAppeal(ui.LayoutView):
    def __init__(self, type: str, accepted: bool, appeal_id: str, staff_member: discord.Member, reason: str, create_time: int, appealer: discord.Member):
        super().__init__(timeout=None)
        self.accepted = accepted
        self.appeal_id = appeal_id
        self.staff = staff_member
        self.reason = reason
        self.create_time = create_time
        self.appealer = appealer

        decision = f"## ✅ Appeal `{self.appeal_id}` Accepted" if self.accepted is True else f"## 🚫 Appeal `{self.appeal_id}` Rejected"
        decision_desc = "Your appeal has been accepted. Apologies for the inconvenience." if self.accepted is True else "Unfortunately, your appeal has been rejected. Please review the rejection reason below for further information."
        accent_color = discord.Color.green() if self.accepted is True else discord.Color.red()
        icon = ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/approved.png") if self.accepted is True else ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/denied.png")
        decision_time = int(datetime.now().timestamp())

        match type:
            case 'receipt':
                container = ui.Container(
                ui.Section(
                    ui.TextDisplay(f"{decision}"),
                    ui.TextDisplay(f"{decision_desc}"),
                    accessory=icon
                ),
                ui.TextDisplay(f"### __Information__"),
                ui.TextDisplay(f"**Date Submitted**\n<t:{self.create_time}:F>\n\n"),
                ui.TextDisplay(f"**Decision Time**\n<t:{decision_time}:F>\n\n"),
                ui.TextDisplay(f"**The server staff have provided the following reason for this decision:**"),
                ui.TextDisplay(f"{reason}\n\n"),
                accent_color=accent_color
                )
            case 'log':
                container = ui.Container(
                ui.Section(
                    ui.TextDisplay(f"{decision}"),
                    ui.TextDisplay(f"This appeal has been resolved by {staff_member.mention}. The details are below."),
                    accessory=icon
                ),
                ui.TextDisplay(f"### __Information__"),
                ui.TextDisplay(f"**Appealer**\n{self.appealer.mention}\n\n"),
                ui.TextDisplay(f"**Staff Member**\n{staff_member.mention}\n\n"),
                ui.TextDisplay(f"**Date Submitted**\n<t:{self.create_time}:F>\n\n"),
                ui.TextDisplay(f"**Decision Time**\n<t:{decision_time}:F>\n\n"),
                ui.TextDisplay(f"**Reason for decision**"),
                ui.TextDisplay(f"{reason}\n\n"),
                accent_color=accent_color
                )
        
        self.add_item(container)

class SupportPanel(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
        self.display = ui.TextDisplay("⌛ Generating panel...")

        self.add_item(self.display)
    
    def generate(self, guild: discord.Guild, description: str | None, categories: list[dict], appeals_enabled: bool, tickets_enabled: bool, panel_channel: int):
        self.guild = guild
        self.description = description

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 📫 {self.guild}'s Support Center"),
                ui.TextDisplay(f"{f'{self.description}' if self.description else 'Please be respectful when contacting staff!'}"),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/hat-kid-idle.gif"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### Open a Support Request Here!"),
            ui.TextDisplay("-# Disclaimer: Please allow some ample time for server staff to respond to your query.")
        )
        if tickets_enabled is True:
            container.add_item(ui.ActionRow(TicketSelectMenu(categories, appeals_enabled, panel_channel)))
        else:
            container.add_item(ui.TextDisplay("`🚫 Sorry, our support system is currently closed at the moment. Please check back later.`"))

        self.add_item(container)
        self.remove_item(self.display)
        return self

class SettingsPanel(ui.LayoutView):
    def __init__(self, interaction: discord.Interaction, author: discord.Member | discord.User | None, message: discord.Message | None):
        super().__init__(timeout=90)
        self.interaction = interaction
        self.author = author
        self.message = message or interaction.message

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user and interaction.user.id == self.author:
            return True
        else:
            return False, await send_blocked(interaction, "Only the person who initiated this command can change the settings.", True)
        
    async def on_timeout(self): 
        for child in self.children:
            disable_all(child)

        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                log.warning(f"Failed to edit view on timeout: {e}")

    @staticmethod
    async def get_settings(interaction: discord.Interaction):
        self = SettingsPanel(interaction, interaction.user, interaction.message)
        self.author = self.interaction.user.id

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        data = await confg.all()

        tickets_enabled = data.get("tickets_enabled")
        appeals_enabled = data.get("appeals_enabled")
        pings_enabled = data.get("pings_enabled")
        roles = data.get("ticket_roles") or {}
        channels = data.get("ticket_channels") or {}
        panel_cfg = data.get("panel_cfg") or {}

        staff_roles = []
        for role in (roles.get("staff_roles") or []):
            if role is not None:
                staff_roles.append(f"<@&{role}>")

        staff_roles_txt = ",".join(staff_roles) if staff_roles else "`None set`"

        is_setup = bool(roles and channels and panel_cfg)

        modmail_access = f"<@&{roles.get('modmail_access')}>" if roles.get('modmail_access') else "`None set`"
        modmail_mgmt = f"<@&{roles.get('modmail_mgmt')}>" if roles.get('modmail_mgmt') else "`None set`"
        appeals_access = f"<@&{roles.get('appeals_access')}>" if roles.get('appeals_access') else "`None set`"
        log_channel = f"<#{channels.get('log_channel')}>" if channels.get('log_channel') else "`None set`"
        appeal_logs = f"<#{channels.get('appeal_logs')}>" if channels.get('appeal_logs') else "`None set`"
        panel_channel = f"<#{panel_cfg.get('channel')}>" if panel_cfg.get('channel') else "`None set`"

        panel_ch = interaction.guild.get_channel(panel_cfg.get('channel')) or None
        panel_msg_id = panel_cfg.get("message_id")
        if panel_ch:
            panel_msg = await panel_ch.fetch_message(panel_msg_id) or None
            panel_link = panel_msg.jump_url if panel_msg else None
    
        container = ui.Container(
            ui.Section(
                ui.TextDisplay("# ⚙️ Settings"),
                ui.TextDisplay("Here are your current settings for your server.\n## Configuration Status"),
                ui.TextDisplay(f"`{'`✅ Configured`' if is_setup else '`❌ Not fully configured`'}`"),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/settings_cog.png")
            ),
            ui.TextDisplay("### __Ticket Statuses__"),
            ui.TextDisplay(
                f"`Tickets Creation`: {'`✅ Enabled`' if tickets_enabled is True else '`❌ Disabled`'}\n"
                f"`Appeals`: {'`✅ Enabled`' if appeals_enabled is True else '`❌ Disabled`'}\n"
                f"`Staff Pings`: {'`✅ Enabled`' if pings_enabled is True else '`❌ Disabled`'}\n"
            ),
            ui.TextDisplay("### __Configured Roles__"),
            ui.TextDisplay(
                f"`Standard access`: {modmail_access}\n"
                f"`Management access`: {modmail_mgmt}\n"
                f"`Appeals access`: {appeals_access}\n"
                f"`Staff Roles`: {staff_roles_txt}\n"
            ),
            ui.TextDisplay("### __Configured Channels__"), 
            ui.TextDisplay(
                f"`Ticket Logs`: {log_channel}\n"
                f"`Appeals`: {appeal_logs}\n"
            ),
            ui.TextDisplay("### __Panel Channels__"),
            ui.TextDisplay(f"`Panel Channel`: {panel_channel}\n"),
            ui.TextDisplay(f"[Link to panel]({panel_link})" if panel_msg else "`No panel message set`"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### 💻 Action Center"),
            ui.TextDisplay("-# Channels & Categories"),
            ui.ActionRow(ConfigChannels(), ConfigRoles(), AddCategories(), DelCategories()),
            ui.TextDisplay("-# Miscellaneous"),
            ui.ActionRow(SendPanel(), ResetConfig(), SetDescription())
        )
        self.add_item(container)
        return self
    
    async def update_view(self, interaction: discord.Interaction, message: discord.Message | None):
        view = await self.get_settings(interaction)
        setup_msg = message or self.message or interaction.message
        try:
            if setup_msg:
                await setup_msg.edit(view=view)
        except Exception as e:
            await send_error(interaction, f"Cannot edit view: {e}")
    
class Receipt(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)

    def set_data(self, title: str, requester: discord.Member, closer: discord.Member, open_reason: str, close_reason: str, open_time: int, close_time: int):
        self.title = title
        self.requester = requester
        self.closer = closer
        self.open_reason = open_reason
        self.close_reason = close_reason
        self.open_time = open_time
        self.close_time = close_time

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🗒️ Transcript for `{self.title}`"),
                ui.TextDisplay(f"Thank you for contacting us. Here is the transcript for `{self.title}`. The ticket information can be found below."),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### Ticket Information"),
            ui.TextDisplay(f"**Requester**: {self.requester.mention} ({self.requester.id})"),
            ui.TextDisplay(f"**Closed By**: {self.closer.mention} ({self.closer.id})\n\n"),
            ui.TextDisplay(f"**Opened at**: <t:{self.open_time}:F>"),
            ui.TextDisplay(f"**Closed at**: <t:{self.close_time}:F>\n\n"),
            ui.TextDisplay(f"**Request Description**: {self.open_reason}"),
            ui.TextDisplay(f"**Close Reason**: {self.close_reason}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### Transcript"),
            ui.TextDisplay("Please download the attached file to view your transcript."),
            id="5"
        )
        self.add_item(container)
        return self

class LogsReceipt(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=None)
    
    def set_data(self, title: str, requester: discord.Member, closer: discord.Member, open_reason: str, close_reason: str, open_time: int, close_time: int):
        self.title = title
        self.requester = requester
        self.closer = closer
        self.open_reason = open_reason
        self.close_reason = close_reason
        self.open_time = open_time
        self.close_time = close_time

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🗒️ Transcript for {self.title}"),
                ui.TextDisplay(f"Here is the transcript for `{self.title}`. The ticket information can be found below."),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### Ticket Information"),
            ui.TextDisplay(f"**Requester**: {self.requester.mention} ({self.requester.id})"),
            ui.TextDisplay(f"**Closed By**: {self.closer.mention} ({self.closer.id})\n\n"),
            ui.TextDisplay(f"**Opened at**: <t:{self.open_time}:F>"),
            ui.TextDisplay(f"**Closed at**: <t:{self.close_time}:F>\n\n"),
            ui.TextDisplay(f"**Request Description**: {self.open_reason}"),
            ui.TextDisplay(f"**Close Reason**: {self.close_reason}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### Transcript"),
            ui.TextDisplay("Please download the attached file to view the transcript."),
            id="6"
        )

        self.add_item(container)
        return self

# -- Modals -- #
class TicketQuestionaire(ui.Modal):
    def __init__(self, category_name: str, category_id: int, team_id: int):
        super().__init__(title=f"✍️ Opening a Request", timeout=None)
        self.cat_name = category_name
        self.category = category_id
        self.team = team_id

        self.ticket_title = ui.Label(
            text="Request Title",
            description="In short, how can we help you today?",
            component=ui.TextInput(
                placeholder="I need help!",
                min_length=1,
                max_length=100,
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.ticket_desc = ui.Label(
            text="Request Description",
            description="Describe your request in a few sentences or so.",
            component=ui.TextInput(
                placeholder="I need help with something!",
                min_length=5,
                max_length=2000,
                style=discord.TextStyle.paragraph,
                required=True
            )
        )

        self.add_item(self.ticket_title)
        self.add_item(self.ticket_desc)

    async def on_submit(self, interaction: discord.Interaction):
        category = await interaction.guild.fetch_channel(self.category)
        title = self.ticket_title.component.value
        description = self.ticket_desc.component.value

        ticket = Ticket(self.cat_name, self.category, title, description, self.team)
        await ticket.create(interaction, category)

class CloseTicketQuestionaire(ui.Modal):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title=f"🔒 Closing Ticket")

        self.channel = channel
        self.reason = ui.Label(
            text="Why are you closing this ticket?",
            description=f"You are closing {self.channel.name}. Please give a reason why otherwise no reason will be given.",
            component=ui.TextInput(
                placeholder="Enter a reason",
                default="No reason given.",
                style=discord.TextStyle.paragraph
            )
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.component.value
        view = ui.LayoutView.from_message(interaction.message)
        await Ticket.close(self, interaction, reason)
        for child in view.children:
            disable_all(child)

class OpenAppeal(ui.Modal):
    def __init__(self):
        super().__init__(title="Opening Appeal", timeout=None)
        self.platform = ui.Label(
            text="Provide the platform of the account",
            description="Please type in the platform you were moderated on as it will pinpoint your account info.",
            component=ui.TextInput(
                placeholder="Platform (e.g Discord, Minecraft, etc.)",
                min_length=1,
                max_length=50,
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.moderated_account = ui.Label(
            text="Provide the ID of the account",
            description="Preferably please give us your account name and its ID. A profile link is also allowed.",
            component=ui.TextInput(
                placeholder="Account Details",
                min_length=5,
                max_length=100,
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.moderated_reason = ui.Label(
            text="Provide the reason for moderation",
            description="Please give us the exact reason you were moderated for - telling us makes this process easier.",
            component=ui.TextInput(
                placeholder="Reason for moderation",
                min_length=5,
                max_length=100,
                style=discord.TextStyle.paragraph,
                required=True
            )
        )

        self.information = ui.Label(
            text="Provide relevant evidence/information",
            description="Please provide us anything that will help us with your case.",
            component=ui.TextInput(
                placeholder="Include info here",
                min_length=10,
                max_length=1000,
                style=discord.TextStyle.paragraph,
                required=True
            )
        )

        self.add_item(self.platform)
        self.add_item(self.moderated_account)
        self.add_item(self.moderated_reason)
        self.add_item(self.information)

    async def on_submit(self, interaction: discord.Interaction):
        platform = self.platform.component.value
        account = self.moderated_account.component.value
        reason = self.moderated_reason.component.value
        info = self.information.component.value

        appeal_instance = Appeal(platform, account, reason, info)
        await appeal_instance.create(interaction)

class AppealDecision(ui.Modal):
    def __init__(self, decision: str, id: str, user: discord.Member | discord.User):
        self.a_id = id
        self.decision = decision
        self.user = user
        
        super().__init__(title=f"{self.decision}ing Appeal", timeout=None)

        options = [discord.SelectOption(
                        label="Custom Reason",
                        description="Provide a reason of your own for this decision",
                        value="custom-reason"
        )]

        if self.decision == "Accept":
            options.append(
                discord.SelectOption(
                        label="Evidence Supports Decision",
                        description="The evidence provided by the appealer supports this decision.",
                        value="The evidence provided by the appealer supports this decision."
                ),
            )
        else:
            options.append(
                discord.SelectOption(
                        label="Lack of Evidence",
                        description="The evidence provided is not sufficient to make a decision",
                        value="The evidence provided is not sufficient to make a decision"
                )
            )
            options.append(
                discord.SelectOption(
                    label="Non-appealable Offense",
                    description="This offense is non-appealable",
                    value="This offense is non-appealable"
                )
            )

        self.prefined_reasons = ui.Label(
            text="Predefined Reasons",
            description="You can select a predefined reason or choose 'Custom Reason' for your own.",
            component=ui.Select(
                max_values=1,
                required=True,
                options=options
            )
        )

        self.reason = ui.Label(
            text="Custom Reason",
            description="Please provide any addition info or your own reason for this decision.",
            component=ui.TextInput(
                style=discord.TextStyle.paragraph,
                min_length=10,
                max_length=2000,
                required=False
            )
        )
        
        self.add_item(self.prefined_reasons)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        decision = self.decision.lower()
        value = self.prefined_reasons.component.values[0]
        custom_reason = self.reason.component.value
        reason_text = f"{value} - {custom_reason}" if custom_reason else f"{value}"

        if value == "custom-reason":
            if not custom_reason:
                reason_text = "No reason provided."
            else:
                reason_text = f"{custom_reason}"
        
        if decision == "accept":
            await Appeal.close(self, interaction, True, reason_text, self.a_id, self.user)
        else:
            await Appeal.close(self, interaction, False, reason_text, self.a_id, self.user)

class ConfigChannelsModal(ui.Modal):
    def __init__(self, log_channel, appeal_channel, panel_channel):
        super().__init__(title=f"Channels Setup", timeout=None)
        self.setup_msg: discord.Message

        self.log_channel = ui.Label(
            text="Where should be the logs channel be?",
            description="This is where transcripts and new ticket notifications go.",
            component=ui.ChannelSelect(
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
                default_values=[log_channel] if log_channel else None
            )
        )
        
        self.appeal_channel = ui.Label(
            text="Where should be the appeals log be?",
            description="This is where appeals get sent and decisions are made here.",
            component=ui.ChannelSelect(
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
                default_values=[appeal_channel] if appeal_channel else None
            )
        )

        self.panel_channel = ui.Label(
            text="Where should the panel go?",
            description="This is where user can create tickets from.",
            component=ui.ChannelSelect(
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1,
                default_values=[panel_channel] if appeal_channel else None
            )
        )

        self.add_item(self.log_channel)
        self.add_item(self.appeal_channel)
        self.add_item(self.panel_channel)

    async def on_submit(self, interaction: discord.Interaction):
        log_ch = self.log_channel.component.values[0].id
        appeal_ch = self.appeal_channel.component.values[0].id
        panel_ch = self.panel_channel.component.values[0].id

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        await confg.ticket_channels.set({
            "log_channel": log_ch,
            "appeal_logs": appeal_ch
        })
        await confg.panel_cfg.set({
            "channel": panel_ch,
            "message_id": None
        })

        await interaction.response.defer()
        await SettingsPanel(interaction.user, self.setup_msg).update_view(interaction, message=self.setup_msg)

class ConfigRolesModal(ui.Modal):
    def __init__(self, std_acc, mgm_acc, appeals_acc, staff_roles):
        super().__init__(title=f"Roles Setup", timeout=None)
        self.setup_msg: discord.Message | None

        self.std_acc = ui.Label(
            text="What should give standard access?",
            description="This role will give access to basic ticket commands.",
            component=ui.RoleSelect(
                min_values=1,
                max_values=1,
                default_values=[std_acc] if std_acc else None
            )
        )
        
        self.mgm_acc = ui.Label(
            text="What should give management access?",
            description="This role will give access to elevated ticket commands.",
            component=ui.RoleSelect(
                min_values=1,
                max_values=1,
                default_values=[mgm_acc] if mgm_acc else None
            )
        )

        self.appeals_acc = ui.Label(
            text="What should give appeals access?",
            description="This role will give access to making appeal decisions and be able to see the channel.",
            component=ui.RoleSelect(
                min_values=1,
                max_values=1,
                default_values=[appeals_acc] if appeals_acc else None
            )
        )

        self.staff_roles = ui.Label(
            text="Please designate your server staff roles!",
            description="You should add roles that are for your staff, and then have them run /staff register to gain access.",
            component=ui.RoleSelect(
                min_values=0,
                max_values=25,
                default_values=staff_roles if staff_roles else None
            )
        )

        self.add_item(self.std_acc)
        self.add_item(self.mgm_acc)
        self.add_item(self.appeals_acc)
        self.add_item(self.staff_roles)

    async def on_submit(self, interaction: discord.Interaction):
        std_acc = self.std_acc.component.values[0].id
        mgm_acc = self.mgm_acc.component.values[0].id
        appeals_acc = self.appeals_acc.component.values[0].id 
        staff_roles = [role.id for role in self.staff_roles.component.values]

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        await confg.ticket_roles.set({
            "modmail_access": std_acc,
            "modmail_mgmt": mgm_acc,
            "appeals_access": appeals_acc,
            "staff_roles": list(staff_roles)
        })

        await interaction.response.defer()
        await SettingsPanel(interaction.user, self.setup_msg).update_view(interaction, message=self.setup_msg)

class AddCatModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Add a Category", timeout=None)
        
        self.cat_title = ui.Label(
            text="What's the name of this category?",
            description="A simple couple worded title would be great!",
            component=ui.TextInput(
                placeholder="Title of category",
                style=discord.TextStyle.short,
                min_length=1,
                max_length=25,
                required=True
            )
        )

        self.cat_desc = ui.Label(
            text="What's the description of this category?",
            description="Please be descriptive so users can understand!",
            component=ui.TextInput(
                placeholder="Description of category",
                style=discord.TextStyle.paragraph,
                min_length=10,
                max_length=100,
                required=True
            )
        )
        
        self.category_id = ui.Label(
            text="Where should this category be?",
            description="Please choose a category for tickets to open under.",
            component=ui.ChannelSelect(
                placeholder="Select a Category",
                channel_types=[discord.ChannelType.category],
                min_values=1,
                max_values=1,
                required=True
            )
        )

        self.cat_team = ui.Label(
            text="Please select a staff role for this category.",
            description="This role will be notified in tickets under this category.",
            component=ui.RoleSelect(
                placeholder="Select a Role",
                min_values=1,
                max_values=1,
                required=True
            )
        )

        self.add_item(self.cat_title)
        self.add_item(self.cat_desc)
        self.add_item(self.category_id)
        self.add_item(self.cat_team)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.cat_title.component.value
        desc = self.cat_desc.component.value
        category_id = self.category_id.component.values[0].id
        team = self.cat_team.component.values[0].id
        
        try:
            new_category = Category(
                title=title,
                description=desc,
                team_role=team,
                category_id=category_id
            )
            await new_category.create(interaction)
        except Exception as e:
            await send_error(interaction, f"Unable to create category: {e}")

        await interaction.response.defer()
        await SettingsPanel(interaction.user, interaction.message).update_view(interaction, interaction.message)
        
class DelCatModal(ui.Modal):
    def __init__(self, categories: list[dict]):
        super().__init__(title=f"Deleting a Category", timeout=None)

        self.cats = categories

        self.menu = ui.Label(
            text="Which category are you deleting?",
            description="Once you submit, the action is permanent.",
            component=CategorySelect(self.cats)
        )

        self.add_item(self.menu)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        result = self.menu.component.values[0]

        try:
            await Category.delete(self, interaction, result)
        except Exception as e:
            return await send_error(interaction, f"{e}", True)

class ResetModal(ui.Modal):
    def __init__(self):
        super().__init__(title="Resetting Config", timeout=None)
        self.setup_msg = discord.Message

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

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)

        if self.question.component.values[0] == "yes":
            await confg.clear()
            await send_success(interaction, "The config was reset.")
            cog.log.info("TicketSystem settings (config) was reset.")
        else:
            await interaction.response.send_message("❌ Reset aborted.")

        await SettingsPanel(interaction.user, self.setup_msg).update_view(interaction, message=self.setup_msg)

class SetDescriptionModal(ui.Modal):
    def __init__(self, default_text: str):
        super().__init__(title=f"Setting Description", timeout=None)

        self.default_text = default_text

        self.description_text = ui.Label(
            text="Create/Edit Description",
            description="Set rules to be displayed in the ticket panel",
            component=ui.TextInput(
                placeholder="Set your description here!",
                default=self.default_text,
                style=discord.TextStyle.paragraph,
                min_length=10,
                max_length=2000,
                required=True
            )
        )

        self.add_item(self.description_text)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        panel_cfg = await confg.panel_cfg()

        try:
            await confg.panel_cfg.set({
                **panel_cfg,
                "description": self.description_text.component.value
            })
            
            await send_success(interaction, f"New description set:\n\n ```{self.description_text.component.value}```")
        except Exception as e:
            await send_error(interaction, f"{e}")

class BlacklistInfo(ui.Modal):
    def __init__(self, info: bool, blacklisted_user: discord.Member | discord.User, reason: str):
        super().__init__(title="⚠️ User is blacklisted!", timeout=None)
        self.info = info
        self.bl_user = blacklisted_user

        self.user = ui.Label(
            text="User Found",
            description="This user was found in the blacklist:",
            component=ui.UserSelect(
                default_values=[blacklisted_user]
            )
        )

        self.bl_reason = ui.Label(
            text="Blacklist Reason",
            description="They were blacklisted for the following reason:",
            component=ui.TextInput(
                style=discord.TextStyle.paragraph,
                default=reason,
                required=False
            )
        )

        self.decision = ui.Label(
            text="Remove This User",
            description="Are you sure you want to remove this user from the blacklist?",
            component=ui.Select(
                placeholder="Select an Option",
                options=[
                    discord.SelectOption(label="✅ Yes", value="yes"),
                    discord.SelectOption(label="❌ No", value="no")
                ],
                required=True
            )
        )

        self.add_item(self.user)
        self.add_item(self.bl_reason)
        if not self.info:
            self.add_item(self.decision)

    async def on_submit(self, interaction: discord.Interaction):
        if self.info:
            return await send_success(interaction, "No action taken as you were viewing information regarding a blacklist.", True)
        else:
            option = self.decision.component.values[0]
            user = int(self.bl_user.id)
            
            match option:
                case "yes":
                    await Blacklist.delete(self, interaction, user)
                case "no":
                    return await send_success(interaction, "No action was taken as you chose not to remove this user from the blacklist.", True)

# -- Selects -- #           
class CategorySelect(ui.Select):
    def __init__(self, categories: list[dict]):
        options = []
        self.map = {}
        for c in categories:
            id = c.get("category_id")

            title = c.get("title")
            desc = c.get("description") or "No description"
            id_str = str(id)
            self.map[id_str] = c
            options.append(
                discord.SelectOption(
                    label=title,
                    value=id,
                    description=desc
                )
            )

        super().__init__(
            placeholder="Select a Category",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class TicketSelectMenu(ui.Select):
    def __init__(self, categories: list[dict], appeals_enabled: bool, panel_channel: int):
        self.map = {str(c["category_id"]): c for c in categories}

        options = [
            discord.SelectOption(
                label=c["title"],
                value=str(c["category_id"]),
                description=c.get("description" or "No description")
            )
            for c in categories
        ]

        if appeals_enabled:
            options.append(
                discord.SelectOption(
                    label="🔨 Appeals",
                    value="appeals",
                    description="Appeal a moderation here."
                )
            )

        super().__init__(
            placeholder="Select a Category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"ticket-select-menu:{panel_channel}"
        )

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        entry = self.map.get(select_value)

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        status = await confg.tickets_enabled()
        ch = await confg.ticket_channels()
        l_ch = interaction.guild.get_channel(ch.get('logs_channel')) if ch.get('logs_channel') else None

        blacklist_check = await cog.db.fetch_blacklist(int(interaction.user.id))
        if blacklist_check:
            if l_ch:
                await l_ch.send(f"{interaction.user.mention} ({interaction.user.id}) tried opening a ticket but was blocked due to being blacklisted.")

            await interaction.message.edit(view=self.view)
            return await send_blocked(interaction, "You're forbidden from using the ticket system. If you believe this is an error, please contact server management. You are unable to use the ticket system's appeal feature for this.", True)

        if status:
            check_dup = await cog.db.existing_check("ticket", interaction.user.id)
            if check_dup:
                channel = interaction.guild.get_channel(check_dup)

                await interaction.message.edit(view=self.view)
                return await send_blocked(interaction, f"You already have an existing ticket open! You can access it here: {channel.mention}", True)
            
            if select_value == "appeals":
                check_dup = await cog.db.existing_check("appeal", interaction.user.id)
                if check_dup:
                    await interaction.message.edit(view=self.view)
                    return await send_blocked(interaction, f"You already have an existing appeal open (Appeal `{check_dup}`). Please run `/appeal status {check_dup}` to check its status.", True)
                
                await interaction.message.edit(view=self.view)
                return await interaction.response.send_modal(OpenAppeal())
            else:
                category_check = await cog.db.fetch_category(int(select_value))
                if not category_check:
                    return await send_error(interaction, "This category no longer exists. Please contact staff an alternative way.", True)
                
                team_id = entry.get("team_id") if entry else None
                modal = TicketQuestionaire(entry["title"], int(select_value), team_id)

                await interaction.message.edit(view=self.view)
                await interaction.response.send_modal(modal)
        else:
            if l_ch:
                await l_ch.send(f"{interaction.user.mention} ({interaction.user.id}) tried opening a ticket but was blocked due to the support system being offline.")

            await interaction.message.edit(view=self.view)
            return await send_blocked(interaction, "Sorry, our support system is currently closed at the moment. Please check back later.", True)

# -- Buttons -- #
class CloseTicket(ui.Button):
    def __init__(self, ticket_id):
        super().__init__(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id=f"close-ticket-button:{ticket_id}")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        check = await cog.staff_check(interaction)
        if not check:
            return await send_blocked(interaction, "You're not permitted to close this ticket. Please contact server staff to close your ticket.", True)
        await interaction.response.send_modal(CloseTicketQuestionaire(interaction.channel))
        
class ConfigRoles(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Roles", style=discord.ButtonStyle.primary, custom_id="config-roles-button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        roles = await confg.ticket_roles()

        stnd_role = interaction.guild.get_role(roles.get('modmail_access'))
        mgmt_role = interaction.guild.get_role(roles.get('modmail_mgmt'))
        appeal_role = interaction.guild.get_role(roles.get('appeals_access'))
        staff_roles = [interaction.guild.get_role(rid) for rid in roles.get('staff_roles') if interaction.guild.get_role(rid)]

        modal = ConfigRolesModal(stnd_role, mgmt_role, appeal_role, staff_roles)
        modal.setup_msg = interaction.message
        await interaction.response.send_modal(modal)

class ConfigChannels(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Channels", style=discord.ButtonStyle.primary, custom_id="config-channels-button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        channels = await confg.ticket_channels()
        panel = await confg.panel_cfg()

        log_channel = interaction.guild.get_channel(channels.get('log_channel'))
        appeal_channel = interaction.guild.get_channel(channels.get('appeal_logs'))
        panel_channel = interaction.guild.get_channel(panel.get('channel'))

        modal = ConfigChannelsModal(log_channel, appeal_channel, panel_channel)
        modal.setup_msg = interaction.message
        await interaction.response.send_modal(modal)

class AddCategories(ui.Button):
    def __init__(self):
        super().__init__(label="📋 Add a Category", style=discord.ButtonStyle.green, custom_id="add-catg-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddCatModal())

class DelCategories(ui.Button):
    def __init__(self):
        super().__init__(label="❌ Delete Categories", style=discord.ButtonStyle.danger, custom_id="del-catg-button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        cats = await cog.db.list_categories()

        if not cats:
            return await send_error(interaction, "No categories found. Aborting.", True)

        await interaction.response.send_modal(DelCatModal(cats))

class AcceptAppeal(ui.Button):
    def __init__(self, a_id: str, user: discord.Member | discord.User):
        super().__init__(label="✅ Accept Appeal", style=discord.ButtonStyle.green, custom_id=f"accept-appeal-button:{a_id}")
        self.a_id = a_id
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AppealDecision(decision='Accept', id=self.a_id, user=self.user))

class DenyAppeal(ui.Button):
    def __init__(self, a_id: str , user: discord.Member | discord.User):
        super().__init__(label="❌ Deny Appeal", style=discord.ButtonStyle.danger, custom_id=f"deny-appeal-button:{a_id}")
        self.a_id = a_id
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AppealDecision(decision='Deny', id=self.a_id, user=self.user))

class SendPanel(ui.Button):
    def __init__(self):
        super().__init__(label="✈️ Send Panel", style=discord.ButtonStyle.green, custom_id="send-panel-button")

    async def callback(self, interaction: discord.Interaction):
        if interaction.message and interaction.message.interaction_metadata:
            original_author = interaction.message.interaction_metadata.user
            if interaction.user != original_author:
                return await send_blocked(interaction, "Only the person who initiated this command can send the panel.", True)
            
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        panel_cfg = await confg.panel_cfg()
        tickets_enabled = await confg.tickets_enabled()
        appeals_enabled = await confg.appeals_enabled()
        categories = await cog.db.list_categories() or []

        channel_id = panel_cfg.get("channel")
        if not channel_id:
            await send_error(interaction, "Please set a panel channel before sending the panel.", True)
            return
        
        channel = await interaction.guild.fetch_channel(channel_id)
        description = panel_cfg.get("description")
        panel_msg_id =  panel_cfg.get("message_id")

        view = SupportPanel()

        if panel_msg_id:
            try:
                old_panel_msg = await channel.fetch_message(panel_msg_id)
                await old_panel_msg.delete()
            except Exception:
                pass
        
        try:
            msg = await channel.send(view=view)
            view.generate(interaction.guild, description, categories, appeals_enabled, tickets_enabled, channel_id)
            await msg.edit(view=view)
            await cog.db.save_view('support-panel', channel_id, msg.id)
        except Exception as e:
            return await send_error(interaction, f"{e}")
        
        await confg.panel_cfg.set({**panel_cfg, "message_id": msg.id})
        await send_success(interaction, f"The panel has been sent to {channel.mention}!")

class ResetConfig(ui.Button):
    def __init__(self):
        super().__init__(label="🚫 Reset Configs", style=discord.ButtonStyle.danger, custom_id="reset-confg-button")

    async def callback(self, interaction: discord.Interaction):
        modal = ResetModal()
        modal.setup_msg = interaction.message
        await interaction.response.send_modal(modal)

class SetDescription(ui.Button):
    def __init__(self):
        super().__init__(label="🗒️ Set Description", style=discord.ButtonStyle.primary, custom_id="set-gl-button")

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)

        panel_cfg = await confg.panel_cfg()
        description = panel_cfg.get("description")
        text = ""

        if description:
            text = description
        else:
            text = "No panel description has been set. Please delete this and create your own. Discord Markdown is supported!"

        modal = SetDescriptionModal(text)
        await interaction.response.send_modal(modal)