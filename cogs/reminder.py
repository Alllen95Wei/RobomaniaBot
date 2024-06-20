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

    @commands.Cog.listener()
    async def on_ready(self):
        self.check_reminders.start()

    @tasks.loop(minutes=1)
    async def check_reminders(self):
        self.real_logger.debug("開始檢查提醒事項...")
        id_list = json_assistant.Reminder.get_all_reminder_id()
        for r in id_list:
            r_obj = json_assistant.Reminder(r)
            end_time = r_obj.get_time()
            if not r_obj.get_notified() and time.time() >= end_time:
                self.real_logger.debug(f"提醒事項 {r} 的時間已到！")
                embed = Embed(title="提醒事項的時間已到！",
                              description=f"提醒事項**「{r_obj.get_title()}」**已在<t:{r_obj.get_time()}:F>到期！",
                              color=default_color)
                embed.add_field(name="說明",
                                value=r_obj.get_description() if r_obj.get_description() != "" else "(無)",
                                inline=False)
                embed.add_field(name="建立者", value=f"<@{r_obj.get_author()}>", inline=False)
                channel = self.bot.get_channel(1128232150135738529)
                mention_msg = ""
                mention_roles = r_obj.get_mention_roles()
                if not mention_roles:
                    mention_msg = "@everyone"
                else:
                    for role in mention_roles:
                        mention_msg += f"<@{role}>"
                await channel.send(content=mention_msg, embed=embed)
                r_obj.set_notified(True)

    class ReminderEditor(ui.Modal):
        def __init__(self, reminder_id: str = None):
            super().__init__(title="提醒事項編輯器")
            self.reminder_id = reminder_id
            if reminder_id is None:
                prefill_data = ["", "", ""]
            else:
                reminder_obj = json_assistant.Reminder(reminder_id)
                prefill_data = [reminder_obj.get_title(),
                                reminder_obj.get_description(),
                                datetime.datetime.fromtimestamp(reminder_obj.get_time(), tz=now_tz).
                                strftime("%Y/%m/%d %H:%M"),
                                ]
            self.add_item(ui.InputText(style=InputTextStyle.short, label="名稱", value=prefill_data[0], required=True))
            self.add_item(ui.InputText(style=InputTextStyle.long, label="說明", value=prefill_data[1], required=False))
            self.add_item(
                ui.InputText(style=InputTextStyle.short, label="預定結束時間 (格式：YYYY/MM/DD HH:MM，24小時制)",
                             placeholder="YYYY/MM/DD HH:MM", value=prefill_data[2],
                             min_length=16, max_length=16, required=True))

        async def callback(self, interaction: Interaction):
            await interaction.response.defer()
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
            reminder_obj.set_author(interaction.user.id)
            reminder_obj.set_title(self.children[0].value)
            reminder_obj.set_description(self.children[1].value)
            embed.add_field(name="提醒事項ID", value="`" + unique_id + "`", inline=False)
            try:
                unix_start_time = int(datetime.datetime.timestamp(
                    datetime.datetime.strptime(self.children[2].value, "%Y/%m/%d %H:%M").replace(tzinfo=now_tz)))
                if unix_start_time < time.time():
                    embed = Embed(title="錯誤",
                                  description=f"輸入的預計結束時間(<t:{int(unix_start_time)}:F>)已經過去！請重新輸入。",
                                  color=error_color)
                    await interaction.followup.send(embed=embed)
                    return
                else:
                    reminder_obj.set_time(unix_start_time)
                    embed.add_field(name="預計結束時間", value=f"<t:{int(unix_start_time)}:F> "
                                                         f"(<t:{int(unix_start_time)}:R>)", inline=False)
            except ValueError:
                embed = Embed(title="錯誤",
                              description=f"輸入的預計結束時間(`{self.children[2].value}`)格式錯誤！請重新輸入。",
                              color=error_color)
                await interaction.followup.send(embed=embed)
                return
            embed.add_field(name="名稱", value=self.children[0].value, inline=False)
            if self.children[1].value != "":
                embed.add_field(name="說明", value=self.children[1].value, inline=False)
            await interaction.followup.send(embed=embed)

    reminder_cmds = discord.SlashCommandGroup(name="reminder")

    @reminder_cmds.command(name="新增", description="新增提醒事項。")
    async def add(self, ctx):
        await ctx.send_modal(self.ReminderEditor())

    @reminder_cmds.command(name="編輯", description="編輯提醒事項。")
    async def edit(self, ctx,
                   reminder_id: Option(str, name="提醒事項id", min_length=5, max_length=5, required=True)):
        if reminder_id in json_assistant.Reminder.get_all_reminder_id():
            await ctx.send_modal(self.ReminderEditor(reminder_id))
        else:
            embed = Embed(title="錯誤", description=f"提醒事項 `{reminder_id}` 不存在！", color=error_color)
            await ctx.respond(embed=embed)

    @reminder_cmds.command(name="刪除", description="刪除提醒事項。")
    async def delete_cmd(self, ctx,
                         reminder_id: Option(str, name="提醒事項id", min_length=5, max_length=5, required=True)):
        if reminder_id in json_assistant.Reminder.get_all_reminder_id():
            embed = Embed(title="刪除成功", description=f"已經刪除提醒事項 `{reminder_id}`。", color=default_color)
        else:
            embed = Embed(title="錯誤", description=f"提醒事項 `{reminder_id}` 不存在！", color=error_color)
        await ctx.respond(embed=embed)

    @reminder_cmds.command(name="新增提及身分組",
                           description="新增「在提醒事項傳送通知」時，會被提及的身分組。一次最多新增3個。")
    async def add_mention_role_cmd(self, ctx,
                                   reminder_id: Option(str, name="提醒事項id", min_length=5, max_length=5,
                                                       required=True),
                                   role_1: Option(discord.Role, name="身分組1", required=True),
                                   role_2: Option(discord.Role, name="身分組2", required=False) = None,
                                   role_3: Option(discord.Role, name="身分組3", required=False) = None):
        if reminder_id in json_assistant.Reminder.get_all_reminder_id():
            roles = [role_1.id]
            if role_2 is not None:
                roles.append(role_2.id)
            if role_3 is not None:
                roles.append(role_3.id)
            r_obj = json_assistant.Reminder(reminder_id)
            result = r_obj.add_mention_roles(roles)
            if len(result) == 0:
                embed = Embed(title="錯誤", description="所提供的身分組皆已在提及清單內。", color=error_color)
            else:
                embed = Embed(title="成功新增提及身分組！", description=f"已成功新增了 {len(result)} 個身分組至提及清單。", color=default_color)
            mention_msg = "*(所有人)*"
            mention_roles = r_obj.get_mention_roles()
            if mention_roles:
                mention_msg = ""
                for r in mention_roles:
                    mention_msg += f"<@{r}>"
            embed.add_field(name="下列的身分組將會在傳送通知時被提及：", value=mention_msg, inline=False)
        else:
            embed = Embed(title="錯誤", description=f"提醒事項 `{reminder_id}` 不存在！", color=error_color)
        await ctx.respond(embed=embed)

    @reminder_cmds.command(name="移除提及身分組",
                           description="移除「在提醒事項傳送通知」時，會被提及的身分組。一次最多移除3個。")
    async def remove_mention_role_cmd(self, ctx,
                                      reminder_id: Option(str, name="提醒事項id", min_length=5, max_length=5,
                                                          required=True),
                                      role_1: Option(discord.Role, name="身分組1", required=True),
                                      role_2: Option(discord.Role, name="身分組2", required=False) = None,
                                      role_3: Option(discord.Role, name="身分組3", required=False) = None):
        if reminder_id in json_assistant.Reminder.get_all_reminder_id():
            roles = [role_1.id]
            if role_2 is not None:
                roles.append(role_2.id)
            if role_3 is not None:
                roles.append(role_3.id)
            r_obj = json_assistant.Reminder(reminder_id)
            result = r_obj.remove_mention_roles(roles)
            if len(result) == 0:
                embed = Embed(title="錯誤", description="所提供的身分組皆不在提及清單內。", color=error_color)
            else:
                embed = Embed(title="成功移除提及身分組！", description=f"已成功移除了 {len(result)} 個身分組至提及清單。", color=default_color)
            mention_msg = "*(所有人)*"
            mention_roles = r_obj.get_mention_roles()
            if mention_roles:
                mention_msg = ""
                for r in mention_roles:
                    mention_msg += f"<@{r}>"
            embed.add_field(name="下列的身分組將會在傳送通知時被提及：", value=mention_msg, inline=False)
        else:
            embed = Embed(title="錯誤", description=f"提醒事項 `{reminder_id}` 不存在！", color=error_color)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Reminder(bot, bot.logger))
    bot.logger.info(f'"{Reminder.__name__}"已被載入。')
