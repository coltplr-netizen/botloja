import os
import discord
from discord import app_commands
from discord.ui import View, Modal, TextInput, Select
from datetime import datetime

# ========= TOKEN =========
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN não encontrado")

# ========= INTENTS =========
intents = discord.Intents.default()
intents.members = True

# ========= CONFIG GERAL =========
CARGOS_AUTORIZADOS = [1468692230607998987]  # Cargo que pode usar painel/aprovar
CANAL_LOG_PEDIDOS = 1442639996015214691    # Log dos pedidos da loja

# ========= CONFIG TICKETS =========
TICKET_CATEGORIA_ID = 1442639995516096563
CANAL_LOG_TICKET_ID = 1442639996015214690
CARGO_STAFF_ID = 1442639992823484467

TICKET_OPCOES = [
    "Suporte",
    "Denúncias",
    "Problema com produtos",
    "Falar com Rugal"
]

tickets_ativos = {}  # channel_id -> dados do ticket


# ========= BOT =========
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

def is_staff(member: discord.Member) -> bool:
    return any(role.id == CARGO_STAFF_ID for role in member.roles)

# ========= PAINEL LOJA =========
def montar_embed_painel() -> discord.Embed:
    return discord.Embed(
        title="🛒 Pedir Stock",
        description=(
            "**Clique no botão abaixo para solicitar um produto.**\n\n"
            "📌 **Como funciona:**\n"
            "• Envie seu pedido\n"
            "• Nossa equipe analisa\n"
            "• Você será avisado quando estiver disponível\n\n"
            "⏰ Atendimento 24/7"
        ),
        color=discord.Color.blurple()
    )

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
        canal_log = interaction.guild.get_channel(CANAL_LOG_PEDIDOS)

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

class PainelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Pedir estoque", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(PedidoModal())

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
    pedido="Nome do pedido"
)
async def aprovar(interaction: discord.Interaction, usuarios: str, pedido: str):
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
                        f"👋 Olá, {user.mention}!\n\n"
                        f"✅ Seu pedido **{pedido}** já está disponível na loja.\n"
                        f"Entre em contato para finalizar."
                    )
                    enviados.append(user.mention)
                except:
                    falha.append(user.mention)

    await interaction.response.send_message(
        f"📨 Avisados: {', '.join(enviados) if enviados else 'Nenhum'}\n"
        f"⚠️ Falha: {', '.join(falha) if falha else 'Nenhuma'}",
        ephemeral=True
    )

# ========= TICKETS =========
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=opcao, value=opcao)
            for opcao in TICKET_OPCOES
        ]

        super().__init__(
            placeholder="Selecione o motivo do seu ticket",
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        motivo = self.values[0]
        categoria = interaction.guild.get_channel(TICKET_CATEGORIA_ID)

        canal = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower(),
            category=categoria
        )

        await canal.set_permissions(interaction.guild.default_role, view_channel=False)
        await canal.set_permissions(interaction.user, view_channel=True, send_messages=True)

        for role in interaction.guild.roles:
            if role.id == CARGO_STAFF_ID:
                await canal.set_permissions(role, view_channel=True, send_messages=True)

        tickets_ativos[canal.id] = {
            "usuario": interaction.user,
            "motivo": motivo,
            "abertura": datetime.utcnow(),
            "assumido_por": None
        }

        await canal.send(
            f"{interaction.user.mention} 🎫 Ticket criado (**{motivo}**)",
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ Seu ticket foi criado em {canal.mention}",
            ephemeral=True
        )

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketControlView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🙋 Assumir", style=discord.ButtonStyle.success)
    async def assumir(self, interaction: discord.Interaction, _):
        if not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)
            return

        dados = tickets_ativos.get(interaction.channel.id)
        if dados and not dados["assumido_por"]:
            dados["assumido_por"] = interaction.user
            await interaction.channel.send(
                f"🙋 Ticket assumido por {interaction.user.mention}"
            )

        await interaction.response.defer()

    @discord.ui.button(label="🔒 Fechar", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction: discord.Interaction, _):
        if not is_staff(interaction.user):
            await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)
            return

        dados = tickets_ativos.get(interaction.channel.id)
        if not dados:
            return

        fechamento = datetime.utcnow()
        duracao = fechamento - dados["abertura"]

        embed = discord.Embed(
            title="🎫 Seu Ticket Foi Finalizado!",
            color=discord.Color.red()
        )
        embed.add_field(name="🔒 Fechado por", value=interaction.user.mention, inline=False)
        embed.add_field(
            name="🙋 Responsável pelo atendimento",
            value=dados["assumido_por"].mention if dados["assumido_por"] else "Não assumido",
            inline=False
        )
        embed.add_field(name="📂 Categoria", value=dados["motivo"], inline=False)
        embed.add_field(name="⏳ Duração", value=str(duracao).split(".")[0], inline=False)

        try:
            await dados["usuario"].send(embed=embed)
        except:
            pass

        canal_log = interaction.guild.get_channel(CANAL_LOG_TICKET_ID)
        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.channel.delete()

@bot.tree.command(name="painel_ticket", description="Envia o painel de tickets")
@app_commands.describe(canal="Canal onde o painel será enviado")
async def painel_ticket(interaction: discord.Interaction, canal: discord.TextChannel):
    if not is_staff(interaction.user):
        await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎫 Sistema de Atendimento",
        description=(
            "**HORÁRIOS DE ATENDIMENTO**\n"
            "Segunda a Sábado (08:00 às 22:00)\n\n"
            "**SUPORTE**\n"
            "Selecione abaixo o motivo do seu ticket.\n\n"
            "_Antes de abrir um ticket, leia nossos termos._"
        ),
        color=discord.Color.dark_blue()
    )

    await canal.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Painel enviado.", ephemeral=True)

# ========= RUN =========
bot.run(TOKEN)
