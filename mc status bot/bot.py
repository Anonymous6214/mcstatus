import discord
from discord.ext import commands

import yaml
import logging

formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
handler = logging.StreamHandler()
handler.setFormatter(formatter)

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

log = logging.getLogger("bot")
log.setLevel(logging.INFO)
log.addHandler(handler)


initial_extensions = [
    "cogs.status",
]


def get_prefix(bot, message):
    prefixes = [bot.config["prefix"]]
    return commands.when_mentioned_or(*prefixes)(bot, message)

description = """
檢查狀態Discord機器人
"""

class ServerStatus(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            description=description,
            case_insensitive=True,
            activity=discord.Game("正在啟動..."),
        )

        self.log = log

        log.info("正在啟動...")

        log.info("正在讀取config...")
        self.config = self.load_config("config.yml")

        log.info("正在讀取擴充插件...")
        for extension in initial_extensions:
            self.load_extension(extension)

        log.info("正在設定初始狀態")
        status_cog = self.get_cog("Status")
        status, text = self.loop.run_until_complete(status_cog.get_status())
        game = discord.Game(text)
        status_cog.activity = game

        self._connection._status = status
        self.activity = game

        try:
            self.load_extension("jishaku")

        except Exception:
            log.info("jishaku 未安裝，繼續中...")

    def load_config(self, filename):
        with open(filename, "r") as f:
            return yaml.safe_load(f)

    async def on_ready(self):
        log.info(f"正在以 [{self.user.name}] 機器人身分登入 - {self.user.id}")

    def run(self):
        super().run(self.config["bot-token"])


if __name__ == "__main__":
    bot = ServerStatus()
    bot.run()
