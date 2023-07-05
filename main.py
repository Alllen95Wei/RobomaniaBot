import time
import datetime
import zoneinfo
import discord
from discord.ext import commands
from discord.ext import tasks
from discord import Option
import os
from dotenv import load_dotenv

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


@tasks.loop(seconds=1)
async def check_meeting():
    meeting_id_list = json_assistant.Meeting.get_all_meeting_id()
    m = bot.get_user(657519721138094080)
    member_list = bot.guilds[0].members
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
                if meeting_obj.get_end_time() != "":
                    embed.add_field(name="預計結束時間", value=f"<t:{int(meeting_obj.get_end_time())}>", inline=False)
                embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
                await m.send(embed=embed)
            elif meeting_obj.get_notified() is False and meeting_obj.get_start_time() - time.time() <= 300:
                embed = discord.Embed(title="會議即將開始！",
                                      description=f"會議**「{meeting_obj}」**即將於<t:{int(meeting_obj.get_start_time())}:R>"
                                                  f"開始！",
                                      color=default_color)
                if meeting_obj.get_description() != "":
                    embed.add_field(name="簡介", value=meeting_obj.get_description(), inline=False)
                if meeting_obj.get_end_time() != "":
                    embed.add_field(name="預計結束時間", value=f"<t:{int(meeting_obj.get_end_time())}>", inline=False)
                embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
                # TODO: 將通知傳送對象改為全伺服器成員
                # for m in member_list:
                try:
                    await m.send(embed=embed)
                except discord.Forbidden:
                    pass
                meeting_obj.set_notified(True)


class GetEventInfo(discord.ui.Modal):
    def __init__(self, meeting_id=None) -> None:
        super().__init__(title="會議", timeout=None)
        self.meeting_id = meeting_id
        if meeting_id is not None:
            meeting_obj = json_assistant.Meeting(meeting_id)
            prefill_data = [meeting_obj.get_name(), meeting_obj.get_description(),
                            datetime.datetime.fromtimestamp(meeting_obj.get_start_time(), tz=now_tz).
                            strftime("%Y/%m/%d %H:%M"),
                            datetime.datetime.fromtimestamp(meeting_obj.get_end_time(), tz=now_tz).
                            strftime("%Y/%m/%d %H:%M") if meeting_obj.get_end_time() != "" else "",
                            meeting_obj.get_link()]
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
        self.add_item(
            discord.ui.InputText(style=discord.InputTextStyle.short, label="結束時間(格式：YYYY/MM/DD HH:MM，24小時制)",
                                 placeholder="如：2021/01/10 13:05", min_length=16, max_length=16,
                                 value=prefill_data[3], required=False))
        self.add_item(discord.ui.InputText(style=discord.InputTextStyle.short, label="會議地點",
                                           placeholder="可貼上Meet或Discord頻道連結",
                                           value=prefill_data[4], required=True))

    async def callback(self, interaction: discord.Interaction):
        if self.meeting_id is not None:
            unique_id = self.meeting_id
            embed = discord.Embed(title="編輯會議",
                                  description=f"會議 `{unique_id}` **({self.children[0].value})** 已經編輯成功！！",
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
        meeting_obj.set_link(self.children[4].value)
        embed.add_field(name="會議ID", value=unique_id, inline=False)
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
        if self.children[3].value != "":
            try:
                unix_end_time = time.mktime(time.strptime(self.children[3].value, "%Y/%m/%d %H:%M"))
                if unix_end_time < unix_start_time:
                    embed = discord.Embed(title="錯誤",
                                          description=f"輸入的結束時間(<t:{int(unix_end_time)}>)早於開始時間！請重新輸入。",
                                          color=error_color)
                    await interaction.response.edit_message(embed=embed)
                    return
                else:
                    meeting_obj.set_end_time(unix_end_time)
                    embed.add_field(name="結束時間", value=f"<t:{int(unix_end_time)}>", inline=False)
            except ValueError:
                embed = discord.Embed(title="錯誤",
                                      description=f"輸入的結束時間(`{self.children[3].value}`)格式錯誤！請重新輸入。",
                                      color=error_color)
                await interaction.response.edit_message(embed=embed)
                return
        embed.add_field(name="會議地點", value=self.children[4].value, inline=False)
        embed.set_footer(text="請記下會議ID，以便後續進行編輯或刪除。")
        await interaction.response.edit_message(embed=embed, view=None)


class GetEventInView(discord.ui.View):
    def __init__(self, meeting_id=None):
        super().__init__()
        self.meeting_id = meeting_id

    @discord.ui.button(label="點此開啟會議視窗", style=discord.ButtonStyle.green, emoji="📝")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(GetEventInfo(self.meeting_id))


@bot.event
async def on_ready():
    print("機器人準備完成！")
    print(f"PING值：{round(bot.latency * 1000)}ms")
    print(f"登入身分：{bot.user}")
    await check_meeting.start()


member = bot.create_group(name="member", description="隊員資訊相關指令。")


@bot.slash_command(name="ping", description="查看機器人延遲。")
async def ping(ctx):
    await ctx.respond(f"PONG！延遲：{round(bot.latency * 1000)}ms")


@member.command(name="info", description="查看隊員資訊。")
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


member_info_manage = bot.create_group(name="manage", description="隊員資訊管理。")


@member_info_manage.command(name="set_real_name", description="設定隊員真實姓名。")
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


@member_info_manage.command(name="add_job", description="新增隊員職務。")
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


@member_info_manage.command(name="remove_job", description="移除隊員職務。")
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
    "2點 - 上課/工作時滑手機",
    "2點 - 打遊戲太吵",
    "3點 - 嚴重影響隊伍形象"]


@member_info_manage.command(name="add_warning_points", description="記點。(對，就是記點，我希望我用不到這個指令)")
async def member_add_warning_points(ctx,
                                    隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                    記點事由: Option(str, "記點事由", choices=warning_points_choices, required=True),
                                    # noqa
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
        if current_points >= 5:
            warning_msg = discord.Embed(title="退隊警告！",
                                        description=f"{隊員.mention} 的點數({current_points}點)已達到5點！",
                                        color=error_color)
            warning_msg.set_footer(text="此訊息僅作為提醒，並非正式的退隊通知。實際處置以主幹為準。")
            embed_list.append(warning_msg)
    else:
        embed = discord.Embed(title="記點", description=f"你沒有權限記點！", color=error_color)
        embed_list = [embed]
    await ctx.respond(embeds=embed_list)


remove_warning_points_choices = [
    "半點 - 自主倒垃圾",
    "半點 - 培訓時去外面拿午餐",
    "1點 - 中午時間/第八節 打掃工作室"]


@member_info_manage.command(name="remove_warning_points", description="銷點。")
async def member_remove_warning_points(ctx,
                                       隊員: Option(discord.Member, "隊員", required=True),  # noqa
                                       銷點事由: Option(str, "銷點事由", choices=remove_warning_points_choices,
                                                        required=True),  # noqa
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
        embed.add_field(name="銷點點數", value=str(points), inline=True)
        embed.add_field(name="目前點數(已減去新點數)", value=str(member_data.get_warning_points()), inline=True)
        embed.add_field(name="銷點事由", value=reason, inline=False)
        if 附註 is not None:
            embed.add_field(name="附註事項", value=附註, inline=False)
        embed.set_thumbnail(url=隊員.display_avatar)
    else:
        embed = discord.Embed(title="銷點", description=f"你沒有權限銷點！", color=error_color)
    await ctx.respond(embed=embed)


@member.command(name="warning_history", description="查詢記點紀錄。")
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


@member.command(name="all_warning_history", description="查詢所有記、銷點紀錄。")
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


@meeting.command(name="create", description="預定新的會議。")
async def create_new_meeting(ctx):
    server = ctx.guild
    manager_role = discord.utils.get(server.roles, id=1114205838144454807)
    if manager_role in ctx.author.roles:
        embed = discord.Embed(title="預定會議", description="請點擊下方的按鈕，開啟會議預定視窗。", color=default_color)
        await ctx.respond(embed=embed, view=GetEventInView(), ephemeral=True)
    else:
        embed = discord.Embed(title="銷點", description=f"你沒有權限預定會議！", color=error_color)
        await ctx.respond(embed=embed)


@meeting.command(name="edit", description="編輯會議資訊。")
async def edit_meeting(ctx, 會議id: Option(str, "欲修改的會議ID", min_length=5, max_length=5, required=True)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        server = ctx.guild
        manager_role = discord.utils.get(server.roles, id=1114205838144454807)
        if manager_role in ctx.author.roles:
            embed = discord.Embed(title="編輯會議", description="請點擊下方的按鈕，開啟會議編輯視窗。", color=default_color)
            await ctx.respond(embed=embed, view=GetEventInView(會議id), ephemeral=True)
        else:
            embed = discord.Embed(title="錯誤", description=f"你沒有權限編輯會議！", color=error_color)
            await ctx.respond(embed=embed)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
        await ctx.respond(embed=embed)


@meeting.command(name="delete", description="刪除會議。")
async def delete_meeting(ctx, 會議id: Option(str, "欲刪除的會議ID", min_length=5, max_length=5, required=True),  # noqa
                         原因: Option(str, "取消會議的原因", required=False)):  # noqa
    id_list = json_assistant.Meeting.get_all_meeting_id()
    if 會議id in id_list:
        server = ctx.guild
        manager_role = discord.utils.get(server.roles, id=1114205838144454807)
        if manager_role in ctx.author.roles:
            meeting_obj = json_assistant.Meeting(會議id)
            if meeting_obj.get_started():
                embed = discord.Embed(title="錯誤", description="此會議已經開始，無法刪除！", color=error_color)
            else:
                if meeting_obj.get_notified():
                    # TODO: 將通知傳送對象改為全伺服器成員
                    # for m in member_list:
                    m = bot.get_user(657519721138094080)
                    notify_embed = discord.Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。", color=default_color)
                    notify_embed.add_field(name="會議標題", value=meeting_obj.get_name(), inline=False)
                    if 原因 is not None:
                        notify_embed.add_field(name="取消原因", value=原因, inline=False)
                    try:
                        await m.send(embed=notify_embed)
                    except discord.Forbidden:
                        pass
                    meeting_obj.delete()
                    embed = discord.Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。", color=default_color)
                else:
                    meeting_obj.delete()
                    embed = discord.Embed(title="會議取消", description=f"會議 `{會議id}` 已經取消。", color=default_color)
        else:
            embed = discord.Embed(title="錯誤", description=f"你沒有權限刪除會議！", color=error_color)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


@meeting.command(name="list_ids", description="列出所有的會議ID。")
async def list_meetings(ctx):
    embed = discord.Embed(title="會議ID列表", description="目前已存在的會議ID如下：", color=default_color)
    for i in json_assistant.Meeting.get_all_meeting_id():
        embed.add_field(name=i, value="", inline=True)
    await ctx.respond(embed=embed)


@meeting.command(name="info", description="以會議id查詢會議資訊。")
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
        if meeting_obj.get_end_time() != "":
            embed.add_field(name="預計結束時間", value=f"<t:{int(meeting_obj.get_end_time())}>", inline=False)
        embed.add_field(name="地點", value=meeting_obj.get_link(), inline=False)
    else:
        embed = discord.Embed(title="錯誤", description=f"會議 `{會議id}` 不存在！", color=error_color)
    await ctx.respond(embed=embed)


bot.run(TOKEN)
