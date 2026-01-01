import discord
import sqlite3

from datetime import datetime
from .Handling import send_blocked, send_error, send_success, send_warning
from .classes import CreateGiveaway

def parse_id(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip("'\""))
    except ValueError:
        return None

class EnterGiveawayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(style=discord.ButtonStyle.green, emoji="🎉", custom_id="giveaway_button")

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Giveaways")
        if not cog:
            await send_error(interaction, "Giveaways not loaded. Please contact bot owner.", True)

        msg_id = str(interaction.message.id)
        user_id = interaction.user.id

        cog.cursor.execute("SELECT is_active FROM giveaways where message_id = ?", (msg_id,))
        result = cog.cursor.fetchone()

        # -- Existing giveaway check --
        if not result:
            await send_error(interaction, "This giveaway does not exist!", True)
            return
        
        # -- Active status check --
        if result[0] == 0:
            await send_blocked(interaction, "This giveaway has already ended.", True)
            return
        
        # -- Blacklist check --
        cog.cursor.execute("SELECT user_id FROM blacklist WHERE user_id = ?", (interaction.user.id,))
        if result := cog.cursor.fetchone():
            await send_blocked(interaction, "You are blacklisted from participating in giveaways. If you think this is an error, please make an appeal via our support form.", True)
            return
        
        # -- if nothing goes wrong, then try to enter the user into the database! --
        try:
            cog.cursor.execute("INSERT INTO entries (message_id, user_id) VALUES (?, ?)", (msg_id, user_id,))
            cog.conn.commit()
        except sqlite3.IntegrityError:
            await send_blocked(interaction, "You are already entered into this giveaway!", True)
            return
        
        cog.cursor.execute("SELECT COUNT(*) FROM entries WHERE message_id = ?", (msg_id,))
        count = cog.cursor.fetchone()[0]

        try:
            embed = interaction.message.embeds[0]
            embed.set_field_at(index=2, name="Entries", value=f"{count}", inline=False)
            await interaction.message.edit(embed=embed)
            await send_success(interaction, "🎉 You've been entered in this giveaway! 🎉", True)
        except discord.HTTPException:
            await send_warning(interaction, "🎉 You've been entered in this giveaway! 🎉\n However the entry counter failed to update, no worries.", True)

class SetRolesButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="⚙️ Configure Roles", style=discord.ButtonStyle.primary, custom_id="ga_set_roles_button")

    async def callback(self, interaction):
        cog = interaction.client.get_cog("Giveaways")
        if not cog:
            await send_error(interaction, "Giveaways not loaded.", True)
            return
        
        await interaction.response.send_modal(SetRolesModal(interaction.message))

        message = await interaction.original_response()
        view = discord.ui.View.from_message(message)
        view.message = message

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(EnterGiveawayButton())

class GiveawaySettingsView(discord.ui.View):
    def __init__(self, author: discord.User | discord.Member):
        super().__init__(timeout=60)
        self.message = None
        self.author = author.id
        self.add_item(SetRolesButton())

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


class GiveawayModal(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Creating Giveaway", timeout=None)
        self.cog = cog

        self.prize_name = discord.ui.Label(
            text="What is the prize name?",
            description="This will be the prize that you're giving away!",
            component= discord.ui.TextInput(
                placeholder="Type the prize name",
                style=discord.TextStyle.short,
                required=True
            )
        )

        self.end_time = discord.ui.Label(
            text="When should this giveaway end?",
            description="Format: Days (d) Hours (h) Minutes (m) seconds (s)",
            component= discord.ui.TextInput(
                placeholder="Type the duration",
                style=discord.TextStyle.short,
                required=True,
                min_length=2
            )
        )

        self.num_winners = discord.ui.Label(
            text="How many winners for this giveaway?",
            description="The number of winners will be declared at the end of the giveaway.",
            component= discord.ui.TextInput(
                placeholder="# of winners",
                style=discord.TextStyle.short,
                required=True,
                min_length=1
            )
        )

        self.ga_channel = discord.ui.Label(
            text="Where should this giveaway be sent?",
            description="The giveaway will be sent to this channel, otherwise your current channel will be selected.",
            component= discord.ui.ChannelSelect(
                placeholder="Select a channel",
                channel_types=[discord.ChannelType.text],
                min_values=1,
                max_values=1
            )
        )

        self.ga_ping = discord.ui.Label(
            text="Notifications",
            description="Would you like to notify users with the giveaway role?",
            component=discord.ui.Select(
                required=True,
                placeholder="Select an option",
                options=[
                    discord.SelectOption(label="Yes", value="yes"),
                    discord.SelectOption(label="No", value="no")
                ]
            )
        )

        self.add_item(self.prize_name)
        self.add_item(self.end_time)
        self.add_item(self.num_winners)
        self.add_item(self.ga_channel)
        self.add_item(self.ga_ping)
    
    async def on_submit(self, interaction):
        prize = self.prize_name.component.value
        duration = self.end_time.component.value
        winners = self.num_winners.component.value
        ga_ping = self.ga_ping.component.values[0]

        confg = self.cog.config.guild(interaction.guild)
        ga_ping_role_id = await confg.ga_notif()
        ga_ping_role = interaction.guild.get_role(ga_ping_role_id)
        allowed_mentions = discord.AllowedMentions.all()

        seconds = CreateGiveaway.parse_duration(duration)

        if self.ga_channel and self.ga_channel.component.values:
            ga_channel_id = int(self.ga_channel.component.values[0])
        else:
            ga_channel_id = interaction.channel.id

        if not seconds:
            await send_error(interaction, "Invalid duration format! Use days as `d`, hours as `h`, minutes as `m`, and seconds as `s`. For example, a 1 hour 20 minute 10 second giveaway would be `1h20m10s`.", True)
            return
        
        end_time_float = datetime.now().timestamp() + seconds
        end_time = int(end_time_float)

        if isinstance(winners, int):
            winners_int = winners
        elif str(winners).strip().isdigit():
            winners_int = int(winners)
        else:
            await send_error(interaction, "Invalid number of winners. Must be an integer at least 1.", True)
            return

        if winners_int <= 0:
            await send_error(interaction, "Invalid number of winners. Must be an integer at least 1.", True)
            return
        
        ga = CreateGiveaway(prize, end_time, winners_int, interaction.user.id, None)
        embed = ga.get_embed(entry_count=0)
        view = GiveawayView()
        msg = None

        try:
            ga_channel = interaction.guild.get_channel(ga_channel_id) if ga_channel_id else interaction.channel
            
            if interaction.response.is_done():
                msg = await ga_channel.send(f"{ga_ping_role.mention}" if ga_ping == "yes" else None,embed=embed, view=view, allowed_mentions=allowed_mentions)
                await send_success(interaction, f"Giveaway `{ga.ga_id}` was started for prize `{prize}`! It will end on <t:{end_time}:f> which is <t:{end_time}:R>!", True)
            else:
                if ga_channel == interaction.channel:
                    await interaction.response.send_message(f"{ga_ping_role.mention}" if ga_ping == "yes" else None,embed=embed, view=view, allowed_mentions=allowed_mentions)
                    msg = await interaction.original_response()
                else:
                    msg = await ga_channel.send(f"{ga_ping_role.mention}" if ga_ping == "yes" else None,embed=embed, view=view, allowed_mentions=allowed_mentions)

            self.cog.cursor.execute("""
                INSERT INTO giveaways (message_id, channel_id, host_id, giveaway_id, prize, winners, end_time, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (msg.id, ga_channel_id, interaction.user.id, ga.ga_id, prize, winners_int, end_time,))

            self.cog.conn.commit()
            self.cog.log.info(f"Giveaway {ga.ga_id} was started for prize \"{prize}\" and ends at {datetime.fromtimestamp(end_time)}")
            await send_success(interaction, f"Giveaway `{ga.ga_id}` was started for prize `{prize}`! It will end on <t:{end_time}:f> which is <t:{end_time}:R>!", True)
        except Exception as e:
            self.cog.log.error(f"Failed to save giveaway: {e}")
            if msg:
                await msg.delete()
                await send_error(interaction, f"Giveaway failed to save. Canceling giveaway due to: `{e}`", True)
            else:
                await send_error(interaction, f"Failed to start the giveaway due to: `{e}`", True)

class AddBlacklist(discord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Blacklist a User", timeout=None)
        self.cog = cog

        self.target = discord.ui.Label(
            text="Who are you blacklisting from giveaways?",
            description="This user will be added to the blacklist from future giveaways.",
            component = discord.ui.UserSelect(
                placeholder="Select a user to blacklist",
                min_values=1,
                max_values=1
            )
        )

        self.reason = discord.ui.Label(
            text="What is the reason for the blacklist?",
            description="This reason will be added to our database for the blacklist.",
            component = discord.ui.TextInput(
                placeholder="Reason for blacklist",
                style=discord.TextStyle.paragraph,
                default="No reason given"
            )
        )

        self.add_item(self.target)
        self.add_item(self.reason)

    async def on_submit(self, interaction):
        target_id = self.target.component.values[0]
        reason = self.reason.component.value

        try:
            self.cog.cursor.execute("INSERT INTO blacklist (user_id, reason) VALUES (?, ?)", (target_id, reason,))
            self.cog.conn.commit()
            self.cog.log.info(f"User {self.target} was added to the blacklist.")
            await send_success(interaction, f"Successfully blacklisted <@{target_id}> ({target_id}) for `{reason}`.")
        except sqlite3.IntegrityError:
            self.cog.log.warning(f"Failed to blacklist user with ID {target_id} due to duplicate entry.")
            await send_error(interaction, f"<@{target_id}> ({target_id}) was already added to the blacklist!")
        except Exception as e:
            self.cog.log.error(f"Failed to blacklist user with ID {target_id} due to: {e}")
            await send_error(interaction, f"Blacklisting failed: `{e}`", True)

class RemoveBlacklist(discord.ui.Modal):
    def __init__(self, cog, reason, user):
        super().__init__(title="Unblacklist a User", timeout=60)
        self.target = user
        self.cog = cog

        self.reason = discord.ui.Label(
            text="⚠️ Blacklisted user!",
            description="This user was blacklisted for the following reason:",
            component=discord.ui.TextInput(
                default=reason,
                style=discord.TextStyle.paragraph,
            )
        )

        self.select = discord.ui.Label(
            text="Unblacklist this user",
            description="Do you want to unblacklist this user?",
            component=discord.ui.Select(
                placeholder="Select an option",
                required=True,
                options=[
                    discord.SelectOption(label="Yes", value="yes"),
                    discord.SelectOption(label="No", value="no")
                ]
            )
        )

        self.add_item(self.reason)
        self.add_item(self.select)

    async def on_submit(self, interaction: discord.Interaction):
        answer = self.select.component.values[0]
        
        if answer == "yes":
            try:
                self.cog.cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (self.target,))
                self.cog.conn.commit()
                self.cog.log.info(f"User {self.target} was removed to the blacklist.")
                await send_success(interaction, f"<@{self.target}> was removed from the blacklist successfully!")
            except Exception as e:
                self.cog.log.error(f"Error in removing user from blacklist: {e}")
                await send_error(interaction, f"{e}")
        else:
            await send_success(interaction, "Process aborted since the selection was `no`.")

    async def on_timeout(self, interaction: discord.Interaction):
        await send_warning(interaction, "User was not removed from the blacklist as the interaction timed out.")

class SetRolesModal(discord.ui.Modal):
    def __init__(self, setup_msg):
        super().__init__(title="Giveaway Roles Setup", timeout=None)
        self.setup_msg = setup_msg

        self.ga_perms = discord.ui.Label(
            text="What role should have settings access?",
            description="This role will give full access.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.ga_notif = discord.ui.Label(
            text="What role should be notified for giveaways?",
            description="This role will be notified for giveaways.",
            component= discord.ui.RoleSelect(
                placeholder="Select a role",
                min_values=1,
                max_values=1
            )
        )

        self.add_item(self.ga_perms)
        self.add_item(self.ga_notif)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Giveaways")
        if not cog: return

        confg = cog.config.guild(interaction.guild)
        ga_perms_role = parse_id(self.ga_perms.component.values[0])
        ga_notif_role = parse_id(self.ga_notif.component.values[0])

        try:
            await confg.ga_perms.set(ga_perms_role)
            await confg.ga_notif.set(ga_notif_role)

            new_embed = await cog.setting_embed(interaction.guild)
            await self.setup_msg.edit(embed=new_embed)
            await send_success(interaction, "Roles configured successfully!")
        except Exception as e:
            cog.log.error(f"Failed to set roles: {e}")
            await send_error(interaction, f"Failed to set roles due to: `{e}`")