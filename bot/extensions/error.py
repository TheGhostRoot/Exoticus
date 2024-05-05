import hikari
import lightbulb
from pypika import Query, Table, Field


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
    
    if event.failed_event is None:
        sector = Schema('sector')
        query = Query.from_(sector).select(sector.system.log_channel_id).where(sector.system.guild_id == guild_id)
        result = await bot_obj.chacheManager.cached_dbselect(query)
        error_channel_id = result[0][0]
        error_channel = bot_obj.get_channel(error_channel_id)
        ref = await record_error(event.exception, event.exc_info, event.failed_event)
        await error_channel.send(f"{event.failed_event} Something went wrong (ref: {ref}).")
    print(event.failed_event)
