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

# ========= CONFIG =========
CARGOS_AUTORIZADOS = [1468692230607998987]

TICKET_CATEGORIA_ID = 1442639995516096563
CANAL_LOG_TICKET_ID = 1442639996015214690
CARGO_STAFF_ID = 1442639992823484467

PAINEL_TICKET_MESSAGE_ID = None
PAINEL_TICKET_CHANNEL_ID = None

ticket_opcoes = [
    "Suporte",
    "Denúncias",
    "Problema com produtos",
    "Falar com Rugal"
]

tickets_ativos = {}

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
def autorizado(member):
    return any(role.id in CARGOS_AUTORIZADOS for role in member.roles)

def is_staff(member):
    return any(role.id == CARGO_STAFF_ID for role in member.roles)

def somente_assumidor(interaction):
    dados = tickets_ativos.get(interaction.channel.id)
    return dados and dados["assumido_por"] == interaction.user

async def atualizar_painel_ticket(guild):
    if not PAINEL_TICKET_MESSAGE_ID or not PAINEL_TICKET_CHANNEL_ID:
        return
    canal = guild.get_channel(PAINEL_TICKET_CHANNEL_ID)
    if not canal:
        return
    try:
        msg = await canal.fetch_message(PAINEL_TICKET_MESSAGE_ID)
        await msg.edit(view=TicketPanelView())
    except:
        pass

# ========= TICKET SELECT =========
class TicketSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione o motivo do seu ticket",
            options=[discord.SelectOption(label=o) for o in ticket_opcoes]
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

        staff = interaction.guild.get_role(CARGO_STAFF_ID)
        await canal.set_permissions(staff, view_channel=True, send_messages=False)

        tickets_ativos[canal.id] = {
            "usuario": interaction.user,
            "motivo": motivo,
            "abertura": datetime.utcnow(),
            "assumido_por": None
        }

        embed = discord.Embed(
            title="🎫 Ticket Aberto",
            description=f"📂 Motivo: **{motivo}**\n\nAguarde um atendente.",
            color=discord.Color.blue()
        )

        await canal.send(embed=embed, view=TicketMainView())
        await interaction.response.send_message(
            f"✅ Ticket criado em {canal.mention}",
            ephemeral=True
        )

# ========= VIEWS =========
class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketMainView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🙋 Assumir", style=discord.ButtonStyle.success)
    async def assumir(self, interaction, _):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

        dados = tickets_ativos.get(interaction.channel.id)
        if dados["assumido_por"]:
            return await interaction.response.send_message("⚠️ Já assumido.", ephemeral=True)

        dados["assumido_por"] = interaction.user

        await interaction.channel.set_permissions(interaction.user, send_messages=True)

        embed = discord.Embed(
            title="🎫 Ticket em Atendimento",
            description=(
                f"📂 Motivo: **{dados['motivo']}**\n"
                f"🙋 Assumido por: {interaction.user.mention}"
            ),
            color=discord.Color.green()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🛠️ Painel Staff", style=discord.ButtonStyle.secondary)
    async def painel_staff(self, interaction, _):
        if not somente_assumidor(interaction):
            return await interaction.response.send_message("❌ Apenas o responsável.", ephemeral=True)

        embed = discord.Embed(
            title="🛠️ Painel Staff",
            description="Ferramentas internas do ticket",
            color=discord.Color.dark_grey()
        )

        await interaction.response.edit_message(embed=embed, view=TicketStaffView())

    @discord.ui.button(label="🔒 Fechar", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction, _):
        if not somente_assumidor(interaction):
            return await interaction.response.send_message("❌ Apenas o responsável.", ephemeral=True)
        await interaction.response.send_modal(FecharTicketModal())

# ========= MODAIS =========
class FecharTicketModal(Modal, title="🔒 Fechar Ticket"):
    motivo = TextInput(
        label="Motivo (opcional)",
        style=discord.TextStyle.paragraph,
        required=False
    )

    async def on_submit(self, interaction):
        dados = tickets_ativos.get(interaction.channel.id)
        fechamento = datetime.utcnow()
        duracao = fechamento - dados["abertura"]

        embed = discord.Embed(
            title="🔒 Seu Ticket Foi Finalizado!",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="Fechado por", value=dados["assumido_por"].mention, inline=False)
        embed.add_field(name="Responsável", value=dados["assumido_por"].mention, inline=False)
        embed.add_field(name="Categoria", value=dados["motivo"], inline=False)
        embed.add_field(
            name="Motivo do encerramento",
            value=self.motivo.value or "Atendimento finalizado.",
            inline=False
        )
        embed.add_field(
            name="Duração",
            value=str(duracao).split(".")[0],
            inline=False
        )

        await interaction.response.send_message("🔒 Ticket encerrado.", ephemeral=True)

        try:
            await dados["usuario"].send(embed=embed)
        except:
            pass

        canal_log = interaction.guild.get_channel(CANAL_LOG_TICKET_ID)
        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.channel.delete()

class RenomearTicketModal(Modal, title="✏️ Renomear Ticket"):
    nome = TextInput(label="Novo nome", required=True)

    async def on_submit(self, interaction):
        await interaction.channel.edit(name=self.nome.value.lower().replace(" ", "-"))
        await interaction.response.send_message("✅ Ticket renomeado.", ephemeral=True)

class UsuarioTicketModal(Modal):
    def __init__(self, acao):
        super().__init__(title=f"{acao} usuário")
        self.acao = acao
        self.usuario = TextInput(label="ID do usuário", required=True)

    async def on_submit(self, interaction):
        dados = tickets_ativos.get(interaction.channel.id)
        if dados["assumido_por"] != interaction.user:
            return await interaction.response.send_message("❌ Apenas o responsável.", ephemeral=True)

        membro = interaction.guild.get_member(int(self.usuario.value))

        if self.acao == "Adicionar":
            await interaction.channel.set_permissions(membro, view_channel=True, send_messages=True)
            msg = "➕ Usuário adicionado."
        else:
            await interaction.channel.set_permissions(membro, view_channel=False)
            msg = "➖ Usuário removido."

        await interaction.response.send_message(msg, ephemeral=True)

# ========= PAINEL STAFF =========
class TicketStaffView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔔 Notificar membro")
    async def notificar(self, interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)
        await dados["usuario"].send("📢 Há uma atualização no seu ticket.")
        await interaction.response.send_message("✅ Membro notificado.", ephemeral=True)

    @discord.ui.button(label="➕ Adicionar usuário")
    async def add_user(self, interaction, _):
        await interaction.response.send_modal(UsuarioTicketModal("Adicionar"))

    @discord.ui.button(label="➖ Remover usuário")
    async def remove_user(self, interaction, _):
        await interaction.response.send_modal(UsuarioTicketModal("Remover"))

    @discord.ui.button(label="✏️ Renomear")
    async def renomear(self, interaction, _):
        await interaction.response.send_modal(RenomearTicketModal())

    @discord.ui.button(label="📞 Suporte via call")
    async def call(self, interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)
        call = await interaction.guild.create_voice_channel(
            f"📞・{interaction.channel.name}",
            category=interaction.channel.category
        )

        await call.set_permissions(interaction.guild.default_role, view_channel=False)
        await call.set_permissions(dados["usuario"], view_channel=True, connect=True)
        await call.set_permissions(dados["assumido_por"], view_channel=True, connect=True)

        await interaction.response.send_message("📞 Call criada.", ephemeral=True)

    @discord.ui.button(label="🔙 Voltar", style=discord.ButtonStyle.danger)
    async def voltar(self, interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)
        embed = discord.Embed(
            title="🎫 Ticket em Atendimento",
            description=f"📂 Motivo: **{dados['motivo']}**\n🙋 {dados['assumido_por'].mention}",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=TicketMainView())

# ========= COMANDO PAINEL =========
@bot.tree.command(name="painel_ticket")
async def painel_ticket(interaction, canal: discord.TextChannel):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    embed = discord.Embed(
        title="🎫 Sistema de Atendimento",
        description="Selecione abaixo o motivo do seu ticket.",
        color=discord.Color.dark_blue()
    )

    msg = await canal.send(embed=embed, view=TicketPanelView())

    global PAINEL_TICKET_MESSAGE_ID, PAINEL_TICKET_CHANNEL_ID
    PAINEL_TICKET_MESSAGE_ID = msg.id
    PAINEL_TICKET_CHANNEL_ID = canal.id

    await interaction.response.send_message("✅ Painel enviado.", ephemeral=True)

# ========= RUN =========
bot.run(TOKEN)
