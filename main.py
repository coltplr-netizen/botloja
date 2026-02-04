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
CARGOS_AUTORIZADOS = [1468692230607998987]
CANAL_LOG_PEDIDOS = 1442639996015214691

# ========= CONFIG TICKETS =========
TICKET_CATEGORIA_ID = 1442639995516096563
CANAL_LOG_TICKET_ID = 1442639996015214690
CARGO_STAFF_ID = 1442639992823484467

ticket_opcoes = [
    "Suporte",
    "Denúncias",
    "Problema com produtos",
    "Falar com Rugal"
]

tickets_ativos = {}  # channel_id -> dados

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
def montar_embed_painel():
    return discord.Embed(
        title="🛒 Pedir Stock",
        description=(
            "**Clique no botão abaixo para solicitar um produto.**\n\n"
            "• Envie seu pedido\n"
            "• Nossa equipe analisa\n"
            "• Você será avisado quando disponível"
        ),
        color=discord.Color.blurple()
    )

class PedidoModal(Modal, title="📦 Pedido"):
    pedido = TextInput(label="O que você deseja?", required=True)
    observacao = TextInput(label="Observação", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        canal_log = interaction.guild.get_channel(CANAL_LOG_PEDIDOS)

        embed = discord.Embed(title="📦 Novo pedido", color=discord.Color.green())
        embed.add_field(name="Usuário", value=interaction.user.mention, inline=False)
        embed.add_field(name="Pedido", value=self.pedido.value, inline=False)
        embed.add_field(name="Obs", value=self.observacao.value or "Nenhuma", inline=False)

        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.response.send_message("✅ Pedido enviado!", ephemeral=True)

class PainelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Pedir estoque", style=discord.ButtonStyle.primary)
    async def pedir(self, interaction: discord.Interaction, _):
        await interaction.response.send_modal(PedidoModal())

@bot.tree.command(name="painel")
async def painel(interaction: discord.Interaction, canal: discord.TextChannel):
    if not autorizado(interaction.user):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    await canal.send(embed=montar_embed_painel(), view=PainelView())
    await interaction.response.send_message("✅ Painel enviado.", ephemeral=True)

# ========= TICKETS =========
def embed_ticket_aberto(user, motivo):
    embed = discord.Embed(
        title="🎫 Ticket Aberto",
        description=(
            f"Bem-vindo {user.mention}\n\n"
            f"📂 **Motivo:** {motivo}\n\n"
            "Aguarde o atendimento da equipe."
        ),
        color=discord.Color.blue()
    )
    return embed

def embed_painel_staff():
    return discord.Embed(
        title="🛠️ Painel Staff",
        description="Uso exclusivo da equipe.",
        color=discord.Color.dark_grey()
    )

class TicketSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione o motivo do seu ticket",
            options=[discord.SelectOption(label=o, value=o) for o in ticket_opcoes]
        )

    async def callback(self, interaction: discord.Interaction):
        motivo = self.values[0]
        categoria = interaction.guild.get_channel(TICKET_CATEGORIA_ID)

        canal = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}".lower(),
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
            embed=embed_ticket_aberto(interaction.user, motivo),
            view=TicketMainView()
        )

        await interaction.response.send_message(f"✅ Ticket criado: {canal.mention}", ephemeral=True)

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🙋 Assumir", style=discord.ButtonStyle.success)
    async def assumir(self, interaction: discord.Interaction, _):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

        dados = tickets_ativos.get(interaction.channel.id)
        if dados:
            dados["assumido_por"] = interaction.user
            await interaction.channel.send(f"🙋 Assumido por {interaction.user.mention}")
        await interaction.response.defer()

    @discord.ui.button(label="🔒 Fechar", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction: discord.Interaction, _):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

        dados = tickets_ativos.get(interaction.channel.id)
        fechamento = datetime.utcnow()
        duracao = fechamento - dados["abertura"]

        embed = discord.Embed(title="🎫 Ticket Finalizado", color=discord.Color.red())
        embed.add_field(name="Fechado por", value=interaction.user.mention)
        embed.add_field(name="Responsável", value=dados["assumido_por"].mention if dados["assumido_por"] else "Ninguém")
        embed.add_field(name="Motivo", value=dados["motivo"])
        embed.add_field(name="Duração", value=str(duracao).split(".")[0])

        try:
            await dados["usuario"].send(embed=embed)
        except:
            pass

        log = interaction.guild.get_channel(CANAL_LOG_TICKET_ID)
        if log:
            await log.send(embed=embed)

        await interaction.channel.delete()

    @discord.ui.button(label="🛠️ Painel Staff", style=discord.ButtonStyle.secondary)
    async def painel_staff(self, interaction: discord.Interaction, _):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

        await interaction.response.edit_message(embed=embed_painel_staff(), view=TicketStaffView())

class TicketStaffView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔙 Voltar", style=discord.ButtonStyle.danger)
    async def voltar(self, interaction: discord.Interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)
        await interaction.response.edit_message(
            embed=embed_ticket_aberto(dados["usuario"], dados["motivo"]),
            view=TicketMainView()
        )

@bot.tree.command(name="painel_ticket")
async def painel_ticket(interaction: discord.Interaction, canal: discord.TextChannel):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    embed = discord.Embed(
        title="🎫 Sistema de Atendimento",
        description="Selecione o motivo do seu ticket abaixo.",
        color=discord.Color.dark_blue()
    )

    await canal.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Painel enviado.", ephemeral=True)

# ========= COMANDOS CONFIG TICKET =========
@bot.tree.command(name="ticket_opcao_add")
async def ticket_opcao_add(interaction: discord.Interaction, nome: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

    if nome in ticket_opcoes:
        return await interaction.response.send_message("⚠️ Opção já existe.", ephemeral=True)

    ticket_opcoes.append(nome)
    await interaction.response.send_message(f"✅ Opção **{nome}** adicionada.", ephemeral=True)

@bot.tree.command(name="ticket_opcao_remove")
async def ticket_opcao_remove(interaction: discord.Interaction, nome: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

    if nome not in ticket_opcoes:
        return await interaction.response.send_message("⚠️ Opção não encontrada.", ephemeral=True)

    ticket_opcoes.remove(nome)
    await interaction.response.send_message(f"🗑️ Opção **{nome}** removida.", ephemeral=True)

@bot.tree.command(name="ticket_opcao_list")
async def ticket_opcao_list(interaction: discord.Interaction):
    texto = "\n".join(f"• {o}" for o in ticket_opcoes)
    await interaction.response.send_message(f"📂 Opções:\n{texto}", ephemeral=True)

# ========= RUN =========
bot.run(TOKEN)
