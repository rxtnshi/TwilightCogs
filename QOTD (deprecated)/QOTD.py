import discord
import asyncio
import datetime
import re
import logging

from redbot.core import commands, app_commands, Config
from discord.ext import tasks
from chuk_llm import ask_ollama_sync

class QOTD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=98394345, force_registration=True)
        self.log = logging.getLogger("twilightcogs.qotd")
        default_guild = {
            "qotd_channel": None,
            "qotd_role": None,
            "qotd_time": None,
            "last_qotd_sent": None,
            "last_qotd_message": None
        }
        self.config.register_guild(**default_guild)

        self.qotd_channel = None
        self.qotd_role = None
        self.qotd_time = None
        self.last_qotd_sent = None
        self.ask_qotd.start()
    
    def cog_unload(self):
        self.ask_qotd.cancel()
        self.log.info("Task canceled since QOTD was unloaded.")

    qotd = app_commands.Group(name="qotd", description="Question of the day", guild_only=True)
    default_qotd_time = datetime.time(hour=16, minute=0, tzinfo=datetime.timezone.utc)

    # -- helper thing for parsing utc stuff --
    def _parse_time_utc(self, time: str) -> datetime.time:
        if not re.fullmatch(r"\d{1,2}:\d{2}", time.strip()):
            raise ValueError("❌ Time must be in HH:MM (24 hour) format. Please try again!")
        
        h, m = map(int, time.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("❌ Hour must be between 0-23 and minute must be between 00-59. Please try again!")
        
        return datetime.time(hour=h, minute=m, tzinfo=datetime.timezone.utc)
    
    # -- actual thing where qotd posts automatically --
    @tasks.loop(minutes=1)
    async def ask_qotd(self):
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        today = now_utc.date().isoformat()

        for guild in self.bot.guilds:
            settings = await self.config.guild(guild).all()

            # -- Check for guild settings --
            if not settings["qotd_channel"]:
                continue

            if settings["last_qotd_sent"] == today:
                continue

            # -- Time Check --
            try:
                target_time = self._parse_time_utc(settings["qotd_time"])
                if now_utc.hour != target_time.hour or now_utc.minute != target_time.minute:
                    continue
            except ValueError:
                continue

            # -- QOTD post --
            channel = guild.get_channel(settings["qotd_channel"])
            qotd_role = guild.get_role(settings["qotd_role"]) if settings["qotd_role"] else None

            if not channel:
                self.log.warning(f"QOTD channel not found in {guild.name} ({guild.id}). Skipping QOTD post.")
                continue

            # -- Check for pinned QOTD --
            if settings["last_qotd_message"]:
                old_pin_id = settings["last_qotd_message"]
                try:
                    old_pin = await channel.fetch_message(old_pin_id)
                    await old_pin.unpin()
                    self.log.info(f"QOTD message {message.id} has been unpinned.")
                except discord.NotFound:
                    self.log.warning(f"QOTD message {message.id} not found. Ignoring unpin.")
                    await self.config.guild(guild).last_qotd_message.set(None)
                except Exception as e:
                    self.log.warning(f"Unable to unpin old qotd. Error: {e}")
                    pass

            # -- Post QOTD and pin --
            try:
                allowed_mentions = discord.AllowedMentions(roles=True)
                question = await self.bot.loop.run_in_executor(
                    None, ask_ollama_sync, "Generate a random, family-friendly question of the day. Don't include extra details and just ask the question!"
                )

                content = f"{qotd_role.mention} {question}" if settings["qotd_role"] else question
                message = await channel.send(content, allowed_mentions=allowed_mentions)

                await self.config.guild(guild).last_qotd_sent.set(today)
                await self.config.guild(guild).last_qotd_message.set(message.id)
                await message.pin()

                self.log.info(f"QOTD successfully sent in {guild} ({guild.id})")
            except Exception as e:
                try:
                    self.log.error(f"Unable to generate QOTD. {e}")
                except Exception:
                    pass


    # -- check for status --
    @ask_qotd.before_loop
    async def check_before_starting_tast(self):
        await self.bot.wait_until_ready()
        self.log.info("QOTD task is ready!")

    @qotd.command(name="generate", description="Generates a QOTD in the channel this command is run")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def generate_qotd(self, interaction: discord.Interaction, ping: bool):
        await interaction.response.defer(ephemeral=True, thinking=True)

        qotd_role_id = await self.config.guild(interaction.guild).qotd_role()
        qotd_role = interaction.guild.get_role(qotd_role_id)
        
        try:
            allowed_mentions = discord.AllowedMentions(roles=True)
            question = await self.bot.loop.run_in_executor(
                    None, ask_ollama_sync, "Generate a random, family-friendly question of the day. Don't include extra details and just ask the question!"
            )

            qotd_message = question

            if qotd_role and ping is True:
                qotd_message = f"{qotd_role.mention} {question}"
            
            await interaction.followup.send("QOTD generated!", ephemeral=True)
            await interaction.channel.send(qotd_message, allowed_mentions=allowed_mentions)
        except Exception as e:
            self.log.error(f"Unable to generate QOTD. {e}")
            await interaction.channel.send(f"Unable to create a QOTD. Please contact the cog creator at `discord.gg/gtz`. Error: `{e}`")

    @qotd.command(name="settings", description="Adjust QOTD settings")
    @app_commands.describe(
        channel = "The channel QOTD should be sent in",
        role = "The role that should be mentioned for QOTD",
        time = "The time that the QOTD should be sent at in HH:MM format (24 hour UTC)",
        clear_pin = "Clears the last set pinned message from the config. Does not actually unpin the message."
    )
    async def qotd_settings(self, interaction: discord.Interaction, channel: discord.TextChannel = None, role: discord.Role = None, time: str = None, clear_pin: bool = False):
        await interaction.response.defer(ephemeral=False)

        is_updated = False

        # -- Checks for changes --
        if channel:
            await self.config.guild(interaction.guild).qotd_channel.set(channel.id)
            is_updated = True
        if role:
            await self.config.guild(interaction.guild).qotd_role.set(role.id)
            is_updated = True
        if time is not None:
            try:
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                today = now_utc.date().isoformat()
                last = await self.config.guild(interaction.guild).last_qotd_sent()

                if last == today:
                    await self.config.guild(interaction.guild).last_qotd_sent.set(None)
                new_time = self._parse_time_utc(time)
                await self.config.guild(interaction.guild).qotd_time.set(new_time.strftime("%H:%M"))

                is_updated = True
                self.log.info(f"Successfully changed the QOTD time in {interaction.guild} ({interaction.guild.id}) to {new_time}")
            except ValueError as e:
                await interaction.followup.send(f"Invalid time: `{e}`")
        if clear_pin is True:
            await self.config.guild(interaction.guild).last_qotd_message.set(None)
            is_updated = True

        # -- Gets values --
        channel_id = await self.config.guild(interaction.guild).qotd_channel()
        qotd_role_id = await self.config.guild(interaction.guild).qotd_role()
        qotd_time = await self.config.guild(interaction.guild).qotd_time()
        qotd_message_id = await self.config.guild(interaction.guild).last_qotd_message()

        qotd_message_link = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{qotd_message_id}"

        cfg_channel = interaction.guild.get_channel(channel_id) if channel_id else None
        cfg_qotd_role = interaction.guild.get_role(qotd_role_id) if qotd_role_id else None

        # -- Sends settings embed --
        embed = discord.Embed(
            title="❓ QOTD Settings",
            description=("✅ Successfully updated settings!" if is_updated is True else "Current QOTD Settings"),
            timestamp=datetime.datetime.now(),
            color=discord.Color.green()
        )

        embed.add_field(name="Channel", value=cfg_channel.mention if cfg_channel else "Not Set", inline=False)
        embed.add_field(name="Role", value=cfg_qotd_role.mention if cfg_qotd_role else "Not Set", inline=False)
        embed.add_field(name="QOTD Time (24 hour format)", value=f"{qotd_time} UTC" if qotd_time else "Not Set", inline=False)
        embed.add_field(name="Last QOTD Message", value=qotd_message_link if qotd_message_id else "None Found", inline=False)

        await interaction.followup.send(embed=embed)