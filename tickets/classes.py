import uuid
import discord

from .databases import TicketDB
from .error_handling import send_blocked, send_error, send_success, send_warning
from datetime import datetime

class Ticket:
    def __init__(self, ticket_type, open_reason):
        self.ticket_id = uuid.uuid4().hex[:6]
        self.open_time = int(datetime.now().timestamp())
        self.ticket_type = ticket_type

        # create_db_ticket(self, interaction, ticket_id, channel_id, ticket_type, open_time, open_reason):
    async def create_ticket(self, interaction):
        check_dup = await TicketDB.check_existing_db_ticket(self, interaction, self.ticket_type)

        if check_dup:
            channel = await interaction.guild.get_channel(check_dup)
            await send_blocked(interaction, f"You already have an existing ticket open! You can access it here: {channel.mention}", True)
            return

    async def close_ticket(self, interaction):
        pass

    async def create_appeal(self, interaction):
        pass

    async def close_appeal(self, interaction):
        pass

class TicketCategory:
    def __init__(self, category_name, category_description, team_role_id):
        self.name = category_name
        self.description = category_description
        self.team_role_id = team_role_id
        self.is_active = True

    async def create_category(self):
        pass

    async def get_category(self):
        pass

    async def delete_category(self):
        pass

    async def set_status(self, status: bool):
        pass

    sss