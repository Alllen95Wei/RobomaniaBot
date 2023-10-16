import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from update import kill_running_bot
from platform import system

intents = discord.Intents.all()
bot = commands.Bot(intents=intents, help_command=None)


@bot.event
async def on_ready():
    print("機器人準備完成！指令已清除完畢。")
    print(f"PING值：{round(bot.latency * 1000)}ms")
    print(f"登入身分：{bot.user.name}#{bot.user.discriminator}")
    clean_user_data = input("刪除資料？(Y/N)")
    if clean_user_data.lower() == "y":
        meeting_data_path = os.path.join(os.path.dirname(__file__), "meeting_data")
        for file in os.listdir(meeting_data_path):
            os.remove(os.path.join(meeting_data_path, file))
            print("刪除檔案：", file)
        member_path = os.path.join(os.path.dirname(__file__), "member_data")
        for file in os.listdir(member_path):
            os.remove(os.path.join(member_path, file))
            print("刪除檔案：", file)
        print("刪除完畢。")
        message_path = os.path.join(os.path.dirname(__file__), "message_data")
        for file in os.listdir(message_path):
            os.remove(os.path.join(message_path, file))
            print("刪除檔案：", file)
        print("刪除完畢。")
        archived_meeting_path = os.path.join(os.path.dirname(__file__), "archived", "meeting")
        for file in os.listdir(archived_meeting_path):
            os.remove(os.path.join(archived_meeting_path, file))
            print("刪除檔案：", file)
    print("結束工作...")
    kill_running_bot(os.getpid(), system())

load_dotenv("TOKEN.env")
TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
