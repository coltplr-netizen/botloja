import os
import discord
from discord import app_commands
from discord.ui import View, Modal, TextInput

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não encontrado")

intents = discord.Intents.default()
intents.members = True

# ========= CONFIG =========
CARGOS_AUTORIZADOS = [1468692230607998987]  # ID do cargo da staff
CANAL_LOG_ID = 1442639996015214691          # ID do canal de logs
# ==========================


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
    return discord.Embed(
        title="🛒 Pedir Stock",
        description=(
            "**Clique no botão abaixo para solicitar um produto.**\n\n"
            "📌 **Como funciona:**\n"
            "**• Envie seu pedido**\n"
            "**• Nossa equipe analisa**\n"
            "**• Você será avisado quando estiver disponível**\n\n"
            "**⏰ Atendimento 24/7**"
        ),
        color=discord.Color.blurple()
    )


# ========= MODAL =========
class PedidoModal(Modal, title="📦 Pedido"):
    pedido = TextInput(
        label="O que você deseja?",
        placeholder="Descreva seu pedido",
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
        embed.add_field(name="Pedido", value=self.pedido.value, inline=False)
        embed.add_field(
            name="Observação",
            value=self.observacao.value or "Nenhuma",
            inline=False
        )

        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.response.send_message(
            "✅ Sua solicitação foi enviada! Aguarde.",
            ephemeral=True
        )


# ========= VIEW =========
class PainelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Pedir estoque", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(PedidoModal())


# ========= COMANDO PAINEL =========
@bot.tree.command(name="painel", description="Envia o painel da loja")
@app_commands.describe(canal="Canal onde o painel será enviado")
async def painel(interaction: discord.Interaction, canal: discord.TextChannel):

    if not autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    await canal.send(embed=montar_embed_painel(), view=PainelView())

    await interaction.response.send_message(
        f"✅ Painel enviado em {canal.mention}",
        ephemeral=True
    )


# ========= COMANDO APROVAR =========
@bot.tree.command(name="aprovar", description="Avisa usuários que o pedido está disponível")
@app_commands.describe(
    usuarios="Usuários que serão avisados",
    pedido="Nome do pedido (ex: Carro)"
)
async def aprovar(
    interaction: discord.Interaction,
    usuarios: str,
    pedido: str
):
    if not autorizado(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    enviados = []
    falha = []

    for palavra in usuarios.split():
        if palavra.startswith("<@") and palavra.endswith(">"):
            user_id = int(palavra.replace("<@", "").replace(">", "").replace("!", ""))
            user = interaction.guild.get_member(user_id)

            if user:
                try:
                    await user.send(
                        f"**👋 Olá, {user.mention}!**\n\n"
                        f"**✅ Seu pedido {pedido} já está disponível na loja.**\n"
                        f"**Compre enquanto há tempo 👀.**\n"
                    )
                    enviados.append(user.mention)
                except:
                    falha.append(user.mention)

    await interaction.response.send_message(
        f"📨 Avisados: {', '.join(enviados) if enviados else 'Nenhum'}\n"
        f"⚠️ Falha: {', '.join(falha) if falha else 'Nenhuma'}",
        ephemeral=True
    )


bot.run(TOKEN)
