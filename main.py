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
        intents = discord.Intents.default()
        intents.message_content = os.getenv("LOG_MESSAGE_CONTENT", "").lower() in {"1", "true", "yes"}
        super().__init__(intents=intents)
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


@bot.tree.command(name="repo_test", description="저장소 복사본에서 수정과 테스트를 확인합니다.")
async def repo_test(interaction: discord.Interaction) -> None:
    owner_id = os.getenv("DISCORD_OWNER_ID", "")
    if not owner_id.isdecimal() or interaction.user.id != int(owner_id):
        await interaction.response.send_message("이 명령을 실행할 권한이 없습니다.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=150)) as session:
            async with session.post("http://worker:8080/repo-test") as response:
                result = await response.json()
                message = result.get("message", "작업 결과가 없습니다.")
    except (aiohttp.ClientError, TimeoutError):
        logger.exception("Repository test request failed")
        message = "작업 서버에 연결할 수 없습니다. 서버 로그를 확인하세요."
    await interaction.followup.send(message[:1900], ephemeral=True)


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)


@bot.event
async def on_interaction(interaction: discord.Interaction) -> None:
    if interaction.type is discord.InteractionType.application_command:
        logger.info("Command name=%s user=%s guild=%s channel=%s",
                    (interaction.data or {}).get("name"), interaction.user.id,
                    interaction.guild_id, interaction.channel_id)


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author == bot.user:
        return
    logger.info("Message user=%s guild=%s channel=%s message=%s",
                message.author.id, message.guild.id if message.guild else None,
                message.channel.id, message.id)
    if bot.intents.message_content:
        logger.info("Message content message=%s content=%r", message.id, message.content)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    logger.error("Command failed user=%s channel=%s", interaction.user.id,
                 interaction.channel_id, exc_info=(type(error), error, error.__traceback__))
    if interaction.response.is_done():
        await interaction.followup.send("명령 실행 중 오류가 발생했습니다.", ephemeral=True)
    else:
        await interaction.response.send_message("명령 실행 중 오류가 발생했습니다.", ephemeral=True)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN 환경변수를 설정해주세요.")
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
