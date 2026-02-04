import os
import discord
from discord import app_commands
from discord.ui import View, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não encontrado")

intents = discord.Intents.default()

# ========= CONFIG =========
CARGOS_AUTORIZADOS = [1468692230607998987]
CANAL_LOG_ID = 1442639996015214691
# ==========================

# Opções de estoque (tipos)
estoques = ["Netflix", "Spotify", "Amazon Prime"]

# Referência do painel
painel_info = {
    "canal_id": None,
    "mensagem_id": None
}


class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"🤖 Online como {self.user}")


bot = Bot()


# ========= HELPERS =========
def autorizado(member: discord.Member) -> bool:
    return any(role.id in CARGOS_AUTORIZADOS for role in member.roles)


def montar_embed_painel() -> discord.Embed:
    descricao = (
        "**Estoques disponíveis:**\n"
        + ("\n".join(f"• {e}" for e in estoques) if estoques else "Nenhum disponível")
    )

    return discord.Embed(
        title="🛒 Pedir Estoque",
        description=(
            "Está precisando de algo que está fora de estoque? Peça aqui!.\n\n"
            + descricao
        ),
        color=discord.Color.blurple()
    )


async def atualizar_painel(guild: discord.Guild):
    if not painel_info["canal_id"] or not painel_info["mensagem_id"]:
        return

    canal = guild.get_channel(painel_info["canal_id"])
    if not canal:
        return

    try:
        msg = await canal.fetch_message(painel_info["mensagem_id"])
        await msg.edit(embed=montar_embed_painel(), view=PainelView())
    except discord.NotFound:
        pass


# ========= MODAL =========
class PedidoEstoqueModal(Modal, title="📦 Pedido de Estoque"):
    estoque = TextInput(
        label="Qual estoque você quer?",
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

        embed = discord.Embed(title="📦 Novo pedido", color=discord.Color.green())
        embed.add_field(name="Usuário", value=interaction.user.mention, inline=False)
        embed.add_field(name="Estoque", value=self.estoque.value, inline=False)
        embed.add_field(name="Obs", value=self.observacao.value or "Nenhuma", inline=False)

        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.response.send_message(
            "✅ Pedido enviado com sucesso!",
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
@bot.tree.command(name="painel", description="Envia o painel de estoque")
@app_commands.describe(canal="Canal onde o painel será enviado")
async def painel(interaction: discord.Interaction, canal: discord.TextChannel):

    if not autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    msg = await canal.send(embed=montar_embed_painel(), view=PainelView())

    painel_info["canal_id"] = canal.id
    painel_info["mensagem_id"] = msg.id

    await interaction.response.send_message(
        f"✅ Painel enviado em {canal.mention}",
        ephemeral=True
    )


# ========= STOCK OPTIONS =========

@bot.tree.command(name="stock_option_add", description="Adiciona opções de estoque (separadas por vírgula)")
async def stock_option_add(interaction: discord.Interaction, nomes: str):

    if not autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    adicionados = []
    for nome in [n.strip() for n in nomes.split(",")]:
        if nome and nome not in estoques:
            estoques.append(nome)
            adicionados.append(nome)

    await atualizar_painel(interaction.guild)

    await interaction.response.send_message(
        f"✅ Adicionados: {', '.join(adicionados) if adicionados else 'Nenhum'}",
        ephemeral=True
    )


@bot.tree.command(name="stock_option_remove", description="Remove opções de estoque (separadas por vírgula)")
async def stock_option_remove(interaction: discord.Interaction, nomes: str):

    if not autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    removidos = []
    for nome in [n.strip() for n in nomes.split(",")]:
        if nome in estoques:
            estoques.remove(nome)
            removidos.append(nome)

    await atualizar_painel(interaction.guild)

    await interaction.response.send_message(
        f"🗑️ Removidos: {', '.join(removidos) if removidos else 'Nenhum'}",
        ephemeral=True
    )


@bot.tree.command(name="stock_option_list", description="Lista as opções de estoque")
async def stock_option_list(interaction: discord.Interaction):

    if not autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    msg = "\n".join(f"• {e}" for e in estoques) if estoques else "Nenhum estoque."
    await interaction.response.send_message(f"📦 **Opções:**\n{msg}", ephemeral=True)


bot.run(TOKEN)
