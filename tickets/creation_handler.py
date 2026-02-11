import uuid
import discord
import asyncio
import chat_exporter
import io
import emoji

from .db_handler import db
from .error_handler import send_blocked, send_error, send_success
from datetime import datetime

class Ticket:
    def __init__(self, category_name: str, category_id: int, open_title: str, open_description: str, team_id: int):
        self.ticket_id = uuid.uuid4().hex[:6]
        self.cat_name = category_name
        self.ticket_type = category_id
        self.open_title = open_title
        self.open_description = open_description
        self.team = team_id

    async def create(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        from .views import TicketInfo, LogInfo

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)

        ticket_channels = await confg.ticket_channels()
        log_ch_id = ticket_channels.get("log_channel")
        log_ch = interaction.guild.get_channel(log_ch_id)
        role = interaction.guild.get_role(self.team)
        cat_name = emoji.replace_emoji(self.cat_name, '')
        ticket_name = f"{cat_name}-{self.ticket_id}"
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True),
            discord.utils.get(interaction.guild.roles, id=self.team): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        }
        
        channel = await interaction.guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites
        )

        ticket_view = TicketInfo()
        log_view = LogInfo()
        log_view.set_data(interaction.user, self.cat_name, self.open_title, self.open_description, interaction.guild, channel, self.ticket_id)
        
        await cog.db.create_ticket(self.ticket_id, int(interaction.user.id), int(channel.id), str(category.name), self.open_title, self.open_description)
        await channel.send(f"{role.mention}", allowed_mentions=discord.AllowedMentions(roles=True))
        user_msg = await channel.send(view=ticket_view, allowed_mentions=discord.AllowedMentions(users=False))

        await cog.db.save_view('ticket-view', channel.id, user_msg.id)
        ticket_view.set_data(interaction.user, self.open_title, self.open_description)
        await user_msg.edit(view=ticket_view)

        await log_ch.send(view=log_view, allowed_mentions=discord.AllowedMentions(users=False))
        await send_success(interaction, f"Your ticket has been successfully created. You may access it at {channel.mention}.", True)

    async def close(self, interaction: discord.Interaction, reason: str):
        from .views import LogsReceipt, Receipt

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        
        channel = interaction.channel
        ticket_channels = await confg.ticket_channels()
        log_ch_id = ticket_channels.get("log_channel")
        log_ch = interaction.guild.get_channel(log_ch_id)
        ticket = await cog.db.fetch_ticket(interaction.channel.id)

        title = ticket.get("title")
        desc = ticket.get("description")
        open_time = int(ticket.get("open_time"))
        close_time = int(datetime.now().timestamp())
        open_reason = f"{title} - {desc}"
        close_reason = reason

        user_id = ticket.get("ticket_user")
        user = None

        if user_id:
            user = interaction.guild.get_member(user_id)
        
        try:
            user_receipt, log_receipt = await Ticket.gen_transcript(interaction, channel)

            user_view = Receipt()
            user_view.set_data(interaction.channel.name, user, interaction.user, open_reason, close_reason, open_time, close_time)
            log_view = LogsReceipt()
            log_view.set_data(interaction.channel.name, user, interaction.user, open_reason, close_reason, open_time, close_time)

            if user:
                await user.send(file=user_receipt)
                await user.send(view=user_view, allowed_mentions=discord.AllowedMentions(users=False))
            
            await log_ch.send(file=log_receipt)
            await log_ch.send(view=log_view, allowed_mentions=discord.AllowedMentions(users=False))
        except Exception as e:
            return await send_error(interaction, f"Failed to send transcripts: `{e}`")
    
        try:
            time_float = int(datetime.now().timestamp() + 10)
            closed = await cog.db.close_ticket(int(interaction.channel.id), int(interaction.user.id), reason)
            if not closed:
                return await send_error(interaction, "No open ticket found for this channel. Please make sure you're running this command in an active ticket channel.")

            await send_success(interaction, f"⌛ Closing the ticket and creating a transcript.\nThis channel will be deleted <t:{time_float}:R>.")
            await asyncio.sleep(10)
            await interaction.channel.delete(reason="Ticket channel deleted because it was closed")
        except Exception as e:
            return await send_error(interaction, f"Failed to delete the channel: `{e}`")
        
    async def gen_transcript(interaction: discord.Interaction, channel: discord.TextChannel):
        cog = interaction.client.get_cog("tickets")

        transcript = await chat_exporter.export(
            channel,
            tz_info="US/Central",
            guild=interaction.guild,
            bot=cog.bot,
        )
        
        if transcript is None:
            return await send_error(interaction, "Unable to generate transcript.")
        
        user_receipt = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript.html")
        log_receipt = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript.html")

        return user_receipt, log_receipt

class Appeal:
    def __init__(self, platform: str, account: str, reason: str, appeal_info: str):
        self.appeal_id = uuid.uuid4().hex[:6]
        self.platform = platform
        self.account = account
        self.reason = reason
        self.info = appeal_info

    async def create(self, interaction: discord.Interaction):
        from .views import AppealPanel
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        channels = await confg.ticket_channels()
        roles = await confg.ticket_roles()
        appeal_role_id = roles.get("appeals_access")
        appeal_role = interaction.guild.get_role(appeal_role_id)
        appeal_channel_id = channels.get("appeal_logs")
        appeal_channel = interaction.guild.get_channel(appeal_channel_id)

        try:
            log_view = AppealPanel()
            user_view = AppealPanel()
            user_view.generate('receipt', self.appeal_id, interaction.user, self.account, self.platform, self.reason, self.info, appeal_role)
            
            msg = await appeal_channel.send(f"{appeal_role.mention}",view=log_view, allowed_mentions=discord.AllowedMentions(roles=True))
            log_view.generate('log', self.appeal_id, interaction.user, self.account, self.platform, self.reason, self.info, appeal_role)
            await msg.edit(view=log_view, allowed_mentions=discord.AllowedMentions(users=False))
            await interaction.user.send(view=user_view)
            await cog.db.save_view('appeal-panel', appeal_channel_id, msg.id, self.appeal_id)
            await cog.db.create_appeal(self.appeal_id, self.account, self.platform, self.reason, int(interaction.user.id), self.info, int(msg.id))
            await send_success(interaction, f"Appeal `{self.appeal_id}` has been opened. Once a decision has been made, you will be notified via DMS. Alternatively, you may check your appeal status using `/appeal status {self.appeal_id}`.", True)
        except Exception as e:
            await send_error(interaction, f"{e}", True)

    async def close(self, interaction: discord.Interaction, accepted: bool, reason: str, a_id: str, user: discord.Member | discord.User):
        from .views import DecisionAppeal
        self.accepted = accepted
        self.reason = reason
        self.a_id = a_id
        self.user = user

        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        channels = await confg.ticket_channels()
        appeal_log_id = channels.get("appeal_logs")
        appeal_ch = interaction.guild.get_channel(appeal_log_id) if appeal_log_id else None

        appeal = await cog.db.fetch_appeal(self.a_id)
        appeal_open_time = int(appeal.get("appeal_time"))

        option = 'accepted' if self.accepted else 'denied'

        original_message = await interaction.original_response()
        log_view = DecisionAppeal(
            type='log',
            accepted=self.accepted,
            appeal_id=self.a_id,
            staff_member=interaction.user,
            reason=self.reason,
            create_time=appeal_open_time,
            appealer=self.user
        )
        user_view = DecisionAppeal(
            type='receipt',
            accepted=self.accepted,
            appeal_id=self.a_id,
            staff_member=interaction.user,
            reason=self.reason,
            create_time=appeal_open_time,
            appealer=self.user
        )
        await cog.db.close_appeal(int(original_message.id), int(interaction.user.id), option, self.reason)

        try:
            await original_message.edit(view=log_view, allowed_mentions=discord.AllowedMentions(users=False))
            await self.user.send(view=user_view)
        except discord.Forbidden:
            await send_error(interaction, f"{self.user.mention} has their DMs turned off so I was unable to message them the result.")
        except discord.NotFound:
            await send_error(interaction, f"The appeal log for Appeal `{self.a_id}` was not found. Sending a new panel.", True)
            await appeal_ch.send(view=log_view)
        except Exception as e:
            await send_error(interaction, f"{e}")

class Category:
    def __init__(self, title: str, description: str, team_role: int, category_id: int):
        self.title = title
        self.desc = description
        self.team = team_role
        self.cat = category_id

    async def create(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        team = interaction.guild.get_role(self.team)
        cat = interaction.guild.get_channel(self.cat)

        check_dup = await cog.db.existing_check("category", self.cat)
        if check_dup:
            return await send_error(interaction, f"An existing category named `{check_dup}` already exists under that category channel.", True)
        try:
            await cog.db.create_category(self.title, self.desc, team.id, cat.id)
        except Exception as e:
            return await send_error(interaction, f"{e}", True)

        text = (
                "Category successfully created. Here are the details:\n\n"
                f"`Title`: `{self.title}`\n"
                f"`Description`: `{self.desc}`\n"
                f"`Responsible Team`: {team.mention}\n"
                f"`Category`: {cat.mention}\n"
            )
        await send_success(interaction, text)

    async def delete(self, interaction: discord.Interaction, category: int):
        cog = interaction.client.get_cog("tickets")

        try:
            name = await cog.db.del_category(category)
            await send_success(interaction, f"Successfully deleted category `{name}` and de-registered from the DB.")
        except Exception as e:
            await send_error(interaction, f"{e}", True)

class Blacklist:
    def __init__(self, user: discord.Member | discord.User, staff_member: discord.Member | discord.User, reason: str):
        self.user = user
        self.staff = staff_member
        self.reason = reason

    async def add(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")

        target = int(self.user.id)
        staff = int(self.staff.id)
        reason = self.reason

        try:
            await cog.db.add_blacklist(target, staff, reason)
        except Exception as e:
            return await send_error(interaction, f"Unable to add user to blacklist: `{e}`")
        
        cog.log.info(f"{interaction.user} ({interaction.user.id}) added {self.user} ({self.user.id}) to the blacklist for {reason}")
        await send_success(interaction, f"Successfully added user to blacklist for: `{reason}`")

    async def delete(self, interaction: discord.Interaction, target: int):
        cog = interaction.client.get_cog("tickets")
        if not target:
            target = int(self.user.id)
        user = interaction.guild.get_member(target)
        try:
            await cog.db.del_blacklist(target)
        except Exception as e:
            return await send_error(interaction, f"Unable to add user to blacklist: `{e}`")
        
        cog.log.info(f"{interaction.user} ({interaction.user.id}) removed {self.user} ({self.user.id}) from the blacklist")
        await send_success(interaction, f"Successfully removed {user.mention if user else target} from the blacklist.")

    async def fetch(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        target = int(self.user.id)

        try:
            result = await cog.db.fetch_blacklist(target)
            return result
        except Exception as e:
            return await send_error(interaction, f"Unable to fetch that user's blacklist: `{e}`")