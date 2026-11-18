import logging
import os

import aiohttp
import discord
from discord import app_commands


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("alpaca_bot")


class AlpacaBot(discord.Client):
    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        # Guild-scoped commands update immediately and are convenient for development.
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced commands to guild %s", guild_id)
        else:
            await self.tree.sync()
            logger.info("Synced global commands")


bot = AlpacaBot()


@bot.tree.command(name="ping", description="Pong으로 응답합니다.")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message("Pong!")


@bot.tree.command(name="run", description="격리된 작업 컨테이너에서 실행을 확인합니다.")
async def run(interaction: discord.Interaction) -> None:
    owner_id = os.getenv("DISCORD_OWNER_ID", "")
    if not owner_id.isdecimal() or interaction.user.id != int(owner_id):
        await interaction.response.send_message("이 명령을 실행할 권한이 없습니다.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            async with session.post("http://worker:8080/run") as response:
                result = await response.json()
                message = result.get("message", "작업 결과가 없습니다.")
    except (aiohttp.ClientError, TimeoutError):
        logger.exception("Worker request failed")
        message = "작업 서버에 연결할 수 없습니다. 서버 로그를 확인하세요."
    await interaction.followup.send(message[:1900], ephemeral=True)


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 환경변수를 설정해주세요.")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
