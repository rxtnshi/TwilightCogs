import discord
import uuid
import re
from datetime import datetime

class CreateGiveaway:
    def __init__(self, prize: str, end_time: int, num_winners: int, ga_host: int, ga_messageid: int, ga_id: str = None):
        self.prize_name = prize
        self.end_time = end_time
        self.num_winners = num_winners
        self.ga_host = ga_host
        self.ga_messageid = ga_messageid
        self.ga_id = ga_id if ga_id else uuid.uuid4().hex[:6]

    def get_embed(self, entry_count: int = 0):
        end_ts = int(self.end_time)

        embed = discord.Embed(
            title="🎉 Giveaway started!",
            description=f"A new giveaway has started by <@{self.ga_host}>! Check the deets below!",
            color=discord.Color.og_blurple(),
            timestamp=datetime.now()
        )

        embed.add_field(name="Prize", value=self.prize_name, inline=False)
        embed.add_field(name="# of Winners", value=self.num_winners, inline=False)
        embed.add_field(name="Entries", value=entry_count, inline=True)
        embed.add_field(name="Ends", value=f"<t:{end_ts}:R> • <t:{end_ts}:f>", inline=False)

        embed.set_footer(text=f"⚙️ Giveaway ID: {self.ga_id}")

        return embed

    @staticmethod
    def parse_duration(duration: str) -> int:
        matches = re.findall(r"(\d+)([dhms])", duration.lower())

        if not matches:
            return None
        
        total_secs = 0
        units = {
            "d": 86400,
            "h": 3600,
            "m": 60,
            "s": 1
        }

        for amount, unit in matches:
            total_secs += int(amount) * units[unit]

        return total_secs