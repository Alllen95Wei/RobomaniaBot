# coding=utf-8
import discord
from discord import Embed, Option, ui, InputTextStyle, Interaction
from discord.ext import commands
from discord.ext import tasks
import time
import datetime
import zoneinfo
import os
from pathlib import Path

import logger
import json_assistant

error_color = 0xF1411C
default_color = 0x012a5e
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
base_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = str(Path(__file__).parent.parent.absolute())


class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot, real_logger: logger.CreateLogger):
        self.bot = bot
        self.real_logger = real_logger

    class ReminderEditor(ui.Modal):
        def __init__(self, reminder_id=None):
            super().__init__(title="提醒事項編輯器")
            self.reminder_id = reminder_id
            if reminder_id is None:
                prefill_data = ["", "", "", "0"]
            else:
                reminder_obj = json_assistant.Reminder(reminder_id)
                prefill_data = [reminder_obj.get_title(),
                                reminder_obj.get_description(),
                                datetime.datetime.fromtimestamp(reminder_obj.get_time(), tz=now_tz).
                                strftime("%Y/%m/%d %H:%M"),
                                reminder_obj.get_progress()]
            self.add_item(ui.InputText(style=InputTextStyle.short, label="名稱", value=prefill_data[0], required=True))
            self.add_item(ui.InputText(style=InputTextStyle.long, label="說明", value=prefill_data[1], required=False))
            self.add_item(ui.InputText(style=InputTextStyle.short, label="預定結束時間 (格式：YYYY/MM/DD HH:MM，24小時制)",
                                       placeholder="YYYY/MM/DD HH:MM", value=prefill_data[2],
                                       min_length=16, max_length=16, required=True))
            self.add_item(ui.InputText(style=InputTextStyle.short, label="目前進度 (百分比)", placeholder="0",
                                       value=prefill_data[3], required=True))

        async def callback(self, interaction: Interaction):
            unique_id = self.reminder_id
            if unique_id is not None:
                embed = Embed(title="編輯提醒事項",
                              description=f"提醒事項 `{unique_id}` **({self.children[0].value})** 已經編輯成功！",
                              color=default_color)
            else:
                unique_id = json_assistant.Reminder.create_new_reminder()
                embed = Embed(title="建立新提醒事項",
                              description=f"你預定的提醒事項：**{self.children[0].value}**，已經建立完成！",
                              color=default_color)
            reminder_obj = json_assistant.Reminder(unique_id)
            reminder_obj.set_title(self.children[0].value)
            reminder_obj.set_description(self.children[1].value)
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
                    reminder_obj.set_time(unix_start_time)
                    embed.add_field(name="開始時間", value=f"<t:{int(unix_start_time)}:F>", inline=False)
            except ValueError:
                embed = Embed(title="錯誤",
                              description=f"輸入的開始時間(`{self.children[2].value}`)格式錯誤！請重新輸入。",
                              color=error_color)
                await interaction.response.edit_message(embed=embed)
                return
            if not self.children[3].value.isdigit():
                embed = Embed(title="錯誤",
                              description=f"輸入的目前進度(`{self.children[3].value}`)應為整數！請重新輸入。",
                              color=error_color)
                await interaction.response.edit_message(embed=embed)
                return
            elif not (0 <= int(self.children[3].value) <= 100):
                embed = Embed(title="錯誤",
                              description=f"輸入的目前進度(`{self.children[3].value}`)應在0~100之間！請重新輸入。",
                              color=error_color)
                await interaction.response.edit_message(embed=embed)
                return
            else:
                reminder_obj.set_progress(int(self.children[3].value))
            embed.add_field(name="名稱", value=self.children[0].value, inline=False)
            if self.children[1].value != "":
                embed.add_field(name="說明", value=self.children[1].value, inline=False)
            embed.add_field(name="預計結束時間", value=f"<t:{self.children[2].value}:F> (<t:{self.children[2].value}:R>)",
                            inline=False)
            embed.add_field(name="目前進度", value=f"`{self.children[3].value} %`", inline=False)
            await

    reminder_cmds = discord.SlashCommandGroup(name="reminder")

    @reminder_cmds.command(name="新增", description="新增提醒事項。")
    async def add(self, ctx):
        await ctx.send_modal(self.ReminderEditor())


def setup(bot):
    bot.add_cog(Reminder(bot, bot.logger))
    bot.logger.info(f'"{Reminder.__name__}"已被載入。')
