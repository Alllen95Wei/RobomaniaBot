import time
import datetime
import zoneinfo
import logging
from colorlog import ColoredFormatter
from PIL import ImageGrab
import discord
from discord.ext import commands
from discord.ext import tasks
from discord import Option
import os
from dotenv import load_dotenv
import update as upd
from platform import system
import re

import json_assistant

# 機器人
intents = discord.Intents.all()
bot = commands.Bot(intents=intents, help_command=None)
# 常用物件、變數
base_dir = os.path.abspath(os.path.dirname(__file__))
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
default_color = 0x012a5e
error_color = 0xF1411C
# 載入TOKEN
load_dotenv(dotenv_path=os.path.join(base_dir, "TOKEN.env"))
TOKEN = str(os.getenv("TOKEN"))


class CreateLogger:
    def __init__(self):
        super().__init__()
        self.c_logger = self.color_logger()

    @staticmethod
    def color_logger():
        display_formatter = ColoredFormatter(
            fmt="%(white)s[%(asctime)s] %(log_color)s%(levelname)-10s%(reset)s %(blue)s%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            reset=True,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "ANONYMOUS": "purple",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red",
            },
        )

        file_formatter = logging.Formatter(
            fmt="[%(asctime)s] %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S")

        logger = logging.getLogger()
        handler = logging.StreamHandler()
        handler.setFormatter(display_formatter)
        logger.addHandler(handler)
        handler = logging.FileHandler("logs.log", encoding="utf-8")
        handler.setFormatter(file_formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        return logger

    def debug(self, message: str):
        self.c_logger.debug(message)

    def info(self, message: str):
        self.c_logger.info(message)

    def warning(self, message: str):
        self.c_logger.warning(message)

    def error(self, message: str):
        self.c_logger.error(message)

    def critical(self, message: str):
        self.c_logger.critical(message)


real_logger = CreateLogger()


@tasks.loop(seconds=1)
async def check_meeting():
    real_logger.debug("開始檢查會議時間...")
    meeting_id_list = json_assistant.Meeting.get_all_meeting_id()
    m = bot.get_channel(1128232150135738529)
    for meeting_id in meeting_id_list:
        meeting_obj = json_assistant.Meeting(meeting_id)
        if meeting_obj.get_started() is False:
            if time.time() >= meeting_obj.get_start_time():
                meeting_obj.set_started(True)
                embed = discord.Embed(title="會議開始！", description=f"會議**「{meeting_obj}」**已經在"
                                                                 f"<t:{int(meeting_obj.get_start_time())}>開始！",
                                      color=default_color)
                if meeting_obj.get_description() != "":
                    embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
                embed.add_field(name="主持人", value=f"<@{meeting_obj.get_host()}> "
                                                  f"({bot.get_user(meeting_obj.get_host())})", inline=False)
                embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
                if meeting_obj.get_absent_members():
                    absent_members = ""
                    for m in meeting_obj.get_absent_members():
                        absent_members += f"<@{m[0]}> - *{m[1]}*\n"
                    embed.add_field(name="請假人員", value=absent_members, inline=False)
                await m.send(embed=embed)
                real_logger.info(f"已傳送會議 {meeting_id} 的開始通知。")
            elif meeting_obj.get_notified() is False and meeting_obj.get_start_time() - time.time() <= 300:
                embed = discord.Embed(title="會議即將開始！",
                                      description=f"會議**「{meeting_obj}」**即將於<t:{int(meeting_obj.get_start_time())}:R>"
                                                  f"開始！",
                                      color=default_color)
                if meeting_obj.get_description() != "":
                    embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
                embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
                await m.send(content="@everyone", embed=embed)
                meeting_obj.set_notified(True)
                real_logger.info(f"已傳送會議 {meeting_id} 的開始通知。")


class GetEventInfo(discord.ui.Modal):
    def __init__(self, meeting_id=None) -> None:
        super().__init__(title="會議", timeout=None)
        self.meeting_id = meeting_id
        if meeting_id is not None:
            meeting_obj = json_assistant.Meeting(meeting_id)
            prefill_data = [meeting_obj.get_name(), meeting_obj.get_description(),
                            datetime.datetime.fromtimestamp(meeting_obj.get_start_time(), tz=now_tz).
                            strftime("%Y/%m/%d %H:%M"),
                            meeting_obj.get_link(),
                            meeting_obj.get_meeting_record_link()]
        else:
            prefill_data = ["", "", "", "", ""]

        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議標題", value=prefill_data[0],
                                           required=True))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.long, label="簡介", max_length=200,
                                           value=prefill_data[1], required=False))
        self.add_item(
            discord.ui.InputText(style=discord.InputTextStyle.short, label="開始時間(格式：YYYY/MM/DD HH:MM，24小時制)",
                                 placeholder="如：2021/01/10 12:05", min_length=16, max_length=16,
                                 value=prefill_data[2], required=True))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議地點",
                                           placeholder="可貼上Meet或Discord頻道連結",
                                           value=prefill_data[3], required=True))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議記錄連結",
                                           placeholder="貼上Google文件連結",
                                           value=prefill_data[4], required=False))

    async def callback(self, interaction: discord.Interaction):
        if self.meeting_id is not None:
            unique_id = self.meeting_id
            embed = discord.Embed(title="編輯會議",
                                  description=f"會議 `{unique_id}` **({self.children[0].value})** 已經編輯成功！",
                                  color=default_color)
        else:
            unique_id = json_assistant.Meeting.create_new_meeting()
            embed = discord.Embed(title="預定新會議",
                                  description=f"你預定的會議：**{self.children[0].value}**，已經預定成功！",
                                  color=default_color)
        meeting_obj = json_assistant.Meeting(unique_id)
        meeting_obj.set_name(self.children[0].value)
        meeting_obj.set_description(self.children[1].value)
        meeting_obj.set_host(interaction.user.id)
        meeting_obj.set_link(self.children[3].value)
        meeting_obj.set_meeting_record_link(self.children[4].value)
        real_logger.info(f"已預定/編輯會議 {unique_id}。")
        embed.add_field(name="會議ID", value=f"`{unique_id}`", inline=False)
        if self.children[1].value != "":
            embed.add_field(name="簡介", value=self.children[1].value, inline=False)
        embed.add_field(name="主持人", value=interaction.user.mention, inline=False)
        try:
            unix_start_time = time.mktime(time.strptime(self.children[2].value, "%Y/%m/%d %H:%M"))
            if unix_start_time < time.time():
                embed = discord.Embed(title="錯誤",
                                      description=f"輸入的開始時間(<t:{int(unix_start_time)}>)已經過去！請重新輸入。",
                                      color=error_color)
                await interaction.response.edit_message(embed=embed)
                return
            else:
                meeting_obj.set_start_time(unix_start_time)
                embed.add_field(name="開始時間", value=f"<t:{int(unix_start_time)}>", inline=False)
        except ValueError:
            embed = discord.Embed(title="錯誤",
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
        embed.set_footer(
            text=f"如要請假，請點選下方按鈕，或使用「/meeting 請假 會議id:{unique_id}」指令，並在會議開始前1小時處理完畢。")
        await m.send(embed=embed, view=AbsentInView(unique_id))
        real_logger.info(f"已傳送預定/編輯會議 {unique_id} 的通知。")


class Absent(discord.ui.Modal):
    def __init__(self, meeting_id: str) -> None:
        super().__init__(title="請假", timeout=None)
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="請假理由",
                                           placeholder="請輸入合理的請假理由。打「家裡有事」的，好自為之(？", required=True))
        self.meeting_id = meeting_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await absence_meeting(interaction, self.meeting_id, self.children[0].value)


class GetEventInfoInView(discord.ui.View):
    def __init__(self, meeting_id=None):
        super().__init__()
        self.meeting_id = meeting_id

    @discord.ui.button(label="點此開啟會議視窗", style=discord.ButtonStyle.green, emoji="📝")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(GetEventInfo(self.meeting_id))


class AbsentInView(discord.ui.View):
    def __init__(self, meeting_id: str):
        super().__init__()
        self.meeting_id = meeting_id

    @discord.ui.button(label="點此開啟請假視窗", style=discord.ButtonStyle.red, emoji="🙋")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(Absent(self.meeting_id))


@bot.event
async def on_ready():
    real_logger.info("機器人準備完成！")
    real_logger.info(f"PING值：{round(bot.latency * 1000)}ms")
    real_logger.info(f"登入身分：{bot.user}")
    activity = discord.Activity(name="GitHub", type=discord.ActivityType.watching)
    await bot.change_presence(activity=activity)
    await check_meeting.start()


@bot.event
async def on_application_command(ctx):
    real_logger.info(f"{ctx.author} 執行了斜線指令 \"{ctx.command.name}\"")


member = bot.create_group(name="member", description="隊員資訊相關指令。")


@bot.slash_command(name="ping", description="查看機器人延遲。")
async def ping(ctx):
    embed = discord.Embed(title="PONG!✨", color=default_color)
    embed.add_field(name="PING值", value=f"`{round(bot.latency * 1000)}` ms")
    await ctx.respond(embed=embed)


@bot.event
async def on_application_command_error(ctx, error):
    embed = discord.Embed(title="錯誤", description=f"發生了一個錯誤，錯誤詳細資料如下。", color=error_color)
    embed.add_field(name="指令名稱", value=f"`{ctx.command.name}`", inline=False)
    embed.add_field(name="使用者", value=f"`{ctx.author}`", inline=False)
    embed.add_field(name="錯誤類型", value=f"`{type(error).__name__}`", inline=False)
    embed.add_field(name="錯誤訊息", value=f"`{error}`", inline=False)
    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(title="指令冷卻中", description=f"這個指令正在冷卻中，請在`{round(error.retry_after)}`秒後再試。",
                              color=error_color)
        await ctx.respond(embed=embed, ephemeral=True)
    else:
        allen = bot.get_user(657519721138094080)
        await allen.send(embed=embed)
        raise error


@member.command(name="查詢", description="查看隊員資訊。")
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
        jobs_str = "None"
    embed = discord.Embed(title="隊員資訊", description=f"{隊員.mention} 的資訊", color=default_color)
    embed.add_field(name="真實姓名", value=member_data.get_real_name(), inline=False)
    embed.add_field(name="職務", value=jobs_str, inline=False)
    embed.add_field(name="總計會議時數", value=member_data.get_total_meeting_time(), inline=False)
    embed.add_field(name="警告點數", value=member_data.get_warning_points(), inline=False)
    embed.set_thumbnail(url=隊員.display_avatar)
    await ctx.respond(embed=embed)


@bot.user_command(name="查看此隊員的資訊")
async def member_info_user(ctx, user: discord.Member):
    await member_info(ctx, user)


member_info_manage = bot.create_group(name="manage", description="隊員資訊管理。")


@member_info_manage.command(name="設定真名", description="設定隊員真實姓名。")
async def member_set_real_name(ctx,
                               隊員: Option(discord.Member, "隊員", required=True),  # noqa
                               真實姓名: Option(str, "真實姓名", required=True)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        member_data = json_assistant.User(隊員.id)
        member_data.set_real_name(真實姓名)
        embed = discord.Embed(title="設定真實姓名", description=f"已將 {隊員.mention} 的真實姓名設定為 {真實姓名}。",
                              color=default_color)
        embed.set_thumbnail(url=隊員.display_avatar)
    else:
        embed = discord.Embed(title="設定真實姓名", description=f"你沒有權限設定真實姓名！",
                              color=error_color)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="新增職務", description="新增隊員職務。")
async def member_add_job(ctx,
                         隊員: Option(discord.Member, "隊員", required=True),  # noqa
                         職務: Option(str, "職務", required=True)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        member_data = json_assistant.User(隊員.id)
        member_data.add_job(職務)
        embed = discord.Embed(title="新增職務", description=f"已將 {隊員.mention} 新增職務 {職務}。",
                              color=default_color)
        embed.set_thumbnail(url=隊員.display_avatar)
    else:
        embed = discord.Embed(title="新增職務", description=f"你沒有權限新增職務！", color=error_color)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="移除職務", description="移除隊員職務。")
async def member_remove_job(ctx,
                            隊員: Option(discord.Member, "隊員", required=True),  # noqa
                            職務: Option(str, "職務", required=True)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        member_data = json_assistant.User(隊員.id)
        member_data.remove_job(職務)
        embed = discord.Embed(title="移除職務", description=f"已將 {隊員.mention} 移除職務 {職務}。",
                              color=default_color)
        embed.set_thumbnail(url=隊員.display_avatar)
    else:
        embed = discord.Embed(title="移除職務", description=f"你沒有權限移除職務！", color=error_color)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="add_meeting_time", description="新增隊員會議時數。")
async def member_add_meeting_time(ctx,
                                  隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                  會議時數: Option(int, "會議時數", required=True)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        member_data = json_assistant.User(隊員.id)
        member_data.add_meeting_time(會議時數)
        embed = discord.Embed(title="新增會議時數", description=f"已將 {隊員.mention} 新增會議時數 {會議時數}。",
                              color=default_color)
        embed.set_thumbnail(url=隊員.display_avatar)
    else:
        embed = discord.Embed(title="新增會議時數", description=f"你沒有權限新增會議時數！", color=error_color)
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
    "3點 - 嚴重影響隊伍形象"]


@member_info_manage.command(name="記點", description="記點。(對，就是記點，我希望我用不到這個指令)")
async def member_add_warning_points(ctx,
                                    隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                    記點事由: Option(str, "記點事由", choices=warning_points_choices, required=True),  # noqa
                                    附註: Option(str, "附註事項", required=False)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        reason = 記點事由[5:]
        member_data = json_assistant.User(隊員.id)
        if 記點事由 == "半點 - 垃圾亂丟":
            member_data.add_warning_points(0.5, reason, 附註)
            points = 0.5
        elif 記點事由 == "半點 - 開會/培訓 無故遲到(5分鐘)":
            member_data.add_warning_points(0.5, reason, 附註)
            points = 0.5
        elif 記點事由 == "1點 - 開會/培訓 無故未到":
            member_data.add_warning_points(1, reason, 附註)
            points = 1
        elif 記點事由 == "1點 - 兩天內沒有交工筆(賽季時為三天)":
            member_data.add_warning_points(1, reason, 附註)
            points = 1
        elif 記點事由 == "1點 - 謊報請假時間/原因":
            member_data.add_warning_points(1, reason, 附註)
            points = 1
        elif 記點事由 == "1點 - 無故遲交文件超過一天":
            member_data.add_warning_points(1, reason, 附註)
            points = 1
        elif 記點事由 == "2點 - 上課/工作時滑手機":
            member_data.add_warning_points(2, reason, 附註)
            points = 2
        elif 記點事由 == "2點 - 打遊戲太吵":
            member_data.add_warning_points(2, reason, 附註)
            points = 2
        elif 記點事由 == "3點 - 嚴重影響隊伍形象":
            member_data.add_warning_points(3, reason, 附註)
            points = 3
        else:
            points = 0
        current_points = member_data.get_warning_points()
        embed = discord.Embed(title="記點", description=f"已將 {隊員.mention} 記點。", color=default_color)
        embed.add_field(name="記點點數", value=str(points), inline=True)
        embed.add_field(name="目前點數(已加上新點數)", value=str(current_points), inline=True)
        embed.add_field(name="記點事由", value=reason, inline=False)
        if 附註 is not None:
            embed.add_field(name="附註事項", value=附註, inline=False)
        embed.set_thumbnail(url=隊員.display_avatar)
        embed_list = [embed]
        mention_text = f"{隊員.mention} 由於**「{reason}」**，依照隊規記上{points}點。"
        await ctx.channel.send(content=mention_text)
        if current_points >= 4:
            warning_msg = discord.Embed(title="退隊警告！",
                                        description=f"{隊員.mention} 的點數已達到{current_points}點！",
                                        color=error_color)
            warning_msg.set_footer(text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。")
            embed_list.append(warning_msg)
    else:
        embed = discord.Embed(title="記點", description=f"你沒有權限記點！", color=error_color)
        embed_list = [embed]
    await ctx.respond(embeds=embed_list)


@member_info_manage.command(name="意外記銷點",
                            description="當一般記點指令中沒有合適的規定來記/銷點，則可使用此指令。請合理使用！")
async def member_add_warning_points(ctx,
                                    隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                    點數: Option(float, "點數", required=True),  # noqa
                                    事由: Option(str, "事由", required=True)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        member_data = json_assistant.User(隊員.id)
        member_data.add_warning_points(點數, "使用「意外記/銷點」指令", 事由)
        current_points = member_data.get_warning_points()
        embed = discord.Embed(title="意外記/銷點", description=f"已將 {隊員.mention} 記/銷點。", color=default_color)
        embed.add_field(name="記點點數", value=str(點數), inline=True)
        embed.add_field(name="目前點數(已加上/減去新點數)", value=str(current_points), inline=True)
        embed.add_field(name="記點事由", value="使用「意外記/銷點」指令", inline=False)
        embed.add_field(name="附註事項", value=事由, inline=False)
        embed.set_thumbnail(url=隊員.display_avatar)
        embed_list = [embed]
        if 點數 > 0:
            mention_text = f"{隊員.mention} 由於**「{事由}」**，記上{點數}點。"
            await ctx.channel.send(content=mention_text)
        if current_points >= 4:
            warning_msg = discord.Embed(title="退隊警告！",
                                        description=f"{隊員.mention} 的點數已達到{current_points}點！",
                                        color=error_color)
            warning_msg.set_footer(text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。")
            embed_list.append(warning_msg)
    else:
        embed = discord.Embed(title="意外記/銷點", description=f"你沒有權限記/銷點！", color=error_color)
        embed_list = [embed]
    await ctx.respond(embeds=embed_list)


remove_warning_points_choices = [
    "半點 - 自主倒垃圾",
    "半點 - 培訓時去外面拿午餐",
    "1點 - 中午時間/第八節 打掃工作室"]


@member_info_manage.command(name="銷點", description="銷點。")
async def member_remove_warning_points(ctx,
                                       隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                       銷點事由: Option(str, "銷點事由", choices=remove_warning_points_choices,  # noqa
                                                        required=True),
                                       附註: Option(str, "附註事項", required=False)):  # noqa
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        reason = 銷點事由[5:]
        member_data = json_assistant.User(隊員.id)
        if 銷點事由 == "半點 - 自主倒垃圾":
            member_data.add_warning_points(-0.5, reason, 附註)
            points = 0.5
        elif 銷點事由 == "半點 - 培訓時去外面拿午餐":
            member_data.add_warning_points(-0.5, reason, 附註)
            points = 0.5
        elif 銷點事由 == "1點 - 中午時間/第八節 打掃工作室":
            member_data.add_warning_points(-1, reason, 附註)
            points = 1
        else:
            points = 0
        embed = discord.Embed(title="銷點", description=f"已將 {隊員.mention} 銷點。", color=default_color)
        if member_data.get_warning_points() < 0:
            member_data.add_warning_points(-member_data.get_warning_points(), "防止負點發生",
                                           "為避免記點點數為負，機器人已自動將點數設為0。")
            embed.set_footer(text="為避免記點點數為負，機器人已自動將點數設為0。")
        embed.add_field(name="銷點點數", value=str(points), inline=True)
        embed.add_field(name="目前點數(已減去新點數)", value=str(member_data.get_warning_points()), inline=True)
        embed.add_field(name="銷點事由", value=reason, inline=False)
        if 附註 is not None:
            embed.add_field(name="附註事項", value=附註, inline=False)
        embed.set_thumbnail(url=隊員.display_avatar)
    else:
        embed = discord.Embed(title="銷點", description=f"你沒有權限銷點！", color=error_color)
    await ctx.respond(embed=embed)


@member_info_manage.command(name="改名", description="將伺服器中所有成員的名稱改為其真名。")
async def member_change_name(ctx):
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        embed = discord.Embed(title="改名", description="已將伺服器中所有成員的名稱改為其真名。", color=default_color)
        no_real_name = ""
        for m in server.members:
            real_name = json_assistant.User(m.id).get_real_name()
            if real_name is not None:
                await m.edit(nick=real_name)
            else:
                no_real_name += f"{m.mention} "
        if no_real_name != "":
            embed.add_field(name="未設定真名的成員", value=no_real_name if no_real_name else "無", inline=False)
    else:
        embed = discord.Embed(title="改名", description=f"你沒有權限改名！", color=error_color)
    await ctx.respond(embed=embed)


@member.command(name="個人記點紀錄", description="查詢記點紀錄。")
async def member_get_warning_history(ctx,
                                     隊員: Option(discord.Member, "隊員", required=True)):  # noqa
    member_data = json_assistant.User(隊員.id)
    embed = discord.Embed(title="記點紀錄", description=f"{隊員.mention} 的記點紀錄", color=default_color)
    embed.add_field(name="目前點數", value=member_data.get_warning_points(), inline=False)
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


@member.command(name="全員記點記錄", description="查詢所有人的記、銷點紀錄。")
async def member_get_all_warning_history(ctx):
    embed = discord.Embed(title="記點紀錄", description="全隊所有記、銷點紀錄", color=default_color)
    for i in json_assistant.User.get_all_warning_history():
        add_or_subtract = "❌記點" if i[3] > 0 else "✅銷點"
        if i[4] is None:
            formatted_history = f"{bot.get_user(i[0]).mention}{add_or_subtract} {abs(i[3])} 點：{i[2]}"
        else:
            formatted_history = f"{bot.get_user(i[0]).mention}{add_or_subtract} {abs(i[3])} 點：{i[2]}\n*({i[4]})*"
        embed.add_field(name=f"{i[1]}", value=formatted_history, inline=False)
    await ctx.respond(embed=embed)


meeting = bot.create_group(name="meeting", description="會議相關指令。")


@meeting.command(name="建立", description="預定新的會議。")
async def create_new_meeting(ctx):
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        embed = discord.Embed(title="預定會議", description="請點擊下方的按鈕，開啟會議預定視窗。", color=default_color)
        await ctx.respond(embed=embed, view=GetEventInfoInView(), ephemeral=True)
    else:
        embed = discord.Embed(title="銷點", description=f"你沒有權限預定會議！", color=error_color)
        await ctx.respond(embed=embed)


@meeting.command(name="編輯", description="編輯會議資訊。")
async def edit_meeting(ctx, 會議id: Option(str, "欲修改的會議ID", min_length=5, max_length=5, required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        server = ctx.guild
        manager_role = discord.utils.get(server.roles, id=1114205838144454807)
        if manager_role in ctx.author.roles:
            embed = discord.Embed(title="編輯會議", description="請點擊下方的按鈕，開啟會議編輯視窗。",
                                  color=default_color)
            await ctx.respond(embed=embed, view=GetEventInfoInView(會議id), ephemeral=True)
        else:
            embed = discord.Embed(title="錯誤", description=f"你沒有權限編輯會議！", color=error_color)
            await ctx.respond(embed=embed)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
        await ctx.respond(embed=embed)


@meeting.command(name="刪除", description="刪除會議。")
async def delete_meeting(ctx, 會議id: Option(str, "欲刪除的會議ID", min_length=5, max_length=5, required=True),  # noqa
                         原因: Option(str, "取消會議的原因", required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        server = ctx.guild
        manager_role = discord.utils.get(server.roles, id=1114205838144454807)
        if manager_role in ctx.author.roles:
            meeting_obj = json_assistant.Meeting(會議id)
            if meeting_obj.get_started():
                embed = discord.Embed(title="錯誤", description="此會議已經開始，無法刪除！", color=error_color)
            else:
                m = bot.get_channel(1128232150135738529)
                notify_embed = discord.Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。",
                                             color=default_color)
                notify_embed.add_field(name="會議標題", value=meeting_obj.get_name(), inline=False)
                notify_embed.add_field(name="取消原因", value=原因, inline=False)
                if meeting_obj.get_notified():
                    await m.send(content="@everyone", embed=notify_embed)
                else:
                    await m.send(embed=notify_embed)
                meeting_obj.delete()
                embed = discord.Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。", color=default_color)
        else:
            embed = discord.Embed(title="錯誤", description=f"你沒有權限刪除會議！", color=error_color)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@meeting.command(name="所有id", description="列出所有的會議ID。")
async def list_meetings(ctx):
    embed = discord.Embed(title="會議ID列表", description="目前已存在的會議ID如下：", color=default_color)
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
            embed = discord.Embed(title="錯誤", description="此會議已經開始，無法請假！", color=error_color)
        elif meeting_obj.get_start_time() - time.time() < 3600:
            embed = discord.Embed(title="錯誤", description=f"請假需在會議一小時前處理完畢。\n"
                                                            f"此會議即將在<t:{int(meeting_obj.get_start_time())}:R>開始！",
                                  color=error_color)
        else:
            absent_members_id = [i[0] for i in meeting_obj.get_absent_members()]
            try:
                author_id = ctx.author.id
                author_mention = ctx.author.mention
            except AttributeError:
                author_id = ctx.user.id
                author_mention = ctx.user.mention
            if author_id in absent_members_id:
                embed = discord.Embed(title="錯誤", description="你已經請過假了！", color=error_color)
            else:
                meeting_obj.add_absent_member(author_id, 原因)
                absent_record_channel = bot.get_channel(1126031617614426142)
                user = json_assistant.User(author_id)
                absent_record_embed = discord.Embed(title="假單",
                                                    description=f"{author_mention}({user.get_real_name()}) 預定不會出席"
                                                                f"會議`{會議id}`**({meeting_obj.get_name()})**。",
                                                    color=default_color)
                absent_record_embed.add_field(name="請假原因", value=原因, inline=False)
                if meeting_obj.get_absent_members():
                    absent_members_str = ""
                    for m in meeting_obj.get_absent_members():
                        absent_members_str += f"<@{m[0]}> - *{m[1]}*\n"
                    absent_record_embed.add_field(name="請假人員", value=absent_members_str, inline=False)
                await absent_record_channel.send(embed=absent_record_embed)
                embed = discord.Embed(title="請假成功", description=f"你已經成功請假。", color=default_color)
                embed.add_field(name="會議ID", value=f"`{會議id}`", inline=False)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    try:
        await ctx.respond(embed=embed)
    except AttributeError:
        await ctx.followup.send(embed=embed, ephemeral=True)


@meeting.command(name="設定會議記錄", description="設定會議記錄連結。")
async def set_meeting_record_link(ctx,
                                  會議id: Option(str, "欲設定的會議ID", min_length=5, max_length=5, required=True),  # noqa
                                  連結: Option(str, "會議記錄連結", required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        server = ctx.guild
        manager_role = discord.utils.get(server.roles, id=1114205838144454807)
        if manager_role in ctx.author.roles:
            meeting_obj = json_assistant.Meeting(會議id)
            regex = re.compile(
                r'^(?:http|ftp)s?://'  # http:// or https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
                r'(?::\d+)?'  # optional port
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            if not re.match(regex, 連結):
                embed = discord.Embed(title="錯誤", description=f"你輸入的連結({連結})格式不正確！", color=error_color)
            else:
                meeting_obj.set_meeting_record_link(連結)
                embed = discord.Embed(title="設定會議記錄連結",
                                      description=f"已將會議 `{會議id}` 的會議記錄連結設定為 `{連結}`。",
                                      color=default_color)
                if meeting_obj.get_absent_members():
                    notify_channel = bot.get_channel(1128232150135738529)
                    absent_members_str = ""
                    for m in meeting_obj.get_absent_members():
                        absent_members_str += f"<@{m[0]}> "
                    notify_embed = discord.Embed(title="會議記錄連結",
                                                 description=f"會議 `{會議id}` 的會議記錄連結已經設定。\n"
                                                             f"缺席的成員，請務必閱讀會議紀錄！",
                                                 color=default_color)
                    notify_embed.add_field(name="會議名稱", value=meeting_obj.get_name(), inline=False)
                    notify_embed.add_field(name="會議記錄連結", value=連結, inline=False)
                    await notify_channel.send(content=absent_members_str, embed=notify_embed)
        else:
            embed = discord.Embed(title="錯誤", description=f"你沒有權限設定會議記錄連結！", color=error_color)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@meeting.command(name="查詢", description="以會議id查詢會議資訊。")
async def get_meeting_info(ctx,
                           會議id: Option(str, "欲查詢的會議ID", min_length=5, max_length=5, required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        meeting_obj = json_assistant.Meeting(會議id)
        embed = discord.Embed(title="會議資訊", description=f"會議 `{會議id}` 的詳細資訊", color=default_color)
        embed.add_field(name="會議名稱", value=meeting_obj.get_name(), inline=False)
        if meeting_obj.get_description() != "":
            embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
        embed.add_field(name="主持人", value=f"<@{meeting_obj.get_host()}>", inline=False)
        embed.add_field(name="開始時間", value=f"<t:{int(meeting_obj.get_start_time())}>", inline=False)
        embed.add_field(name="地點", value=meeting_obj.get_link(), inline=False)
        if meeting_obj.get_meeting_record_link() != "":
            embed.add_field(name="會議記錄", value=meeting_obj.get_meeting_record_link(), inline=False)
        if meeting_obj.get_absent_members():
            absent_members_str = ""
            for m in meeting_obj.get_absent_members():
                absent_members_str += f"<@{m[0]}> - *{m[1]}*\n"
            embed.add_field(name="請假人員", value=absent_members_str, inline=False)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@bot.slash_command(name="screenshot", description="在機器人伺服器端截圖。")
async def screenshot(ctx,
                     私人訊息: Option(bool, "是否以私人訊息回應", required=False) = False):  # noqa
    if ctx.author == bot.get_user(657519721138094080):
        try:
            await ctx.defer()
            # 截圖
            img = ImageGrab.grab()
            img.save("screenshot.png")
            file = discord.File("screenshot.png")
            embed = discord.Embed(title="截圖", color=default_color)
            await ctx.respond(embed=embed, file=file, ephemeral=私人訊息)
        except Exception as e:
            embed = discord.Embed(title="錯誤", description=f"發生錯誤：`{e}`", color=error_color)
            await ctx.respond(embed=embed, ephemeral=私人訊息)
    else:
        embed = discord.Embed(title="錯誤", description="你沒有權限使用此指令。", color=error_color)
        私人訊息 = True  # noqa
        await ctx.respond(embed=embed, ephemeral=私人訊息)


@bot.slash_command(name="update", description="更新機器人。")
async def update(ctx,
                 私人訊息: Option(bool, "是否以私人訊息回應", required=False) = False):  # noqa: PEP 3131
    if ctx.author == bot.get_user(657519721138094080):
        embed = discord.Embed(title="更新中", description="更新流程啟動。", color=default_color)
        await ctx.respond(embed=embed, ephemeral=私人訊息)
        event = discord.Activity(type=discord.ActivityType.playing, name="更新中...")
        await bot.change_presence(status=discord.Status.idle, activity=event)
        upd.update(os.getpid(), system())
    else:
        embed = discord.Embed(title="錯誤", description="你沒有權限使用此指令。", color=error_color)
        私人訊息 = True  # noqa: PEP 3131
        await ctx.respond(embed=embed, ephemeral=私人訊息)


bot.run(TOKEN)
