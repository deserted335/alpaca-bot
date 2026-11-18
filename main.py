import logging
import os
import io

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


async def send_result(interaction: discord.Interaction, content: str, file: discord.File | None = None) -> None:
    """작업 결과를 명령을 실행한 텍스트 채널에 일반 메시지로 게시합니다."""
    content = content[:1900]
    channel = interaction.channel
    if isinstance(channel, discord.abc.Messageable):
        try:
            if file:
                await channel.send(content, file=file)
            else:
                await channel.send(content)
        except discord.HTTPException:
            logger.exception("Failed to send result to channel=%s", interaction.channel_id)
            if file:
                file.reset()
        else:
            # 결과를 채널에 게시했으니 본인만 보이는 "생각 중..." 응답은 지웁니다.
            try:
                await interaction.delete_original_response()
            except discord.HTTPException:
                logger.warning("Failed to delete deferred response", exc_info=True)
            return
    # 채널에 보낼 수 없으면(권한 부족, DM 등) 기존 방식으로 대신 응답합니다.
    if file:
        await interaction.followup.send(content, file=file, ephemeral=True)
    else:
        await interaction.followup.send(content, ephemeral=True)


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
    await send_result(interaction, message)


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
    await send_result(interaction, message)


@bot.tree.command(name="develop", description="Claude에게 저장소 수정 작업을 요청합니다.")
@app_commands.describe(task="수행할 작업")
async def develop(interaction: discord.Interaction, task: str) -> None:
    owner_id = os.getenv("DISCORD_OWNER_ID", "")
    if not owner_id.isdecimal() or interaction.user.id != int(owner_id):
        await interaction.response.send_message("이 명령을 실행할 권한이 없습니다.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
            async with session.post("http://worker:8080/develop", json={"task": task}) as response:
                result = await response.json()
        message = result.get("message", "작업 결과가 없습니다.")
        diff = result.get("diff", "")
        if diff:
            attachment = discord.File(io.BytesIO(diff.encode("utf-8")), filename="changes.patch")
            await send_result(interaction, message, file=attachment)
        else:
            await send_result(interaction, message)
    except (aiohttp.ClientError, TimeoutError):
        logger.exception("Development request failed")
        await send_result(interaction, "작업 서버에 연결할 수 없거나 시간이 초과됐습니다.")


@bot.tree.command(name="pr", description="검토한 작업으로 GitHub 초안 PR을 만듭니다.")
@app_commands.describe(job_id="/develop 결과에 표시된 작업 ID")
async def create_pr(interaction: discord.Interaction, job_id: str) -> None:
    owner_id = os.getenv("DISCORD_OWNER_ID", "")
    if not owner_id.isdecimal() or interaction.user.id != int(owner_id):
        await interaction.response.send_message("이 명령을 실행할 권한이 없습니다.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True, ephemeral=True)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as session:
            async with session.post("http://worker:8080/pr", json={"job_id": job_id}) as response:
                result = await response.json()
        await send_result(interaction, result.get("message", "PR 결과가 없습니다."))
    except (aiohttp.ClientError, TimeoutError):
        logger.exception("PR request failed")
        await send_result(interaction, "PR 요청에 실패했습니다. GitHub 브랜치와 서버 로그를 확인하세요.")


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
