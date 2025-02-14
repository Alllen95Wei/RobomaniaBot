# coding=utf-8
import discord
from discord.ext import commands
from discord import Embed, Option, PCMVolumeTransformer, FFmpegPCMAudio
import os
import zoneinfo
from pathlib import Path

import logger

default_color = 0x012a5e
error_color = 0xF1411C
now_tz = zoneinfo.ZoneInfo("Asia/Taipei")
base_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = str(Path(__file__).parent.parent.absolute())


class Player:
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.voice_client = None
        self.volume: float = 0.3
        self.voice_client: discord.VoiceClient

    async def join(
        self, voice_channel: discord.VoiceChannel
    ) -> tuple[bool, discord.VoiceChannel]:
        if self.voice_client is None:
            self.voice_client = await voice_channel.connect()
            await voice_channel.guild.change_voice_state(
                channel=voice_channel, self_mute=False, self_deaf=True
            )
            return True, voice_channel
        else:
            return False, self.voice_client.channel

    async def leave(self) -> tuple[bool, discord.VoiceChannel | None]:
        if self.voice_client is not None:
            channel = self.voice_client.channel
            await self.stop()
            await self.voice_client.disconnect(force=False)
            self.voice_client = None
            return True, channel
        return False, None

    async def play(self, file_path: str) -> bool:
        if self.voice_client is not None:
            self.voice_client: discord.VoiceClient
            if self.voice_client.is_playing():
                self.voice_client.stop()
            self.voice_client.play(
                PCMVolumeTransformer(
                    original=FFmpegPCMAudio(source=file_path),
                    volume=self.volume,
                )
            )
            return True
        return False

    async def pause(self) -> tuple[bool, str]:
        if self.voice_client is not None and self.voice_client.is_playing():
            self.voice_client.pause()
            return True, ""
        if self.voice_client is None:
            return False, "Not connected to a voice channel"
        else:
            return False, "Not playing"

    async def resume(self) -> tuple[bool, str]:
        if self.voice_client is not None and self.voice_client.is_paused():
            self.voice_client.resume()
            return True, ""
        if self.voice_client is None:
            return False, "Not connected to a voice channel"
        else:
            return False, "Not paused"

    async def stop(self) -> tuple[bool, str]:
        if self.voice_client is not None and self.voice_client.is_playing():
            self.voice_client.stop()
            return True, ""
        if self.voice_client is None:
            return False, "Not connected to a voice channel"
        else:
            return False, "Not playing"

    async def set_volume(self, volume: float) -> tuple[bool, int, str]:
        previous_volume = int(self.volume)
        self.volume = volume
        if self.voice_client is not None and self.voice_client.source is not None:
            self.voice_client.source.volume = volume
            return True, previous_volume, ""
        if self.voice_client is None:
            return False, previous_volume, "Not connected to a voice channel"
        else:
            return False, previous_volume, "No source"


class PlayerCog(commands.Cog):
    def __init__(self, bot: commands.Bot, real_logger: logger.CreateLogger):
        self.bot = bot
        self.real_logger = real_logger

        self.player = Player(bot)

    PLAYER_CMDS = discord.SlashCommandGroup("player")

    @PLAYER_CMDS.command(name="join", description="加入使用者目前所在的語音頻道。")
    async def join(self, ctx: discord.ApplicationContext):
        member = ctx.user
        if member.voice is not None:
            try:
                result, channel = await self.player.join(member.voice.channel)
                if result:
                    embed = Embed(title="已加入語音頻道", description=f"已連線至 {channel.mention} ！",
                                  color=default_color)
                else:
                    embed = Embed(
                        title="錯誤：已加入其他頻道",
                        description=f"機器人目前已連線至 {channel.mention} 。請使用 `/player leave` 指令，中斷機器人與其的連線。",
                        color=error_color)
            except Exception as e:
                embed = Embed(title="錯誤",
                              description="發生未知錯誤。",
                              color=error_color)
                embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        else:
            embed = Embed(title="錯誤：使用者未在任何頻道內",
                          description="你尚未加入任何語音頻道，或是機器人無權限加入頻道。請加入一個機器人有權限加入的語音頻道，再使用此指令。",
                          color=error_color)
        await ctx.respond(embed=embed)

    @PLAYER_CMDS.command(name="leave", description="從目前連線的語音頻道中斷連線。")
    async def leave(self, ctx: discord.ApplicationContext):
        try:
            result, channel = await self.player.leave()
            if result:
                embed = Embed(title="已離開語音頻道", description=f"已從 {channel.mention} 中斷連線。", color=default_color)
            else:
                embed = Embed(title="錯誤：尚未加入語音頻道",
                              description="機器人尚未加入任何語音頻道。請使用 `/player join` 指令，將機器人加入語音頻道。",
                              color=error_color)
        except Exception as e:
            embed = Embed(title="錯誤",
                          description="發生未知錯誤。",
                          color=error_color)
            embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)

    @PLAYER_CMDS.command(name="play", description="播放指定的音檔。原先播放中的音訊將被停止。")
    async def play(self, ctx, file_path: Option(str, name="file_path")):
        try:
            result = await self.player.play(file_path)
            if result:
                embed = Embed(title="▶️ 開始播放", description=f"已開始播放 `{file_path}`！", color=default_color)
                embed.set_footer(text="原先播放中的音訊將立即停止。")
            else:
                embed = Embed(title="錯誤：尚未加入語音頻道",
                              description="機器人尚未加入任何語音頻道。請使用 `/player join` 指令，將機器人加入語音頻道。",
                              color=error_color)
        except Exception as e:
            embed = Embed(title="錯誤",
                          description="發生未知錯誤。",
                          color=error_color)
            embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)

    @PLAYER_CMDS.command(name="pause", description="暫停播放中的音訊。")
    async def pause(self, ctx):
        try:
            result, detail = await self.player.pause()
            if result:
                embed = Embed(title="⏸️ 暫停", description="已暫停播放。", color=default_color)
            else:
                if detail == "Not connected to a voice channel":
                    embed = Embed(title="錯誤：尚未加入語音頻道",
                                  description="機器人尚未加入任何語音頻道。請使用 `/player join` 指令，將機器人加入語音頻道。",
                                  color=error_color)
                else:
                    embed = Embed(title="錯誤：未在播放中", description="機器人目前未在播放音訊。", color=error_color)
        except Exception as e:
            embed = Embed(title="錯誤",
                          description="發生未知錯誤。",
                          color=error_color)
            embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)

    @PLAYER_CMDS.command(name="resume", description="恢復播放音訊。")
    async def resume(self, ctx):
        try:
            result, detail = await self.player.resume()
            if result:
                embed = Embed(title="⏯️ 恢復播放", description="已恢復播放。", color=default_color)
            else:
                if detail == "Not connected to a voice channel":
                    embed = Embed(title="錯誤：尚未加入語音頻道",
                                  description="機器人尚未加入任何語音頻道。請使用 `/player join` 指令，將機器人加入語音頻道。",
                                  color=error_color)
                else:
                    embed = Embed(title="錯誤：未暫停", description="機器人目前未暫停。", color=error_color)
        except Exception as e:
            embed = Embed(title="錯誤",
                          description="發生未知錯誤。",
                          color=error_color)
            embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)

    @PLAYER_CMDS.command(name="stop", description="停止播放音訊。")
    async def stop(self, ctx):
        try:
            result, detail = await self.player.stop()
            if result:
                embed = Embed(title="⏹️ 停止播放", description="已停止播放。", color=default_color)
            else:
                if detail == "Not connected to a voice channel":
                    embed = Embed(title="錯誤：尚未加入語音頻道",
                                  description="機器人尚未加入任何語音頻道。請使用 `/player join` 指令，將機器人加入語音頻道。",
                                  color=error_color)
                else:
                    embed = Embed(title="錯誤：未在播放中", description="機器人目前未在播放音訊。", color=error_color)
        except Exception as e:
            embed = Embed(title="錯誤",
                          description="發生未知錯誤。",
                          color=error_color)
            embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)

    @PLAYER_CMDS.command(name="set_volume", description="設定播放音量。")
    async def set_volume(self, ctx, volume: Option(int, name="volume", description="音量百分比 (0~100)", min_value=0, max_value=100)):
        try:
            result, previous_volume, detail = await self.player.set_volume(volume / 100)
            embed = Embed(title="已設定音量", description=f"音量已從 `{previous_volume * 100} %` 變更為 `{volume} %`。",
                          color=default_color)
            if not result:
                if detail == "Not connected to a voice channel":
                    detail = "機器人尚未加入任何語音頻道"
                else:
                    detail = "機器人目前未在播放音訊"
                embed.add_field(name="變更將在下次生效", value=f"由於{detail}，此次音量變更會在下次播放音訊時生效。", inline=False)
        except Exception as e:
            embed = Embed(title="錯誤",
                          description="發生未知錯誤。",
                          color=error_color)
            embed.add_field(name="錯誤訊息", value="```" + str(e) + "```", inline=False)
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(PlayerCog(bot, bot.logger))
    bot.logger.info(f'"{PlayerCog.__name__}"已被載入。')
