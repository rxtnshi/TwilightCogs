import discord
import logging
import sqlite3
import random
import os

from redbot.core import commands, app_commands, Config
from redbot.core.data_manager import cog_data_path
from discord.ext import tasks
from datetime import datetime

from .Handling import send_blocked, send_error, send_success, send_warning
from .ViewsModals import GiveawayView, GiveawayModal, AddBlacklist, RemoveBlacklist, GiveawaySettingsView
from .classes import CreateGiveaway

       
class Giveaways(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log = logging.getLogger("twilightcogs.giveaways")

        self.config = Config.get_conf(self, identifier=98083421, force_registration=True)
        default_guild = {
            "ga_perms": None,
            "ga_notif": None
        }
        self.config.register_guild(**default_guild)

        self.ga_perms = None
        self.ga_notif = None

        self.db_path = os.path.join(cog_data_path(self), "giveaways.db")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.init_db()
        self.loop.start()

    def init_db(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS giveaways (
                message_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                host_id INTEGER,
                giveaway_id TEXT,
                prize TEXT,
                winners INTEGER,
                end_time REAL,
                is_active INTEGER DEFAULT 1
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                message_id INTEGER,
                user_id INTEGER,
                PRIMARY KEY (message_id, user_id),
                FOREIGN KEY (message_id) REFERENCES giveaways (message_id) ON DELETE CASCADE
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                user_id INTEGER PRIMARY KEY,
                reason TEXT
            )
        """)
        self.conn.commit()

    def cog_unload(self):
        self.loop.cancel()
        self.conn.close()

    @tasks.loop(seconds=1)
    async def loop(self):
        try:
            current_time = datetime.now().timestamp()

            self.cursor.execute("SELECT message_id, channel_id, winners, end_time FROM giveaways WHERE is_active = 1 AND end_time <= ?", (current_time,))

            ended_giveaways = self.cursor.fetchall()

            for ga in ended_giveaways:
                await self.end_giveaway(ga)
        except sqlite3.ProgrammingError:
            self.loop.cancel()
        except Exception as e:
            self.log.error(f"Error in loop: {e}")

    def send_end_ga(self, content: str, reroll: bool = False):
        embed = discord.Embed(
            title="🎉 Giveaway ended!" if not reroll else "🎉 Winners Rerolled!",
            description="Congratulations to the winners below!" if not reroll else "There are new winners!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )

        embed.add_field(name="Winners", value=content, inline=False)
        return embed
    
    async def perms_check(self, interaction: discord.Interaction):
        config = self.config.guild(interaction.guild)
        ga_perms = await config.ga_perms()

        if interaction.user.guild_permissions.administrator:
            return True

        return bool(ga_perms and any(r.id == ga_perms for r in interaction.user.roles))

    async def end_giveaway(self, ga_data):
        message_id, channel_id, num_winners, end_time = ga_data
        end_time_ts = int(end_time)

        self.cursor.execute("UPDATE giveaways SET is_active = 0 WHERE message_id = ?", (message_id,))
        self.conn.commit()

        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.log.error(f"This giveaway wasn't found. Channel ID of the supposed giveaway: `{channel_id}`")
            return
        
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            self.log.warning("Tried to end a giveaway but couldn't find it.")
            self.log.error(f"This giveaway wasn't found. Message ID of the supposed giveaway: `{message_id}`")
            return
        
        self.cursor.execute("SELECT user_id FROM entries WHERE message_id = ?", (message_id,))
        entries = [row[0] for row in self.cursor.fetchall()]

        winner_text = "No winner" # placeholder
        if not entries:
            embed = self.send_end_ga("No winners as there were no entries!")
            await message.reply(embed=embed)
        else:
            winner_count = min(len(entries), num_winners)
            if winner_count >= len(entries):
                winner_ids = list(entries)
            else: 
                winner_ids = random.sample(entries, winner_count)
            
            winner_mentions = [f"<@{uid}>" for uid in winner_ids]
            if winner_count > 1:
                winner_text = ", ".join(winner_mentions)
            else:
                winner_text = winner_mentions[0]

            embed = self.send_end_ga(f"{winner_text}")
            await message.reply(f"{winner_text}", embed=embed)

        embed = message.embeds[0]
        embed.color = discord.Color.light_grey()
        embed.title = "🎉 Giveaway Ended! 🎉"
        embed.set_field_at(index=3, name="Ended", value=f"<t:{end_time_ts}:R> • <t:{end_time_ts}:f>", inline=False)
        embed.add_field(name="Winners", value=f"{winner_text}", inline=False)

        view = GiveawayView()
        for child in view.children:
            child.disabled = True
        
        await message.edit(embed=embed, view=view)

    async def setting_embed(self, guild: discord.Guild):
        ga_perm_role = await self.config.guild(guild).ga_perms()
        ga_notif_role = await self.config.guild(guild).ga_notif()

        embed = discord.Embed(
            title="⚙️ Giveaway Settings",
            description="Here are the current settings!",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Giveaway Perms", value=f"<@&{ga_perm_role}>" if ga_perm_role else "`None`", inline=False)
        embed.add_field(name="Giveaway Notifications", value=f"<@&{ga_notif_role}>" if ga_notif_role else "`None`", inline=False)

        return embed

    giveaway = app_commands.Group(name="giveaway", description="Giveaway commands", guild_only=True)

    @giveaway.command(name="start", description="Starts the interactive giveaway creation tool")
    async def start_giveaway(self, interaction):
        cog = interaction.client.get_cog("Giveaways")

        allowed = await self.perms_check(interaction)
        if not allowed:
            await send_blocked(interaction, "You are not allowed to run this command.", True)
            return

        modal = GiveawayModal(cog)
        await interaction.response.send_modal(modal)

    @giveaway.command(name="end", description="Ends a giveaway manually")
    @app_commands.describe(id="The ID of the giveaway you want to end immediately")
    async def cancel_giveaway(self, interaction, id: str):
        allowed = await self.perms_check(interaction)
        if not allowed:
            await send_blocked(interaction, "You are not allowed to run this command.", True)
            return
        
        ga_id = id
        self.cursor.execute("SELECT message_id, channel_id, winners, end_time FROM giveaways WHERE is_active = 1 AND giveaway_id = ?", (ga_id,))
        result = self.cursor.fetchall()

        if not result:
            await send_error(interaction, f"Couldn't find a giveaway id matching `{ga_id}`. Please try again!", True)
            return
        
        try:
            await self.end_giveaway(result[0])
            await send_success(interaction, f"Giveaway `{id}` was successfully ended!", True)
        except Exception as e:
            self.log.error(f"Tried to end giveaway {id}: {e}")
            await send_error(interaction, f"Tried to end giveaway {id}: `{e}`", True)

    @giveaway.command(name="reroll", description="Reroll X winners for a specific giveaway")
    @app_commands.describe(id="The giveaway ID you're rerolling from", winners="# of winners to reroll")
    async def reroll_giveaway(self, interaction, id: str, winners: int):
        allowed = await self.perms_check(interaction)
        if not allowed:
            await send_blocked(interaction, "You are not allowed to run this command.", True)
            return
        
        if winners <= 0:
            await send_error(interaction, "Number of winners must be at least 1 user.", True)
            return
        
        self.cursor.execute("SELECT message_id, channel_id FROM giveaways WHERE is_active = 0 AND giveaway_id = ?", (id,))
        ga_data = self.cursor.fetchone()

        if not ga_data:
            await send_error(interaction, f"Couldn't find an inactive giveaway matching ID `{id}`. Please try again!", True)
            return
        
        message_id, channel_id = ga_data

        channel = self.bot.get_channel(channel_id)
        if not channel:
            await send_error(interaction, f"This giveaway wasn't found. Channel ID of the supposed giveaway: `{channel_id}`", True)
            return
        
        winner_text = "No winner" # placeholder
        try:
            message = await channel.fetch_message(message_id)
            self.cursor.execute("SELECT user_id FROM entries WHERE message_id = ?", (message_id,))
            entry_data = [row[0] for row in self.cursor.fetchall()]

            winner_count = min(len(entry_data), winners)
            if winner_count >= len(entry_data):
                winner_ids = list(entry_data)
            else: 
                winner_ids = random.sample(entry_data, winner_count)

            winner_mentions = [f"<@{uid}>" for uid in winner_ids]
            if winner_count > 1:
                winner_text = ", ".join(winner_mentions)
            else:
                winner_text = winner_mentions[0]

            ga_embed = message.embeds[0]
            ga_embed.set_field_at(index=4, name="Winners", value=f"{winner_text}", inline=False)

            embed = self.send_end_ga(f"{winner_text}", True)
            await message.reply(f"{winner_text}", embed=embed)
            await send_success(interaction, f"Successfully rerolled giveaway `{id}`!", True)
        except discord.NotFound:
            self.log.warning("Tried to end a giveaway but couldn't find it.")
            await send_error(interaction, f"This giveaway wasn't found. Message ID of the supposed giveaway: `{message_id}`", True)
            return
        except Exception as e:
            self.log.warning(f"General Exception: {e}")
            await send_error(f"General Exception: `{e}`")

    @giveaway.command(name="settings", description="Display all giveaway settings")
    async def show_settings(self, interaction):
        allowed = await self.perms_check(interaction)
        if not allowed:
            await send_blocked(interaction, "You are not allowed to run this command.", True)
            return
        
        embed = await self.setting_embed(interaction.guild)
        view = GiveawaySettingsView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    @giveaway.command(name="blacklist", description="Blacklist a user from giveaways")
    async def add_blacklist(self, interaction):
        allowed = await self.perms_check(interaction)
        if not allowed:
            await send_blocked(interaction, "You are not allowed to run this command.", True)
            return
        
        cog = interaction.client.get_cog("Giveaways")
        modal = AddBlacklist(cog)
        await interaction.response.send_modal(modal)

    @giveaway.command(name="unblacklist", description="Remove a user from the blacklist")
    @app_commands.describe(user="The user you want to remove from the blacklist")
    async def remove_blacklist(self, interaction, user: discord.Member):
        allowed = await self.perms_check(interaction)
        if not allowed:
            await send_blocked(interaction, "You are not allowed to run this command.", True)
            return
        
        cog = interaction.client.get_cog("Giveaways")
        user_id = user.id
        self.cursor.execute("SELECT reason FROM blacklist WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()

        if not result:
            await send_error(interaction, f"{user.mention} was not found in the blacklist!", True)
            return
        
        reason = result[0]
        modal = RemoveBlacklist(cog, reason, user_id)
        await interaction.response.send_modal(modal)

    @giveaway.command(name="list", description="Lists active giveaways")
    async def list_active_giveaways(self, interaction):
        self.cursor.execute("SELECT giveaway_id, prize, channel_id, message_id, end_time FROM giveaways WHERE is_active = 1")
        result = self.cursor.fetchall()
        text = ""
        
        for ga_id, prize, channel_id, message_id, end_time in result:
            msg_link = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}"
            text += f"[{prize} ({ga_id})]({msg_link})\nEnds <t:{int(end_time)}:R> • <t:{int(end_time)}:f>\n\n"

        embed = discord.Embed(
            title="🎉 Active Giveaways",
            description="Here is a list of current active running giveaways!",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )

        embed.add_field(name="Current Givaways", value=text if text else "`No active giveaways`", inline=False)

        await interaction.response.send_message(embed=embed)
