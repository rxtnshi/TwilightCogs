import uuid
import discord
import asyncio
import chat_exporter
import io

from .db_handler import db
from .error_handler import send_blocked, send_error, send_success
from datetime import datetime

class Ticket:
    def __init__(self, category_id: int, open_title: str, open_description: str, team_id: int):
        self.ticket_id = uuid.uuid4().hex[:6]
        self.ticket_type = category_id
        self.open_title = open_title
        self.open_description = open_description
        self.team = team_id

    async def create(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        from .views import TicketInfo, LogInfo

        cog = interaction.client.get_cog("tickets")
        check_dup = await cog.db.existing_check("ticket", interaction.user.id)
        allowed_mentions = discord.AllowedMentions.all()
        confg = cog.config.guild(interaction.guild)

        ticket_channels = await confg.ticket_channels()
        log_ch_id = ticket_channels.get("log_channel")
        log_ch = interaction.guild.get_channel(log_ch_id)

        if check_dup:
            channel = interaction.guild.get_channel(check_dup)
            await send_blocked(interaction, f"You already have an existing ticket open! You can access it here: {channel.mention}", True)
            return
        
        overwrites =  {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=False, embed_links=True),
            discord.utils.get(interaction.guild.roles, id=self.team): discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, embed_links=True)
        }
        
        channel = await interaction.guild.create_text_channel(
            name=f"{self.ticket_type}-{self.ticket_id}",
            category=category,
            overwrites=overwrites
        )

        ticket_view = TicketInfo(interaction.user, self.open_title, self.open_description)
        log_view = LogInfo(interaction.user, self.open_title, self.open_description, interaction.guild, channel)
        
        await cog.db.create_ticket(self.ticket_id, interaction.user, channel.id, category.name, self.open_title, self.open_description)
        await channel.send(view=ticket_view, allowed_mentions=allowed_mentions)
        await log_ch.send(view=log_view)
        await send_success(interaction, f"Your ticket has been successfully created. You may access it at {channel.mention}", True)

    async def close(self, interaction: discord.Interaction, reason: str):
        cog = interaction.client.get_cog("tickets")
        check = cog.staff_check(interaction.user)
        closed = cog.db.close_ticket(interaction.channel.id, interaction.user, reason)

        if not check:
            return await send_blocked(interaction, "You're not permitted to close this ticket. Please contact server staff to close your ticket.", True)
        
        if not closed:
            return await send_error(interaction, "No open ticket found for this channel. Please make sure you're running this command in an active ticket channel.")
        
        try:
            time_float = datetime.now().timestamp() + 10
            await send_success(interaction, f"⌛ Closing the ticket and creating a transcript.\nThis channel will be deleted <t:{time_float}:R>.")
            await self.gen_transcript(interaction)
            await asyncio.sleep(10)
            await interaction.channel.delete(reason="Ticket channel deleted because it was closed")
        except Exception as e:
            return await send_error(interaction, f"Failed to delete the ticket channel: `{e}`")
        
    async def gen_transcript(self, interaction: discord.Interaction):
        from .views import LogsReceipt, Receipt
        cog = interaction.guild.get_cog("tickets")

        confg = cog.config.guild(interaction.guild)
        ticket_channels = await confg.ticket_channels()
        log_ch_id = ticket_channels.get("log_channel")
        log_ch = interaction.guild.get_channel(log_ch_id)
        user = await cog.db.get_ticket_opener(interaction)

        transcript = await chat_exporter.export(
            channel = interaction.channel,
            tz_info = "US/Central",
            bot = cog.bot
        )

        if transcript is None:
            return await send_error(interaction, "Unable to generate transcript.")
        
        user_receipt = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.html")
        log_receipt = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.html")

        user_view = Receipt(user_receipt)
        log_view = LogsReceipt(log_receipt)

        if user:
            await user.send(view=user_view)

        await log_ch.send(view=log_view)

class Appeal:
    def __init__(self, platform: str, account: str, appeal_info: str):
        self.appeal_id = uuid.uuid4().hex[:6]
        self.platform = platform
        self.account = account
        self.info = appeal_info

    async def create(self, interaction: discord.Interaction):
        from .views import AppealPanel
        cog = interaction.client.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)
        channels = await confg.ticket_channels()
        appeal_channel_id = channels.get("appeal_logs")
        appeal_channel = interaction.guild.get_channel(appeal_channel_id)

        try:
            view = AppealPanel(self.appeal_id, interaction.user, self.account, self.platform, self.info)
            msg = await appeal_channel.send(view=view)
            await cog.db.create_appeal(self.appeal_id, self.account, self.platform, interaction.user.id, self.info, msg.id)

            await send_success(interaction, f"Appeal `{self.appeal_id}` has been opened. Once a decision has been made, you will be notified via DMS. Alternatively, you may check your appeal status using `/appeal status [appeal_id]`.", True)
        except Exception as e:
            await send_error(interaction, f"Unable to open appeal: {e}")

class Category:
    def __init__(self, title: str, description: str, team_role: discord.Role | None, category_id: discord.CategoryChannel):
        self.title = title
        self.desc = description
        self.team = team_role
        self.cat = category_id

    async def create(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("tickets")
        
        try:
            await cog.db.create_category(self.title, self.desc, self.team.id, self.cat.id)

            text = (
                "Category successfully created. Here are the details:\n\n"
                f"`Title`: `{self.title}`\n"
                f"`Description`: `{self.desc}`\n"
                f"`Responsible Team`: {self.team.mention}\n"
                f"`Category`: {self.cat.mention}\n"
            )
            await send_success(interaction, text)
        except Exception as e:
            await send_error(interaction, f"{e}", True)

    async def delete(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        cog = interaction.client.get_cog("tickets")

        try:
            await cog.db.del_category(self, category)
            await send_success(interaction, f"Successfully deleted category {category.name} and de-registered from the DB.")
        except Exception as e:
            await send_error(interaction, f"{e}", True)