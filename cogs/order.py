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


class Order(commands.Cog):
    def __init__(self, bot: commands.Bot, real_logger: logger.CreateLogger):
        self.bot = bot
        self.real_logger = real_logger

    @tasks.loop(seconds=1)
    async def check_order_is_due(self, order_id: str):
        order_obj = json_assistant.Order(order_id)
        end_time = order_obj.get_end_time()
        forced = False
        if time.time() >= end_time or order_obj.order_has_closed():
            if order_obj.order_has_closed():
                forced = True
            order_obj.set_order_has_closed(True)
            notification_embed = Embed(title="團購結束！", description=f"由<@{order_obj.get_manager()}>所負責的"
                                                                  f"團購`{order_id}`已結束！", color=default_color)
            notification_embed.add_field(name="標題", value=order_obj.get_title(), inline=False)
            notification_embed.add_field(name="結束於", value=f"<t:{int(time.time())}>", inline=False)
            if not forced:
                notification_embed.set_footer(text="本團購因結單時間到，由機器人自動停止接受新要求。")
            else:
                notification_embed.set_footer(text="本團購由負責人手動結束。")
            notification_channel = self.bot.get_channel(1199648739091042377)
            await notification_channel.send(content=f"<@{order_obj.get_manager()}>你的團購已自動結束！", embed=notification_embed)
            order_list = order_obj.get_current_order()
            order_embed = Embed(title=f"本次的團購名單", description=f"`{order_id}`的參與者與團購品項如下：",
                                color=default_color)
            if order_list:
                order_str = ""
                for order in order_list:
                    order_request = order_list[order]
                    order_str += f"\n<@{order}>："
                    for order_item in order_request:
                        order_str += f"\n* {order_item}"
            else:
                order_str = "(無)"
            order_embed.description += order_str
            await notification_channel.send(embed=order_embed)

    class OrderEditor(ui.Modal):
        def __init__(self, outer_instance, order_id: str = ""):
            super().__init__(title="開始新的團購" if order_id == "" else "編輯團購")
            self.bot = outer_instance.bot
            self.outer_instance = outer_instance
            self.order_id = order_id
            if order_id == "":
                prefill_data = ["", "", "", ""]
            else:
                order_obj = json_assistant.Order(order_id)
                prefill_data = [order_obj.get_title(),
                                order_obj.get_description(),
                                order_obj.get_menu_link(),
                                datetime.datetime.fromtimestamp(order_obj.get_end_time(), tz=now_tz)
                                .strftime("%Y/%m/%d %H:%M")]

            self.add_item(ui.InputText(style=InputTextStyle.short, label="標題", value=prefill_data[0]))
            self.add_item(ui.InputText(style=InputTextStyle.long, label="說明", value=prefill_data[1], required=False))
            self.add_item(ui.InputText(style=InputTextStyle.short, label="菜單連結", value=prefill_data[2]))
            self.add_item(ui.InputText(style=InputTextStyle.short, label="結單時間 (格式：YYYY/MM/DD HH:MM，24小時制)",
                                       placeholder="YYYY/MM/DD HH:MM"))

        async def callback(self, interaction: Interaction):
            await interaction.response.defer()
            if self.order_id == "":
                order_id = json_assistant.Order.generate_order_id()
                embed = Embed(
                    title="開始新的團購",
                    description=f"成功開始了新的團購！\n本次的代碼為：`{order_id}`",
                    color=default_color,
                )
                notification_embed = Embed(title="新的團購已開始！",
                                           description=f"由<@{interaction.user.id}>開始的新團購已開始！",
                                           color=default_color)
            else:
                order_id = self.order_id
                embed = Embed(
                    title="編輯團購資訊",
                    description=f"已編輯團購資訊。\n本次的代碼為：`{order_id}`",
                    color=default_color
                )
                notification_embed = Embed(title="團購資訊變動",
                                           description=f"由<@{interaction.user.id}>開始的團購有異動。",
                                           color=default_color)
            order_obj = json_assistant.Order(order_id)
            embed.add_field(name="標題", value=self.children[0].value, inline=False)
            embed.add_field(
                name="說明", value=self.children[1].value, inline=False
            ) if self.children[1].value else None
            embed.add_field(name="菜單連結", value=self.children[2].value, inline=False)
            try:
                unix_end_time = datetime.datetime.timestamp(
                    datetime.datetime.strptime(
                        self.children[4].value, "%Y/%m/%d %H:%M"
                    ).replace(tzinfo=now_tz)
                )
                if unix_end_time < time.time():
                    embed = discord.Embed(
                        title="錯誤",
                        description=f"輸入的時間(<t:{int(unix_end_time)}:F>)已經過去！請重新輸入。",
                        color=error_color,
                    )
                    order_obj.delete()
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                else:
                    order_obj.set_end_time(int(unix_end_time))
                    embed.add_field(
                        name="結單時間",
                        value=f"<t:{int(unix_end_time)}:F> (<t:{int(unix_end_time)}:R>)",
                        inline=False,
                    )
            except ValueError:
                embed = discord.Embed(
                    title="錯誤",
                    description=f"輸入的時間(`{self.children[2].value}`)格式錯誤！請重新輸入。",
                    color=error_color,
                )
                order_obj.delete()
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            notification_embed.add_field(name="團購ID", value=order_id, inline=False)
            notification_embed.add_field(name="標題", value=self.children[0].value, inline=False)
            notification_embed.add_field(name="說明", value=self.children[1].value if self.children[1].value else "(無說明)",
                                         inline=False)
            notification_embed.add_field(name="菜單連結", value=self.children[2].value, inline=False)
            notification_embed.add_field(name="結單時間", value=f"<t:{int(unix_end_time)}:F> (<t:{int(unix_end_time)}:R>)",
                                         inline=False)
            notification_embed.add_field(name="負責人", value=f"<@{interaction.user.id}>")
            notification_embed.set_footer(text=f"請點選下方按鈕加入團購，或使用「/order 加入 團購id:{order_id}」指令。")
            order_obj.set_title(self.children[0].value)
            order_obj.set_description(self.children[1].value)
            order_obj.set_menu_link(self.children[2].value)
            order_obj.set_end_time(int(unix_end_time))
            order_obj.set_manager(interaction.user.id)
            await self.outer_instance.check_order_is_due.start(order_id)
            await self.bot.get_channel(1199648739091042377).send(embed=notification_embed)
            await interaction.followup.send(embed=embed, ephemeral=True)

    class AddItemsToOrder(ui.Modal):
        def __init__(self, user_id: int, order_id: str):
            super().__init__(title="加入團購", timeout=None)
            self.order_id = order_id
            self.order_obj = json_assistant.Order(order_id)
            prefill_data = [order_id, self.order_obj.get_user_order(user_id)]
            self.add_item(ui.InputText(style=InputTextStyle.short, label="(自動填入，勿動！)團購ID",
                                       min_length=5, max_length=5, value=prefill_data[0]))
            self.add_item(ui.InputText(style=InputTextStyle.long, label="點餐內容 (請使用換行分隔不同品項)",
                                       placeholder="使用Enter換行，以分隔不同品項"))

        async def callback(self, interaction: Interaction):
            embed = Embed(title="成功加入團購！", description=f"你已成功加入團購`{self.order_id}`！", color=default_color)
            embed.add_field(name="團購ID", value=self.children[0].value, inline=False)
            order_list = self.children[1].value.split("\n")
            self.order_obj.add_order(interaction.user.id, order_list)
            order_str = ""
            for order in order_list:
                order_str += f"* {order}\n"
            embed.add_field(name="點餐內容", value=order_str, inline=False)
            embed.add_field(name="對團購有疑問？", value=f"請向本次團購的負責人：<@{self.order_obj.get_manager()}>詢問。")
            await interaction.followup.send(embed=embed, ephemeral=True)

    order_cmds = discord.SlashCommandGroup(name="order", description="建立、加入、編輯、刪除訂單等相關指令。")

    @order_cmds.command(name="開始", description="開始新的團購。")
    @commands.has_role(1200075814146932826)
    async def start_new_order(self, ctx):
        await ctx.send_modal(self.OrderEditor(self))

    @order_cmds.command(name="編輯", description="編輯團購資訊。")
    @commands.has_role(1200075814146932826)
    async def edit_order(self, ctx,
                         團購id: Option(str, "欲編輯的團購資訊ID", min_length=5, max_length=5,  # noqa
                                        required=True)):
        if 團購id in json_assistant.Order.get_all_order_id():
            order_obj = json_assistant.Order(團購id)
            if order_obj.get_manager() != ctx.author.id:
                embed = Embed(title="錯誤", description="你不是此團購的負責人，無法編輯此團購。", color=error_color)
                embed.add_field(name="團購ID", value=團購id, inline=False)
                embed.add_field(name="管理員", value=f"<@{order_obj.get_manager()}>", inline=False)
                embed.set_footer(text="僅有訂單負責人可修改團購資訊。")
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                await ctx.send_modal(self.OrderEditor(self, 團購id))
        else:
            embed = Embed(title="錯誤", description=f"輸入團購ID`{團購id}`不存在。", color=error_color)
            await ctx.respond(embed=embed, ephemeral=True)

    @order_cmds.command(name="結束", description="手動結束團購。")
    @commands.has_role(1200075814146932826)
    async def stop_manually(self, ctx,
                            團購id: Option(str, "欲編輯的團購資訊ID", min_length=5, max_length=5,  # noqa
                                          required=True)):
        if 團購id in json_assistant.Order.get_all_order_id():
            order_obj = json_assistant.Order(團購id)
            if order_obj.get_manager() != ctx.author.id:
                embed = Embed(title="錯誤", description="你不是此團購的負責人，無法編輯此團購。", color=error_color)
                embed.add_field(name="團購ID", value=團購id, inline=False)
                embed.add_field(name="管理員", value=f"<@{order_obj.get_manager()}>", inline=False)
                embed.set_footer(text="僅有訂單負責人可修改團購資訊。")
            else:
                order_obj.set_order_has_closed(True)
                embed = Embed(title="已手動結束團購", description=f"成功結束你的團購`{團購id}`。", color=default_color)
                embed.set_footer(text="使用此指令後，可能仍需一段時間才會看到機器人傳送結束通知。")
        else:
            embed = Embed(title="錯誤", description=f"輸入團購ID`{團購id}`不存在。", color=error_color)
        await ctx.respond(embed=embed, ephemeral=True)

    @order_cmds.command(name="加入", description="加入團購。")
    async def join_order(self, ctx,
                         團購id: Option(str, "欲加入的團購ID", min_length=5, max_length=5,  # noqa
                                        required=True)):
        if 團購id in json_assistant.Order.get_all_order_id():
            await ctx.send_modal(self.AddItemsToOrder(ctx.author.id, 團購id))
        else:
            embed = Embed(title="錯誤", description=f"輸入團購ID`{團購id}`不存在。", color=error_color)
            await ctx.respond(embed=embed, ephemeral=True)
