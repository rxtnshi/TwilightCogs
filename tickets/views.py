import discord
import uuid
import logging

from .db_handler import db
from discord import ui
from .creation_handler import Ticket, Appeal, Category
from .error_handler import send_blocked, send_error, send_success

log = logging.getLogger("twilightcogs.ticketsv2")
def parse_id(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip("'\""))
    except ValueError:
        return None

# -- Views/LayoutViews -- #
class TicketInfo(ui.LayoutView):
    def __init__(self, author: discord.Member | discord.User, title: str, description: str):
        self.author = author
        self.title = title
        self.description = description

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"## 🛈 Request Information"),
                ui.TextDisplay(content=f"{self.title}\n\n"),
                ui.TextDisplay(content=f"{self.description}"),
                ui.TextDisplay(content=f"-# Thank you for contacting us. A member of our staff team will get to you shortly."),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/8bnPxj.gif")
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(content=f"# Action Center"),
            ui.ActionRow(UploadFile()),
        )

        self.add_item(container)

class LogInfo(ui.LayoutView):
    def __init__(self, author: discord.Member | discord.User, title: str, description: str, ticket_guild: discord.Guild, ticket_channel: discord.TextChannel):
        self.author = author
        self.title = title
        self.description = description
        self.guild = ticket_guild
        self.channel = ticket_channel

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🚨 New Support Request!"),
                ui.TextDisplay(content=f"{self.title}\n\n"),
                ui.TextDisplay(content=f"{self.description}"),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png")
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(
                ui.Button(
                    label="Access Ticket",
                    style=discord.ButtonStyle.link(),
                    url=f"https://discord.com/channels/{self.guild.id}/{self.channel.id}/",
                )
            )
        )

        self.add_item(container)

class AppealPanel(ui.LayoutView):
    def __init__(self, appeal_id: str,user: discord.Member, moderated_account: str, platform: str, appeal_info: str):
        self.appeal_id = appeal_id
        self.user = user
        self.platform = platform
        self.moderated_account = moderated_account
        self.appeal_info = appeal_info
        
        container = ui.Container(
            ui.Section(
                ui.TextDisplay(f"## 🚨 Appeal `{self.appeal_id}`Submitted"),
                ui.TextDisplay(f"An appeal was submitted by {self.user.mention}. Please review the details below."),
                accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/pending.png")
            ),
            ui.TextDisplay("### Moderated Account Info"),
            ui.TextDisplay(f"`Platform`: `{self.platform}`\n`Account ID`: `{self.moderated_account}`"),
            ui.TextDisplay("### Appeal Info"),
            ui.TextDisplay(f"{self.appeal_info}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(AcceptAppeal(), DenyAppeal())
        )

        self.add_item(container)

class DecisionAppeal(ui.LayoutView):
    def __init__(self, accepted: bool, staff_member: discord.Member, reason: str):
        self.accepted = accepted
        self.staff = staff_member
        self.reason = reason
        
        # container = ui.Container(
        #     ui.Section(
        #         ui.TextDisplay(f"## Appeal `{self.appeal_id}` {'accepted' if self.accepted }"),
        #         ui.TextDisplay(f"An appeal was submitted by {self.user.mention}. Please review the details below."),
        #         accessory=discord.ui.Thumbnail(media="https://cdn.rxtnshi.xyz/raw/pending.png")
        #     ),
        #     ui.TextDisplay("### Moderated Account Info"),
        #     ui.TextDisplay(f"`Platform`: `{self.platform}`\n`Account ID`: `{self.moderated_account}`"),
        #     ui.TextDisplay("### Appeal Info"),
        #     ui.TextDisplay(f"{self.appeal_info}"),
        #     ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        #     ui.ActionRow(AcceptAppeal(), DenyAppeal())
        # )

        # self.add_item(container)

class SupportPanel(ui.LayoutView):
    def __init__(self, guild: discord.Guild, guidelines: str | None, categories: list[dict], appeals_enabled: bool, tickets_enabled: bool):
        super().__init__()
        self.guild = guild
        self.guidelines = guidelines

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"# ❓ {self.guild}'s Support Center"),
                ui.TextDisplay(content=f"### Guidelines\n {f'{self.guidelines}' if self.guidelines else 'Please be respectful when contacting staff!'}"),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### Open a Support Request Here!"),
            ui.TextDisplay("-# Disclaimer: Please allow some ample time for server staff to respond to your query."),
        )
        if tickets_enabled is True:
            container.add_item(ui.ActionRow(TicketSelectMenu(categories, appeals_enabled)))
        else:
            container.add_item(ui.TextDisplay("`🚫 Sorry, our support system is currently closed at the moment. Please check back later.`"))

        self.add_item(container)

class SettingsPanel(ui.LayoutView):
    def __init__(self, interaction: discord.Interaction, author: discord.Member | discord.User | None, message: discord.Message | None):
        super().__init__(timeout=10)
        self.interaction = interaction
        self.author = author
        self.message = message or interaction.message

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user and interaction.user.id == self.author:
            return True
        else:
            return False, await send_blocked(interaction, "Only the person who initiated this command can change the settings.", True)
        
    async def on_timeout(self, interaction: discord.Interaction):
        if interaction.response.is_done():
            await interaction.followup("This panel has expired. Please run `/staff setup` to continue editing.")
        else:
            await interaction.response.send_message("This panel has expired. Please run `/staff setup` to continue editing.")

    @staticmethod
    async def get_settings(interaction: discord.Interaction):
        self = SettingsPanel(interaction, interaction.user, interaction.message)
        self.author = self.interaction.user.id

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        data = await confg.all()

        tickets_enabled = data.get("tickets_enabled")
        appeals_enabled = data.get("appeals_enabled")
        roles = data.get("ticket_roles") or {}
        log.info(roles)
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

        panel_channel_id = panel_cfg.get("channel")
        panel_message_id = panel_cfg.get("message_id")
        panel_link = (
            f"https://discord.com/channels/{interaction.guild.id}/{panel_channel_id}/{panel_message_id}"
            if panel_channel_id and panel_message_id
            else None
        )
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
                f"`Appeals Enabled`: {'`✅ Enabled`' if appeals_enabled is True else '`❌ Disabled`'}\n"
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
            ui.TextDisplay(f"[Link to panel]({panel_link})" if panel_link else "`No panel message set`"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("### __Action Center__"),
            ui.TextDisplay("-# Channels & Categories"),
            ui.ActionRow(ConfigChannels(), ConfigRoles(), AddCategories(), DelCategories()),
            ui.TextDisplay("-# Miscellaneous"),
            ui.ActionRow(SendPanel(), ConfigFileCheck(), ResetConfig())
        )
        self.add_item(container)
        return self
    
    async def update_view(self, interaction: discord.Interaction, message: discord.Message | None):
        view = await self.get_settings(interaction, message or self.message)
        setup_msg = message or self.message or interaction.message
        try:
            if setup_msg:
                await setup_msg.edit(view=view)
        except Exception as e:
            await send_error(interaction, f"Cannot edit view: {e}")
    
class Receipt(ui.LayoutView):
    def __init__(self, file: discord.File, title: str, requester: discord.Member, closer: discord.Member, open_reason: str, close_reason: str, open_time: int, close_time: int):
        self.file = discord.MediaGalleryItem(media=file)
        self.title = title
        self.requester = requester
        self.closer = closer
        self.open_reason = open_reason
        self.close_reason = close_reason
        self.open_time = open_time
        self.close_time = close_time

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"## 🗒️ Transcript for {self.title}"),
                ui.TextDisplay(content=f"Here is the transcript for `{self.title}`. The ticket information can be found below."),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(content="# Ticket Information"),
            ui.TextDisplay(content=f"**Requester**: {self.requester.mention} ({self.requester.id})"),
            ui.TextDisplay(content=f"**Closed By**: {self.closer.mention} ({self.closer.id})\n\n"),
            ui.TextDisplay(content=f"**Opened at**: <t:{self.open_reason}:F>"),
            ui.TextDisplay(content=f"**Closed at**: <t:{self.open_reason}:F>\n\n"),
            ui.TextDisplay(content=f"**Request Description**: {self.open_reason}"),
            ui.TextDisplay(content=f"**Close Reason**: {self.close_reason}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("# View Transcript"),
            ui.MediaGallery(self.file)
        )

        self.add_item(container)

class LogsReceipt(ui.LayoutView):
    def __init__(self, file: discord.File, title: str, requester: discord.Member, closer: discord.Member, open_reason: str, close_reason: str, open_time: int, close_time: int):
        self.file = discord.MediaGalleryItem(media=file)
        self.title = title
        self.requester = requester
        self.closer = closer
        self.open_reason = open_reason
        self.close_reason = close_reason
        self.open_time = open_time
        self.close_time = close_time

        container = ui.Container(
            ui.Section(
                ui.TextDisplay(content=f"## 🗒️ Transcript for {self.title}"),
                ui.TextDisplay(content=f"Here is the transcript for `{self.title}`. The ticket information can be found below."),
                accessory=ui.Thumbnail(media="https://cdn.rxtnshi.xyz/u/clipboard.png"),
            ),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(content="# Ticket Information"),
            ui.TextDisplay(content=f"**Requester**: {self.requester.mention} ({self.requester.id})"),
            ui.TextDisplay(content=f"**Closed By**: {self.closer.mention} ({self.closer.id})\n\n"),
            ui.TextDisplay(content=f"**Opened at**: <t:{self.open_reason}:F>"),
            ui.TextDisplay(content=f"**Closed at**: <t:{self.open_reason}:F>\n\n"),
            ui.TextDisplay(content=f"**Request Description**: {self.open_reason}"),
            ui.TextDisplay(content=f"**Close Reason**: {self.close_reason}"),
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay("# View Transcript"),
            ui.MediaGallery(self.file)
        )

        self.add_item(container)

# -- Modals -- #
class TicketQuestionaire(ui.Modal):
    def __init__(self, category_id: int, team_id: int):
        super().__init__(title=f"✍️ Opening a Request", timeout=None)
        self.category = category_id
        self.team = team_id

        self.ticket_title = ui.Label(
            text="Request Title",
            description="In short, how can we help you today?",
            component=ui.TextInput(
                placeholder="I need help!",
                max_length=40,
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.ticket_desc = ui.Label(
            text="Request Description",
            description="Describe your request in a few sentences or so.",
            component=ui.TextInput(
                placeholder="I need help with something!",
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

        ticket = Ticket(self.category, title, description, self.team)
        await ticket.create(interaction, category)

class TicketSelectMenu(ui.Select):
    def __init__(self, categories: list[dict], appeals_enabled: bool):
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
        )

    async def callback(self, interaction: discord.Interaction):
        select_value = self.values[0]
        entry = self.map.get(select_value)
        
        if select_value == "appeals":
            await interaction.response.send_modal(OpenAppeal())
            return
        
        team_id = entry.get("team_id") if entry else None
        modal = TicketQuestionaire(int(select_value), team_id)
        await interaction.response.send_modal(modal)

class FileUploadAnalysisModal(ui.Modal):
    def __init__(self, scans_enabled: bool):
        super().__init__(title="File Uploads", timeout=None)
        self.scans_enabled = scans_enabled

        if self.scans_enabled:
            self.file_upload = ui.Label(
                text = "Upload Your File",
                description = "This file will be analyzed by VirusTotal before being uploaded to the ticket.",
                component= ui.FileUpload(
                    min_values = 1,
                    custom_id = "file-upload-object",
                    required = False
                )
            )
        else:
            self.file_upload = ui.Label(
                text = "Upload Your File",
                description = "Your file will be uploaded to this channel.",
                component= ui.FileUpload(
                    min_values = 1,
                    custom_id = "file-upload-object",
                    required = False
                )
            )

        self.add_item(self.file_upload)

    async def on_submit(self, interaction: discord.Interaction):
        file = self.file_upload.component.values

        if self.scans_enabled:
            import vt
            pass
        else:
            pass

class CloseTicketQuestionaire(ui.Modal):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(title=f"🔒 Closing Ticket")

        self.channel = channel
        self.reason = ui.Label(
            text="Why are you closing this ticket?",
            description=f"You are closing {self.channel.name}. Please give a reason why otherwise no reason will be given.",
            component=ui.TextInput(
                label="Enter a reason",
                default="No reason given.",
                style=discord.TextStyle.paragraph
            )
        )

        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason.component.value
        await Ticket.close_ticket(self, interaction, reason)

class OpenAppeal(ui.Modal):
    def __init__(self):
        super().__init__(title="Opening Appeal", timeout=None)
        self.platform = ui.Label(
            text="What platform were you moderated on?",
            description="Please type in the platform you were moderated on as it will pinpoint your account info.",
            component=ui.TextInput(
                label="Platform (e.g Discord, Minecraft, etc.)",
                max_length=20,
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.moderated_account = ui.Label(
            text="Provide the ID of the moderated account",
            description="Preferably please give us your account name and its ID. A profile link is also allowed.",
            component=ui.TextInput(
                label="Account Details",
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.moderated_reason = ui.Label(
            text="What's the reason you were moderated for?",
            description="Please give us the exact reason you were moderated for - telling us makes this process easier.",
            component=ui.TextInput(
                label="Reason for moderation",
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.information = ui.Label(
            text="Provide relevant evidence/information",
            description="Please provide us anything that will help us with your case.",
            component=ui.TextInput(
                label="Platform (e.g Discord, Minecraft, etc.)",
                max_length=20,
                style=discord.TextStyle.short,
                required=True
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        platform = self.platform.component.value
        account = self.moderated_account.component.value
        reason = self.moderated_reason.component.value
        info = self.information.component.value

        db.create_appeal(self, self.appeal_id, account, platform, interaction.user.id, )

class AppealDecision(ui.Modal):
    def __init__(self, decision: str):
        super().__init__(title=f"{self.decision}ing Appeal", timeout=None)
        self.decision = decision

        self.prefined_reasons = ui.Label(
            text="Predefined Reasons",
            description="You can select a predefined reason or choose 'Custom Reason' for your own.",
            component=ui.Select(
                max_values=1,
                required=True,
                options=[
                    discord.SelectOption(
                        label="Evidence Supports Decision",
                        description="The evidence provided by the appealer supports this decision. - accept",
                        value="The evidence provided by the appealer supports this decision."
                    ),
                    discord.SelectOption(
                        label="Lack of Evidence",
                        description="The evidence provided is not sufficient to make a decision - denial",
                        value="The evidence provided is not sufficient to make a decision"
                    ),
                    discord.SelectOption(
                        label="Non-appealable Offense",
                        description="This offense is non-appealable - denial",
                        value="This offense is non-appealable"
                    ),
                    discord.SelectOption(
                        label="Custom Reason",
                        description="Provide a reason of your own for this decision",
                        value="custom-reason"
                    )
                ]
            )
        )

        self.reason = ui.Label(
            text="Custom Reason",
            description="Please provide any addition info or your own reason for this decision.",
            component=ui.TextInput(
                style=discord.TextStyle.paragraph,
                min_length=10,
                required=False
            )
        )
        
        self.add_item(self.prefined_reasons)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        decision = self.decision.lower()
        log_msg = interaction.message
        reason_text = None

        if self.prefined_reasons.component.values[0] == "custom-reason":
            pass

        if decision == "accept":
            await Ticket.close_appeal(self, interaction, log_msg.id, 'ACCEPTED', f"{reason_text}")
        else:
            await Ticket.close_appeal(self, interaction, log_msg.id, 'DENIED', f"{reason_text}")

class ConfigChannelsModal(ui.Modal):
    def __init__(self):
        super().__init__(title=f"Channels Setup", timeout=None)
        self.setup_msg: discord.Message

        self.log_channel = ui.Label(
            text="Where should be the logs channel be?",
            description="This is where transcripts and new ticket notifications go.",
            component=ui.ChannelSelect(
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1
            )
        )
        
        self.appeal_channel = ui.Label(
            text="Where should be the appeals log be?",
            description="This is where appeals get sent and decisions are made here.",
            component=ui.ChannelSelect(
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1
            )
        )

        self.panel_channel = ui.Label(
            text="Where should the panel go?",
            description="This is where user can create tickets from.",
            component=ui.ChannelSelect(
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1
            )
        )

        self.add_item(self.log_channel)
        self.add_item(self.appeal_channel)
        self.add_item(self.panel_channel)

    async def on_submit(self, interaction: discord.Interaction):
        log_ch = parse_id(self.log_channel.component.values[0].id)
        appeal_ch = parse_id(self.appeal_channel.component.values[0].id)
        panel_ch = parse_id(self.panel_channel.component.values[0].id)

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
    def __init__(self):
        super().__init__(title=f"Roles Setup", timeout=None)
        self.setup_msg: discord.Message | None

        self.std_acc = ui.Label(
            text="What should give standard access?",
            description="This role will give access to basic ticket commands.",
            component=ui.RoleSelect(
                min_values=1,
                max_values=1
            )
        )
        
        self.mgm_acc = ui.Label(
            text="What should give management access?",
            description="This role will give access to elevated ticket commands.",
            component=ui.RoleSelect(
                min_values=1,
                max_values=1
            )
        )

        self.appeals_acc = ui.Label(
            text="What should give appeals access?",
            description="This role will give access to making appeal decisions and be able to see the channel.",
            component=ui.RoleSelect(
                min_values=1,
                max_values=1
            )
        )

        self.staff_roles = ui.Label(
            text="Please designate your server staff roles!",
            description="You should add roles that are for your staff, and then have them run /staff register to gain access.",
            component=ui.RoleSelect(
                min_values=0,
                max_values=25
            )
        )

        self.add_item(self.std_acc)
        self.add_item(self.mgm_acc)
        self.add_item(self.appeals_acc)
        self.add_item(self.staff_roles)

    async def on_submit(self, interaction: discord.Interaction):
        std_acc = parse_id(self.std_acc.component.values[0].id)
        mgm_acc = parse_id(self.mgm_acc.component.values[0].id)
        appeals_acc = parse_id(self.appeals_acc.component.values[0].id)
        staff_roles = [parse_id(role.id) for role in self.staff_roles.component.values]
        log.info(f"{staff_roles}")

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
        self.setup_msg: discord.Message | None
        
        self.cat_title = ui.Label(
            text="What's the name of this category?",
            description="A simple couple worded title would be great!",
            component=ui.TextInput(
                placeholder="Title of category",
                style=discord.TextStyle.short,
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
                max_values=1
            )
        )

        self.cat_team = ui.Label(
            text="Please select a staff role for this category.",
            description="This role will be notified in tickets under this category, or you can leave empty for no mentions.",
            component=ui.RoleSelect(
                placeholder="Select a Role",
                max_values=1
            )
        )

        self.add_item(self.cat_title)
        self.add_item(self.cat_desc)
        self.add_item(self.category_id)
        self.add_item(self.cat_team)

    async def on_submit(self, interaction: discord.Interaction):
        title = self.cat_title.component.value
        desc = self.cat_desc.component.value
        category_id = self.category_id.component.values[0]

        
        if self.cat_team.component.values[0]:
            team = self.cat_team.component.values[0]
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
        else:
            try:
                new_category = Category(
                    title=title,
                    description=desc,
                    team_role=None,
                    category_id=category_id
                )
                await new_category.create(interaction)
            except Exception as e:
                await send_error(interaction, f"Unable to create category: {e}")

        await interaction.response.defer()
        await SettingsPanel(interaction.user, self.setup_msg).update_view(interaction, message=self.setup_msg)
        
class DelCatModal(ui.Modal):
    def __init__(self, msg: discord.Message):
        self.setup_msg = msg
        pass

class ConfigFileCheckModal(ui.Modal):
    def __init__(self):
        super().__init__(title=f"VirusTotal Config", timeout=None)

        self.key = ui.Label(
            text="VirusTotal Key",
            description="In order to enable file scans, please make sure you have an API key from VirusTotal.",
            component=ui.TextInput(
                placeholder="Input API Key here",
                style=discord.TextStyle.long,
                max_length=64,
                required=True
            ) 
        )

        self.add_item(self.key)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        key = self.key.component.value

        try:
            await confg.file_scans.set({
                "vt_key": key,
                "enabled": False
            })
            await send_success(interaction, f"Key set! Since you've set a new key, you will now have to re-enable file scans by running `/staff setup`.\n\nYour current key is: ||`{self.key}`||")
        except Exception as e:
            await send_error(interaction, f"Unable to set VirusTotal key: {e}")

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
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)

        if self.question.component.values[0] == "yes":
            await confg.clear()
            await send_success(interaction, "The config was reset.")
            cog.log.info("TicketSystem settings (config) was reset.")
        else:
            await interaction.response.send_message("❌ Reset aborted.")

        await SettingsPanel(interaction.user, self.setup_msg).update_view(interaction, message=self.setup_msg)

# -- Buttons -- #
class UploadFile(ui.Button):
    def __init__(self):
        super().__init__(label="📂 Upload a File", style=discord.ButtonStyle.green, custom_id="upload-file-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(FileUploadAnalysisModal())

class CloseTicket(ui.Button):
    def __init__(self):
        super().__init__(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close-ticket-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CloseTicketQuestionaire())
        
class ConfigRoles(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Roles", style=discord.ButtonStyle.primary, custom_id="config-roles-button")

    async def callback(self, interaction: discord.Interaction):
        modal = ConfigRolesModal()
        modal.setup_msg = interaction.message
        await interaction.response.send_modal(modal)

class ConfigChannels(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Channels", style=discord.ButtonStyle.primary, custom_id="config-channels-button")

    async def callback(self, interaction: discord.Interaction):
        modal = ConfigChannelsModal()
        modal.setup_msg = interaction.message
        await interaction.response.send_modal(modal)

class ConfigFileCheck(ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure File Checks", style=discord.ButtonStyle.primary, custom_id="config-vt-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ConfigFileCheckModal())

class AddCategories(ui.Button):
    def __init__(self):
        super().__init__(label="📋 Add a Category", style=discord.ButtonStyle.green, custom_id="add-catg-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AddCatModal())

class DelCategories(ui.Button):
    def __init__(self):
        super().__init__(label="❌ Delete Categories", style=discord.ButtonStyle.danger, custom_id="del-catg-button")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DelCatModal())

class AcceptAppeal(ui.Button):
    def __init__(self):
        super().__init__(label="✅ Accept Appeal", style=discord.ButtonStyle.green, custom_id="accept-appeal-button")

    async def callback(self, interaction):
        await interaction.response.send_modal(AppealDecision(decision="Accept"))

class DenyAppeal(ui.Button):
    def __init__(self):
        super().__init__(label="❌ Deny Appeal", style=discord.ButtonStyle.green, custom_id="deny-appeal-button")

    async def callback(self, interaction):
        await interaction.response.send_modal(AppealDecision(decision="Deny"))

class SendPanel(ui.Button):
    def __init__(self):
        super().__init__(label="✈️ Send Panel", style=discord.ButtonStyle.green, custom_id="send-panel-button")

    async def callback(self, interaction):
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        panel_cfg = await confg.panel_cfg()
        tickets_enabled = await confg.tickets_enabled()
        appeals_enabled = await confg.appeals_enabled()
        categories = await cog.db.list_categories()

        channel_id = panel_cfg.get("channel")
        channel = await interaction.guild.fetch_channel(channel_id)
        guidelines = panel_cfg.get("guidelines")
        panel_msg_id =  panel_cfg.get("message_id")

        if panel_msg_id:
            try:
                old_panel_msg = await channel.fetch_message(panel_msg_id)
                msg = await channel.send(view=SupportPanel(interaction.guild, guidelines, categories, appeals_enabled, tickets_enabled))
                await old_panel_msg.delete()
            except Exception as e:
                await send_error(interaction, f"{e}")
        
        msg = await channel.send(view=SupportPanel(interaction.guild, guidelines, categories, appeals_enabled, tickets_enabled))
        await confg.panel_cfg.set({
            **panel_cfg,
            "message_id": msg.id
        })

        await send_success(interaction, f"The panel has been sent to {channel.mention}!")
        await SettingsPanel(interaction.user, interaction.message).update_view(interaction, message=interaction.message)

class ResetConfig(ui.Button):
    def __init__(self):
        super().__init__(label="🚫 Reset Configs", style=discord.ButtonStyle.danger, custom_id="reset-confg-button")

    async def callback(self, interaction):
        modal = ResetModal()
        modal.setup_msg = interaction.message
        await interaction.response.send_modal(modal)