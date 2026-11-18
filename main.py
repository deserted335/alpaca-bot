import logging
import os

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
