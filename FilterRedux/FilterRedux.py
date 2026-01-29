import discord
import typing
import re

from datetime import datetime
from redbot.core import commands, app_commands, Config, modlog
from .MessageHandling import check_wl, check_perms, delete_message_hit

async def check_edit_perms(bot, interaction: discord.Interaction):
    cog = bot.get_cog("FilterRedux")

    if not cog:
        return False
    
    return await check_perms(cog, interaction.user, interaction.guild)

class FilterRedux(commands.Cog):
    """Probably a filter rewrite to fit our needs more since base filter cog isn't really for us"""

    def __init__(self, bot):
        self.bot = bot

        self.config = Config.get_conf(self, identifier=49303402, force_registration=True)
        default_guild = {
			"whitelist_users": [],
            "whitelist_roles": [],
            "filtered_words": []
		}
        self.config.register_guild(**default_guild)

    filter = app_commands.Group(name="filter", description="Basic level features", guild_only=True)

    @filter.command(name="add", description="Adds a word to the filter")
    async def add_word(self, interaction: discord.Interaction, word: str):
        if not await check_edit_perms(self.bot, interaction.user):
            await interaction.response.send_message(f"**`⚠️ Error`**: You do not have sufficient permission.")
            return
        
        async with self.config.guild(interaction.guild).filtered_words() as words:
            if word.lower() in (w.lower() for w in words):
                await interaction.response.send_message(f"**`⚠️ Error`**: `{word}` is already in the filter.", ephemeral=True)
                return
            words.append(word)
            await interaction.response.send_message(f"**`✅ Success`**: `{word}` added to the filter.", ephemeral=True)

    @filter.command(name="remove", description="Removes a word from the filter")
    async def remove_word(self, interaction: discord.Interaction, word: str):
        if not await check_edit_perms(self.bot, interaction.user):
            await interaction.response.send_message(f"**`⚠️ Error`**: You do not have sufficient permission.")
            return
        
        async with self.config.guild(interaction.guild).filtered_words() as words:
            before = len(words)
            words[:] = [w for w in words if w.lower() != word.lower()]
            removed = len(words) < before

        if removed:
            await interaction.response.send_message(f"**`✅ Success`**: `{word}` removed from the filter.", ephemeral=True)
        else:
            await interaction.response.send_message(f"**`⚠️ Error`**: `{word}` is not in the filter.", ephemeral=True)

    @filter.command(name="list", description="Lists all filtered words and whitelisted users/roles")
    async def list_everything(self, interaction: discord.Interaction):
        if not await check_edit_perms(self.bot, interaction):
            await interaction.response.send_message(f"**`⚠️ Error`**: You do not have sufficient permission.", ephemeral=True)
            return
        
        sconfg = self.config.guild(interaction.guild)
        embed = discord.Embed(
            title="Filtered Words",
            description="Here is a list of words that have been added to the filter.",
            timestamp=datetime.now()
        )

        word_list = await sconfg.filtered_words()
        disp = ""
        if not word_list:
            disp = "No filtered words"

        for w in word_list:
            disp += f"{w}\n"
        
        embed.add_field(name="Words", value=disp, inline=False)

        wl_users = await sconfg.whitelist_users()
        wl_roles = await sconfg.whitelist_roles()

        u_disp = ""
        r_disp = ""

        if not wl_users:
            u_disp = "No whitelisted users"
        
        if not wl_roles:
            r_disp = "No whitelisted roles"

        for u in wl_users:
            u_disp += f"- <@{u}>\n"

        for r in wl_roles:
            r_disp += f"- <@{r}>\n"


        embed.add_field(name="Whitelisted Users", value=u_disp, inline=False)
        embed.add_field(name="Whitelisted Roles", value=r_disp, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @filter.command(name="whitelist", description="Add or remove a user/role from the whitelist")
    @app_commands.choices(
		option=[
			app_commands.Choice(name="Add", value="add"),
			app_commands.Choice(name="Remove", value="remove"),
		]
	)
    async def whitelist_set(self, interaction: discord.Interaction, option: str, target: typing.Union[discord.Member, discord.Role]):
        if not await check_edit_perms(self.bot, interaction):
            await interaction.response.send_message(f"**`⚠️ Error`**: You do not have sufficient permission.", ephemeral=False)
            return
        
        is_user = isinstance(target, (discord.User, discord.Member))
        is_role = isinstance(target, discord.Role)

        if is_user:
            config = self.config.guild(interaction.guild).whitelist_users()
        else:
            config = self.config.guild(interaction.guild).whitelist_roles()

        if not is_user and not is_role:
            await interaction.response.send_message(f"**`⚠️ Error`**: Invalid role or member. Please try again.", ephemeral=False)
            return

        if option == "add":
            async with config() as items:
                if target.id in items:
                    await interaction.response.send_message(f"**`⚠️ Error`**: {target.mention} is already in the whitelist!", ephemeral=False)
                    return
                items.append(target.id)
            await interaction.response.send_message(f"**`✅ Success`**: {target.mention} added to the whitelist!")

        elif option == "remove":
            async with config() as items:
                if target.id not in items:
                    await interaction.response.send_message(f"**`⚠️ Error`**: {target.mention} is not in the whitelist!", ephemeral=False)
                    return
                items.remove(target.id)
            await interaction.response.send_message(f"**`✅ Success`**: {target.mention} removed from the whitelist!")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        
        sconfg = self.config.guild(message.guild)
        filter = await sconfg.filtered_words()

        if not filter:
            return
        
        if await check_wl(self, message.author, message.guild):
            return
        
        if await check_perms(self.bot, message.author):
            return
        
        content = message.content
        hit = None

        for word in filter:
            if re.search(r'\b' + re.escape(word) + r'\b', content, re.IGNORECASE):
                hit = word
                break

        if not hit:
            return
        
        await delete_message_hit(message.author, message, hit)