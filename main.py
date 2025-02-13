# coding=utf-8
import time
import datetime
import zoneinfo
import discord
from discord.ext import commands
from discord.ext import tasks
from discord import Option, Embed
import os
from shlex import split
from subprocess import run
from dotenv import load_dotenv
from platform import system
import re
import git

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
default_color = 0x012a5e
error_color = 0xF1411C
real_logger = logger.CreateLogger()
大會_URL = "https://discord.com/channels/1114203090950836284/1114209308910026792"  # noqa
# 載入TOKEN
load_dotenv(dotenv_path=os.path.join(base_dir, "TOKEN.env"))
TOKEN = str(os.getenv("TOKEN"))

bot.logger = real_logger


@tasks.loop(seconds=5)
async def check_meeting():
    real_logger.debug("開始檢查會議時間...")
    meeting_id_list = json_assistant.Meeting.get_all_meeting_id()
    m = bot.get_channel(1128232150135738529)
    for meeting_id in meeting_id_list:
        try:
            meeting_obj = json_assistant.Meeting(meeting_id)
            if meeting_obj.get_started() is False:
                if time.time() >= meeting_obj.get_start_time():
                    real_logger.info(f"會議 {meeting_id} 已經開始！")
                    meeting_obj.set_started(True)
                    embed = Embed(title="會議開始！", description=f"會議**「{meeting_obj}」**已經在"
                                                                 f"<t:{int(meeting_obj.get_start_time())}:F>開始！",
                                  color=default_color)
                    if meeting_obj.get_description() != "":
                        embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
                    embed.add_field(name="主持人", value=f"<@{meeting_obj.get_host()}> "
                                                         f"({bot.get_user(meeting_obj.get_host())})", inline=False)
                    embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
                    if meeting_obj.get_absent_members():
                        absent_members = ""
                        for mem in meeting_obj.get_absent_members():
                            member_obj = json_assistant.User(mem[0])
                            absent_members += f"<@{mem[0]}>({member_obj.get_real_name()}) - *{mem[1]}*\n"
                        embed.add_field(name="請假人員", value=absent_members, inline=False)
                    await m.send(content="@everyone", embed=embed)
                    real_logger.info(f"已傳送會議 {meeting_id} 的開始通知。")
                elif meeting_obj.get_notified() is False and meeting_obj.get_start_time() - time.time() <= 300:
                    real_logger.info(f"會議 {meeting_id} 即將開始(傳送通知)！")
                    embed = Embed(title="會議即將開始！",
                                  description=f"會議**「{meeting_obj}」**即將於"
                                              f"<t:{int(meeting_obj.get_start_time())}:R>開始！",
                                  color=default_color)
                    if meeting_obj.get_description() != "":
                        embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
                    embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
                    await m.send(content="@everyone", embed=embed)
                    meeting_obj.set_notified(True)
                    real_logger.info(f"已傳送會議 {meeting_id} 的開始通知。")
            elif meeting_obj.get_started() and time.time() - meeting_obj.get_start_time() >= 172800:
                meeting_obj.archive()
                real_logger.info(f"會議 {meeting_id} 距離開始時間已超過2天，已將其封存。")
        except TypeError as e:
            real_logger.warning(f"檢查會議 {meeting_id} 時發生錯誤，跳過此會議。({e})")


class GetEventInfo(discord.ui.Modal):
    def __init__(self, meeting_id=None) -> None:
        super().__init__(title="會議", timeout=None)
        self.meeting_id = meeting_id
        if meeting_id is not None:
            meeting_obj = json_assistant.Meeting(meeting_id)
            prefill_data = [meeting_obj.get_name(),
                            "1" if meeting_obj.get_absent_members() is None else "",
                            datetime.datetime.fromtimestamp(meeting_obj.get_start_time(), tz=now_tz).
                            strftime("%Y/%m/%d %H:%M"),
                            meeting_obj.get_link(),
                            meeting_obj.get_meeting_record_link()]
        else:
            prefill_data = ["", "", "", 大會_URL, ""]

        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議標題", value=prefill_data[0],
                                           required=True))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="強制參加(停用請假)？",
                                           placeholder="輸入任何字元，即可停用此會議的請假功能",
                                           max_length=1, value=prefill_data[1], required=False))
        self.add_item(
            discord.ui.InputText(style=discord.InputTextStyle.short, label="開始時間(格式：YYYY/MM/DD HH:MM，24小時制)",
                                 placeholder="如：2021/01/10 12:05", min_length=16, max_length=16,
                                 value=prefill_data[2], required=True))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議地點(預設為Discord - 大會)",
                                           placeholder="可貼上Meet或Discord頻道連結",
                                           value=prefill_data[3], required=True))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議記錄連結",
                                           placeholder="貼上Google文件連結",
                                           value=prefill_data[4], required=False))

    async def callback(self, interaction: discord.Interaction):
        if self.meeting_id is not None:
            unique_id = self.meeting_id
            embed = Embed(title="編輯會議",
                          description=f"會議 `{unique_id}` **({self.children[0].value})** 已經編輯成功！",
                          color=default_color)
        else:
            unique_id = json_assistant.Meeting.create_new_meeting()
            embed = Embed(title="預定新會議",
                          description=f"你預定的會議：**{self.children[0].value}**，已經預定成功！",
                          color=default_color)
        meeting_obj = json_assistant.Meeting(unique_id)
        meeting_obj.set_name(self.children[0].value)
        meeting_obj.disable_absent(True if self.children[1].value != "" else False)
        meeting_obj.set_host(interaction.user.id)
        meeting_obj.set_link(self.children[3].value)
        meeting_obj.set_meeting_record_link(self.children[4].value)
        real_logger.info(f"已預定/編輯會議 {unique_id}。")
        embed.add_field(name="會議ID", value=f"`{unique_id}`", inline=False)
        if self.children[1].value != "":
            embed.add_field(name="強制參加", value="已停用此會議的請假功能。", inline=False)
        else:
            embed.add_field(name="可請假", value="成員可透過指令或按鈕請假。", inline=False)
        embed.add_field(name="主持人", value=interaction.user.mention, inline=False)
        try:
            unix_start_time = datetime.datetime.timestamp(
                datetime.datetime.strptime(self.children[2].value, "%Y/%m/%d %H:%M").replace(tzinfo=now_tz))
            if unix_start_time < time.time():
                embed = Embed(title="錯誤",
                              description=f"輸入的開始時間(<t:{int(unix_start_time)}:F>)已經過去！請重新輸入。",
                              color=error_color)
                await interaction.response.edit_message(embed=embed)
                return
            else:
                meeting_obj.set_start_time(unix_start_time)
                embed.add_field(name="開始時間", value=f"<t:{int(unix_start_time)}:F>", inline=False)
        except ValueError:
            embed = Embed(title="錯誤",
                          description=f"輸入的開始時間(`{self.children[2].value}`)格式錯誤！請重新輸入。",
                          color=error_color)
            await interaction.response.edit_message(embed=embed)
            return
        embed.add_field(name="會議地點", value=self.children[3].value, inline=False)
        if self.children[4].value != "":
            embed.add_field(name="會議記錄連結", value=self.children[4].value, inline=False)
        embed.set_footer(text="請記下會議ID，以便後續進行編輯或刪除。")
        await interaction.response.edit_message(embed=embed, view=None)
        m = bot.get_channel(1128232150135738529)
        embed.title = "新會議"
        embed.description = f"會議 `{unique_id}` **({self.children[0].value})** 已經預定成功！"
        if self.children[1].value != "":
            embed.set_footer(text="若因故不能參加會議，請向主幹告知事由。")
        else:
            embed.set_footer(text="如要請假，最晚請在會議開始前10分鐘處理完畢。")
        await m.send(embed=embed,
                     view=AbsentInView(unique_id) if self.children[1].value == "" else None)
        real_logger.info(f"已傳送預定/編輯會議 {unique_id} 的通知。")


class Absent(discord.ui.Modal):
    def __init__(self, meeting_id: str) -> None:
        super().__init__(title="請假", timeout=None)
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="請假理由",
                                           placeholder="請輸入合理的請假理由。打「家裡有事」的，好自為之(？", required=True))
        self.meeting_id = meeting_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await absence_meeting(interaction, self.meeting_id, self.children[0].value)


class RespondLeaderMailbox(discord.ui.Modal):
    class ResponseType:
        public = "公開"
        private = "私人"

    def __init__(self, message_id: str, response_type) -> None:
        super().__init__(title="回覆信箱訊息", timeout=None)
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.long, label="回覆內容", required=True))
        self.message_id = message_id
        self.response_type = response_type

    async def callback(self, interaction: discord.Interaction):
        await reply_to_leader_mail(interaction, self.message_id, self.children[0].value, self.response_type)


class GetEventInfoInView(discord.ui.View):
    def __init__(self, meeting_id=None):
        super().__init__(timeout=None)
        self.meeting_id = meeting_id

    @discord.ui.button(label="點此開啟會議視窗", style=discord.ButtonStyle.green, emoji="📝")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(GetEventInfo(self.meeting_id))


class AbsentInView(discord.ui.View):
    def __init__(self, meeting_id: str):
        super().__init__(timeout=None)
        self.meeting_id = meeting_id

    @discord.ui.button(label="點此開啟請假視窗", style=discord.ButtonStyle.red, emoji="🙋")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(Absent(self.meeting_id))


class RespondLeaderMailboxInView(discord.ui.View):
    def __init__(self, message_id: str):
        super().__init__(timeout=None)
        self.message_id = message_id

    @discord.ui.button(label="以私人訊息回覆", style=discord.ButtonStyle.green, emoji="💬")
    async def private_respond(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RespondLeaderMailbox(self.message_id,
                                                                   RespondLeaderMailbox.ResponseType.private))

    @discord.ui.button(label="以公開訊息回覆", style=discord.ButtonStyle.blurple, emoji="📢")
    async def public_respond(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(RespondLeaderMailbox(self.message_id,
                                                                   RespondLeaderMailbox.ResponseType.public))


@bot.event
async def on_ready():
    real_logger.info("機器人準備完成！")
    real_logger.info(f"PING值：{round(bot.latency * 1000)}ms")
    real_logger.info(f"登入身分：{bot.user}")
    activity = discord.Activity(name="GitHub", type=discord.ActivityType.watching,
                                url="https://github.com/Alllen95Wei/RobomaniaBot")
    await bot.change_presence(activity=activity)
    await check_meeting.start()


@bot.event
async def on_application_command(ctx):
    if ctx.command.parent is None:
        real_logger.info(f"{ctx.author} 執行了斜線指令 \"{ctx.command.name}\"")
    else:
        real_logger.info(f"{ctx.author} 執行了斜線指令 \"{ctx.command.parent.name} {ctx.command.name}\"")


member_cmd = bot.create_group(name="member", description="隊員資訊相關指令。")


@bot.slash_command(name="ping", description="查看機器人延遲。")
async def ping(ctx):
    embed = Embed(title="PONG!✨", color=default_color)
    embed.add_field(name="PING值", value=f"`{round(bot.latency * 1000)}` ms")
    await ctx.respond(embed=embed)


@bot.event
async def on_application_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        embed = Embed(title="指令冷卻中",
                      description=f"這個指令正在冷卻中，請在`{round(error.retry_after)}`秒後再試。",
                      color=error_color)
        await ctx.respond(embed=embed, ephemeral=True)
    elif isinstance(error, commands.NotOwner) or isinstance(error, commands.MissingRole):
        embed = Embed(title="錯誤", description="你沒有權限使用此指令。", color=error_color)
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        embed = Embed(title="錯誤", description="發生了一個錯誤，錯誤詳細資料如下。", color=error_color)
        if ctx.command.parent is None:
            embed.add_field(name="指令名稱", value=f"`{ctx.command.name}`", inline=False)
        else:
            embed.add_field(name="指令名稱", value=f"`{ctx.command.parent.name} {ctx.command.name}`", inline=False)
        embed.add_field(name="使用者", value=f"`{ctx.author}`", inline=False)
        embed.add_field(name="錯誤類型", value=f"`{type(error).__name__}`", inline=False)
        embed.add_field(name="錯誤訊息", value=f"`{error}`", inline=False)
        allen = bot.get_user(657519721138094080)
        await allen.send(embed=embed)
        embed = Embed(title="錯誤", description="發生了一個錯誤，已經通知開發者。", color=error_color)
        await ctx.respond(embed=embed, ephemeral=True)
        raise error


@member_cmd.command(name="查詢", description="查看隊員資訊。")
async def member_info(ctx,
                      隊員: Option(discord.Member, "隊員", required=False) = None):  # noqa
    if 隊員 is None:
        隊員 = ctx.author  # noqa
    member_data = json_assistant.User(隊員.id)
    jobs_str = ""
    if len(member_data.get_jobs()) != 0:
        for job in member_data.get_jobs():
            jobs_str += f"* {job}\n"
    else:
        jobs_str = "(無)"
    embed = Embed(title="隊員資訊", description=f"{隊員.mention} 的資訊", color=default_color)
    embed.add_field(name="真實姓名", value=member_data.get_real_name(), inline=False)
    embed.add_field(name="職務", value=jobs_str, inline=False)
    # embed.add_field(name="總計會議時數", value=member_data.get_total_meeting_time(), inline=False)
    embed.add_field(name="警告點數", value=f"`{member_data.get_warning_points()}` 點", inline=False)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@member_cmd.command(name="查詢記點人員", description="列出所有點數不為0的隊員。")
async def member_list_bad_guys(ctx):
    members = json_assistant.User.get_all_user_id()
    embed = Embed(title="遭記點隊員清單", description="以下為點數不為0的所有隊員：", color=default_color)
    bad_guys: list[dict[str, str | float | int]] = []
    for m in members:
        member_obj = json_assistant.User(m)
        if member_obj.get_warning_points() != 0:
            bad_guys.append({"name": member_obj.get_real_name(), "points": member_obj.get_warning_points()})
    bad_guys.sort(key=lambda x: x["points"], reverse=True)
    for bad_guy in bad_guys:
        medals = ("🥇", "🥈", "🥉")
        if bad_guys.index(bad_guy) <= 2:
            bad_guy["name"] = medals[bad_guys.index(bad_guy)] + " " + bad_guy["name"]
        embed.add_field(name=bad_guy["name"], value=f"`{bad_guy['points']}` 點", inline=False)
    if len(embed.fields) == 0:
        embed.add_field(name="(沒有遭記點隊員)", value="所有人目前皆無點數！", inline=False)
    await ctx.respond(embed=embed)


@bot.user_command(name="查看此隊員的資訊")
async def member_info_user(ctx, user: discord.Member):
    await member_info(ctx, user)


member_info_manage = bot.create_group(name="manage", description="隊員資訊管理。")


@member_info_manage.command(name="設定真名", description="設定隊員真實姓名。")
@commands.has_role(1114205838144454807)
async def member_set_real_name(ctx,
                               隊員: Option(discord.Member, "隊員", required=True),  # noqa
                               真實姓名: Option(str, "真實姓名", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    member_data.set_real_name(真實姓名)
    embed = Embed(title="設定真實姓名", description=f"已將 {隊員.mention} 的真實姓名設定為 {真實姓名}。",
                  color=default_color)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="新增職務", description="新增隊員職務。")
@commands.has_role(1114205838144454807)
async def member_add_job(ctx,
                         隊員: Option(discord.Member, "隊員", required=True),  # noqa
                         職務: Option(str, "職務", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    member_data.add_job(職務)
    embed = Embed(title="新增職務", description=f"已將 {隊員.mention} 新增職務 {職務}。",
                  color=default_color)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="移除職務", description="移除隊員職務。")
@commands.has_role(1114205838144454807)
async def member_remove_job(ctx,
                            隊員: Option(discord.Member, "隊員", required=True),  # noqa
                            職務: Option(str, "職務", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    member_data.remove_job(職務)
    embed = Embed(title="移除職務", description=f"已將 {隊員.mention} 移除職務 {職務}。",
                  color=default_color)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="add_meeting_time", description="新增隊員會議時數。")
@commands.has_role(1114205838144454807)
async def member_add_meeting_time(ctx,
                                  隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                  會議時數: Option(int, "會議時數", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    member_data.add_meeting_time(會議時數)
    embed = Embed(title="新增會議時數", description=f"已將 {隊員.mention} 新增會議時數 {會議時數}。",
                  color=default_color)
    embed.set_thumbnail(url=隊員.display_avatar)
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
    "3點 - 嚴重影響隊伍形象"]


@member_info_manage.command(name="記點", description="記點。(對，就是記點，我希望我用不到這個指令)")
@commands.has_role(1114205838144454807)
async def member_add_warning_points(ctx,
                                    隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                    記點事由: Option(str, "記點事由", choices=warning_points_choices,  # noqa
                                                     required=True),
                                    附註: Option(str, "附註事項", required=False)):  # noqa
    reason = 記點事由[5:]
    member_data = json_assistant.User(隊員.id)
    points = 記點事由[0:1]
    if points == "半":
        points = 0.5
    else:
        points = int(points)
    member_data.add_warning_points(points, reason, 附註)
    current_points = member_data.get_warning_points()
    embed = Embed(title="記點", description=f"已將 {隊員.mention} 記點。", color=default_color)
    embed.add_field(name="記點點數", value=f"`{points}` 點", inline=True)
    embed.add_field(name="目前點數 (已加上新點數)", value=f"`{current_points}` 點", inline=True)
    embed.add_field(name="記點事由", value=reason, inline=False)
    if 附註 is not None:
        embed.add_field(name="附註事項", value=附註, inline=False)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)
    mention_text = f"{隊員.mention} 由於**「{reason}」**，依照隊規記上 `{points}` 點。"
    await ctx.channel.send(content=mention_text)
    if current_points >= 4:
        warning_msg = Embed(title="退隊警告！",
                            description=f"{隊員.mention} 的點數已達到 {current_points} 點！",
                            color=error_color)
        warning_msg.set_footer(text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。")
        await ctx.channel.send(embed=warning_msg)


@member_info_manage.command(name="意外記銷點",
                            description="當一般記點指令中沒有合適的規定來記/銷點，則可使用此指令。請合理使用！")
@commands.has_role(1114205838144454807)
async def member_add_warning_points_with_exceptions(ctx,
                                                    隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                                    點數: Option(float, "點數", required=True),  # noqa
                                                    事由: Option(str, "事由", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    member_data.add_warning_points(點數, "使用「意外記/銷點」指令", 事由)
    current_points = member_data.get_warning_points()
    embed = Embed(title="意外記/銷點", description=f"已將 {隊員.mention} 記/銷點。", color=default_color)
    embed.add_field(name="記/銷點點數", value=f"`{點數}` 點", inline=True)
    embed.add_field(name="目前點數 (已加上/減去新點數)", value=f"`{current_points}` 點", inline=True)
    embed.add_field(name="記點事由", value="使用「意外記/銷點」指令", inline=False)
    embed.add_field(name="附註事項", value=事由, inline=False)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)
    if 點數 > 0:
        mention_text = f"{隊員.mention} 由於**「{事由}」**，記上 {點數} 點。"
        await ctx.channel.send(content=mention_text)
    if current_points >= 4:
        warning_msg = Embed(title="退隊警告！",
                            description=f"{隊員.mention} 的點數已達到 {current_points} 點！",
                            color=error_color)
        warning_msg.set_footer(text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。")
        await ctx.channel.send(embed=warning_msg)


remove_warning_points_choices = [
    "半點 - 自主倒垃圾",
    "半點 - 培訓時去外面拿午餐",
    "1點 - 中午時間/第八節 打掃工作室"]


@member_info_manage.command(name="銷點", description="銷點。")
@commands.has_role(1114205838144454807)
async def member_remove_warning_points(ctx,
                                       隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                       銷點事由: Option(str, "銷點事由", choices=remove_warning_points_choices,  # noqa
                                                        required=True),
                                       附註: Option(str, "附註事項", required=False)):  # noqa
    reason = 銷點事由[5:]
    member_data = json_assistant.User(隊員.id)
    points = 銷點事由[0:1]
    if points == "半":
        points = -0.5
    else:
        points = int(points) * -1
    member_data.add_warning_points(points, reason, 附註)
    embed = Embed(title="銷點", description=f"已將 {隊員.mention} 銷點。", color=default_color)
    if member_data.get_warning_points() < 0:
        member_data.add_warning_points(-member_data.get_warning_points(), "防止負點發生",
                                       "為避免記點點數為負，機器人已自動將點數設為0。")
        embed.set_footer(text="為避免記點點數為負，機器人已自動將點數設為0。")
    embed.add_field(name="銷點點數", value=f"`{points}` 點", inline=True)
    embed.add_field(name="目前點數 (已減去新點數)", value=f"`{member_data.get_warning_points()}` 點", inline=True)
    embed.add_field(name="銷點事由", value=reason, inline=False)
    if 附註 is not None:
        embed.add_field(name="附註事項", value=附註, inline=False)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="全體改名", description="將伺服器中所有成員的名稱改為其真名。")
@commands.has_role(1114205838144454807)
async def member_change_name(ctx):
    await ctx.defer()
    embed = Embed(title="改名", description="已將伺服器中所有成員的名稱改為其真名。", color=default_color)
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
        embed.add_field(name="未設定真名的成員", value=no_real_name if no_real_name else "無", inline=False)
    if failed != "":
        embed.add_field(name="改名失敗的成員", value=failed if failed else "無", inline=False)
    await ctx.respond(embed=embed)


@bot.user_command(name="更改暱稱為真名")
@commands.has_role(1114205838144454807)
async def member_change_name_user(ctx, user: discord.Member):
    member_obj = json_assistant.User(user.id)
    real_name = member_obj.get_real_name()
    if real_name:
        await user.edit(nick=real_name)
        embed = Embed(title="改名", description=f"已將 {user.mention} 的名稱改為其真名({real_name})。",
                      color=default_color)
    else:
        embed = Embed(title="改名", description=f"{user.mention} 沒有設定真名！", color=error_color)
    await ctx.respond(embed=embed, ephemeral=True)


@member_cmd.command(name="個人記點紀錄", description="查詢記點紀錄。")
async def member_get_warning_history(ctx,
                                     隊員: Option(discord.Member, "隊員", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    embed = Embed(title="記點紀錄", description=f"{隊員.mention} 的記點紀錄", color=default_color)
    embed.add_field(name="目前點數", value=f"`{member_data.get_warning_points()}` 點", inline=False)
    raw_history = member_data.get_raw_warning_history()
    if len(raw_history) == 0:
        embed.add_field(name="(無紀錄)", value="表現優良！", inline=False)
    else:
        for i in raw_history:
            add_or_subtract = "❌記點" if i[2] > 0 else "✅銷點"
            if i[3] is None:
                formatted_history = f"{add_or_subtract} {abs(i[2])} 點：{i[1]}"
            else:
                formatted_history = f"{add_or_subtract} {abs(i[2])} 點：{i[1]}\n*({i[3]})*"
            embed.add_field(name=i[0], value=formatted_history, inline=False)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@bot.user_command(name="查看此隊員的記點紀錄")
async def member_get_warning_history_user(ctx, user: discord.Member):
    await member_get_warning_history(ctx, user)


@member_cmd.command(name="全員記點記錄", description="查詢所有人的記、銷點紀錄。")
async def member_get_all_warning_history(ctx):
    embed = Embed(title="此指令目前維護中",
                  description="此指令由於存在問題，目前停用中。\n如要查詢目前有被記點的成員，請使用 `/member 查詢記點人員` 。",
                  color=error_color)
    # embed = Embed(title="記點紀錄", description="全隊所有記、銷點紀錄", color=default_color)
    # for i in json_assistant.User.get_all_warning_history():
    #     add_or_subtract = "❌記點" if i[3] > 0 else "✅銷點"
    #     if i[4] is None:
    #         formatted_history = f"{bot.get_user(i[0]).mention}{add_or_subtract} {abs(i[3])} 點：{i[2]}"
    #     else:
    #         formatted_history = f"{bot.get_user(i[0]).mention}{add_or_subtract} {abs(i[3])} 點：{i[2]}\n*({i[4]})*"
    #     embed.add_field(name=f"{i[1]}", value=formatted_history, inline=False)
    await ctx.respond(embed=embed)


meeting = bot.create_group(name="meeting", description="會議相關指令。")


@meeting.command(name="建立", description="預定新的會議。")
@commands.has_role(1114205838144454807)
async def create_new_meeting(ctx):
    embed = Embed(title="預定會議", description="請點擊下方的按鈕，開啟會議預定視窗。", color=default_color)
    await ctx.respond(embed=embed, view=GetEventInfoInView(), ephemeral=True)


@meeting.command(name="編輯", description="編輯會議資訊。")
@commands.has_role(1114205838144454807)
async def edit_meeting(ctx, 會議id: Option(str, "欲修改的會議ID", min_length=5, max_length=5, required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        embed = Embed(title="編輯會議", description="請點擊下方的按鈕，開啟會議編輯視窗。",
                      color=default_color)
        await ctx.respond(embed=embed, view=GetEventInfoInView(會議id), ephemeral=True)
    else:
        embed = Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
        await ctx.respond(embed=embed)


@meeting.command(name="刪除", description="刪除會議。")
@commands.has_role(1114205838144454807)
async def delete_meeting(ctx, 會議id: Option(str, "欲刪除的會議ID", min_length=5, max_length=5, required=True),  # noqa
                         原因: Option(str, "取消會議的原因", required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        meeting_obj = json_assistant.Meeting(會議id)
        if meeting_obj.get_started():
            embed = Embed(title="錯誤", description="此會議已經開始，無法刪除！", color=error_color)
        else:
            m = bot.get_channel(1128232150135738529)
            notify_embed = Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。",
                                 color=default_color)
            notify_embed.add_field(name="會議標題", value=meeting_obj.get_name(), inline=False)
            notify_embed.add_field(name="取消原因", value=原因, inline=False)
            if meeting_obj.get_notified():
                await m.send(content="@everyone", embed=notify_embed)
            else:
                await m.send(embed=notify_embed)
            meeting_obj.delete()
            embed = Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。", color=default_color)
    else:
        embed = Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@meeting.command(name="所有id", description="列出所有的會議ID。")
async def list_meetings(ctx):
    embed = Embed(title="會議ID列表", description="目前已存在的會議ID如下：", color=default_color)
    for i in json_assistant.Meeting.get_all_meeting_id():
        embed.add_field(name=i, value="", inline=True)
    await ctx.respond(embed=embed)


@meeting.command(name="請假", description="登記請假。")
async def absence_meeting(ctx, 會議id: Option(str, "不會出席的會議ID"),  # noqa
                          原因: Option(str, "請假的原因", required=True)):  # noqa
    try:
        await ctx.defer()
    except AttributeError:
        await ctx.response.defer()
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        meeting_obj = json_assistant.Meeting(會議id)
        if meeting_obj.get_started():
            embed = Embed(title="錯誤", description="此會議已經開始，無法請假！", color=error_color)
        elif meeting_obj.get_start_time() - time.time() < 600:
            embed = Embed(title="錯誤", description="請假需在會議10分鐘前處理完畢。\n"
                                                    f"此會議即將在<t:{int(meeting_obj.get_start_time())}:R>開始！",
                          color=error_color)
        else:
            absent_status = meeting_obj.get_absent_members()
            if isinstance(absent_status, type(None)):
                embed = Embed(title="錯誤：強制參加",
                              description="此會議已被設置為「強制參加」，因此無法透過此系統請假。\n"
                                          "若因故不能參加會議，請向主幹告知事由。",
                              color=error_color)
            else:
                absent_members_id = [i[0] for i in absent_status]
                try:
                    author_id = ctx.author.id
                    author_mention = ctx.author.mention
                except AttributeError:
                    author_id = ctx.user.id
                    author_mention = ctx.user.mention
                if author_id in absent_members_id:
                    embed = Embed(title="錯誤", description="你已經請過假了！", color=error_color)
                else:
                    meeting_obj.add_absent_member(author_id, 原因)
                    absent_record_channel = bot.get_channel(1126031617614426142)
                    user = json_assistant.User(author_id)
                    absent_record_embed = Embed(title="假單",
                                                description=f"{author_mention}({user.get_real_name()}) 預定不會出席"
                                                            f"會議`{會議id}`**({meeting_obj.get_name()})**。",
                                                color=default_color)
                    absent_record_embed.add_field(name="請假原因", value=原因, inline=False)
                    if meeting_obj.get_absent_members():
                        absent_members_str = ""
                        for m in meeting_obj.get_absent_members():
                            member_real_name = json_assistant.User(m[0]).get_real_name()
                            absent_members_str += f"<@{m[0]}>({member_real_name}) - *{m[1]}*\n"
                        absent_record_embed.add_field(name="請假人員", value=absent_members_str, inline=False)
                    await absent_record_channel.send(embed=absent_record_embed)
                    embed = Embed(title="請假成功", description="你已經成功請假。", color=default_color)
                    embed.add_field(name="會議ID", value=f"`{會議id}`", inline=False)
    else:
        embed = Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    try:
        await ctx.respond(embed=embed)
    except AttributeError:
        await ctx.followup.send(embed=embed, ephemeral=True)


@meeting.command(name="設定會議記錄", description="設定會議記錄連結。")
@commands.has_role(1114205838144454807)
async def set_meeting_record_link(ctx,
                                  meeting_id: Option(str, "欲設定的會議ID", min_length=5, max_length=5, required=True),
                                  連結: Option(str, "會議記錄連結", required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if meeting_id in id_list:
        meeting_obj = json_assistant.Meeting(meeting_id)
        regex = re.compile(
            r'^(?:http|ftp)s?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        if not re.match(regex, 連結):
            embed = Embed(title="錯誤", description=f"你輸入的連結({連結})格式不正確！", color=error_color)
        else:
            meeting_obj.set_meeting_record_link(連結)
            embed = Embed(title="設定會議記錄連結",
                          description=f"已將會議 `{meeting_id}` 的會議記錄連結設定為 `{連結}`。",
                          color=default_color)
            if meeting_obj.get_absent_members():
                notify_channel = bot.get_channel(1128232150135738529)
                absent_members_str = ""
                for m in meeting_obj.get_absent_members():
                    absent_members_str += f"<@{m[0]}> "
                notify_embed = Embed(title="會議記錄連結",
                                     description=f"會議 `{meeting_id}` 的會議記錄連結已經設定。\n"
                                                 f"缺席的成員，請務必閱讀會議紀錄！",
                                     color=default_color)
                notify_embed.add_field(name="會議名稱", value=meeting_obj.get_name(), inline=False)
                notify_embed.add_field(name="會議記錄連結", value=連結, inline=False)
                await notify_channel.send(content=absent_members_str, embed=notify_embed)
    else:
        embed = Embed(title="錯誤", description=f"會議 `{meeting_id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@meeting.command(name="查詢", description="以會議id查詢會議資訊。")
async def get_meeting_info(ctx,
                           會議id: Option(str, "欲查詢的會議ID", min_length=5, max_length=5, required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        meeting_obj = json_assistant.Meeting(會議id)
        embed = Embed(title="會議資訊", description=f"會議 `{會議id}` 的詳細資訊", color=default_color)
        embed.add_field(name="會議名稱", value=meeting_obj.get_name(), inline=False)
        if meeting_obj.get_description() != "":
            embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
        embed.add_field(name="主持人", value=f"<@{meeting_obj.get_host()}>", inline=False)
        embed.add_field(name="開始時間", value=f"<t:{int(meeting_obj.get_start_time())}:F>", inline=False)
        embed.add_field(name="地點", value=meeting_obj.get_link(), inline=False)
        if meeting_obj.get_meeting_record_link() != "":
            embed.add_field(name="會議記錄", value=meeting_obj.get_meeting_record_link(), inline=False)
        if meeting_obj.get_absent_members():
            absent_members_str = ""
            for m in meeting_obj.get_absent_members():
                absent_members_str += f"<@{m[0]}> - *{m[1]}*\n"
            embed.add_field(name="請假人員", value=absent_members_str, inline=False)
    else:
        embed = Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@commands.cooldown(1, 300)
@bot.slash_command(name="隊長信箱", description="匿名寄送訊息給隊長。")
async def send_message_to_leader(ctx,
                                 訊息: Option(str, "訊息內容", required=True)):  # noqa
    mail_id = json_assistant.Message.create_new_message()
    mail = json_assistant.Message(mail_id)
    data = {
        "author": ctx.author.id,
        "time": time.time(),
        "content": 訊息,
        "replied": False,
        "response": ""
    }
    mail.write_raw_info(data)
    mail_embed = Embed(title="隊長信箱", description=f"來自 {ctx.author.mention} 的訊息！", color=default_color)
    mail_embed.add_field(name="訊息ID", value=f"`{mail_id}`", inline=False)
    mail_embed.add_field(name="傳送時間", value=f"<t:{int(time.time())}:F>", inline=False)
    mail_embed.add_field(name="訊息內容", value=訊息, inline=False)
    mail_embed.set_thumbnail(url=ctx.author.display_avatar)
    mail_embed.set_footer(text="如果要回覆此訊息，請點選下方的按鈕。")
    mailbox_channel = bot.get_channel(1149274793917558814)
    await mailbox_channel.send(embed=mail_embed, view=RespondLeaderMailboxInView(mail_id))
    embed = Embed(title="隊長信箱", description="你的訊息已經傳送給隊長。", color=default_color)
    embed.add_field(name="訊息內容", value=訊息, inline=False)
    embed.add_field(name="此訊息會被其他成員看到嗎？", value="放心，隊長信箱的訊息僅會被隊長本人看到。\n"
                                                "如果隊長要**公開**回覆你的訊息，也僅會將訊息的內容公開，不會提到你的身分。")
    embed.add_field(name="隊長會回覆我的訊息嗎？", value="隊長可以選擇以**私人**或**公開**方式回覆你的訊息。\n"
                                              "- **私人**：你會收到一則機器人傳送的私人訊息。(請確認你已允許陌生人傳送私人訊息！)\n"
                                              "- **公開**：隊長的回覆會在<#1152158914847199312>與你的訊息一同公布。(不會公開你的身分！)")
    await ctx.respond(embed=embed, ephemeral=True)


@bot.slash_command(name="隊長信箱回覆", description="(隊長限定)回覆隊長信箱的訊息。")
async def reply_to_leader_mail(ctx,
                               msg_id: Option(str, "欲回覆的訊息ID", min_length=5, max_length=5, required=True),
                               msg: Option(str, "回覆的訊息內容", required=True),  # noqa
                               response_type: Option(str, "選擇以公開或私人方式回覆", choices=["公開", "私人"],
                                                     required=True)):
    if isinstance(ctx, discord.Interaction):
        await ctx.response.defer()
    else:
        await ctx.defer()
    leader = bot.get_user(842974332862726214)
    if isinstance(ctx, discord.Interaction):
        author = ctx.user
    else:
        author = ctx.author
    if author == leader:
        if msg_id in json_assistant.Message.get_all_message_id():
            mail = json_assistant.Message(msg_id)
            if mail.get_replied():
                embed = Embed(title="錯誤", description="這則訊息已被回覆。", color=error_color)
                embed.add_field(name="你的回覆", value=mail.get_response())
            else:
                response_embed = Embed(title="隊長信箱回覆", description="隊長回覆了信箱中的訊息！",
                                       color=default_color)
                response_embed.add_field(name="你的訊息內容", value=mail.get_content(), inline=False)
                response_embed.add_field(name="隊長的回覆內容", value=msg, inline=False)
                if response_type == "公開":
                    response_channel = bot.get_channel(1152158914847199312)
                    await response_channel.send(embed=response_embed)
                    embed = Embed(title="回覆成功！",
                                  description=f"已將你的回覆傳送到{response_channel.mention}。",
                                  color=default_color)
                    embed.add_field(name="對方的訊息內容", value=mail.get_content(), inline=False)
                    embed.add_field(name="你的回覆內容", value=msg, inline=False)
                elif response_type == "私人":
                    sender = bot.get_user(mail.get_author())
                    try:
                        await sender.send(embed=response_embed)
                        embed = Embed(title="回覆成功！", description=f"已將你的回覆傳送給{sender.mention}。",
                                      color=default_color)
                        embed.add_field(name="對方的訊息內容", value=mail.get_content(), inline=False)
                        embed.add_field(name="你的回覆內容", value=msg, inline=False)
                    except discord.errors.HTTPException as error:
                        if error.code == 50007:
                            embed = Embed(title="錯誤",
                                          description=f"{sender.mention} 不允許機器人傳送私人訊息。",
                                          color=error_color)
                        else:
                            raise error
                else:
                    embed = Embed(title="錯誤", description=f"所指定的回覆類型 (`{response_type}`) 不存在！")
                mail.set_replied(True)
                mail.set_response(msg)
        else:
            embed = Embed(title="錯誤", description=f"訊息 `{msg_id}` 不存在！", color=error_color)
    else:
        embed = Embed(title="錯誤", description="你不是隊長，無法使用此指令！", color=error_color)
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
async def clear_messages(ctx: discord.ApplicationContext,
                         count: Option(int, name="刪除訊息數", description="要刪除的訊息數量", min_value=1,
                                       max_value=50)):
    channel = ctx.channel
    channel: discord.TextChannel
    try:
        await channel.purge(limit=count)
        embed = Embed(title="已清除訊息", description=f"已成功清除 {channel.mention} 中的 `{count}` 則訊息。", color=default_color)
    except Exception as e:
        embed = Embed(title="錯誤", description="發生未知錯誤。", color=error_color)
        embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
    await ctx.respond(embed=embed)


@bot.slash_command(name="debug", description="(開發者專用)除錯用")
@commands.is_owner()
async def debug(ctx):
    embed = Embed(title="除錯資訊", description="目前資訊如下：", color=default_color)
    embed.add_field(name="Time", value=f"<t:{int(time.time())}> ({time.time()})")
    embed.add_field(name="Version", value=git.Repo(search_parent_directories=True).head.object.hexsha)
    await ctx.respond(embed=embed)


@bot.slash_command(name="about", description="Provides information about this robot.",
                   description_localizations={"zh-TW": "提供關於這隻機器人的資訊。"})
async def about(ctx,
                私人訊息: Option(bool, "是否以私人訊息回應", required=False) = False):  # noqa
    embed = Embed(title="關於", color=default_color)
    embed.set_thumbnail(url=bot.user.display_avatar)
    embed.add_field(name="程式碼與授權", value="本機器人由<@657519721138094080>維護，使用[Py-cord]"
                                         "(https://github.com/Pycord-Development/pycord)進行開發。\n"
                                         "本機器人的程式碼及檔案皆可在[這裡](https://github.com/Alllen95Wei/RobomaniaBot)"
                                         "查看。",
                    inline=True)
    embed.add_field(name="聯絡", value="如果有任何技術問題及建議，請聯絡<@657519721138094080>。", inline=True)
    repo = git.Repo(search_parent_directories=True)
    update_msg = repo.head.reference.commit.message
    raw_sha = repo.head.object.hexsha
    sha = raw_sha[:7]
    embed.add_field(name=f"分支訊息：{sha}", value=update_msg, inline=False)
    year = time.strftime("%Y")
    embed.set_footer(text=f"©Allen Why, {year} | 版本：commit {sha[:7]}")
    await ctx.respond(embed=embed, ephemeral=私人訊息)


@bot.slash_command(name="dps", description="查詢伺服器電腦的CPU及記憶體使用率。")
async def dps(ctx):
    embed = Embed(title="伺服器電腦資訊", color=default_color)
    embed.add_field(name="CPU使用率", value=f"{detect_pc_status.get_cpu_usage()}%")
    embed.add_field(name="記憶體使用率", value=f"{detect_pc_status.get_ram_usage_detail()}")
    await ctx.respond(embed=embed)


@bot.slash_command(name="update", description="更新機器人。")
@commands.is_owner()
async def update(ctx,
                 私人訊息: Option(bool, "是否以私人訊息回應", required=False) = False):  # noqa
    embed = Embed(title="更新中", description="更新流程啟動。", color=default_color)
    await ctx.respond(embed=embed, ephemeral=私人訊息)
    event = discord.Activity(type=discord.ActivityType.playing, name="更新中...")
    await bot.change_presence(status=discord.Status.idle, activity=event)
    upd.update(os.getpid(), system())


@bot.slash_command(name="cmd", description="在伺服器端執行指令並傳回結果。")
@commands.is_owner()
async def cmd(ctx,
              指令: Option(str, "要執行的指令", required=True),  # noqa: PEP 3131
              執行模組: Option(str, choices=["subprocess", "os"], description="執行指令的模組",  # noqa: PEP 3131
                               required=False) = "subprocess",
              私人訊息: Option(bool, "是否以私人訊息回應", required=False) = False):  # noqa: PEP 3131
    try:
        await ctx.defer(ephemeral=私人訊息)
        command = split(指令)
        if command[0] == "cmd":
            embed = Embed(title="錯誤", description="基於安全原因，你不能執行這個指令。", color=error_color)
            await ctx.respond(embed=embed, ephemeral=私人訊息)
            return
        if 執行模組 == "subprocess":
            result = str(run(command, capture_output=True, text=True).stdout)
        else:
            result = str(os.popen(指令).read())
        if result != "":
            embed = Embed(title="執行結果", description=f"```{result}```", color=default_color)
        else:
            embed = Embed(title="執行結果", description="終端未傳回回應。", color=default_color)
    except WindowsError as e:
        if e.winerror == 2:
            embed = Embed(title="錯誤", description="找不到指令。請嘗試更換執行模組。", color=error_color)
        else:
            embed = Embed(title="錯誤", description=f"發生錯誤：`{e}`", color=error_color)
    except Exception as e:
        embed = Embed(title="錯誤", description=f"發生錯誤：`{e}`", color=error_color)
    try:
        await ctx.respond(embed=embed, ephemeral=私人訊息)
    except discord.errors.HTTPException as HTTPError:
        if "fewer in length" in str(HTTPError):
            txt_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "full_msg.txt")
            with open(txt_file_path, "w") as file:
                file.write(str(result))  # noqa
            await ctx.respond("由於訊息長度過長，因此改以文字檔方式呈現。", file=discord.File(txt_file_path),
                              ephemeral=私人訊息)
            os.remove(txt_file_path)


@bot.event
async def on_message(message):
    if message.author.id == bot.user.id:
        return
    if "The startCompetition() method" in message.content or "Warning at" in message.content:
        await message.reply("<:deadge:1200367980748476437>" * 3)


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if member.bot:
        return
    if before.channel is None or after.channel is None or before.channel.id != after.channel.id:
        member_real_name = json_assistant.User(member.id).get_real_name()
        if member_real_name is None:
            member_real_name = member.name
        if not isinstance(before.channel, type(None)):
            await before.channel.send(
                f"<:left:1208779447440777226> **{member_real_name}** "
                f"在 <t:{int(time.time())}:T> 離開 {before.channel.mention}。",
                delete_after=43200)
        if not isinstance(after.channel, type(None)):
            await after.channel.send(
                f"<:join:1208779348438683668> **{member_real_name}** "
                f"在 <t:{int(time.time())}:T> 加入 {after.channel.mention}。",
                delete_after=43200)


bot.load_extensions("cogs.reminder", "cogs.verification", "cogs.backup_sys", "cogs.player")
bot.run(TOKEN)
