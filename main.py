import os
import discord
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não encontrado")

intents = discord.Intents.default()

# ===== CONFIGURAÇÕES =====
CARGOS_AUTORIZADOS = [1468692230607998987]  # IDs dos cargos que podem usar /painel
CANAL_LOG_ID = 1442639996015214691          # ID do canal de logs

ESTOQUES_DISPONIVEIS = [
    "Netflix",
    "Spotify",
    "Amazon Prime"
]
# =========================


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"🤖 Online como {self.user}")


bot = Bot()


# ===== MODAL =====
class PedidoEstoqueModal(Modal, title="📦 Pedido de Estoque"):
    estoque = TextInput(
        label="Qual estoque você quer?",
        placeholder="Ex: Netflix, Spotify...",
        required=True
    )

    observacao = TextInput(
        label="Observação (opcional)",
        style=discord.TextStyle.paragraph,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        canal_log = interaction.guild.get_channel(CANAL_LOG_ID)

        embed = discord.Embed(
            title="📦 Novo pedido de estoque",
            color=discord.Color.green()
        )
        embed.add_field(name="Usuário", value=interaction.user.mention, inline=False)
        embed.add_field(name="Estoque", value=self.estoque.value, inline=False)
        embed.add_field(name="Observação", value=self.observacao.value or "Nenhuma", inline=False)

        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.response.send_message(
            "✅ Seu pedido foi enviado com sucesso!",
            ephemeral=True
        )


# ===== BOTÃO =====
class PainelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Pedir estoque", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(PedidoEstoqueModal())


# ===== COMANDO =====
@bot.tree.command(name="painel", description="Envia o painel de pedidos de estoque")
async def painel(interaction: discord.Interaction):

    # Verificar cargos
    if not any(role.id in CARGOS_AUTORIZADOS for role in interaction.user.roles):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🛒 Painel de Estoque",
        description=(
            "Clique no botão abaixo para solicitar um estoque.\n\n"
            "**Estoques disponíveis:**\n"
            + "\n".join(f"• {e}" for e in ESTOQUES_DISPONIVEIS)
        ),
        color=discord.Color.blurple()
    )

    await interaction.response.send_message(
        embed=embed,
        view=PainelView()
    )


bot.run(TOKEN)

