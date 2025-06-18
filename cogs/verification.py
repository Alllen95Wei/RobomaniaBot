# coding=utf-8
import discord
from discord import Embed
from discord.ext import commands
from discord.ui import View, Modal
import os
import zoneinfo
from pathlib import Path
import logging

import logger
import json_assistant

error_color = 0xF1411C
default_color = 0x012a5e
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
base_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = str(Path(__file__).parent.parent.absolute())


class Verification(commands.Cog):
    def __init__(self, bot: commands.Bot, real_logger: logger.CreateLogger):
        self.bot = bot
        self.real_logger = real_logger

    class GetRealName(Modal):
        def __init__(self, outer_instance) -> None:
            super().__init__(title="審核", timeout=None)

            self.add_item(
                discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    label="請輸入你的真實姓名",
                    max_length=100,
                    required=True,
                )
            )
            self.outer_instance = outer_instance
            self.bot = outer_instance.bot

        async def callback(self, interaction: discord.Interaction):
            logging.info(f"提交審核要求：{interaction.user.name} 提交了審核需求")
            logging.info(f"   ⌊真名：{self.children[0].value}")
            embed = Embed(
                title="已提交新的審核要求！", description="你的回應已送出！請等待管理員的審核。", color=default_color
            )
            embed.add_field(
                name="你的帳號名稱",
                value=f"{interaction.user.name}",
                inline=False,
            )
            embed.add_field(name="你的回應", value=self.children[0].value, inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
            embed = Embed(
                title="收到新的審核要求", description="有新的審核要求，請盡快處理。", color=default_color
            )
            embed.set_thumbnail(url=interaction.user.display_avatar)
            embed.add_field(
                name="帳號名稱", value=f"<@{interaction.user.id}>", inline=False
            )
            embed.add_field(name="真實姓名", value=self.children[0].value, inline=False)
            embed.add_field(
                name="按鈕功能說明",
                value="點擊「確認，身分無誤」後，機器人會：\n1. 設定該成員真名為提交內容\n2. 變更該成員暱稱為真名\n3. 傳送通知給該成員",
                inline=False
            )
            await self.bot.get_channel(1114444831054376971).send(
                content="@everyone", embed=embed,
                view=self.outer_instance.SetRealName(self.outer_instance, interaction.user, self.children[0].value)
            )

    class VerificationModalToView(View):
        def __init__(self, outer_instance):
            super().__init__()
            self.outer_instance = outer_instance

        @discord.ui.button(label="點此開始審核", style=discord.ButtonStyle.green, emoji="📝")
        async def button_callback(
                self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.response.send_modal(
                self.outer_instance.GetRealName(self.outer_instance)
            )

    class SetRealName(View):
        def __init__(self, outer_instance, user: discord.User, real_name: str):
            super().__init__()
            self.outer_instance = outer_instance
            self.member: discord.Member = outer_instance.bot.get_guild(1114203090950836284).get_member(user.id)
            self.real_name = real_name

        @discord.ui.button(label="確認，身分無誤", style=discord.ButtonStyle.green, emoji="✅")
        async def valid_button_callback(
                self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.response.defer()
            logging.info(f"{self.member.name} 的身分已經過 {interaction.user.name} 確認無誤")
            member_obj = json_assistant.User(self.member.id)
            member_obj.set_real_name(self.real_name)
            try:
                await self.member.edit(nick=self.real_name)
            except Exception as e:
                logging.warning(f"無法更改 {self.member.name} 的暱稱為其真名")
                logging.warning(f"{type(e).__name__}: {e}")
            notify_embed = Embed(
                title="你的身分已經過驗證！",
                description="管理員在經過審核後，已確認了你的身分。\n"
                            "你的真名已經記錄在資料庫中，並且設為你在伺服器中的暱稱。\n"
                            "感謝你的配合！",
                color=default_color
            )
            await self.member.send(embed=notify_embed)
            self.disable_all_items()
            embed = Embed(title="已完成審核", description=f"{interaction.user.mention} 已確認 {self.member.mention} 的審核要求。",
                          color=default_color)
            embed.add_field(name="審核結果", value="✅ 通過")
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(embed=embed)

        @discord.ui.button(label="此身分有問題", style=discord.ButtonStyle.red, emoji="❌")
        async def invalid_button_callback(
                self, button: discord.ui.Button, interaction: discord.Interaction
        ):
            await interaction.response.defer()
            logging.info(f"{self.member.name} 的身分已被 {interaction.user.name} 撤回")
            notify_embed = Embed(
                title="你的身分未通過驗證",
                description="管理員在經過審核後，認為你所提供的身分有問題。\n"
                            "請私訊伺服器管理員以了解詳情。",
                color=error_color
            )
            await self.member.send(embed=notify_embed)
            self.disable_all_items()
            embed = Embed(title="已完成審核", description=f"{interaction.user.mention} 已確認 {self.member.mention} 的審核要求。",
                          color=default_color)
            embed.add_field(name="審核結果", value="❌ 撤回")
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member | discord.User):
        guild_joined = member.guild
        if not member.bot and guild_joined.id == 1114203090950836284:
            self.real_logger.info(f"新成員加入：{member.name}")
            embed = Embed(
                title=f"歡迎加入 {guild_joined.name} ！",
                description="在正式加入此伺服器前，請告訴我們你的**真名**，以便我們授予你適當的權限！",
                color=default_color,
            )
            try:
                await member.send(
                    embed=embed, view=self.VerificationModalToView(self)
                )
                self.real_logger.info("   ⌊已成功傳送驗證提示")
            except discord.errors.HTTPException as error:
                if error.code == 50007:
                    self.real_logger.warning("   ⌊無法傳送驗證提示(私人訊息關閉)")
                    await guild_joined.system_channel.send(
                        f"{member.mention}，由於你的私人訊息已關閉，無法透過機器人進行快速審核。\n"
                        f"請私訊管理員你的**真名**，以便我們授予你適當的身分組！"
                    )
                else:
                    raise error

    @discord.slash_command(name="verify_test", description="測試")
    @commands.is_owner()
    async def verify_test(self, ctx: discord.ApplicationContext):
        await ctx.respond("Triggered.", ephemeral=True)
        await self.on_member_join(ctx.user)


def setup(bot):
    bot.add_cog(Verification(bot, bot.logger))
    bot.logger.info(f'已載入 "{Verification.__name__}"。')
