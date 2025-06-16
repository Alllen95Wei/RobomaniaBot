# coding=utf-8
import time
import datetime
import zoneinfo
import discord
from discord.ext import commands
from discord import Option, Embed
import os
from shlex import split
from subprocess import run
from dotenv import load_dotenv
from platform import system
import git
import logging
from typing import Literal

import json_assistant
import detect_pc_status
import update as upd
import logger

# import arduino_reader

# 機器人
intents = discord.Intents.all()
bot = commands.Bot(intents=intents, help_command=None)
# 常用物件、變數
base_dir = os.path.abspath(os.path.dirname(__file__))
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
default_color = 0x012A5E
error_color = 0xF1411C
real_logger = logger.CreateLogger()
# 載入TOKEN
load_dotenv(dotenv_path=os.path.join(base_dir, "TOKEN.env"))
TOKEN = str(os.getenv("TOKEN"))

bot.logger = real_logger


class RespondLeaderMailbox(discord.ui.Modal):
    class ResponseType:
        public = "公開"
        private = "私人"

    def __init__(self, message_id: str, response_type) -> None:
        super().__init__(title="回覆信箱訊息", timeout=None)
        self.add_item(
            discord.ui.InputText(
                style=discord.InputTextStyle.long, label="回覆內容", required=True
            )
        )
        self.message_id = message_id
        self.response_type = response_type

    async def callback(self, interaction: discord.Interaction):
        await reply_to_leader_mail(
            interaction, self.message_id, self.children[0].value, self.response_type
        )


class RespondLeaderMailboxInView(discord.ui.View):
    def __init__(self, message_id: str):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(
        label="以私人訊息回覆", style=discord.ButtonStyle.green, emoji="💬"
    )
    async def private_respond(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.send_modal(
            RespondLeaderMailbox(
                self.message_id, RespondLeaderMailbox.ResponseType.private
            )
        )

    @discord.ui.button(
        label="以公開訊息回覆", style=discord.ButtonStyle.blurple, emoji="📢"
    )
    async def public_respond(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        await interaction.response.send_modal(
            RespondLeaderMailbox(
                self.message_id, RespondLeaderMailbox.ResponseType.public
            )
        )


@bot.event
async def on_ready():
    real_logger.info("機器人準備完成！")
    real_logger.info(f"PING值：{round(bot.latency * 1000)}ms")
    real_logger.info(f"登入身分：{bot.user}")
    activity = discord.Activity(
        name="GitHub",
        type=discord.ActivityType.watching,
        url="https://github.com/Alllen95Wei/RobomaniaBot",
    )
    await bot.change_presence(activity=activity)


@bot.event
async def on_application_command(ctx):
    if ctx.command.parent is None:
        real_logger.info(f'{ctx.author} 執行了斜線指令 "{ctx.command.name}"')
    else:
        real_logger.info(
            f'{ctx.author} 執行了斜線指令 "{ctx.command.parent.name} {ctx.command.name}"'
        )


@bot.slash_command(name="ping", description="查看機器人延遲。")
async def ping(ctx):
    embed = Embed(title="PONG!✨", color=default_color)
    embed.add_field(name="PING值", value=f"`{round(bot.latency * 1000)}` ms")
    await ctx.respond(embed=embed)


@bot.event
async def on_application_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = Embed(
            title="指令冷卻中",
            description=f"這個指令正在冷卻中，請在`{round(error.retry_after)}`秒後再試。",
            color=error_color,
        )
        await ctx.respond(embed=embed, ephemeral=True)
    elif isinstance(error, commands.NotOwner) or isinstance(
        error, commands.MissingRole
    ):
        embed = Embed(
            title="錯誤", description="你沒有權限使用此指令。", color=error_color
        )
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        embed = Embed(
            title="錯誤",
            description="發生了一個錯誤，錯誤詳細資料如下。",
            color=error_color,
        )
        if ctx.command.parent is None:
            embed.add_field(
                name="指令名稱", value=f"`{ctx.command.name}`", inline=False
            )
        else:
            embed.add_field(
                name="指令名稱",
                value=f"`{ctx.command.parent.name} {ctx.command.name}`",
                inline=False,
            )
        embed.add_field(name="使用者", value=f"`{ctx.author}`", inline=False)
        embed.add_field(
            name="錯誤類型", value=f"`{type(error).__name__}`", inline=False
        )
        embed.add_field(name="錯誤訊息", value=f"`{error}`", inline=False)
        allen = bot.get_user(657519721138094080)
        await allen.send(embed=embed)
        embed = Embed(
            title="錯誤",
            description="發生了一個錯誤，已經通知開發者。",
            color=error_color,
        )
        await ctx.respond(embed=embed, ephemeral=True)
        raise error


# member_cmd = bot.create_group(name="member", description="隊員資訊相關指令。")


# @member_cmd.command(name="查詢", description="查看隊員資訊。")
# async def member_info(ctx,
#                       隊員: Option(discord.Member, "隊員", required=False) = None):
#     if 隊員 is None:
#         隊員 = ctx.author
#     member_data = json_assistant.User(隊員.id)
#     jobs_str = ""
#     if len(member_data.get_jobs()) != 0:
#         for job in member_data.get_jobs():
#             jobs_str += f"* {job}\n"
#     else:
#         jobs_str = "(無)"
#     embed = Embed(title="隊員資訊", description=f"{隊員.mention} 的資訊", color=default_color)
#     embed.add_field(name="真實姓名", value=member_data.get_real_name(), inline=False)
#     embed.add_field(name="職務", value=jobs_str, inline=False)
#     # embed.add_field(name="總計會議時數", value=member_data.get_total_meeting_time(), inline=False)
#     embed.add_field(name="警告點數", value=f"`{member_data.get_warning_points()}` 點", inline=False)
#     embed.set_thumbnail(url=隊員.display_avatar)
#     await ctx.respond(embed=embed)


# @member_cmd.command(name="查詢記點人員", description="列出點數不為 0 的隊員。")
# async def member_list_bad_guys(ctx):
#     members = json_assistant.User.get_all_user_id()
#     embed = Embed(title="遭記點隊員清單", description="以下為點數不為 0 的前 25 名隊員：", color=default_color)
#     bad_guys: list[dict[str, str | float | int]] = []
#     for m in members:
#         member_obj = json_assistant.User(m)
#         if member_obj.get_warning_points() != 0:
#             bad_guys.append({"name": member_obj.get_real_name(), "points": member_obj.get_warning_points()})
#     bad_guys.sort(key=lambda x: x["points"], reverse=True)
#     if len(bad_guys) > 25:
#         bad_guys = bad_guys[:25]
#     for bad_guy in bad_guys:
#         medals = ("🥇", "🥈", "🥉")
#         if bad_guys.index(bad_guy) <= 2:
#             bad_guy["name"] = medals[bad_guys.index(bad_guy)] + " " + bad_guy["name"]
#         embed.add_field(name=bad_guy["name"], value=f"`{bad_guy['points']}` 點", inline=False)
#     if len(embed.fields) == 0:
#         embed.add_field(name="(沒有遭記點隊員)", value="所有人目前皆無點數！", inline=False)
#     await ctx.respond(embed=embed)


# @member_cmd.command(name="以真名查詢id", description="使用真名查詢使用者的 Discord ID，可用於讀取已離開成員的資料。")
# async def member_search_by_real_name(ctx, real_name: Option(str, name="真名", description="成員的真名", required=True)):
#     members = json_assistant.User.get_all_user_id()
#     results = []
#     for m in members:
#         member_obj = json_assistant.User(m)
#         if member_obj.get_real_name() == real_name:
#             results.append(m)
#     if len(results) != 0:
#         embed = Embed(title="搜尋結果", description=f"真名為 `{real_name}` 的資料共有 {len(results)} 筆：", color=default_color)
#         for result in results:
#             embed.add_field(name=result, value="", inline=False)
#     else:
#         embed = Embed(title="搜尋結果", description=f"沒有任何真名為 `{real_name}` 的資料。", color=error_color)
#     await ctx.respond(embed=embed)


# @bot.user_command(name="查看此隊員的資訊")
# async def member_info_user(ctx, user: discord.Member):
#     await member_info(ctx, user)


member_info_manage = bot.create_group(name="manage", description="隊員資訊管理。")


@member_info_manage.command(name="設定真名", description="設定隊員真實姓名。")
@commands.has_role(1114205838144454807)
async def member_set_real_name(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    real_name: Option(str, "真實姓名", name="真實姓名", required=True),
):
    member_data = json_assistant.User(member.id)
    member_data.set_real_name(real_name)
    embed = Embed(
        title="設定真實姓名",
        description=f"已將 {member.mention} 的真實姓名設定為 {real_name}。",
        color=default_color,
    )
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="新增職務", description="新增隊員職務。")
@commands.has_role(1114205838144454807)
async def member_add_job(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    job: Option(str, "職務", name="職務", required=True),
):
    member_data = json_assistant.User(member.id)
    member_data.add_job(job)
    embed = Embed(
        title="新增職務",
        description=f"已將 {member.mention} 新增職務 {job}。",
        color=default_color,
    )
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="移除職務", description="移除隊員職務。")
@commands.has_role(1114205838144454807)
async def member_remove_job(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    job: Option(str, "職務", name="職務", required=True),
):
    member_data = json_assistant.User(member.id)
    member_data.remove_job(job)
    embed = Embed(
        title="移除職務",
        description=f"已將 {member.mention} 移除職務 {job}。",
        color=default_color,
    )
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="add_meeting_time", description="新增隊員會議時數。")
@commands.has_role(1114205838144454807)
async def member_add_meeting_time(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    meeting_hours: Option(int, "會議時數", name="會議時數", required=True),
):
    member_data = json_assistant.User(member.id)
    member_data.add_meeting_time(meeting_hours)
    embed = Embed(
        title="新增會議時數",
        description=f"已將 {member.mention} 新增會議時數 {meeting_hours}。",
        color=default_color,
    )
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)


warning_points_choices = [
    "半點 - 垃圾亂丟",
    "半點 - 開會/培訓 無故遲到(5分鐘)",
    "1點 - 開會/培訓 無故未到",
    "1點 - 兩天內沒有交工筆(賽季時為三天)",
    "1點 - 謊報請假時間/原因",
    "1點 - 無故遲交文件超過一天",
    "2點 - 上課/工作時滑手機",
    "2點 - 打遊戲太吵",
    "2點 - 操作不當導致公安意外",
    "3點 - 嚴重影響隊伍形象",
]


@member_info_manage.command(
    name="記點", description="記點。(對，就是記點，我希望我用不到這個指令)"
)
@commands.has_role(1114205838144454807)
async def member_add_warning_points(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    reason: Option(
        str, "記點事由", name="記點事由", choices=warning_points_choices, required=True
    ),
    comment: Option(str, "附註事項", name="附註", required=False),
):
    reason = reason[5:]
    member_data = json_assistant.User(member.id)
    points = reason[0:1]
    if points == "半":
        points = 0.5
    else:
        points = int(points)
    member_data.add_warning_points(points, reason, comment)
    current_points = member_data.get_warning_points()
    embed = Embed(
        title="記點", description=f"已將 {member.mention} 記點。", color=default_color
    )
    embed.add_field(name="記點點數", value=f"`{points}` 點", inline=True)
    embed.add_field(
        name="目前點數 (已加上新點數)", value=f"`{current_points}` 點", inline=True
    )
    embed.add_field(name="記點事由", value=reason, inline=False)
    if comment is not None:
        embed.add_field(name="附註事項", value=comment, inline=False)
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)
    mention_text = f"{member.mention} 由於**「{reason}」**，依照隊規記上 `{points}` 點。"
    await ctx.channel.send(content=mention_text)
    if current_points >= 4:
        warning_msg = Embed(
            title="退隊警告！",
            description=f"{member.mention} 的點數已達到 {current_points} 點！",
            color=error_color,
        )
        warning_msg.set_footer(
            text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。"
        )
        await ctx.channel.send(embed=warning_msg)


@member_info_manage.command(
    name="意外記銷點",
    description="當一般記點指令中沒有合適的規定來記/銷點，則可使用此指令。請合理使用！",
)
@commands.has_role(1114205838144454807)
async def member_add_warning_points_with_exceptions(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    pts: Option(float, "點數", name="點數", required=True),
    reason: Option(str, "事由", name="事由", required=True),
):
    member_data = json_assistant.User(member.id)
    member_data.add_warning_points(pts, "使用「意外記/銷點」指令", reason)
    current_points = member_data.get_warning_points()
    embed = Embed(
        title="意外記/銷點",
        description=f"已將 {member.mention} 記/銷點。",
        color=default_color,
    )
    embed.add_field(name="記/銷點點數", value=f"`{pts}` 點", inline=True)
    embed.add_field(
        name="目前點數 (已加上/減去新點數)", value=f"`{current_points}` 點", inline=True
    )
    embed.add_field(name="記點事由", value="使用「意外記/銷點」指令", inline=False)
    embed.add_field(name="附註事項", value=reason, inline=False)
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)
    if pts > 0:
        mention_text = f"{member.mention} 由於**「{reason}」**，記上 {pts} 點。"
        await ctx.channel.send(content=mention_text)
    if current_points >= 4:
        warning_msg = Embed(
            title="退隊警告！",
            description=f"{member.mention} 的點數已達到 {current_points} 點！",
            color=error_color,
        )
        warning_msg.set_footer(
            text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。"
        )
        await ctx.channel.send(embed=warning_msg)


remove_warning_points_choices = [
    "半點 - 自主倒垃圾",
    "半點 - 培訓時去外面拿午餐",
    "1點 - 中午時間/第八節 打掃工作室",
]


@member_info_manage.command(name="銷點", description="銷點。")
@commands.has_role(1114205838144454807)
async def member_remove_warning_points(
    ctx,
    member: Option(discord.Member, "隊員", name="隊員", required=True),
    reason: Option(
        str, "銷點事由", name="銷點事由", choices=remove_warning_points_choices, required=True
    ),
    comment: Option(str, "附註事項", name="附註事項", required=False),
):
    reason = reason[5:]
    member_data = json_assistant.User(member.id)
    points = reason[0:1]
    if points == "半":
        points = -0.5
    else:
        points = int(points) * -1
    member_data.add_warning_points(points, reason, comment)
    embed = Embed(
        title="銷點", description=f"已將 {member.mention} 銷點。", color=default_color
    )
    if member_data.get_warning_points() < 0:
        member_data.add_warning_points(
            -member_data.get_warning_points(),
            "防止負點發生",
            "為避免記點點數為負，機器人已自動將點數設為0。",
        )
        embed.set_footer(text="為避免記點點數為負，機器人已自動將點數設為0。")
    embed.add_field(name="銷點點數", value=f"`{points}` 點", inline=True)
    embed.add_field(
        name="目前點數 (已減去新點數)",
        value=f"`{member_data.get_warning_points()}` 點",
        inline=True,
    )
    embed.add_field(name="銷點事由", value=reason, inline=False)
    if comment is not None:
        embed.add_field(name="附註事項", value=comment, inline=False)
    embed.set_thumbnail(url=member.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(
    name="全體改名", description="將伺服器中所有成員的名稱改為其真名。"
)
@commands.has_role(1114205838144454807)
async def member_change_name(ctx):
    await ctx.defer()
    embed = Embed(
        title="改名",
        description="已將伺服器中所有成員的名稱改為其真名。",
        color=default_color,
    )
    no_real_name = ""
    failed = ""
    server = bot.get_guild(1114203090950836284)
    for m in server.members:
        real_name = json_assistant.User(m.id).get_real_name()
        real_logger.info(f"正在改名 {m} 為真名({real_name})")
        if real_name is not None:
            try:
                await m.edit(nick=real_name)
            except discord.Forbidden:
                failed += f"{m.mention} "
        else:
            no_real_name += f"{m.mention} "
    if no_real_name != "":
        embed.add_field(
            name="未設定真名的成員",
            value=no_real_name if no_real_name else "無",
            inline=False,
        )
    if failed != "":
        embed.add_field(
            name="改名失敗的成員", value=failed if failed else "無", inline=False
        )
    await ctx.respond(embed=embed)


@bot.user_command(name="更改暱稱為真名")
@commands.has_role(1114205838144454807)
async def member_change_name_user(ctx, user: discord.Member):
    member_obj = json_assistant.User(user.id)
    real_name = member_obj.get_real_name()
    if real_name:
        await user.edit(nick=real_name)
        embed = Embed(
            title="改名",
            description=f"已將 {user.mention} 的名稱改為其真名({real_name})。",
            color=default_color,
        )
    else:
        embed = Embed(
            title="改名",
            description=f"{user.mention} 沒有設定真名！",
            color=error_color,
        )
    await ctx.respond(embed=embed, ephemeral=True)


# @member_cmd.command(name="個人記點紀錄", description="查詢記點紀錄。")
# async def member_get_warning_history(ctx,
#                                      隊員: Option(discord.Member, "隊員", required=True)):
#     member_data = json_assistant.User(隊員.id)
#     embed = Embed(title="記點紀錄", description=f"{隊員.mention} 的記點紀錄", color=default_color)
#     embed.add_field(name="目前點數", value=f"`{member_data.get_warning_points()}` 點", inline=False)
#     raw_history = member_data.get_raw_warning_history()
#     if len(raw_history) == 0:
#         embed.add_field(name="(無紀錄)", value="表現優良！", inline=False)
#     else:
#         for i in raw_history:
#             add_or_subtract = "❌記點" if i[2] > 0 else "✅銷點"
#             if i[3] is None:
#                 formatted_history = f"{add_or_subtract} {abs(i[2])} 點：{i[1]}"
#             else:
#                 formatted_history = f"{add_or_subtract} {abs(i[2])} 點：{i[1]}\n*({i[3]})*"
#             embed.add_field(name=i[0], value=formatted_history, inline=False)
#     embed.set_thumbnail(url=隊員.display_avatar)
#     await ctx.respond(embed=embed)


# @bot.user_command(name="查看此隊員的記點紀錄")
# async def member_get_warning_history_user(ctx, user: discord.Member):
#     await member_get_warning_history(ctx, user)


# @member_cmd.command(name="全員記點記錄", description="查詢所有人的記、銷點紀錄。")
# async def member_get_all_warning_history(ctx):
#     embed = Embed(title="此指令目前維護中",
#                   description="此指令由於存在問題，目前停用中。\n如要查詢目前有被記點的成員，請使用 `/member 查詢記點人員` 。",
#                   color=error_color)
#     embed = Embed(title="記點紀錄", description="全隊所有記、銷點紀錄", color=default_color)
#     for i in json_assistant.User.get_all_warning_history():
#         add_or_subtract = "❌記點" if i[3] > 0 else "✅銷點"
#         if i[4] is None:
#             formatted_history = f"{bot.get_user(i[0]).mention}{add_or_subtract} {abs(i[3])} 點：{i[2]}"
#         else:
#             formatted_history = f"{bot.get_user(i[0]).mention}{add_or_subtract} {abs(i[3])} 點：{i[2]}\n*({i[4]})*"
#         embed.add_field(name=f"{i[1]}", value=formatted_history, inline=False)
#     await ctx.respond(embed=embed)


@commands.cooldown(1, 300)
@bot.slash_command(name="隊長信箱", description="匿名寄送訊息給隊長。")
async def send_message_to_leader(
    ctx, msg: Option(str, "訊息內容", name="訊息", required=True)
):
    mail_id = json_assistant.Message.create_new_message()
    mail = json_assistant.Message(mail_id)
    data = {
        "author": ctx.author.id,
        "time": time.time(),
        "content": msg,
        "replied": False,
        "response": "",
    }
    mail.write_raw_info(data)
    mail_embed = Embed(
        title="隊長信箱",
        description=f"來自 {ctx.author.mention} 的訊息！",
        color=default_color,
    )
    mail_embed.add_field(name="訊息ID", value=f"`{mail_id}`", inline=False)
    mail_embed.add_field(
        name="傳送時間", value=f"<t:{int(time.time())}:F>", inline=False
    )
    mail_embed.add_field(name="訊息內容", value=msg, inline=False)
    mail_embed.set_thumbnail(url=ctx.author.display_avatar)
    mail_embed.set_footer(text="如果要回覆此訊息，請點選下方的按鈕。")
    mailbox_channel = bot.get_channel(1149274793917558814)
    await mailbox_channel.send(
        embed=mail_embed, view=RespondLeaderMailboxInView(mail_id)
    )
    embed = Embed(
        title="隊長信箱", description="你的訊息已經傳送給隊長。", color=default_color
    )
    embed.add_field(name="訊息內容", value=msg, inline=False)
    embed.add_field(
        name="此訊息會被其他成員看到嗎？",
        value="放心，隊長信箱的訊息僅會被隊長本人看到。\n"
        "如果隊長要**公開**回覆你的訊息，也僅會將訊息的內容公開，不會提到你的身分。",
    )
    embed.add_field(
        name="隊長會回覆我的訊息嗎？",
        value="隊長可以選擇以**私人**或**公開**方式回覆你的訊息。\n"
        "- **私人**：你會收到一則機器人傳送的私人訊息。(請確認你已允許陌生人傳送私人訊息！)\n"
        "- **公開**：隊長的回覆會在<#1152158914847199312>與你的訊息一同公布。(不會公開你的身分！)",
    )
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="隊長信箱回覆", description="(隊長限定)回覆隊長信箱的訊息。")
async def reply_to_leader_mail(
    ctx,
    msg_id: Option(str, "欲回覆的訊息ID", min_length=5, max_length=5, required=True),
    msg: Option(str, "回覆的訊息內容", required=True),
    response_type: Option(
        str, "選擇以公開或私人方式回覆", choices=["公開", "私人"], required=True
    ),
):
    if isinstance(ctx, discord.Interaction):
        await ctx.response.defer()
    else:
        await ctx.defer()
    author = ctx.user
    if author.id == 842974332862726214:
        if msg_id in json_assistant.Message.get_all_message_id():
            mail = json_assistant.Message(msg_id)
            if mail.get_replied():
                embed = Embed(
                    title="錯誤", description="這則訊息已被回覆。", color=error_color
                )
                embed.add_field(name="你的回覆", value=mail.get_response())
            else:
                response_embed = Embed(
                    title="隊長信箱回覆",
                    description="隊長回覆了信箱中的訊息！",
                    color=default_color,
                )
                response_embed.add_field(
                    name="你的訊息內容", value=mail.get_content(), inline=False
                )
                response_embed.add_field(name="隊長的回覆內容", value=msg, inline=False)
                if response_type == "公開":
                    response_channel = bot.get_channel(1152158914847199312)
                    await response_channel.send(embed=response_embed)
                    embed = Embed(
                        title="回覆成功！",
                        description=f"已將你的回覆傳送到{response_channel.mention}。",
                        color=default_color,
                    )
                    embed.add_field(
                        name="對方的訊息內容", value=mail.get_content(), inline=False
                    )
                    embed.add_field(name="你的回覆內容", value=msg, inline=False)
                elif response_type == "私人":
                    sender = bot.get_user(mail.get_author())
                    try:
                        await sender.send(embed=response_embed)
                        embed = Embed(
                            title="回覆成功！",
                            description=f"已將你的回覆傳送給{sender.mention}。",
                            color=default_color,
                        )
                        embed.add_field(
                            name="對方的訊息內容",
                            value=mail.get_content(),
                            inline=False,
                        )
                        embed.add_field(name="你的回覆內容", value=msg, inline=False)
                    except discord.errors.HTTPException as error:
                        if error.code == 50007:
                            embed = Embed(
                                title="錯誤",
                                description=f"{sender.mention} 不允許機器人傳送私人訊息。",
                                color=error_color,
                            )
                        else:
                            raise error
                else:
                    embed = Embed(
                        title="錯誤",
                        description=f"所指定的回覆類型 (`{response_type}`) 不存在！",
                    )
                mail.set_replied(True)
                mail.set_response(msg)
        else:
            embed = Embed(
                title="錯誤", description=f"訊息 `{msg_id}` 不存在！", color=error_color
            )
    else:
        embed = Embed(
            title="錯誤", description="你不是隊長，無法使用此指令！", color=error_color
        )
    if isinstance(ctx, discord.Interaction):
        await ctx.followup.send(embed=embed, ephemeral=True)
    else:
        await ctx.respond(embed=embed, ephemeral=True)


# @bot.slash_command(name="查詢工作室環境", description="取得工作室目前濕度及溫度。")
# async def get_workshop_environment(ctx):
#     ar = arduino_reader.ArduinoReader()
#     ar.read()
#     embed = Embed(title="工作室環境", description=ar.get_raw(), color=default_color)
#     embed.add_field(name="濕度", value=f"{ar.humidity()}%", inline=True)
#     embed.add_field(name="溫度", value=f"{ar.temperature()}°C", inline=True)
#     await ctx.respond(embed=embed)


@bot.slash_command(name="clear", description="清除目前頻道中的訊息。")
@commands.has_role(1114205838144454807)
async def clear_messages(
    ctx: discord.ApplicationContext,
    count: Option(
        int,
        name="刪除訊息數",
        description="要刪除的訊息數量",
        min_value=1,
        max_value=50,
    ),
):
    channel = ctx.channel
    channel: discord.TextChannel
    await ctx.defer()
    try:
        await channel.purge(limit=count)
        embed = Embed(
            title="已清除訊息",
            description=f"已成功清除 {channel.mention} 中的 `{count}` 則訊息。",
            color=default_color,
        )
        await ctx.channel.send(embed=embed, delete_after=5)
    except Exception as e:
        embed = Embed(title="錯誤", description="發生未知錯誤。", color=error_color)
        embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)


@bot.slash_command(name="debug", description="(開發者專用)除錯用")
@commands.is_owner()
async def debug(ctx):
    embed = Embed(title="除錯資訊", description="目前資訊如下：", color=default_color)
    embed.add_field(name="Time", value=f"<t:{int(time.time())}> ({time.time()})")
    embed.add_field(
        name="Version",
        value=git.Repo(search_parent_directories=True).head.object.hexsha,
    )
    await ctx.respond(embed=embed)


@bot.slash_command(
    name="about",
    description="Provides information about this robot.",
    description_localizations={"zh-TW": "提供關於這隻機器人的資訊。"},
)
async def about(
    ctx, is_private: Option(bool, "是否以私人訊息回應", name="私人訊息", required=False) = False
):
    embed = Embed(title="關於", color=default_color)
    embed.set_thumbnail(url=bot.user.display_avatar)
    embed.add_field(
        name="程式碼與授權",
        value="本機器人由<@657519721138094080>維護，使用[Py-cord]"
        "(https://github.com/Pycord-Development/pycord)進行開發。\n"
        "本機器人的程式碼及檔案皆可在[這裡](https://github.com/Alllen95Wei/RobomaniaBot)"
        "查看。",
        inline=True,
    )
    embed.add_field(
        name="聯絡",
        value="如果有任何技術問題及建議，請聯絡<@657519721138094080>。",
        inline=True,
    )
    repo = git.Repo(search_parent_directories=True)
    update_msg = repo.head.reference.commit.message
    raw_sha = repo.head.object.hexsha
    sha = raw_sha[:7]
    embed.add_field(name=f"分支訊息：{sha}", value=update_msg, inline=False)
    year = time.strftime("%Y")
    embed.set_footer(text=f"©Allen Why, {year} | 版本：commit {sha[:7]}")
    await ctx.respond(embed=embed, ephemeral=is_private)


@bot.slash_command(name="dps", description="查詢伺服器電腦的CPU及記憶體使用率。")
async def dps(ctx):
    embed = Embed(title="伺服器電腦資訊", color=default_color)
    embed.add_field(name="CPU使用率", value=f"{detect_pc_status.get_cpu_usage()}%")
    embed.add_field(
        name="記憶體使用率", value=f"{detect_pc_status.get_ram_usage_detail()}"
    )
    await ctx.respond(embed=embed)


@bot.slash_command(name="update", description="更新機器人。")
@commands.is_owner()
async def update(
    ctx, is_private: Option(bool, "是否以私人訊息回應", name="私人訊息", required=False) = False
):
    embed = Embed(title="更新中", description="更新流程啟動。", color=default_color)
    await ctx.respond(embed=embed, ephemeral=is_private)
    event = discord.Activity(type=discord.ActivityType.playing, name="更新中...")
    await bot.change_presence(status=discord.Status.idle, activity=event)
    upd.update(os.getpid(), system())


@bot.slash_command(name="cmd", description="在伺服器端執行指令並傳回結果。")
@commands.is_owner()
async def cmd(
    ctx,
    command: Option(str, "要執行的指令", name="指令", required=True),
    desired_module: Option(
        str,
        name="執行模組",
        choices=["subprocess", "os"],
        description="執行指令的模組",
        required=False,
    ) = "subprocess",
    is_private: Option(bool, "是否以私人訊息回應", name="私人訊息", required=False) = False,
):
    try:
        await ctx.defer(ephemeral=is_private)
        if split(command)[0] == "cmd":
            embed = Embed(
                title="錯誤",
                description="基於安全原因，你不能執行這個指令。",
                color=error_color,
            )
            await ctx.respond(embed=embed, ephemeral=is_private)
            return
        if desired_module == "subprocess":
            result = str(run(command, capture_output=True, text=True).stdout)
        else:
            result = str(os.popen(command).read())
        if result != "":
            embed = Embed(
                title="執行結果", description=f"```{result}```", color=default_color
            )
        else:
            embed = Embed(
                title="執行結果", description="終端未傳回回應。", color=default_color
            )
    except WindowsError as e:
        if e.winerror == 2:
            embed = Embed(
                title="錯誤",
                description="找不到指令。請嘗試更換執行模組。",
                color=error_color,
            )
        else:
            embed = Embed(
                title="錯誤", description=f"發生錯誤：`{e}`", color=error_color
            )
    except Exception as e:
        embed = Embed(title="錯誤", description=f"發生錯誤：`{e}`", color=error_color)
    try:
        await ctx.respond(embed=embed, ephemeral=is_private)
    except discord.errors.HTTPException as HTTPError:
        if "fewer in length" in str(HTTPError):
            txt_file_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "full_msg.txt"
            )
            with open(txt_file_path, "w") as file:
                file.write(str(result))
            await ctx.respond(
                "由於訊息長度過長，因此改以文字檔方式呈現。",
                file=discord.File(txt_file_path),
                ephemeral=is_private,
            )
            os.remove(txt_file_path)


@bot.event
async def on_message(message):
    if message.author.id == bot.user.id:
        return
    if (
        "The startCompetition() method" in message.content
        or "Warning at" in message.content
    ):
        await message.reply("<:deadge:1200367980748476437>" * 3)


@bot.event
async def on_voice_state_update(
    member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
):
    if member.bot:
        return
    if (
        before.channel is None
        or after.channel is None
        or before.channel.id != after.channel.id
    ):
        member_real_name = json_assistant.User(member.id).get_real_name()
        if member_real_name is None:
            member_real_name = member.name
        if not isinstance(before.channel, type(None)):
            await before.channel.send(
                f"<:left:1208779447440777226> **{member_real_name}** "
                f"在 <t:{int(time.time())}:T> 離開 {before.channel.mention}。",
                delete_after=43200,
            )
            log_vc_activity("leave", member, before.channel)
        if not isinstance(after.channel, type(None)):
            await after.channel.send(
                f"<:join:1208779348438683668> **{member_real_name}** "
                f"在 <t:{int(time.time())}:T> 加入 {after.channel.mention}。",
                delete_after=43200,
            )
            log_vc_activity("join", member, after.channel)


VC_LOGGER = logging.getLogger("VC")


def log_vc_activity(
    join_or_leave: Literal["join", "leave"],
    user: discord.User | discord.Member,
    channel: discord.VoiceChannel,
):
    log_path = os.path.join(
        base_dir,
        "logs",
        f"VC {datetime.datetime.now(tz=now_tz).strftime('%Y.%m.%d')}.log",
    )
    if not os.path.exists(log_path):
        with open(log_path, "w"):
            pass
    original_handler: logging.FileHandler
    try:
        original_handler = VC_LOGGER.handlers[0]
    except IndexError:
        original_handler = logging.FileHandler("logs/VC.log")
    if original_handler.baseFilename != log_path:
        formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        log_path = os.path.join(
            base_dir,
            "logs",
            f"VC {datetime.datetime.now(tz=now_tz).strftime('%Y.%m.%d')}.log",
        )
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(formatter)
        VC_LOGGER.addHandler(handler)
        VC_LOGGER.removeHandler(original_handler)
    join_or_leave = "加入" if join_or_leave == "join" else "離開"
    message = user.name + " " + join_or_leave + "了 " + channel.name
    VC_LOGGER.info(message)


bot.load_extensions(
    "cogs.member", "cogs.reminder", "cogs.new_verification", "cogs.backup_sys", "cogs.meeting"
)
bot.run(TOKEN)
