import os
import discord
from discord import app_commands
from discord.ui import View, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não encontrado")

intents = discord.Intents.default()

# ========= CONFIGURAÇÕES =========
CARGOS_AUTORIZADOS = [1468692230607998987]  # ID do cargo autorizado
CANAL_LOG_ID = 1442639996015214691          # ID do canal de logs
# =================================

# Estoques (em memória)
estoques = [
    "Netflix",
    "Spotify",
    "Amazon Prime"
]


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"🤖 Online como {self.user}")


bot = Bot()


# ========= FUNÇÃO AUXILIAR =========
def usuario_autorizado(member: discord.Member) -> bool:
    return any(role.id in CARGOS_AUTORIZADOS for role in member.roles)


# ========= MODAL =========
class PedidoEstoqueModal(Modal, title="📦 Pedido de Estoque"):
    estoque = TextInput(
        label="Qual estoque deseja?",
        placeholder="Ex: Netflix",
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


# ========= VIEW =========
class PainelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Pedir estoque", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(PedidoEstoqueModal())


# ========= COMANDO PAINEL =========
@bot.tree.command(name="painel", description="Envia o painel de pedidos de estoque")
@app_commands.describe(canal="Canal onde o painel será enviado")
async def painel(interaction: discord.Interaction, canal: discord.TextChannel):

    if not usuario_autorizado(interaction.user):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🛒 Pedido de Estoque",
        description=(
            "Clique no botão abaixo para solicitar um estoque.\n\n"
            "**Estoques disponíveis:**\n"
            + ("\n".join(f"• {e}" for e in estoques) if estoques else "Nenhum estoque disponível")
        ),
        color=discord.Color.blurple()
    )

    await canal.send(embed=embed, view=PainelView())

    await interaction.response.send_message(
        f"✅ Painel enviado em {canal.mention}",
        ephemeral=True
    )


# ========= COMANDOS DE ESTOQUE =========

@bot.tree.command(name="add_stock", description="Adiciona um estoque")
async def add_stock(interaction: discord.Interaction, nome: str):

    if not usuario_autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    if nome in estoques:
        await interaction.response.send_message("⚠️ Esse estoque já existe.", ephemeral=True)
        return

    estoques.append(nome)
    await interaction.response.send_message(f"✅ Estoque **{nome}** adicionado.", ephemeral=True)


@bot.tree.command(name="remove_stock", description="Remove um estoque")
async def remove_stock(interaction: discord.Interaction, nome: str):

    if not usuario_autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    if nome not in estoques:
        await interaction.response.send_message("⚠️ Estoque não encontrado.", ephemeral=True)
        return

    estoques.remove(nome)
    await interaction.response.send_message(f"🗑️ Estoque **{nome}** removido.", ephemeral=True)


@bot.tree.command(name="list_stock", description="Lista os estoques disponíveis")
async def list_stock(interaction: discord.Interaction):

    if not usuario_autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    if not estoques:
        msg = "Nenhum estoque cadastrado."
    else:
        msg = "\n".join(f"• {e}" for e in estoques)

    await interaction.response.send_message(
        f"📦 **Estoques cadastrados:**\n{msg}",
        ephemeral=True
    )


bot.run(TOKEN)

