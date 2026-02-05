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
CARGO_STAFF_ID = 1442639992823484467
TICKET_CATEGORIA_ID = 1442639995516096563
CANAL_LOG_TICKET_ID = 1442639996015214690

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
def is_staff(member):
    return any(r.id == CARGO_STAFF_ID for r in member.roles)

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

# ========= SELECT =========
class TicketSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Selecione o motivo do ticket",
            options=[discord.SelectOption(label=o) for o in ticket_opcoes]
        )

    async def callback(self, interaction):
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
            description=f"📂 Motivo: **{motivo}**\n\nAguarde atendimento.",
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
            description=f"📂 {dados['motivo']}\n🙋 {interaction.user.mention}",
            color=discord.Color.green()
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🛠️ Painel Staff")
    async def painel_staff(self, interaction, _):
        if not somente_assumidor(interaction):
            return await interaction.response.send_message("❌ Apenas responsável.", ephemeral=True)

        embed = discord.Embed(
            title="🛠️ Painel Staff",
            description="Ferramentas do ticket",
            color=discord.Color.dark_grey()
        )

        await interaction.response.edit_message(embed=embed, view=TicketStaffView())

    @discord.ui.button(label="🔒 Fechar", style=discord.ButtonStyle.danger)
    async def fechar(self, interaction, _):
        if not somente_assumidor(interaction):
            return await interaction.response.send_message("❌ Apenas responsável.", ephemeral=True)
        await interaction.response.send_modal(FecharTicketModal())

# ========= MODAIS =========
class FecharTicketModal(Modal, title="🔒 Fechar Ticket"):
    motivo = TextInput(label="Motivo (opcional)", required=False)

    async def on_submit(self, interaction):
        dados = tickets_ativos.get(interaction.channel.id)
        duracao = datetime.utcnow() - dados["abertura"]

        embed = discord.Embed(title="🔒 Ticket Finalizado", color=discord.Color.red())
        embed.add_field(name="Responsável", value=dados["assumido_por"].mention, inline=False)
        embed.add_field(name="Categoria", value=dados["motivo"], inline=False)
        embed.add_field(name="Motivo", value=self.motivo.value or "Finalizado", inline=False)
        embed.add_field(name="Duração", value=str(duracao).split(".")[0], inline=False)

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
        await interaction.response.send_message("✅ Renomeado.", ephemeral=True)

class UsuarioTicketModal(Modal):
    def __init__(self, acao):
        super().__init__(title=f"{acao} usuário")
        self.acao = acao
        self.usuario = TextInput(label="ID do usuário", required=True)

    async def on_submit(self, interaction):
        dados = tickets_ativos.get(interaction.channel.id)
        if dados["assumido_por"] != interaction.user:
            return await interaction.response.send_message("❌ Apenas responsável.", ephemeral=True)

        try:
            membro = interaction.guild.get_member(int(self.usuario.value))
        except:
            return await interaction.response.send_message("❌ ID inválido.", ephemeral=True)

        if not membro:
            return await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)

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

    @discord.ui.button(label="🔔 Notificar")
    async def notificar(self, interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)
        await dados["usuario"].send("📢 Atualização no seu ticket.")
        await interaction.response.send_message("✅ Notificado.", ephemeral=True)

    @discord.ui.button(label="➕ Adicionar usuário")
    async def add_user(self, interaction, _):
        await interaction.response.send_modal(UsuarioTicketModal("Adicionar"))

    @discord.ui.button(label="➖ Remover usuário")
    async def remove_user(self, interaction, _):
        await interaction.response.send_modal(UsuarioTicketModal("Remover"))

    @discord.ui.button(label="✏️ Renomear")
    async def renomear(self, interaction, _):
        await interaction.response.send_modal(RenomearTicketModal())

    @discord.ui.button(label="📞 Criar call")
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
            description=f"📂 {dados['motivo']}\n🙋 {dados['assumido_por'].mention}",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=TicketMainView())

# ========= COMANDOS =========
@bot.tree.command(name="painel_ticket")
async def painel_ticket(interaction, canal: discord.TextChannel):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Sem permissão.", ephemeral=True)

    embed = discord.Embed(
        title="🎫 Sistema de Atendimento",
        description="Selecione o motivo abaixo",
        color=discord.Color.dark_blue()
    )

    msg = await canal.send(embed=embed, view=TicketPanelView())

    global PAINEL_TICKET_MESSAGE_ID, PAINEL_TICKET_CHANNEL_ID
    PAINEL_TICKET_MESSAGE_ID = msg.id
    PAINEL_TICKET_CHANNEL_ID = canal.id

    await interaction.response.send_message("✅ Painel enviado.", ephemeral=True)

@bot.tree.command(name="ticket_opcao_add")
async def ticket_opcao_add(interaction, nome: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

    if nome in ticket_opcoes:
        return await interaction.response.send_message("⚠️ Já existe.", ephemeral=True)

    ticket_opcoes.append(nome)
    await atualizar_painel_ticket(interaction.guild)

    await interaction.response.send_message("✅ Opção adicionada.", ephemeral=True)

@bot.tree.command(name="ticket_opcao_remove")
async def ticket_opcao_remove(interaction, nome: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

    if nome not in ticket_opcoes:
        return await interaction.response.send_message("⚠️ Não existe.", ephemeral=True)

    ticket_opcoes.remove(nome)
    await atualizar_painel_ticket(interaction.guild)

    await interaction.response.send_message("🗑️ Opção removida.", ephemeral=True)

@bot.tree.command(name="ticket_opcao_list")
async def ticket_opcao_list(interaction):
    texto = "\n".join(f"• {o}" for o in ticket_opcoes)
    await interaction.response.send_message(f"📂 Opções:\n{texto}", ephemeral=True)

# ========= RUN =========
bot.run(TOKEN)
