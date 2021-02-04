import discord
from discord.ext import commands, tasks

from mcstatus import MinecraftServer
import asyncio
import functools
import logging
import yaml
import traceback
import datetime


log = logging.getLogger("bot")


class ServerNotFound(commands.CommandError):
    def __init__(self, ip):
        self.ip = ip

        super().__init__(f"找不到伺服器IP: {ip}")


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.activity = None
        self.status = None

        self.last_set = None

        self.ip = ip = self.bot.config["server-ip"]
        log.info(f"正在尋找伺服器IP: {ip}")
        self.server = MinecraftServer.lookup(ip)

        if not self.server:
            log.critical(f"找不到伺服器IP: {ip}")
            raise ServerNotFound(ip)

        log.info(f"找到伺服器IP: {ip}")

        self.status_updater_task.start()

    def cog_unload(self):
        self.status_updater_task.cancel()

    @commands.command(
        aliases=["list", "who", "online"],
    )
    async def players(self, ctx):
        """Get player list for the current server"""
        partial = functools.partial(self.server.query)
        try:
            query = await self.bot.loop.run_in_executor(None, partial)

        except Exception as exc:
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            return await ctx.send(
                "無法ping到伺服器\n"
                "伺服器可能在離線狀態或是沒有打開監聽端口\n"
                "在 server.properties裡面找到 `enable-query` 並打開\n"
                f"Error: ```py\n{exc}\n```"
            )

        players = "\n".join(query.players.names)
        em = discord.Embed(
            title="目前上線玩家:",
            description=players,
            color=discord.Color.green(),
        )

        em.set_footer(text=f"伺服器 IP: `{self.ip}`")
        await ctx.send(embed=em)

    @commands.group(
        invoke_without_command=True,
        aliases=["ip"],
    )
    async def server(self, ctx):
        """Get the ip of the current server"""
        await ctx.send(f"IP: **`{self.ip}`**")

    @server.command(name="set")
    @commands.is_owner()
    async def _set(self, ctx, ip):
        """Set the IP for the server via command.

        This will automatically update the config file.
        """
        server = MinecraftServer.lookup(ip)
        if not server:
            return await ctx.send("找不到伺服器")

        self.server = server
        self.ip = ip
        self.bot.config["server-ip"] = ip
        with open("config.yml", "w") as config:
            yaml.dump(self.bot.config, config, indent=4, sort_keys=True)

        await self.update_status()

        await ctx.send(f"IP已經設定成: `{ip}`")

    @commands.command()
    async def update(self, ctx):
        await self.update_status(force=True)
        await ctx.send("狀態已更新")

    async def set_status(self, status, text, *, force=False):
        game = discord.Game(text)

        now = datetime.datetime.utcnow()
        if (
            not force
            and self.last_set
            and self.last_set + datetime.timedelta(minutes=30) < now
            and self.activity == game
            and self.status == status
        ):
            return

        await self.bot.change_presence(status=status, activity=game)
        self.status = status
        self.activity = game

        log.info(f"設定狀態 {status}: {text}")

    async def get_status(self):
        partial = functools.partial(self.server.status)
        try:
            server = await self.bot.loop.run_in_executor(None, partial)

        except Exception:
            return discord.Status.dnd, "離線中"

        if server.players.online == server.players.max:
            status = discord.Status.idle
        else:
            status = discord.Status.online

        maintenance_text = self.bot.config["maintenance-mode-detection"]
        if maintenance_text:
            if not isinstance(maintenance_text, str):
                logging.warning(
                    "無效的維護模式設定"
                    f"它必須是一個字符串, 然而是 {type(maintenance_text)} "
                )
                return None

            if isinstance(server.description, dict):
                description = server.description.get("text", "")
                extras = server.description.get("extra")
                if extras:
                    for extra in extras:
                        description += extra.get("text", "")

            else:
                description = str(server.description)

            if maintenance_text.lower() in description.lower():
                return discord.Status.dnd, "維護中"

        return status, f"{server.players.online}/{server.players.max} 在線中"

    async def update_status(self, *, force=False):
        status, text = await self.get_status()

        await self.set_status(status, text, force=force)

    @tasks.loop(seconds=60)
    async def status_updater_task(self):
        await self.update_status()

    @status_updater_task.before_loop
    async def before_printer(self):
        await self.bot.wait_until_ready()
        log.info("下一個狀態設定必須等待10秒")
        await asyncio.sleep(10)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if len(self.guilds) == 1:
            log.info("加入第一個伺服器，正在設定狀態")
            await self.update_status()


def setup(bot):
    bot.add_cog(Status(bot))
