import uuid
import discord
import asyncio
import chat_exporter
import io

from .views import TicketInfo, LogInfo, Receipt, LogsReceipt
from .databases import TicketDB
from .error_handling import send_blocked, send_error, send_success
from datetime import datetime

class Ticket:
    def __init__(self, ticket_type, open_title, open_description, team_id):
        self.ticket_id = uuid.uuid4().hex[:6]
        self.open_time = int(datetime.now().timestamp())
        self.ticket_type = ticket_type
        self.open_title = open_title
        self.open_description = open_description
        self.team = team_id

    async def create_ticket(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        check_dup = await TicketDB.check_existing_db_ticket(interaction, self.ticket_type)
        allowed_mentions = discord.AllowedMentions.all()
        cog = interaction.guild.get_cog("tickets")
        confg = cog.config.guild(interaction.guild)

        ticket_channels = await confg.ticket_channels()
        log_ch_id = ticket_channels["log_channel"]
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

        await channel.send(view=ticket_view, allowed_mentions=allowed_mentions)
        await log_ch.send(view=log_view)


    async def close_ticket(self, interaction: discord.Interaction, reason: str):
        target_id = interaction.channel.id
        closed = await TicketDB.close_ticket(target_id, reason)

        if not closed:
            return await send_error(interaction, "No open ticket found for this channel. Please make sure you're running this command in an active ticket channel.")
        
        try:
            time_float = datetime.now().timestamp() + 10
            await send_success(interaction, f"⌛ Closing the ticket and creating a transcript.\nThis channel will be deleted <t:{time_float}:R>.")
            await self.create_transcript(interaction)
            await asyncio.sleep(10)
            await interaction.channel.delete()
        except Exception as e:
            return await send_error(interaction, f"Failed to delete the ticket channel: `{e}`")
        
    async def create_transcript(self, interaction: discord.Interaction):
        cog = interaction.guild.get_cog("tickets")

        confg = cog.config.guild(interaction.guild)
        ticket_channels = await confg.ticket_channels()
        log_ch_id = ticket_channels["log_channel"]
        log_ch = interaction.guild.get_channel(log_ch_id)
        user = await TicketDB.get_ticket_opener(interaction)

        transcript = await chat_exporter.export(
            channel = interaction.channel,
            tz_info = "US/Central",
            bot = cog.bot
        )

        if transcript is None:
            return await send_error(interaction, "Unable to generate transcript.")
        
        user_receipt = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel}.html")
        log_receipt = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel}.html")

        user_view = Receipt(user_receipt)
        log_view = LogsReceipt(log_receipt)

        if user:
            await user.send(view=user_view)

        await log_ch.send(view=log_view)

    # async def create_appeal(self, interaction, moderated_account_id, platform, appeal_info):
    async def create_appeal(self, interaction: discord.Interaction, moderated_account_id: int, platform: str, appeal_info: str):
        pass

    # async def create_appeal(self, interaction, moderated_account_id, platform, appeal_info):
    async def close_appeal(self, interaction: discord.Interaction, decision: str, ):
        pass

class TicketCategory:
    def __init__(self, category_name, category_description, team_role_id):
        self.name = category_name
        self.description = category_description
        self.team_role_id = team_role_id
        self.is_active = True
    
    @staticmethod
    async def create_category(category_name, description, team_role_id):
        count = await TicketDB.return_category_count()

        if count <= 24:
            try:
                await TicketDB.save_category(category_name, description, team_role_id)
                await send_success(f"Successfully created a category!\n__**{category_name}**__\n`Description:` {description}\n`Responsible Team:` <@&{team_role_id}>")
            except Exception as e:
                await send_error(f"Unable to create that category: {e}")
        else:
            await send_blocked("You currently reached the max amount of categories (24). Please remove one or more to create a new one.")

    @staticmethod
    async def get_category(category_name):
        check = await TicketDB.get_category(category_name)
        return category_name if check else None

    @staticmethod
    async def delete_category(category_name):
        check = await TicketDB.get_category(category_name)

        if check:
            await TicketDB.delete_category(category_name)
            await send_success(f"Successfully removed {category_name}!")
        else:
            await send_error(f"Unable to delete `{category_name}`. Refer to console for details.")

    @staticmethod
    async def set_status(category_name, status: bool):
        check = await TicketDB.get_category(category_name)

        if check:
            await TicketDB.modify_category_status(category_name, status)
            await send_success(f"Updated `{category_name}` status to **`{status}`**.")
        else:
            await send_error(f"`{category_name}` was not found in current categories.")