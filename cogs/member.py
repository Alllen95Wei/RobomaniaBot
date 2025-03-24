# coding=utf-8
import discord
from discord.ext import commands
from discord import Option, Embed
import os
import zoneinfo
from pathlib import Path
import logging

import json_assistant

base_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = str(Path(__file__).parent.parent.absolute())
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
default_color = 0x012a5e
error_color = 0xF1411C


class Member(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    MEMBER_CMD = discord.SlashCommandGroup(name="member", description="隊員資訊相關指令。")

    @MEMBER_CMD.command(name="查詢", description="查看隊員資訊。")
    async def member_info(self, ctx,
                          member: Option(discord.Member, "隊員", required=False) = None):  # noqa
        if member is None:
            member = ctx.author  # noqa
        member_data = json_assistant.User(member.id)
        jobs_str = ""
        if len(member_data.get_jobs()) != 0:
            for job in member_data.get_jobs():
                jobs_str += f"* {job}\n"
        else:
            jobs_str = "(無)"
        embed = Embed(title="隊員資訊", description=f"{member.mention} 的資訊", color=default_color)
        embed.add_field(name="真實姓名", value=member_data.get_real_name(), inline=False)
        embed.add_field(name="職務", value=jobs_str, inline=False)
        # embed.add_field(name="總計會議時數", value=member_data.get_total_meeting_time(), inline=False)
        embed.add_field(name="警告點數", value=f"`{member_data.get_warning_points()}` 點", inline=False)
        embed.set_thumbnail(url=member.display_avatar)
        await ctx.respond(embed=embed)

    @MEMBER_CMD.command(name="查詢記點人員", description="列出點數不為 0 的隊員。")
    async def member_list_bad_guys(self, ctx):
        members = json_assistant.User.get_all_user_id()
        embed = Embed(title="遭記點隊員清單", description="以下為點數不為 0 的前 25 名隊員：", color=default_color)
        bad_guys: list[dict[str, str | float | int]] = []
        for m in members:
            member_obj = json_assistant.User(m)
            if member_obj.get_warning_points() != 0:
                bad_guys.append({"name": member_obj.get_real_name(), "points": member_obj.get_warning_points()})
        bad_guys.sort(key=lambda x: x["points"], reverse=True)
        if len(bad_guys) > 25:
            bad_guys = bad_guys[:25]
        for bad_guy in bad_guys:
            medals = ("🥇", "🥈", "🥉")
            if bad_guys.index(bad_guy) <= 2:
                bad_guy["name"] = medals[bad_guys.index(bad_guy)] + " " + bad_guy["name"]
            embed.add_field(name=bad_guy["name"], value=f"`{bad_guy['points']}` 點", inline=False)
        if len(embed.fields) == 0:
            embed.add_field(name="(沒有遭記點隊員)", value="所有人目前皆無點數！", inline=False)
        await ctx.respond(embed=embed)

    @MEMBER_CMD.command(name="以真名查詢id", description="使用真名查詢使用者的 Discord ID，可用於讀取已離開成員的資料。")
    async def member_search_by_real_name(self, ctx,
                                         real_name: Option(str, name="真名", description="成員的真名", required=True)):
        members = json_assistant.User.get_all_user_id()
        results = []
        for m in members:
            member_obj = json_assistant.User(m)
            if member_obj.get_real_name() == real_name:
                results.append(m)
        if len(results) != 0:
            embed = Embed(title="搜尋結果", description=f"真名為 `{real_name}` 的資料共有 {len(results)} 筆：",
                          color=default_color)
            for result in results:
                embed.add_field(name=result, value="", inline=False)
        else:
            embed = Embed(title="搜尋結果", description=f"沒有任何真名為 `{real_name}` 的資料。", color=error_color)
        await ctx.respond(embed=embed)

    @MEMBER_CMD.command(name="個人記點紀錄", description="查詢記點紀錄。")
    async def member_get_warning_history(self, ctx,
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

    @discord.user_command(name="查看此隊員的資訊")
    async def member_info_user(self, ctx, user: discord.Member):
        await self.member_info(ctx, user)

    @discord.user_command(name="查看此隊員的記點紀錄")
    async def member_get_warning_history_user(self, ctx, user: discord.Member):
        await self.member_get_warning_history(ctx, user)


def setup(bot: commands.Bot):
    bot.add_cog(Member(bot))
    logging.info(f'已載入 "{Member.__name__}"。')
