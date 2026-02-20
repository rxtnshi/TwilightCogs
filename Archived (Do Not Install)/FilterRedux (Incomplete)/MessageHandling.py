import discord

from datetime import datetime
from redbot.core import Config, modlog

async def check_wl(cog, user: discord.Member, guild: discord.Guild) -> bool:
    sconfg = cog.config.guild(guild)

    wl_roles = await sconfg.whitelist_roles()
    wl_users = await sconfg.whitelist_users()

    if user.id in wl_users or any(r.id in wl_roles for r in user.roles):
        return True
    
    return False

async def check_perms(cog, user: discord.Member, guild: discord.Guild) -> bool:
    admin_roles = await cog.bot.get_admin_roles(guild)
    admin_roles_ids = {role.id for role in admin_roles}

    for role in user.roles:
        if role.id in admin_roles_ids:
            return True
    
    return False

async def notify_filter_hit(user: discord.Member, msg: discord.Message, trigger: str):
    channel = await modlog.get_modlog_channel(user.guild)
    if not channel:
        print("[FilterRedux] Failed to get the modlog channel. This may be due to it not existing.")
        return
    
    log_embed = discord.Embed(
        title="🚨 Filter Hit!",
        description=f"Filter has detected a restricted word from {user.mention} in {msg.channel.mention}. ",
        timestamp=datetime.now()
    )

    log_embed.set_thumbnail(url=user.display_avatar.url)
    log_embed.add_field(name="Detected Word", value=trigger)
    log_embed.add_field(name="Message Content", value=msg.content, inline=False)

    user_embed = discord.Embed(
        title="🚨 Filter Hit!",
        description="This is **NOT** an official warning. Filter has detected a restricted word in your message. If this continues, you may be moderated.",
        timestamp=datetime.now()
    )

    user_embed.set_thumbnail(url="https://cdn.rxtnshi.xyz/u/RBHN8b.gif")
    user_embed.add_field(name="Message Content", value=msg.content, inline=False)

    try:
        await user.send(embed=user_embed)
    except discord.Forbidden:
        await channel.send(f"Unable to notify {user.mention} of their filter hit.")

    await channel.send(embed=log_embed)

async def delete_message_hit(user: discord.User, msg: discord.Message, trigger: str):
    try:
        await msg.delete()
        await notify_filter_hit(user, msg, trigger)
    except discord.HTTPException as e:
        print(f"[Filter] Failed to delete a filter hit ({msg.id}) due to: {e}")