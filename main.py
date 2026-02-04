import os
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands sincronizados")

    async def on_ready(self):
        print(f"🤖 Bot online como {self.user}")

bot = Bot()

@bot.tree.command(name="ping", description="Testa se o bot está online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Bot online.")

bot.run(TOKEN)