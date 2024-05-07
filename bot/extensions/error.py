import hikari
import lightbulb
from pypika import Query, Table, Field, Schema


plugin = lightbulb.Plugin("error")

def load(bot):
    bot.add_plugin(plugin)
    global bot_obj
    bot_obj = bot


def unload(bot):
    bot.remove_plugin(plugin)
    global bot_obj
    bot_obj = bot


# Starting error handling || This doesnt Work yet
@plugin.listener(hikari.ExceptionEvent)
async def on_error(event: hikari.ExceptionEvent):
    print("Error")
    guild_id = event.failed_event.interaction.guild_id
    channel_id = event.failed_event.interaction.channel_id
    user_id = event.failed_event.interaction.user.id
    username = event.failed_event.interaction.user.username
    command_id = event.failed_event.interaction.command_id
    command_name = event.failed_event.interaction.command_name
    exception = event.exception
    content = f"**User:** <@{user_id}> | {username} | {user_id}\n**Channel:** <#{channel_id}> | {channel_id}\n**Command:** </{command_name}:{command_id}> | {command_name} | {command_id}\n**Error:** `{exception}`"
    try:
        sector = Schema('sector')
        query = Query.from_(sector.system).select(sector.system.error_channel_id).where(sector.system.guild_id == guild_id)
        result = await bot_obj.cm.cached_dbselect(str(query))
        channel = await plugin.bot.rest.fetch_channel(result)
        try:
            embed = hikari.Embed(
            title = "Error",
            description = content,
            color = 0xFF0000)
            await channel.send(embed = embed)
            return
        except Exception as e:
            user = await plugin.bot.rest.fetch_user(442729843055132674)
            await user.send(f"{content}\n Error: {e}")
            print(content)
            return
    except Exception as e:
        user = await plugin.bot.rest.fetch_user(442729843055132674)
        await user.send(f"{content}\n Error: {e}")
        print(content)
        return
    

    