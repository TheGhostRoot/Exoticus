from asyncpg import UniqueViolationError
import hikari
import lightbulb
from pypika import Query, Schema

from ..data.static.functions import *
import random

plugin = lightbulb.Plugin("moderation")


def load(bot):
    bot.add_plugin(plugin)
    global bot_obj
    bot_obj = bot


def unload(bot):
    bot.remove_plugin(plugin)
    global bot_obj
    bot_obj = bot

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
                        sector.moderation.admin_approved,
                        sector.moderation.admin_revoked,
                        sector.moderation.admin_issuer,
                        sector.moderation.user_id,
                        sector.moderation.violation,
                        sector.moderation.sanction,
                        sector.moderation.duration,
                        sector.moderation.proof,
                        sector.moderation.remarks,
                        sector.moderation.timestamp,
                        sector.moderation.status
                    )
                    .insert(case_id, 0, 0, moderator.id, user.id, violation, sanction, duration, proof.url, remarks, datetime.now().strftime('%Y-%m-%d %H:%M'), 'Pending')
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
            description=f"""<:icon_user:1252618658031861861> **User:** {user.mention} | {user.username} | {id}\n\n<:icon_ban:1157787079149895731> **Sanction:** {sanction} {duration}\n\n<:icon_verified:1252619859703890013> **Violation:** {
                violation}\n\n<:icon_file:1252618923052892220> **Proof:** {proof.url}\n\n<:icon_channel:1157786923486683176> **Case ID:** `{case_id}`\n\n<:icon_info:1252620053396848711> **Remarks:** {remarks}\n\n<:icon_staff:1157786955996729376> **Issued by** {moderator.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*""",
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
        if event.respond:
            await event.respond(f"Mod Penalty created in <#{channel_id}>!")
        

# Listener for interaction create event


@plugin.listener(hikari.InteractionCreateEvent)
async def on_interaction_create_test(event: hikari.InteractionCreateEvent):
    if isinstance(event.interaction, hikari.ComponentInteraction):
        custom_id = event.interaction.custom_id
        guild_id = event.interaction.guild_id

        # Check if the custom ID starts with "CID-"
        if custom_id.startswith("CID-"):
            if custom_id.endswith("-UNBAN"):
                custom_id = custom_id[:-6]
                # Fetch information from the database
            if bot_obj:
                sector = Schema(bot_obj.db.schema)
                query = (
                    Query.from_(sector.moderation)
                    .select(
                        sector.moderation.case_id,
                        sector.moderation.admin_approved,
                        sector.moderation.admin_revoked,
                        sector.moderation.admin_issuer,
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
                    case_id, admin_approved, admin_revoked, admin_issuer, user_id, violation, sanction, duration, proof, remarks, timestamp, status = case[
                        0]

                    # Fetch admin roles
                    admin = event.interaction.member
                    if guild_id and admin:
                        admin_approved = admin.id
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
                                
                                if admin_permissions.BAN_MEMBERS: #and admin_approved != admin_issuer
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Permissions Checked")
                                    content = await event.interaction.fetch_initial_response()
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Sending Penalty message to {user.mention}")
                                    
                                    # Create embed for ban message
                                    try:
                                        embed = await create_embed(
                                            "You have been Banned",
                                            f"""**User** \n {user.mention} | {user} | {user_id} \n \n **Issued by**\n <@{admin_issuer}> | Approved by {event.interaction.user.mention} \n \n **Reason** \n You have been permanently banned for **{
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
                                            .set(sector.moderation.admin_approved, admin_approved)
                                            .set(sector.moderation.status, "Approved")
                                            .where(sector.moderation.case_id == case_id)
                                        )
                                        await bot_obj.db.execute(query.get_sql())
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> DB Entry `Approved` Executed")
                                    except Exception as e:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Executing DB Entry `Approved`")
                                        return
                                    try:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Editing Embed")
                                        edited_button = []
                                        unban_button = plugin.bot.rest.build_message_action_row()
                                        unban_button.add_interactive_button(
                                            components.ButtonStyle.SUCCESS,
                                            case_id+"-UNBAN",
                                            label=f"Unban",
                                        )
                                        edited_button.append(unban_button)
                                        await event.interaction.message.edit(components=edited_button)
                                        # edit old Embed (add Revoked Moderator to embed)
                                        if len(event.interaction.message.embeds) > 0:
                                            embed = event.interaction.message.embeds[0]
                                            if embed.description is not None:
                                                embed.description += f"\n<:icon_invite:1157786940255518811> **Approved by:** {admin.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                                            else:
                                                embed.description = f"\n<:icon_invite:1157786940255518811> **Approved by:** {admin.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                                            await event.interaction.message.edit(embed=embed)

                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Embed Edited")
                                    except Exception as e:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Editing Embed")
                                        return





                                elif admin_approved == admin_issuer:
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
                                            f"""**User** \n {user.mention} | {user} | {user_id} \n \n **Issued by**\n <@{admin_issuer}> | Approved by {event.interaction.user.mention} \n \n **Reason** \n You have been timed out for **{
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
                                            content = await event.interaction.fetch_initial_response()
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Executing DB Entry `Approved`")
                                        
                                        try:
                                            # Update Admin in Database
                                            query = (
                                                Query.update(sector.moderation)
                                                .set(sector.moderation.admin_approved, admin_approved)
                                                .set(sector.moderation.status, "Approved")
                                                .where(sector.moderation.case_id == case_id)
                                            )
                                            await bot_obj.db.execute(query.get_sql())
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> DB Entry `Approved` Executed")
                                        except Exception as e:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Executing DB Entry `Approved`")
                                            return
                                        try:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Editing Embed")
                                            edited_button = []
                                            unban_button = plugin.bot.rest.build_message_action_row()
                                            unban_button.add_interactive_button(
                                                components.ButtonStyle.SUCCESS,
                                                case_id+"-UNBAN",
                                                label=f"Remove Timeout",
                                            )
                                            edited_button.append(unban_button)
                                            await event.interaction.message.edit(components=edited_button)
                                            # edit old Embed (add Revoked Moderator to embed)
                                            if len(event.interaction.message.embeds) > 0:
                                                embed = event.interaction.message.embeds[0]
                                                if embed.description is not None:
                                                    embed.description += f"\n<:icon_invite:1157786940255518811> **Approved by:** {admin.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                                                else:
                                                    embed.description = f"\n<:icon_invite:1157786940255518811> **Approved by:** {admin.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                                                await event.interaction.message.edit(embed=embed)
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Embed Edited")
                                        except Exception as e:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Editing Embed")
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
                        elif user and status == "Approved":
                            if sanction == "Ban":
                                await event.interaction.create_initial_response(content=f"**<:icon_loading:1245685294079152180> Revoking Ban on {user.mention}.** | Case ID: `{case_id}`", flags=64, response_type=hikari.ResponseType.MESSAGE_CREATE)
                                content = await event.interaction.fetch_initial_response()
                                if int(admin_revoked) == 0:
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Checking Permissions")
                                    admin_approved = admin.id
                                    admin_permissions = admin.permissions
                                    if admin_permissions.BAN_MEMBERS or admin_approved == admin_issuer:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Permissions Checked")
                                        content = await event.interaction.fetch_initial_response()
                                        try:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Unbanning {user.mention}")
                                            await plugin.bot.rest.unban_user(guild_id, user_id)
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Unbanned {user.mention}")
                                            content = await event.interaction.fetch_initial_response()
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Executing DB Entry `Revoked`")
                                            try:
                                                # Update Revoke Admin in DB and Change Status to Revoked
                                                query = (
                                                    Query.update(sector.moderation)
                                                    .set(sector.moderation.admin_revoked, admin_revoked)
                                                    .set(sector.moderation.status, "Revoked")
                                                    .where(sector.moderation.case_id == case_id)
                                                )
                                                await bot_obj.db.execute(query.get_sql())
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> DB Entry `Revoked` Executed")
                                                content = await event.interaction.fetch_initial_response()
                                                try:
                                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Editing Embed")
                                                    edited_button = []
                                                    await event.interaction.message.edit(components=edited_button)
                                                    # edit old Embed (add Revoked Moderator to embed)
                                                    if len(event.interaction.message.embeds) > 0:
                                                        embed = event.interaction.message.embeds[0]
                                                        if embed.description is not None:
                                                            embed.description += f"\n<:icon_verified:1157786964364365864> **Revoked by:** {admin.mention}"
                                                        else:
                                                            embed.description = f"\n<:icon_verified:1157786964364365864> **Revoked by:** {admin.mention}"
                                                        await event.interaction.message.edit(embed=embed)

                                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Embed Edited")
                                                except Exception as e:
                                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Editing Embed")
                                                    return
                                            except Exception as e:
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Executing DB Entry `Revoked`")
                                                return


                                        except Exception as e:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Unbanning {user.mention}")
                                            return
                            elif sanction == "Timeout":
                                await event.interaction.create_initial_response(content=f"**<:icon_loading:1245685294079152180> Removing Timout on {user.mention}.** | Case ID: `{case_id}`", flags=64, response_type=hikari.ResponseType.MESSAGE_CREATE)
                                content = await event.interaction.fetch_initial_response()
                                if int(admin_revoked) == 0:
                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Checking Permissions")
                                    admin_approved = admin.id
                                    admin_permissions = admin.permissions
                                    if admin_permissions.BAN_MEMBERS or admin_approved == admin_issuer:
                                        await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Permissions Checked")
                                        content = await event.interaction.fetch_initial_response()
                                        try:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Removing Timeout from {user.mention}")
                                            await plugin.bot.rest.edit_member(guild_id, user, communication_disabled_until=None)
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Timout Removed from {user.mention}")
                                            content = await event.interaction.fetch_initial_response()
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Executing DB Entry `Revoked`")
                                            try:
                                                # Update Revoke Admin in DB and Change Status to Revoked
                                                query = (
                                                    Query.update(sector.moderation)
                                                    .set(sector.moderation.admin_revoked, admin_revoked)
                                                    .set(sector.moderation.status, "Revoked")
                                                    .where(sector.moderation.case_id == case_id)
                                                )
                                                await bot_obj.db.execute(query.get_sql())
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> DB Entry `Revoked` Executed")
                                                content = await event.interaction.fetch_initial_response()
                                                try:
                                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_loading:1245685294079152180> Editing Embed")
                                                    edited_button = []
                                                    await event.interaction.message.edit(components=edited_button)
                                                    # edit old Embed (add Revoked Moderator to embed)
                                                    if len(event.interaction.message.embeds) > 0:
                                                        embed = event.interaction.message.embeds[0]
                                                        if embed.description is not None:
                                                            embed.description += f"\n<:icon_verified:1157786964364365864> **Removed by:** {admin.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                                                        else:
                                                            embed.description = f"\n<:icon_verified:1157786964364365864> **Removed by:** {admin.mention} | *{datetime.now().strftime('%Y-%m-%d %H:%M')}*"
                                                        await event.interaction.message.edit(embed=embed)

                                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_correct:1157786925680308386> Embed Edited")
                                                except Exception as e:
                                                    await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Editing Embed")
                                                    return
                                            except Exception as e:
                                                await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Executing DB Entry `Revoked`")
                                                return


                                        except Exception as e:
                                            await event.interaction.edit_initial_response(content=f"{content.content}\n- <:icon_wrong:1157786966381822003> Error Unbanning {user.mention}")
                                            return
                                    

