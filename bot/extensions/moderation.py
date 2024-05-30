from asyncpg import UniqueViolationError
import hikari
import lightbulb
from pypika import Query, Table, Schema

from ..data.static.functions import *
import random
from hikari import errors

plugin = lightbulb.Plugin("moderation")


def load(bot):
    bot.add_plugin(plugin)
    global bot_obj
    bot_obj = bot


def unload(bot):
    bot.remove_plugin(plugin)
    global bot_obj
    bot_obj = bot


@plugin.command()
@lightbulb.command("ping", "ping pong!")
@lightbulb.implements(lightbulb.SlashCommand)
async def ping(event: lightbulb.Context) -> None:
    guild_id = event.guild_id
    await event.respond("That")


############################################################################################################
async def mod_penalty_send(event, user, sanktion, dauer, regelbruch, proof, zusätzliches, moderator, id, penalty_row):
    try:
        embed = hikari.Embed(
            title="Neue Mod Penalty",
            description=f"**User:** {user.mention}\n\n**ID:** {id}\n\n**Sanktion:** {sanktion} {dauer}\n\n**Regelbruch:** {
                regelbruch}\n\n**Beweismittel:** {proof}\n\n**Zusätzliche Informationen:** {zusätzliches}\n\n**Moderator** {moderator.mention}",
            color=0xE74C3C,
        )
        embed.set_footer(
            text=(f"Uhrzeit: {datetime.now().strftime('%H:%M')}"))

        # type: ignore
        channel = await fetch_channel_from_id(plugin.bot.config.PENALTY_CHANNEL_ID)
        await channel_send_embed(channel, embed, penalty_row)
        # type: ignore
        await event.respond(f"Mod Penalty erstellt in <#{plugin.bot.config.PENALTY_CHANNEL_ID}>!")
    except Exception as e:
        await error_message("Fehler MP-01", e)
        content = f"Fehler **MP-01**"
        await interaction_response(event, content, component=None)

############################################################################################################
############################################################################################################
############################################################################################################
# Mod Warn Command


@plugin.command()
@lightbulb.option("remarks", "Additional things you want to mention", required=False)
@lightbulb.option("proof", "Proof of violation", hikari.Attachment, required=True)
@lightbulb.option("violation", "Reason for the sanction", required=True)
@lightbulb.option("id", "The user's ID", required=True)
@lightbulb.option("user", "The accused user", type=hikari.OptionType.USER, required=True)
@lightbulb.command("mod-warn", "Send a warning to a User.")
@lightbulb.implements(lightbulb.SlashCommand, lightbulb.UserCommand)
async def mod_warn(event: lightbulb.Context) -> None:
    await mod_ban(event)

# Mod Timeout Command


@plugin.command()
@lightbulb.option("remarks", "Additional things you want to mention", required=False)
@lightbulb.option("proof", "Proof of violation", hikari.Attachment, required=True)
@lightbulb.option("violation", "Reason for the sanction", required=True)
@lightbulb.option("duration", "Duration of the sanction", choices=["1 Day", "3 Days", "1 Weeks", "2 Weeks"], required=True)
@lightbulb.option("id", "The user's ID", required=True)
@lightbulb.option("user", "The accused user", type=hikari.OptionType.USER, required=True)
@lightbulb.command("mod-timeout", "Timeout a User in a Guild.")
@lightbulb.implements(lightbulb.SlashCommand, lightbulb.UserCommand)
async def mod_timeout(event: lightbulb.Context) -> None:
    await mod_ban(event)


# Mod Ban Command
@plugin.command()
@lightbulb.option("remarks", "Additional things you want to mention", required=False)
@lightbulb.option("proof", "Proof of violation", hikari.Attachment, required=False)
@lightbulb.option("violation", "Reason for the sanction", required=False)
@lightbulb.option("id", "The user's ID", required=False)
@lightbulb.option("user", "The accused user", type=hikari.OptionType.USER, required=False)
@lightbulb.command("mod-ban", "Ban a User from the Guild.")
@lightbulb.implements(lightbulb.SlashCommand, lightbulb.UserCommand)
async def mod_ban(event: lightbulb.Context) -> None:
    remarks = event.options.remarks

    # Check if remarks is None, if so, set it to "No Remarks"
    if remarks is None:
        remarks = "No Remarks"

    user = event.options.user
    id = event.options.id

    # Check if the ID and the User ID match
    if int(id) != int(user.id):
        await event.respond("The ID and the User ID do not match!")
        return

    guild_id = event.guild_id

    # Get the log channel from the database
    if bot_obj:
        sector = Schema(bot_obj.db.schema)
        query = Query.from_(sector.system).select(
            sector.system.log_channel_id).where(sector.system.guild_id == guild_id)
        channel_id = await bot_obj.db.field(query.get_sql())
        channel_id = int(channel_id)

    # Check if the log channel is set. If not, return an error message.
    if channel_id is None:
        await event.respond("No Log-channel found! Please set a Log-channel in your Dashboard!")
        return

    violation = event.options.violation
    proof = event.options.proof
    moderator = event.member
    if event.command is not None and event.command.name == "mod-ban":
        sanction = "Ban"
        duration = "Permanent"
    elif event.command is not None and event.command.name == "mod-timeout":
        sanction = "Timeout"
        duration = event.options.duration
    else:
        sanction = "Warn"
        duration = "3 Months"

    # Generate a random case_id
    for _ in range(3):
        case_id = "CID-" + \
            ''.join(random.choices('abcdefghijklmnopqrstuvwxyz1234567890', k=8))
        if moderator is not None:
            # Insert the case into the database
            try:
                sector = Schema(bot_obj.db.schema)
                query = (
                    Query.into(sector.moderation)
                    .columns(
                        sector.moderation.case_id,
                        sector.moderation.admin_id,
                        sector.moderation.moderator_id,
                        sector.moderation.user_id,
                        sector.moderation.violation,
                        sector.moderation.sanction,
                        sector.moderation.duration,
                        sector.moderation.proof,
                        sector.moderation.remarks,
                        sector.moderation.timestamp,
                        sector.moderation.status
                    )
                    .insert(case_id, 0, moderator.id, user.id, violation, sanction, duration, proof.url, remarks, datetime.now().strftime('%Y-%m-%d %H:%M'), 'Pending')
                )
                await bot_obj.db.execute(query.get_sql())
                break
            except UniqueViolationError:
                continue
    else:
        await event.respond("Failed to generate a unique case ID after 3 attempts.")
        return

    if moderator is not None:
        embed = hikari.Embed(
            title="New Mod Penalty",
            description=f"""**User:** {user.mention} | {user.username} | {id}\n\n**Sanction:** {sanction} {duration}\n\n**Violation:** {
                violation}\n\n**Proof:** {proof.url}\n\n**Case ID:** `{case_id}`\n\n**Remarks:** {remarks}\n\n**Moderator** {moderator.mention}""",
            color=0xE74C3C,
        )
        button = plugin.bot.rest.build_message_action_row()
        button.add_interactive_button(
            components.ButtonStyle.DANGER,
            case_id,
            label=sanction,
        )
        embed.set_footer(
            text=(f"Time: {datetime.now().strftime('%H:%M')}"))

        # type: ignore
        channel = await plugin.bot.rest.fetch_channel(channel_id)
        await channel.send(embed=embed, components=[button])  # type: ignore
        # type: ignore
        await event.respond(f"Mod Penalty created in <#{channel_id}>!")

# Listener for interaction create event


@plugin.listener(hikari.InteractionCreateEvent)
async def on_interaction_create_test(event: hikari.InteractionCreateEvent):
    if isinstance(event.interaction, hikari.ComponentInteraction):
        custom_id = event.interaction.custom_id
        guild_id = event.interaction.guild_id

        # Check if the custom ID starts with "CID-"
        if custom_id.startswith("CID-"):
            # Fetch information from the database
            if bot_obj:
                sector = Schema(bot_obj.db.schema)
                query = (
                    Query.from_(sector.moderation)
                    .select(
                        sector.moderation.case_id,
                        sector.moderation.admin_id,
                        sector.moderation.moderator_id,
                        sector.moderation.user_id,
                        sector.moderation.violation,
                        sector.moderation.sanction,
                        sector.moderation.duration,
                        sector.moderation.proof,
                        sector.moderation.remarks,
                        sector.moderation.timestamp,
                        sector.moderation.status,
                    )
                    .where(sector.moderation.case_id == custom_id)
                )
                query_str = str(query)
                case = await bot_obj.db.records(query_str)
                if case:
                    case_id, admin_id, moderator_id, user_id, violation, sanction, duration, proof, remarks, timestamp, status = case[
                        0]

                    # Fetch admin roles
                    admin = event.interaction.member
                    if guild_id and admin:
                        admin_id = admin.id
                        admin_permissions = admin.permissions
                        user = await plugin.bot.rest.fetch_user(user_id)
                        if user and status == "Pending":
                            if sanction == "Ban":
                                # Create button to unban server
                                button = plugin.bot.rest.build_message_action_row()
                                button.add_link_button(
                                    "https://discord.gg/dcu9q27tJg",
                                    label="Unban Server",
                                )
                                await event.interaction.create_initial_response(content=f"**<:icon_loading:1245685294079152180> Executing {sanction} on {user.mention}.** | Case ID: `{case_id}`", flags=64, response_type=hikari.ResponseType.MESSAGE_CREATE)
                                content = await event.interaction.fetch_initial_response()
                                
                                if admin_permissions.BAN_MEMBERS and admin_id != moderator_id:
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Permissions Checked")
                                    content = await event.interaction.fetch_initial_response()
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Sending Penalty message to {user.mention}")
                                    
                                    # Create embed for ban message
                                    try:
                                        embed = await create_embed(
                                            "You have been Banned",
                                            f"""**User** \n {user.mention} | {user} | {user_id} \n \n **Moderator**\n <@{moderator_id}> | Approved by {event.interaction.user.mention} \n \n **Reason** \n You have been permanently banned for **{
                                                violation}**, if this is incorrect, please contact the unbanning server or {event.interaction.user.mention} \n \n **Unbanning Server** \n https://discord.gg/dcu9q27tJg""",
                                            "#FF6669",
                                        )
                                        if embed is not None:
                                            await user.send(embed=embed, component=button)
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Sending Penalty message to {user.mention}")

                                    except Exception as e:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Sending Penalty message to {user.mention}")
                                    
                                    content = await event.interaction.fetch_initial_response()
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Banning {user.mention}")
                                    
                                    # Execute Ban
                                    try:
                                        await plugin.bot.rest.ban_user(guild_id, user_id, reason=violation)
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Banned {user.mention}")
                                    except Exception as e:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Banning {user.mention}")
                                        return
                                    
                                    content = await event.interaction.fetch_initial_response()
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Executing DB Entry `Approved`")
                                    
                                    try:
                                        # Update Admin in Database
                                        query = (
                                            Query.update(sector.moderation)
                                            .set(sector.moderation.admin_id, admin_id)
                                            .set(sector.moderation.status, "Approved")
                                            .where(sector.moderation.case_id == case_id)
                                        )
                                        # await bot_obj.db.execute(query.get_sql())
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> DB Entry `Approved` Executed")
                                    except Exception as e:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Executing DB Entry `Approved`")
                                        return
                                elif admin_id == moderator_id:
                                    # Timeout user until the sanction is approved
                                    await plugin.bot.rest.edit_member(guild_id, user, communication_disabled_until=datetime.utcnow() + timedelta(seconds=259200), reason=f"Timeout until sanction is approved (3 Days) | case ID: {case_id}")
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> You cannot approve your own sanction.\n- <:icon_exclamation:1245726822516396115> {user.mention} has been timed out for 3 days until the sanction is approved.")
                                    return
                                else:
                                    # You do not have permission to perform this action.
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> You do not have permission to perform this action.")
                                    return


                            elif sanction == "Timeout":
                                await event.interaction.create_initial_response(content=f"**<:icon_loading:1245685294079152180> Executing {sanction} on {user.mention}.** | Case ID: `{case_id}`", flags=64, response_type=hikari.ResponseType.MESSAGE_CREATE)
                                content = await event.interaction.fetch_initial_response()

                                if admin_permissions.MUTE_MEMBERS:
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Permissions Checked")
                                    content = await event.interaction.fetch_initial_response()


                                    timeout_duration = {
                                        "1 Day": timedelta(days=1),
                                        "3 Days": timedelta(days=3),
                                        "1 Weeks": timedelta(weeks=1),
                                        "2 Weeks": timedelta(weeks=2),
                                    }.get(duration)

                                    if timeout_duration:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Timing out {user.mention} for {duration}")
                                        try:
                                            await plugin.bot.rest.edit_member(guild_id, user, communication_disabled_until=datetime.utcnow() + timeout_duration, reason=f"Timeout for {duration} | case ID: {case_id}")
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Timeout applied to {user.mention} for {duration}")
                                            content = await event.interaction.fetch_initial_response()

                                            embed = await create_embed(
                                            "You have been Timed Out",
                                            f"""**User** \n {user.mention} | {user} | {user_id} \n \n **Moderator**\n <@{moderator_id}> | Approved by {event.interaction.user.mention} \n \n **Reason** \n You have been timed out for **{
                                                violation}**, if this is incorrect, please contact the unbanning server or {event.interaction.user.mention} \n \n **Unbanning Server** \n https://discord.gg/dcu9q27tJg \n \n **Duration** \n {duration}""",
                                            "#FF6669",
                                            )
                                        except Exception as e:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error applying Timeout to {user.mention}")
                                            return
                                        
                                        if embed is not None:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Sending Penalty message to {user.mention}")
                                            try:
                                                await user.send(embed=embed)
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Timeout message sent to {user.mention}")
                                                content = await event.interaction.fetch_initial_response()

                                            except Exception as e:
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Sending Penalty message to {user.mention}")
                                                content = await event.interaction.fetch_initial_response()
                                                return
                                    else:
                                        # Invalid duration
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Invalid Timeout Duration")
                                        return
                                else:
                                    # You do not have permission to perform this action.
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> You do not have permission to perform this action.")
                            elif sanction == "Warn":
                                await event.interaction.create_initial_response(content=f"**<:icon_loading:1245685294079152180> Executing {sanction} on {user.mention}.** | Case ID: `{case_id}`", flags=64, response_type=hikari.ResponseType.MESSAGE_CREATE)
                                content = await event.interaction.fetch_initial_response()

                                if admin_permissions.VIEW_AUDIT_LOG:
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Permissions Checked")
                                    content = await event.interaction.fetch_initial_response()

                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Sending Warning message to {user.mention}")

                                    embed = await create_embed(
                                        "You have been Warned",
                                        f"Hey {user.mention}, \n\nWe regret to inform you that you have received a warning. The reason for this is **{violation}**. This warning will remain in effect for 3 months. \n If you receive a total of three warnings, a permanent ban will be imposed! \n\nIf you believe there is an error, you can always open a <#963132179813109790>. \n\nPlease remember to maintain a respectful tone and promote a positive atmosphere in our community. \n\nBest regards, \nThe moderation team",
                                        "#FF6669"
                                    )

                                    try:
                                        if embed is not None:
                                            await user.send(embed=embed)
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Warning sent to {user.mention}")
                                    except Exception as e:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error sending Warning message to {user.mention}")
                                        return
                                else:
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> You do not have permission to perform this action.")
                                    return


@plugin.listener(hikari.InteractionCreateEvent)
async def on_interaction_create(event: hikari.InteractionCreateEvent):
    if isinstance(event.interaction, hikari.ComponentInteraction):
        custom_id = event.interaction.custom_id
        guild_id = event.interaction.guild_id

        if custom_id in ["permban", "timeout", "warn"]:

            if custom_id == "permban":
                values = get_embed_values(event)

                if values:
                    regelbruch = values[0]
                    moderator = values[2]
                    id = values[3]
                    user = await fetch_user_from_id(int(id))

                    if user:
                        embed = await create_embed("Du wurdest Permanent Gebannt", f"**User** \n {user.mention} | {user} | {id} \n \n **Teammitglied**\n {moderator} | Angenommen von {event.interaction.user.mention} \n \n **Grund** \n Du wurdest wegen **{regelbruch}** Permanent Gebannt, sollte dies falsch sein, melde dich bitte auf dem Entbannungsserver oder bei {event.interaction.user.mention} \n \n **Entbannungsserver** \n Comming Soon.", "#FF6669")

                        try:
                            if embed is not None:
                                await user.send(embed=embed)
                            else:
                                await user.send(content="No embed provided.")
                            embed = await create_embed("Permanent Gebannt", f"> **User:** {user.mention} | {user.username}\n> **ID:** {user.id}\n> **Regelbruch:** {regelbruch}\n> **Dauer:** Permanent\n> **Teammitglied:** {moderator}", "#E74D3C")
                            # type: ignore
                            channel = await fetch_channel_from_id(plugin.bot.config.MODERATION_LOG_CHANNEL_ID)
                            await channel_send_embed(channel, embed, component=None)
                        except Exception as e:
                            embed = await create_embed("Permanent Gebannt", f"> **User:** {user.mention} | {user.username}\n> **ID:** {user.id}\n> **Regelbruch:** {regelbruch}\n> **Dauer:** Permanent\n> **Teammitglied:** {moderator}", "#E74D3C")
                            # type: ignore
                            channel = await fetch_channel_from_id(plugin.bot.config.MODERATION_LOG_CHANNEL_ID)
                            await channel_send_embed(channel, embed, component=None)
                            await error_message("Fehler MP-04", e)
                            content = f"Fehler **MP-04**"
                            await interaction_response(event, content, component=None)

                        try:
                            await user_permanent_ban(guild_id, int(id), regelbruch)
                        except Exception as e:
                            await error_message("Fehler **MP-02**", e)
                            content = f"Fehler **MP-02**"
                            await interaction_response(event, content, component=None)

                        edited_button = []
                        ban_button = plugin.bot.rest.build_message_action_row()
                        ban_button.add_interactive_button(
                            components.ButtonStyle.DANGER,
                            "ban",
                            label=f"gebannt von {
                                event.interaction.user.username}",
                            is_disabled=True,
                        )
                        unban_button = plugin.bot.rest.build_message_action_row()
                        unban_button.add_interactive_button(
                            components.ButtonStyle.SUCCESS,
                            "unban",
                            label=f"Entbannen",
                        )
                        edited_button.append(ban_button)
                        edited_button.append(unban_button)
                        await event.interaction.message.edit(components=edited_button)

            elif custom_id == "timeout":
                values = get_embed_values(event)

                if values:
                    regelbruch = values[0]
                    dauer = values[1]
                    moderator = values[2]
                    id = values[3]

                    if guild_id and dauer:
                        try:
                            user = await plugin.bot.rest.fetch_member(guild_id, id)
                        except Exception as e:
                            await error_message("Fehler **F-01**", e)
                            content = f"Fehler **F-01**"
                            await interaction_response(event, content, component=None)
                            return

                        duration_mapping = {
                            "1 Tag": 1 * 24 * 60 * 60,
                            "3 Tage": 3 * 24 * 60 * 60,
                            "1 Woche": 7 * 24 * 60 * 60,
                            "2 Wochen": 14 * 24 * 60 * 60,
                            "1 Monat": 30 * 24 * 60 * 60,
                            "3 Monate": 3 * 30 * 24 * 60 * 60,
                        }
                        duration = duration_mapping.get(dauer)

                        if duration and user:

                            try:
                                await user.edit(
                                    communication_disabled_until=datetime.utcnow()
                                    + timedelta(seconds=duration),
                                    reason=regelbruch,
                                )
                                content = f"Fehler **MP-01**"
                                await interaction_response(event, content, component=None)
                            except Exception as e:
                                await error_message("Fehler **MP-03**", e)
                                content = f"Fehler **MP-03**"
                                await interaction_response(event, content, component=None)

                            embed = await create_embed("Du wurdest Timeouted", f"**User** \n {user.mention} | user | {id} \n \n **Teammitglied**\n {moderator} | Angenommen von {event.interaction.user.mention} \n \n **Grund** \nDu wurdest wegen **{regelbruch}** für {dauer} in den Timeout versetzt. Infolge hast du eine Verwarnung erhalten. Die verwarnung bleibt für 3 Monate bestehen. Solltest du insgesamt drei Verwarnungen erhalten, droht ein Permaneter ausschluss!\n\nWenn du der Meinung bist, dass hier ein Fehler vorliegt, kannst du jederzeit ein <#963132179813109790> öffnen.\n\nBitte achte in Zukunft darauf, einen respektvollen Umgangston zu wahren und eine positive Atmosphäre in unserer Community zu fördern.\n \n **Entbannungsserver** \n Comming Soon.", "#FF6669")

                            try:
                                await user_send_dm(user, embed, component=None)
                                embed = await create_embed("Timeout", f"> **User:** {user.mention} | {user.username}\n> **ID:** {user.id}\n> **Regelbruch:** {regelbruch}\n> **Dauer:** Timeout {dauer}\n> **Teammitglied:** {moderator}", "#FF6669")
                                # type: ignore
                                channel = await fetch_channel_from_id(plugin.bot.config.MODERATION_LOG_CHANNEL_ID)
                                await channel_send_embed(channel, embed, component=None)
                            except Exception as e:
                                embed = await create_embed("Timeout", f"> **User:** {user.mention} | {user.username}\n> **ID:** {user.id}\n> **Regelbruch:** {regelbruch}\n> **Dauer:** Timeout {dauer}\n> **Teammitglied:** {moderator}", "#FF6669")
                                # type: ignore
                                channel = await fetch_channel_from_id(plugin.bot.config.MODERATION_LOG_CHANNEL_ID)
                                await channel_send_embed(channel, embed, component=None)
                                await error_message("Fehler MP-04", e)
                                content = f"Fehler **MP-04**"
                                await interaction_response(event, content, component=None)

                            edited_button = []
                            timeout_button = plugin.bot.rest.build_message_action_row()
                            timeout_button.add_interactive_button(
                                components.ButtonStyle.PRIMARY,
                                "timeout",
                                label=f"Timedout von {
                                    event.interaction.user.username}",
                                is_disabled=True,
                            )
                            remove_timeout_button = plugin.bot.rest.build_message_action_row()
                            remove_timeout_button.add_interactive_button(
                                components.ButtonStyle.SUCCESS,
                                "remove_timeout",
                                label=f"Remove Timeout",
                            )
                            edited_button.append(timeout_button)
                            edited_button.append(remove_timeout_button)
                            await event.interaction.message.edit(components=edited_button)

            elif custom_id == "warn":
                values = get_embed_values(event)

                if values:
                    regelbruch = values[0]
                    id = values[3]

                    if guild_id:
                        try:
                            user = await plugin.bot.rest.fetch_member(guild_id, id)
                        except Exception as e:
                            await error_message("Fehler **F-01**", e)
                            content = f"Fehler **F-01**"
                            await interaction_response(event, content, component=None)

                        embed = await create_embed("Du wurdest Verwarnt", f"Hey {user.mention}, \n\nWir müssen dir leider mitteilen, dass du eine Verwarnung erhalten hast. Grund dafür ist **{regelbruch}**. Diese Verwarnung bleibt für 3 Monate bestehen. \n Solltest du insgesamt drei Verwarnungen erhalten, droht ein Permanenter ausschluss!\n\nWenn du der Meinung bist, dass hier ein Fehler vorliegt, kannst du jederzeit ein <#963132179813109790> öffnen.\n\nBitte achte in Zukunft darauf, einen respektvollen Umgangston zu wahren und eine positive Atmosphäre in unserer Community zu fördern. \n\nBeste Grüße, \nDas Moderationsteam", "#FF6669")

                        try:
                            await user_send_dm(user, embed, component=None)
                        except Exception as e:
                            await error_message("Fehler **MP-04**", e)
                            content = f"Fehler **MP-04**"
                            await interaction_response(event, content, component=None)

                        content = f"{user.mention} Erfolgreich Verwarnt"
                        await interaction_response(event, content, component=None)

                        edited_button = []
                        warn_button = plugin.bot.rest.build_message_action_row()
                        warn_button.add_interactive_button(
                            components.ButtonStyle.SECONDARY,
                            "warn",
                            label=f"Verwarnt von {
                                event.interaction.user.username}",
                            is_disabled=True,
                        )
                        remove_warn_button = plugin.bot.rest.build_message_action_row()
                        remove_warn_button.add_interactive_button(
                            components.ButtonStyle.SUCCESS,
                            "remove_warn",
                            label=f"Remove Warn",
                        )
                        edited_button.append(warn_button)
                        edited_button.append(remove_warn_button)
                        await event.interaction.message.edit(components=edited_button)

        elif custom_id in ["unban", "remove_timeout", "remove_warn"]:
            values = get_embed_values(event)
            if values:
                id = values[3]
                if custom_id == "unban":
                    # if user is banned <- check if user is banned fia db
                    # if interaction.user has permission <- check via db
                    await user_unban(guild_id, id)
                    # Edit Button
                    return
                elif custom_id == "remove_timeout":
                    # if user is still in timeout
                    # if interaction.user has permission <- check via db
                    # remove timeout
                    # Edit Button
                    return
                elif custom_id == "remove_warn":
                    # set warn to false in db
                    return
