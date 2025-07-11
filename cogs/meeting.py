# coding=utf-8
import discord
from discord import Option, Embed, ButtonStyle, InputTextStyle
from discord.ext import commands, tasks
from discord.ui import View, Modal, InputText
import re
import os
import zoneinfo
from pathlib import Path
import logging
import time
import datetime

import json_assistant

error_color = 0xF1411C
default_color = 0x012A5E
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
base_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = str(Path(__file__).parent.parent.absolute())
大會_URL = (  # noqa
    "https://discord.com/channels/1114203090950836284/1114209308910026792"
)
NOTIFY_CHANNEL_ID = 1128232150135738529

MEETING_TASKS: dict[str, dict[str, tasks.Loop | None]] = {}
ONGOING_DISCORD_MEETINGS: dict[int, str] = {}


class Meeting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def notify_meeting(self, meeting_id):
        meeting_obj = json_assistant.Meeting(meeting_id)
        start_time = int(meeting_obj.get_start_time())
        if start_time - time.time() > 1000:
            return
        if not meeting_obj.get_notified():
            embed = Embed(
                title="會議即將開始！",
                description=f"會議**「{meeting_obj}」**(`{meeting_id}`) 即將於 "
                f"<t:{start_time}:R> 開始！",
                color=default_color,
            )
            if meeting_obj.get_description() != "":
                embed.add_field(
                    name="簡介",
                    value=meeting_obj.get_description(),
                    inline=False,
                )
            embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
            ch = self.bot.get_channel(NOTIFY_CHANNEL_ID)
            await ch.send(content="@everyone", embed=embed)
            if meeting_obj.get_absent_requests() is not None:
                for request in meeting_obj.get_absent_requests().get("pending"):
                    embed = Embed(
                        title="請準時參加會議",
                        description="你的假單因 **尚未經過審核**，因此仍需準時出席會議。\n"
                        "如因故無法參加會議，請立即告知主幹。",
                        color=default_color,
                    )
                    embed.add_field(
                        name="開始時間", value=f"<t:{start_time}:R>", inline=False
                    )
                    try:
                        await self.bot.get_user(request["member"]).send(embed=embed)
                    except discord.Forbidden:
                        logging.warning(
                            f"成員 {request['member']} 似乎關閉了陌生人私訊功能，因此無法傳送通知。"
                        )
            meeting_obj.set_notified(True)
        MEETING_TASKS[meeting_id]["notify"].stop()
        del MEETING_TASKS[meeting_id]["notify"]

    async def notify_start_meeting(self, meeting_id):
        meeting_obj = json_assistant.Meeting(meeting_id)
        if meeting_obj.get_start_time() - time.time() > 1000:
            return
        if not meeting_obj.get_started():
            meeting_obj.set_started(True)
            if meeting_obj.get_link().startswith(
                "https://discord.com/channels/1114203090950836284"
            ):
                ONGOING_DISCORD_MEETINGS[int(meeting_obj.get_link().split("/")[-1])] = (
                    meeting_id
                )
            embed = Embed(
                title="會議開始！",
                description=f"會議**「{meeting_obj}」**(`{meeting_id}`) 已經在 "
                f"<t:{int(meeting_obj.get_start_time())}:F> 開始！",
                color=default_color,
            )
            if meeting_obj.get_description() != "":
                embed.add_field(
                    name="簡介",
                    value=meeting_obj.get_description(),
                    inline=False,
                )
            embed.add_field(
                name="主持人",
                value=f"<@{meeting_obj.get_host()}>",
                inline=False,
            )
            embed.add_field(name="會議地點", value=meeting_obj.get_link(), inline=False)
            if meeting_obj.get_absent_requests() is not None:
                absent_members = ""
                for request in meeting_obj.get_absent_requests().get("reviewed"):
                    if request["result"].get("approved", False):
                        member_obj = json_assistant.User(request["member"])
                        absent_members += (
                            f"<@{request['member']}>({member_obj.get_real_name()}) - "
                            f"*{request['reason']}*\n"
                        )
                if absent_members != "":
                    embed.add_field(name="請假人員", value=absent_members, inline=False)
            ch = self.bot.get_channel(NOTIFY_CHANNEL_ID)
            await ch.send(content="@everyone", embed=embed)
            host = self.bot.get_user(meeting_obj.get_host())
            end_embed = Embed(
                title="會議結束了嗎？",
                description="請在會議結束後，按下下方的按鈕。",
                color=default_color,
            )
            try:
                await host.send(
                    embed=end_embed, view=Meeting.EndMeetingView(self.bot, meeting_id)
                )
            except discord.Forbidden:
                pass
            if (
                meeting_obj.get_link().startswith(
                    "https://discord.com/channels/1114203090950836284"
                )
                and meeting_obj.get_attend_records() is not None
            ):
                channel_id = int(meeting_obj.get_link().split("/")[-1])
                channel = self.bot.get_channel(channel_id)
                for member in channel.members:
                    if member.bot:
                        continue
                    meeting_obj.add_attend_record(
                        member.id, "join", int(meeting_obj.get_start_time())
                    )
        MEETING_TASKS[meeting_id]["start"].stop()
        del MEETING_TASKS[meeting_id]["start"]

    async def auto_end_meeting(self, meeting_id):
        meeting_obj = json_assistant.Meeting(meeting_id)
        if (meeting_obj.get_start_time() + 21600) - time.time() > 1000:
            return
        meeting_obj.set_end_time(int(time.time()))
        for channel_id, mid in ONGOING_DISCORD_MEETINGS.items():
            if mid == meeting_id:
                del ONGOING_DISCORD_MEETINGS[channel_id]
                break
        embed = Embed(
            title="會議已自動結束",
            description=f"由於距離會議開始已經過 6 小時尚未結束，因此機器人自動結束了會議**「{meeting_obj.get_name()}」**。",
            color=default_color,
        )
        embed.add_field(
            name="會議 ID 及名稱",
            value=f"`{meeting_id}` ({meeting_obj.get_name()})",
            inline=False,
        )
        embed.add_field(
            name="開始時間", value=f"<t:{meeting_obj.get_start_time()}:F>", inline=False
        )
        meeting_obj.archive()
        ch = self.bot.get_channel(NOTIFY_CHANNEL_ID)
        await ch.send(embed=embed)
        host = self.bot.get_user(meeting_obj.get_host())
        try:
            await host.send(embed=embed)
        except discord.Forbidden:
            pass
        MEETING_TASKS[meeting_id]["end"].stop()
        del MEETING_TASKS[meeting_id]

    def setup_tasks(self, meeting_id) -> float:
        meeting_obj = json_assistant.Meeting(meeting_id)
        if meeting_id in MEETING_TASKS.keys():
            for _, task in MEETING_TASKS[meeting_id].items():
                if task is not None:
                    task.cancel()
        if not meeting_obj.get_start_time() - time.time() >= 300:
            notify_timestamp = time.time() + 5
        else:
            notify_timestamp = meeting_obj.get_start_time() - 300
        notify_time = (
            datetime.datetime.fromtimestamp(notify_timestamp, now_tz)
            .astimezone(None)
            .timetz()
        )
        start_time = (
            datetime.datetime.fromtimestamp(meeting_obj.get_start_time(), now_tz)
            .astimezone(None)
            .timetz()
        )
        auto_end_time = (
            datetime.datetime.fromtimestamp(
                meeting_obj.get_start_time() + 21600, now_tz
            )
            .astimezone(None)
            .timetz()
        )
        MEETING_TASKS[meeting_id] = {
            "notify": tasks.Loop(
                coro=self.notify_meeting,
                seconds=tasks.MISSING,
                minutes=tasks.MISSING,
                hours=tasks.MISSING,
                time=notify_time,
                count=None,
                reconnect=True,
                loop=self.bot.loop,
            ),
            "start": tasks.Loop(
                coro=self.notify_start_meeting,
                seconds=tasks.MISSING,
                minutes=tasks.MISSING,
                hours=tasks.MISSING,
                time=start_time,
                count=None,
                reconnect=True,
                loop=self.bot.loop,
            ),
            "end": tasks.Loop(
                coro=self.auto_end_meeting,
                seconds=tasks.MISSING,
                minutes=tasks.MISSING,
                hours=tasks.MISSING,
                time=auto_end_time,
                count=None,
                reconnect=True,
                loop=self.bot.loop,
            ),
        }
        MEETING_TASKS[meeting_id]["notify"].start(meeting_id)
        MEETING_TASKS[meeting_id]["start"].start(meeting_id)
        MEETING_TASKS[meeting_id]["end"].start(meeting_id)
        return notify_timestamp

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot or ONGOING_DISCORD_MEETINGS == {}:
            return
        if (
            before.channel is None
            or after.channel is None
            or before.channel.id != after.channel.id
        ):
            if (
                after.channel is not None
                and after.channel.id in ONGOING_DISCORD_MEETINGS.keys()
            ):
                meeting_obj = json_assistant.Meeting(
                    ONGOING_DISCORD_MEETINGS[after.channel.id]
                )
                meeting_obj.add_attend_record(member.id, "join", int(time.time()))
            elif (
                before.channel is not None
                and before.channel.id in ONGOING_DISCORD_MEETINGS.keys()
            ):
                meeting_obj = json_assistant.Meeting(
                    ONGOING_DISCORD_MEETINGS[before.channel.id]
                )
                meeting_obj.add_attend_record(member.id, "leave", int(time.time()))

    # @tasks.loop(seconds=5)
    # async def check_meeting(self):
    #     logging.debug("開始檢查會議時間...")
    #     meeting_id_list = json_assistant.Meeting.get_all_meeting_id()
    #     m = self.bot.get_channel(NOTIFY_CHANNEL_ID)
    #     for meeting_id in meeting_id_list:
    #         try:
    #             meeting_obj = json_assistant.Meeting(meeting_id)
    #             if meeting_obj.get_started() is False:
    #                 if time.time() >= meeting_obj.get_start_time():
    #                     logging.info(f"會議 {meeting_id} 已經開始！")
    #                     meeting_obj.set_started(True)
    #                     embed = Embed(
    #                         title="會議開始！",
    #                         description=f"會議**「{meeting_obj}」**已經在"
    #                         f"<t:{int(meeting_obj.get_start_time())}:F>開始！",
    #                         color=default_color,
    #                     )
    #                     if meeting_obj.get_description() != "":
    #                         embed.add_field(
    #                             name="簡介",
    #                             value=meeting_obj.get_description(),
    #                             inline=False,
    #                         )
    #                     embed.add_field(
    #                         name="主持人",
    #                         value=f"<@{meeting_obj.get_host()}> "
    #                         f"({self.bot.get_user(meeting_obj.get_host())})",
    #                         inline=False,
    #                     )
    #                     embed.add_field(
    #                         name="會議地點", value=meeting_obj.get_link(), inline=False
    #                     )
    #                     if meeting_obj.get_absent_requests() is not None:
    #                         absent_members = ""
    #                         for request in meeting_obj.get_absent_requests().get(
    #                             "reviewed"
    #                         ):
    #                             if request["result"].get("approved", False):
    #                                 member_obj = json_assistant.User(request["member"])
    #                                 absent_members += (
    #                                     f"<@{request['member']}>({member_obj.get_real_name()}) - "
    #                                     f"*{request['reason']}*\n"
    #                                 )
    #                         embed.add_field(
    #                             name="請假人員", value=absent_members, inline=False
    #                         )
    #                     await m.send(content="@everyone", embed=embed)
    #                     logging.info(f"已傳送會議 {meeting_id} 的開始通知。")
    #                 elif (
    #                     meeting_obj.get_notified() is False
    #                     and meeting_obj.get_start_time() - time.time() <= 300
    #                 ):
    #                     logging.info(f"會議 {meeting_id} 即將開始(傳送通知)！")
    #                     embed = Embed(
    #                         title="會議即將開始！",
    #                         description=f"會議**「{meeting_obj}」**即將於"
    #                         f"<t:{int(meeting_obj.get_start_time())}:R>開始！",
    #                         color=default_color,
    #                     )
    #                     if meeting_obj.get_description() != "":
    #                         embed.add_field(
    #                             name="簡介",
    #                             value=meeting_obj.get_description(),
    #                             inline=False,
    #                         )
    #                     embed.add_field(
    #                         name="會議地點", value=meeting_obj.get_link(), inline=False
    #                     )
    #                     await m.send(content="@everyone", embed=embed)
    #                     meeting_obj.set_notified(True)
    #                     logging.info(f"已傳送會議 {meeting_id} 的開始通知。")
    #             elif (
    #                 meeting_obj.get_started()
    #                 and time.time() - meeting_obj.get_start_time() >= 172800
    #             ):
    #                 meeting_obj.archive()
    #                 logging.info(
    #                     f"會議 {meeting_id} 距離開始時間已超過2天，已將其封存。"
    #                 )
    #         except TypeError as e:
    #             logging.warning(
    #                 f"檢查會議 {meeting_id} 時發生錯誤，跳過此會議。({e})"
    #             )

    class MeetingEditor(Modal):
        def __init__(self, outer_instance, meeting_id=None) -> None:
            super().__init__(title="會議", timeout=None)
            self.meeting_id = meeting_id
            self.outer_instance = outer_instance

            if meeting_id is not None:
                meeting_obj = json_assistant.Meeting(meeting_id)
                prefill_data = [
                    meeting_obj.get_name(),
                    "1" if meeting_obj.get_absent_requests() is None else "",
                    datetime.datetime.fromtimestamp(
                        meeting_obj.get_start_time(), tz=now_tz
                    ).strftime("%Y/%m/%d %H:%M"),
                    meeting_obj.get_link(),
                    meeting_obj.get_meeting_record_link(),
                ]
            else:
                prefill_data = ["", "", "", 大會_URL, ""]

            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="會議標題",
                    value=prefill_data[0],
                    required=True,
                )
            )
            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="強制參加(停用請假)？",
                    placeholder="輸入任何字元，即可停用此會議的請假功能",
                    max_length=1,
                    value=prefill_data[1],
                    required=False,
                )
            )
            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="開始時間(格式：YYYY/MM/DD HH:MM，24小時制)",
                    placeholder="如：2021/01/10 12:05",
                    min_length=16,
                    max_length=16,
                    value=prefill_data[2],
                    required=True,
                )
            )
            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="會議地點(預設為Discord - 大會)",
                    placeholder="可貼上Meet或Discord頻道連結",
                    value=prefill_data[3],
                    required=True,
                )
            )
            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="會議記錄連結",
                    placeholder="貼上Google文件連結",
                    value=prefill_data[4],
                    required=False,
                )
            )

        async def callback(self, interaction: discord.Interaction):
            is_edit = False
            if self.meeting_id is not None:
                unique_id = self.meeting_id
                embed = Embed(
                    title="編輯會議",
                    description=f"會議 `{unique_id}` **({self.children[0].value})** 已經編輯成功！",
                    color=default_color,
                )
                is_edit = True
            else:
                unique_id = json_assistant.Meeting.create_new_meeting()
                embed = Embed(
                    title="預定新會議",
                    description=f"你預定的會議：**{self.children[0].value}**，已經預定成功！",
                    color=default_color,
                )
            meeting_obj = json_assistant.Meeting(unique_id)
            meeting_obj.set_name(self.children[0].value)
            meeting_obj.disable_absent(True if self.children[1].value != "" else False)
            meeting_obj.set_host(interaction.user.id)
            meeting_obj.set_link(self.children[3].value)
            if not self.children[3].value.startswith(
                "https://discord.com/channels/1114203090950836284/"
            ):
                meeting_obj.toggle_attend_records(False)
            meeting_obj.set_meeting_record_link(self.children[4].value)
            meeting_obj.set_notified(False)
            logging.info(f"已預定/編輯會議 {unique_id}。")
            embed.add_field(name="會議ID", value=f"`{unique_id}`", inline=False)
            if self.children[1].value != "":
                embed.add_field(
                    name="強制參加", value="已停用此會議的請假功能。", inline=False
                )
            else:
                embed.add_field(
                    name="可請假", value="成員可透過指令或按鈕請假。", inline=False
                )
            embed.add_field(name="主持人", value=interaction.user.mention, inline=False)
            try:
                unix_start_time = int(
                    datetime.datetime.timestamp(
                        datetime.datetime.strptime(
                            self.children[2].value, "%Y/%m/%d %H:%M"
                        ).replace(tzinfo=now_tz)
                    )
                )
                if unix_start_time < time.time():
                    embed = Embed(
                        title="錯誤",
                        description=f"輸入的開始時間(<t:{unix_start_time}:F>)已經過去！請重新輸入。",
                        color=error_color,
                    )
                    await interaction.response.edit_message(embed=embed)
                    meeting_obj.delete()
                    return
                else:
                    meeting_obj.set_start_time(unix_start_time)
                    embed.add_field(
                        name="開始時間",
                        value=f"<t:{unix_start_time}:F>",
                        inline=False,
                    )
            except ValueError:
                embed = Embed(
                    title="錯誤",
                    description=f"輸入的開始時間(`{self.children[2].value}`)格式錯誤！請重新輸入。",
                    color=error_color,
                )
                await interaction.response.edit_message(embed=embed)
                meeting_obj.delete()
                return
            embed.add_field(name="會議地點", value=self.children[3].value, inline=False)
            if self.children[4].value != "":
                embed.add_field(
                    name="會議記錄連結", value=self.children[4].value, inline=False
                )
            embed.set_footer(text="請記下會議 ID，以便後續進行編輯或刪除。")
            await interaction.response.edit_message(embed=embed, view=None)
            m = self.outer_instance.bot.get_channel(NOTIFY_CHANNEL_ID)
            if is_edit:
                embed.title = "會議資訊更新"
                embed.description = f"會議 `{unique_id}` **({self.children[0].value})** 的資訊已更新。**請以最新通知訊息為主！**"
            else:
                embed.title = "新會議"
                embed.description = (
                    f"會議 `{unique_id}` **({self.children[0].value})** 已經預定成功！"
                )
            if self.children[1].value != "":
                embed.set_footer(text="若因故不能參加會議，請向主幹告知事由。")
            else:
                embed.set_footer(text="如要請假，最晚請在會議開始前 10 分鐘處理完畢。")
            await m.send(
                embed=embed,
                view=(
                    self.outer_instance.AbsentInView(self.outer_instance, unique_id)
                    if self.children[1].value == ""
                    else None
                ),
            )
            logging.info(f"已傳送預定/編輯會議 {unique_id} 的通知。")
            self.outer_instance.setup_tasks(unique_id)

    class GetEventInfoInView(View):
        def __init__(self, outer_instance, meeting_id=None):
            super().__init__(timeout=None)
            self.meeting_id = meeting_id
            self.outer_instance = outer_instance

        @discord.ui.button(
            label="點此開啟會議視窗", style=ButtonStyle.green, emoji="📝"
        )
        async def button_callback(
            self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.response.send_modal(
                Meeting.MeetingEditor(self.outer_instance, self.meeting_id)
            )

    class Absent(Modal):
        def __init__(self, outer_instance, meeting_id: str) -> None:
            super().__init__(title="請假", timeout=None)
            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="請假理由",
                    placeholder="請輸入合理的請假理由，而不是「有事」",
                    required=True,
                )
            )

            self.outer_instance = outer_instance
            self.meeting_id = meeting_id

        async def callback(self, interaction: discord.Interaction) -> None:
            await self.outer_instance.absence_meeting(
                interaction, self.meeting_id, self.children[0].value
            )

    class AbsentInView(View):
        def __init__(self, outer_instance, meeting_id: str):
            self.meeting_id = meeting_id  # init meeting_id for "get_button_life()"

            super().__init__(timeout=self.get_button_life())

            self.outer_instance = outer_instance

        def get_button_life(self) -> float | None:
            meeting_obj = json_assistant.Meeting(self.meeting_id)
            absent_deadline = meeting_obj.get_start_time() - 60 * 10
            button_life = absent_deadline - time.time()
            return button_life if button_life > 0 else 0

        @discord.ui.button(label="點此開啟請假視窗", style=ButtonStyle.red, emoji="🙋")
        async def button_callback(
            self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            meeting_obj = json_assistant.Meeting(self.meeting_id)
            absent_deadline = meeting_obj.get_start_time() - 60 * 10
            if time.time() > absent_deadline:
                embed = Embed(
                    title="錯誤：自動請假期限已到",
                    description="請假需在會議 10 分鐘前處理完畢。\n"
                    f"此會議即將在 <t:{int(meeting_obj.get_start_time())}:R> 開始！",
                    color=error_color,
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_modal(
                    Meeting.Absent(self.outer_instance, self.meeting_id)
                )
            self.timeout = self.get_button_life()

    class ReviewAbsentRequest(Modal):
        def __init__(
            self, bot, meeting_id: str, member_id: int, approved: bool, reason: str
        ) -> None:
            super().__init__(title="接受" if approved else "拒絕" + "假單原因")
            self.add_item(
                InputText(
                    style=InputTextStyle.short,
                    label="要回傳給該成員的回覆",
                    placeholder="非必填，可留空",
                    required=False,
                )
            )

            self.bot = bot
            self.meeting_id = meeting_id
            self.member_id = member_id
            self.approved = approved
            self.reason = reason

        async def callback(self, interaction: discord.Interaction) -> None:
            await interaction.response.defer()
            operation = "接受" if self.approved else "拒絕"
            response = self.children[0].value
            meeting_obj = json_assistant.Meeting(self.meeting_id)
            meeting_obj.review_absent_request(
                self.member_id,
                time.time(),
                interaction.user.id,
                self.approved,
                response,
            )
            request_member = self.bot.get_user(self.member_id)
            embed = Embed(
                title=f"已{operation}假單",
                description=f"{interaction.user.mention} 已**「{operation}」**了 {request_member.mention} 的假單。",
                color=default_color,
            )
            embed.add_field(
                name="會議 ID 及名稱",
                value=f"`{self.meeting_id}` ({meeting_obj.get_name()})",
                inline=False,
            )
            embed.add_field(name="請假原因", value=self.reason, inline=False)
            if response != "":
                embed.add_field(name=f"{operation}原因", value=response, inline=False)
            await interaction.edit_original_response(embed=embed, view=None)
            if self.approved:
                response_embed = Embed(
                    title="假單已通過審核",
                    description=f"{interaction.user.mention} 已**「{operation}」**了你的會議假單。",
                    color=default_color,
                )
            else:
                response_embed = Embed(
                    title="假單未通過審核",
                    description=(
                        f"{interaction.user.mention} 已**「{operation}」**了你的會議假單。\n"
                        "⚠️**注意：會議開始後，你仍須參加會議！**"
                    ),
                    color=default_color,
                )
            response_embed.add_field(
                name="會議 ID 及名稱",
                value=f"`{self.meeting_id}` ({meeting_obj.get_name()})",
                inline=False,
            )
            response_embed.add_field(name="請假原因", value=self.reason, inline=False)
            if response != "":
                response_embed.add_field(
                    name=f"{operation}原因", value=response, inline=False
                )
            await request_member.send(embed=response_embed)

    class ReviewAbsentRequestInView(View):
        def __init__(self, bot, meeting_id: str, member_id: int, reason: str) -> None:
            super().__init__(timeout=None)

            self.bot = bot
            self.meeting_id = meeting_id
            self.member_id = member_id
            self.reason = reason

        @discord.ui.button(label="接受", style=ButtonStyle.green, emoji="✅")
        async def approve(
            self, button: discord.ui.Button, interaction: discord.Interaction
        ) -> None:
            await interaction.response.send_modal(
                Meeting.ReviewAbsentRequest(
                    self.bot, self.meeting_id, self.member_id, True, self.reason
                )
            )

        @discord.ui.button(label="拒絕", style=ButtonStyle.red, emoji="🔙")
        async def decline(
            self, button: discord.ui.Button, interaction: discord.Interaction
        ) -> None:
            await interaction.response.send_modal(
                Meeting.ReviewAbsentRequest(
                    self.bot, self.meeting_id, self.member_id, False, self.reason
                )
            )

    class EndMeetingView(View):
        def __init__(self, bot: commands.Bot, meeting_id: str):
            super().__init__(timeout=None)

            self.bot = bot
            self.meeting_id = meeting_id

        @discord.ui.button(label="結束會議", style=ButtonStyle.green, emoji="🔚")
        async def end_meeting(
            self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.response.defer()
            meeting_obj = json_assistant.Meeting(self.meeting_id)
            meeting_obj.set_end_time(int(time.time()))
            for channel_id, mid in ONGOING_DISCORD_MEETINGS.items():
                if mid == self.meeting_id:
                    del ONGOING_DISCORD_MEETINGS[channel_id]
                    break
            embed = Embed(
                title="會議已結束",
                description=f"{interaction.user.mention} 已結束了會議**「{meeting_obj.get_name()}」**。",
                color=default_color,
            )
            embed.add_field(
                name="會議 ID 及名稱",
                value=f"`{self.meeting_id}` ({meeting_obj.get_name()})",
                inline=False,
            )
            embed.add_field(
                name="結束時間", value=f"<t:{int(time.time())}:F>", inline=False
            )
            meeting_obj.archive()  # 在訊息建構完後再封存，避免資料遺失
            await interaction.edit_original_response(embed=embed, view=None)
            ch = self.bot.get_channel(NOTIFY_CHANNEL_ID)
            await ch.send(embed=embed)
            if MEETING_TASKS.get(self.meeting_id, {}).get("end", None):
                MEETING_TASKS.get(self.meeting_id, {}).get("end", None).cancel()
                del MEETING_TASKS[self.meeting_id]

    MEETING_CMDS = discord.SlashCommandGroup(
        name="meeting", description="會議相關指令。"
    )

    @MEETING_CMDS.command(name="建立", description="預定新的會議。")
    @commands.has_role(1114205838144454807)
    async def create_new_meeting(self, ctx):
        embed = Embed(
            title="預定會議",
            description="請點擊下方的按鈕，開啟會議預定視窗。",
            color=default_color,
        )
        await ctx.respond(
            embed=embed, view=self.GetEventInfoInView(self), ephemeral=True
        )

    @MEETING_CMDS.command(name="編輯", description="編輯會議資訊。")
    @commands.has_role(1114205838144454807)
    async def edit_meeting(
        self,
        ctx,
        meeting_id: Option(
            str,
            "欲編輯的會議ID",
            name="會議id",
            min_length=5,
            max_length=5,
            required=True,
        ),
    ):
        id_list = json_assistant.Meeting.get_all_meeting_id()
        if meeting_id in id_list:
            embed = Embed(
                title="編輯會議",
                description="請點擊下方的按鈕，開啟會議編輯視窗。",
                color=default_color,
            )
            await ctx.respond(
                embed=embed,
                view=self.GetEventInfoInView(self, meeting_id),
                ephemeral=True,
            )
        else:
            embed = Embed(
                title="錯誤",
                description=f"會議 `{meeting_id}` 不存在！",
                color=error_color,
            )
            await ctx.respond(embed=embed)

    @MEETING_CMDS.command(name="結束", description="手動結束會議。")
    @commands.has_role(1114205838144454807)
    async def end_meeting(
        self,
        ctx: discord.ApplicationContext,
        meeting_id: Option(
            str,
            "欲結束的會議 ID",
            name="會議id",
            min_length=5,
            max_length=5,
            required=True,
        ),
    ):
        id_list = json_assistant.Meeting.get_all_meeting_id()
        btn_obj = None
        if meeting_id in id_list:
            meeting_obj = json_assistant.Meeting(meeting_id)
            if meeting_obj.get_started():
                embed = Embed(
                    title="會議結束了嗎？",
                    description="請在會議結束後，按下下方的按鈕。",
                    color=default_color,
                )
                btn_obj = self.EndMeetingView(self.bot, meeting_id)
            else:
                embed = Embed(
                    title="錯誤：會議尚未開始",
                    description=f"會議 `{meeting_id}` 尚未開始，因此無法結束。",
                    color=error_color,
                )
        else:
            embed = Embed(
                title="錯誤",
                description=f"會議 `{meeting_id}` 不存在！",
                color=error_color,
            )
        await ctx.respond(embed=embed, view=btn_obj, ephemeral=True)

    @MEETING_CMDS.command(name="刪除", description="刪除會議。")
    @commands.has_role(1114205838144454807)
    async def delete_meeting(
        self,
        ctx,
        meeting_id: Option(
            str,
            "欲刪除的會議 ID",
            name="會議id",
            min_length=5,
            max_length=5,
            required=True,
        ),
        reason: Option(str, "取消會議的原因", name="原因", required=True),
    ):
        id_list = json_assistant.Meeting.get_all_meeting_id()
        if meeting_id in id_list:
            meeting_obj = json_assistant.Meeting(meeting_id)
            if meeting_obj.get_started():
                embed = Embed(
                    title="錯誤",
                    description="此會議已經開始，無法刪除！",
                    color=error_color,
                )
            else:
                m = self.bot.get_channel(NOTIFY_CHANNEL_ID)
                notify_embed = Embed(
                    title="會議取消",
                    description=f"會議 `{meeting_id}` 已經取消。",
                    color=default_color,
                )
                notify_embed.add_field(
                    name="會議標題", value=meeting_obj.get_name(), inline=False
                )
                notify_embed.add_field(name="取消原因", value=reason, inline=False)
                if meeting_obj.get_notified():
                    await m.send(content="@everyone", embed=notify_embed)
                else:
                    await m.send(embed=notify_embed)
                meeting_obj.delete()
                if meeting_id in MEETING_TASKS.keys():
                    for _, task in MEETING_TASKS[meeting_id].items():
                        if task is not None:
                            task.cancel()
                    del MEETING_TASKS[meeting_id]
                embed = Embed(
                    title="會議取消",
                    description=f"會議 `{meeting_id}` 已經取消。",
                    color=default_color,
                )
        else:
            embed = Embed(
                title="錯誤",
                description=f"會議 `{meeting_id}` 不存在！",
                color=error_color,
            )
        await ctx.respond(embed=embed)

    @MEETING_CMDS.command(name="所有id", description="列出所有的會議ID。")
    async def list_meetings(self, ctx):
        embed = Embed(
            title="會議 ID 列表",
            description="目前已存在的會議 ID 如下：",
            color=default_color,
        )
        for i in json_assistant.Meeting.get_all_meeting_id():
            embed.add_field(name=i, value="", inline=True)
        await ctx.respond(embed=embed)

    @MEETING_CMDS.command(name="請假", description="登記請假。")
    async def absence_meeting(
        self,
        ctx: discord.ApplicationContext,
        meeting_id: Option(
            str,
            "要請假的會議 ID",
            name="會議id",
            min_length=5,
            max_length=5,
            required=True,
        ),
        reason: Option(str, "請假的原因", name="原因", required=True),
    ):
        if isinstance(ctx, discord.ApplicationContext):
            await ctx.defer()
        else:
            await ctx.response.defer()
        id_list = json_assistant.Meeting.get_all_meeting_id()
        if meeting_id in id_list:
            meeting_obj = json_assistant.Meeting(meeting_id)
            if meeting_obj.get_started():
                embed = Embed(
                    title="錯誤：會議已開始",
                    description="此會議已經開始，無法請假！",
                    color=error_color,
                )
            elif meeting_obj.get_start_time() - time.time() < 600:
                embed = Embed(
                    title="錯誤：自動請假期限已到",
                    description="請假需在會議 10 分鐘前處理完畢。\n"
                    f"此會議即將在 <t:{int(meeting_obj.get_start_time())}:R> 開始！",
                    color=error_color,
                )
            else:
                absent_status = meeting_obj.get_absent_requests()
                if absent_status is None:
                    embed = Embed(
                        title="錯誤：強制參加",
                        description="此會議已被設置為「強制參加」，因此無法透過此系統請假。\n"
                        "若因故不能參加會議，請向主幹告知事由。",
                        color=error_color,
                    )
                else:
                    absent_members_id = [
                        i["member"]
                        for i in absent_status["pending"] + absent_status["reviewed"]
                    ]
                    author_id = ctx.user.id
                    author_mention = ctx.user.mention
                    if author_id in absent_members_id:
                        embed = Embed(
                            title="錯誤",
                            description="你已經請過假了！",
                            color=error_color,
                        )
                    else:
                        meeting_obj.add_absent_request(author_id, time.time(), reason)
                        absent_record_channel = self.bot.get_channel(
                            1126031617614426142
                        )
                        user = json_assistant.User(author_id)
                        absent_record_embed = Embed(
                            title="假單",
                            description=f"{author_mention}({user.get_real_name()}) 提交了會議的假單。",
                            color=default_color,
                        )
                        absent_record_embed.add_field(
                            name="會議 ID 及名稱",
                            value=f"`{meeting_id}` ({meeting_obj.get_name()})",
                            inline=False,
                        )
                        absent_record_embed.add_field(
                            name="請假原因", value=reason, inline=False
                        )
                        await absent_record_channel.send(
                            embed=absent_record_embed,
                            view=self.ReviewAbsentRequestInView(
                                self.bot, meeting_id, ctx.user.id, reason
                            ),
                        )
                        embed = Embed(
                            title="已送出假單",
                            description="你的假單已送出，請等候主幹的審核。\n"
                            "⚠️**注意：會議開始後，若你的假單未通過審核，即等於沒有請假，仍須參加會議！**",
                            color=default_color,
                        )
                        embed.add_field(
                            name="會議 ID 及名稱",
                            value=f"`{meeting_id}` ({meeting_obj.get_name()})",
                            inline=False,
                        )
                        embed.add_field(name="請假原因", value=reason, inline=False)
        else:
            embed = Embed(
                title="錯誤",
                description=f"會議 `{meeting_id}` 不存在！",
                color=error_color,
            )
        if isinstance(ctx, discord.ApplicationContext):
            await ctx.respond(embed=embed)
        else:
            await ctx.followup.send(embed=embed, ephemeral=True)

    @MEETING_CMDS.command(name="設定會議記錄", description="設定會議記錄連結。")
    @commands.has_role(1114205838144454807)
    async def set_meeting_record_link(
        self,
        ctx,
        meeting_id: Option(
            str, "欲設定的會議ID", min_length=5, max_length=5, required=True
        ),
        link: Option(str, "會議記錄連結", name="會議記錄連結", required=True),
    ):
        id_list = json_assistant.Meeting.get_all_meeting_id()
        if meeting_id in id_list:
            meeting_obj = json_assistant.Meeting(meeting_id)
            regex = re.compile(
                r"^(?:http|ftp)s?://"  # http:// or https://
                r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
                r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
                r"(?::\d+)?"  # optional port
                r"(?:/?|[/?]\S+)$",
                re.IGNORECASE,
            )
            if not re.match(regex, link):
                embed = Embed(
                    title="錯誤",
                    description=f"你輸入的連結({link})格式不正確！",
                    color=error_color,
                )
            else:
                meeting_obj.set_meeting_record_link(link)
                embed = Embed(
                    title="設定會議記錄連結",
                    description=f"已將會議 `{meeting_id}` 的會議記錄連結設定為 `{link}`。",
                    color=default_color,
                )
                if (
                    meeting_obj.get_absent_requests() is not None
                    and len(meeting_obj.get_absent_requests().get("reviewed", [])) > 0
                ):
                    notify_channel = self.bot.get_channel(NOTIFY_CHANNEL_ID)
                    absent_members_str = ""
                    for request in meeting_obj.get_absent_requests().get(
                        "reviewed", []
                    ):
                        if request["result"].get("approved", False):
                            absent_members_str += f"<@{request['member']}> "
                    notify_embed = Embed(
                        title="會議記錄連結",
                        description=f"會議 `{meeting_id}` 的會議記錄連結已經設定。\n"
                        "缺席的成員，請務必閱讀會議紀錄！",
                        color=default_color,
                    )
                    notify_embed.add_field(
                        name="會議名稱", value=meeting_obj.get_name(), inline=False
                    )
                    notify_embed.add_field(
                        name="會議記錄連結", value=link, inline=False
                    )
                    await notify_channel.send(
                        content=absent_members_str, embed=notify_embed
                    )
        else:
            embed = Embed(
                title="錯誤",
                description=f"會議 `{meeting_id}` 不存在！",
                color=error_color,
            )
        await ctx.respond(embed=embed)

    @MEETING_CMDS.command(name="查詢", description="以會議id查詢會議資訊。")
    async def get_meeting_info(
        self,
        ctx,
        meeting_id: Option(
            str,
            "欲查詢的會議ID",
            name="會議id",
            min_length=5,
            max_length=5,
            required=True,
        ),
    ):
        id_list = json_assistant.Meeting.get_all_meeting_id()
        if meeting_id in id_list:
            meeting_obj = json_assistant.Meeting(meeting_id)
            embed = Embed(
                title="會議資訊",
                description=f"會議 `{meeting_id}` 的詳細資訊",
                color=default_color,
            )
            embed.add_field(name="會議名稱", value=meeting_obj.get_name(), inline=False)
            if meeting_obj.get_description() != "":
                embed.add_field(
                    name="簡介", value=meeting_obj.get_description(), inline=False
                )
            embed.add_field(
                name="主持人", value=f"<@{meeting_obj.get_host()}>", inline=False
            )
            embed.add_field(
                name="開始時間",
                value=f"<t:{int(meeting_obj.get_start_time())}:F>",
                inline=False,
            )
            embed.add_field(name="地點", value=meeting_obj.get_link(), inline=False)
            if meeting_obj.get_meeting_record_link() != "":
                embed.add_field(
                    name="會議記錄",
                    value=meeting_obj.get_meeting_record_link(),
                    inline=False,
                )
            if meeting_obj.get_absent_requests() is not None:
                absent_members_str = ""
                for request in meeting_obj.get_absent_requests().get("reviewed"):
                    if request["result"].get("approved", False):
                        member_obj = json_assistant.User(request["member"])
                        absent_members_str += (
                            f"<@{request['member']}>({member_obj.get_real_name()}) - "
                            f"*{request['reason']}*\n"
                        )
                embed.add_field(name="請假人員", value=absent_members_str, inline=False)
        else:
            embed = Embed(
                title="錯誤",
                description=f"會議 `{meeting_id}` 不存在！",
                color=error_color,
            )
        await ctx.respond(embed=embed)

    @staticmethod
    def member_list_to_id_list(member_list: list[discord.Member]) -> list[int]:
        return [m.id for m in member_list]

    @MEETING_CMDS.command(
        name="自動記點", description="自動為尚未出席目前會議的「高一、高二」成員記點。"
    )
    @commands.has_role(1114205838144454807)
    async def auto_add_warning_points(
        self,
        ctx: discord.ApplicationContext,
        voice_channel: Option(
            discord.VoiceChannel,
            "會議所在的語音頻道",
            name="語音頻道",
            required=False,
        ) = None,
    ):
        await ctx.defer()
        content = ""
        voice_channel: discord.VoiceChannel | None
        if len(ONGOING_DISCORD_MEETINGS) == 0:
            embed = Embed(
                title="錯誤：未有會議進行中",
                description="目前沒有正在 Discord 進行的會議。",
                color=error_color,
            )
        elif len(ONGOING_DISCORD_MEETINGS) > 1 and voice_channel is None:
            embed = Embed(
                title="錯誤：多個會議進行中",
                description="目前有多個正在 Discord 進行的會議。請使用 `語音頻道` 參數指定會議所在的語音頻道。\n"
                "下方列出正在進行的會議：",
                color=error_color,
            )
            for channel_id, mid2 in ONGOING_DISCORD_MEETINGS.items():
                embed.add_field(name=mid2, value=f"<@{channel_id}>", inline=False)
        elif voice_channel.id not in ONGOING_DISCORD_MEETINGS.keys():
            embed = Embed(
                title="錯誤：語音頻道無效",
                description=f"你提供的語音頻道 {voice_channel.mention} 並未在進行會議。",
                color=error_color,
            )
        else:
            if voice_channel is None:
                voice_channel = self.bot.get_channel(ONGOING_DISCORD_MEETINGS.keys()[0])
            meeting_obj = json_assistant.Meeting(
                ONGOING_DISCORD_MEETINGS[voice_channel.id]
            )
            if time.time() - meeting_obj.get_start_time() < 300:
                embed = Embed(
                    title="錯誤：緩衝時間尚未結束",
                    description=f"會議 `{meeting_obj.event_id}` 開始未滿 5 分鐘，依據隊規仍在緩衝時間內，不應記點。\n"
                    f"請在 <t:{meeting_obj.get_start_time() + 300}:T> 後再使用此指令。",
                    color=error_color,
                )
            else:
                team_members = set(
                    self.member_list_to_id_list(
                        self.bot.get_guild(1114203090950836284)
                        .get_role(1114212978707923167)  # 高一
                        .members
                        + self.bot.get_guild(1114203090950836284)
                        .get_role(1114212714634559518)  # 高二
                        .members
                    )
                )
                attendants = self.member_list_to_id_list(voice_channel.members)
                absent_members = []
                if meeting_obj.get_absent_requests() is not None:
                    for request in meeting_obj.get_absent_requests().get(
                        "reviewed", []
                    ):
                        if request["result"].get("approved", False):
                            absent_members.append(request["member"])
                good_members = set(attendants + absent_members)
                missing_members = set()
                for m in team_members:
                    if m not in good_members:
                        missing_members.add(f"<@{m}>")
                        json_assistant.User(m).add_warning_points(
                            0.5,
                            "開會/培訓 無故遲到(5分鐘)",
                            f"由 {ctx.user.mention} 透過自動記點執行",
                        )
                embed = Embed(
                    title="記點完成",
                    description=(
                        f"已為 {len(missing_members)} 位成員記上半點。"
                        if len(missing_members) > 0
                        else "沒有任何成員需被記點。"
                    ),
                    color=default_color,
                )
                embed.add_field(
                    name="會議 ID 及名稱",
                    value=f"`{meeting_obj.event_id}` ({meeting_obj.get_name()})",
                    inline=False,
                )
                content = (
                    " ".join(missing_members)
                    + "\n由於**「開會/培訓 無故遲到(5分鐘)」**，依照隊規記上 `0.5` 點。"
                )
        await ctx.respond(content=content, embed=embed)

    @MEETING_CMDS.command(
        name="重新載入提醒", description="重新讀取所有會議，並設定未開始會議的提醒。"
    )
    @commands.is_owner()
    async def reload_meetings(self, ctx: discord.ApplicationContext):
        global MEETING_TASKS
        for meeting_id in MEETING_TASKS.keys():
            for _, task in MEETING_TASKS[meeting_id].items():
                if task is not None:
                    task.cancel()
        MEETING_TASKS = {}
        id_list = json_assistant.Meeting.get_all_meeting_id()
        done_list = []
        for mid in id_list:
            meeting_obj = json_assistant.Meeting(mid)
            if not meeting_obj.get_started():
                notify_time = int(self.setup_tasks(mid))
                done_list.append((mid, notify_time))
        embed = Embed(
            title="已重新載入會議提醒",
            description="下列會議尚未開始，已為其設定提醒：",
            color=default_color,
        )
        for mid, notify_time in done_list:
            embed.add_field(
                name=mid,
                value=f"將於 <t:{notify_time}:F> (<t:{notify_time}:R>) 提醒",
                inline=False,
            )
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Meeting(bot))
    logging.info(f'已載入 "{Meeting.__name__}"。')
