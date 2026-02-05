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
    return any(role.id == CARGO_STAFF_ID for role in member.roles)

def somente_assumidor(interaction):
    dados = tickets_ativos.get(interaction.channel.id)
    return dados and dados["assumido_por"] == interaction.user

async def atualizar_painel_ticket(guild: discord.Guild):
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
            placeholder="Selecione o motivo do ticket",
            options=[discord.SelectOption(label=o, value=o) for o in ticket_opcoes]
        )

    async def callback(self, interaction: discord.Interaction):
        categoria = interaction.guild.get_channel(TICKET_CATEGORIA_ID)
        motivo = self.values[0]

        canal = await interaction.guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=categoria
        )

        await canal.set_permissions(interaction.guild.default_role, view_channel=False)
        await canal.set_permissions(interaction.user, view_channel=True, send_messages=True)

        staff_role = interaction.guild.get_role(CARGO_STAFF_ID)
        await canal.set_permissions(staff_role, view_channel=True, send_messages=False)

        tickets_ativos[canal.id] = {
            "usuario": interaction.user,
            "motivo": motivo,
            "abertura": datetime.utcnow(),
            "assumido_por": None
        }

        embed = discord.Embed(
            title="🎫 Ticket Aberto",
            description=f"Motivo: **{motivo}**\n\nAguarde um atendente.",
            color=discord.Color.blue()
        )

        await canal.send(embed=embed, view=TicketMainView())
        await interaction.response.send_message(f"✅ Ticket criado: {canal.mention}", ephemeral=True)

class RenomearTicketModal(Modal, title="✏️ Renomear Ticket"):
    novo_nome = TextInput(
        label="Novo nome do ticket",
        placeholder="Ex: pagamento-pendente",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.channel.edit(
            name=self.novo_nome.value.lower().replace(" ", "-")
        )
        await interaction.response.send_message(
            "✅ Ticket renomeado com sucesso.",
            ephemeral=True
        )

class UsuarioTicketModal(Modal):
    def __init__(self, acao: str):
        super().__init__(title=f"{acao} usuário do ticket")
        self.acao = acao

        self.usuario = TextInput(
            label="ID do usuário",
            placeholder="Cole o ID do usuário",
            required=True
        )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            user_id = int(self.usuario.value)
        except ValueError:
            await interaction.response.send_message(
                "❌ ID inválido.",
                ephemeral=True
            )
            return

        membro = interaction.guild.get_member(user_id)

        if not membro:
            await interaction.response.send_message(
                "❌ Usuário não encontrado no servidor.",
                ephemeral=True
            )
            return

        if self.acao == "Adicionar":
            await interaction.channel.set_permissions(
                membro,
                view_channel=True,
                send_messages=True
            )
            msg = f"➕ {membro.mention} adicionado ao ticket."
        else:
            await interaction.channel.set_permissions(
                membro,
                view_channel=False
            )
            msg = f"➖ {membro.mention} removido do ticket."

        await interaction.response.send_message(msg, ephemeral=True)



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
                f"Motivo: **{dados['motivo']}**\n"
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

class FecharTicketModal(Modal, title="🔒 Fechar Ticket"):
    motivo = TextInput(
        label="Motivo do encerramento (opcional)",
        style=discord.TextStyle.paragraph,
        required=False,
        placeholder="Ex: Atendimento concluído, cliente inativo..."
    )

    async def on_submit(self, interaction: discord.Interaction):
        dados = tickets_ativos.get(interaction.channel.id)

        if not dados:
            await interaction.response.send_message(
                "❌ Ticket não encontrado.",
                ephemeral=True
            )
            return

        fechamento = datetime.utcnow()
        duracao = fechamento - dados["abertura"]

        # ===== EMBED ESTILO A IMAGEM =====
        embed = discord.Embed(
            title="🔒 Seu Ticket Foi Finalizado!",
            color=discord.Color.dark_red()
        )

        embed.add_field(
            name="🔒 Fechado por",
            value=dados["assumido_por"].mention,
            inline=False
        )

        embed.add_field(
            name="🙋 Responsável pelo atendimento",
            value=dados["assumido_por"].mention,
            inline=False
        )

        embed.add_field(
            name="📂 Categoria do Ticket",
            value=dados["motivo"],
            inline=False
        )

        embed.add_field(
            name="📝 Motivo do Encerramento",
            value=self.motivo.value or "O atendimento foi finalizado.",
            inline=False
        )

        embed.add_field(
            name="⏳ Duração do Atendimento",
            value=str(duracao).split(".")[0],
            inline=False
        )

        # RESPONDE A INTERACTION (resolve o bug)
        await interaction.response.send_message(
            "🔒 Ticket encerrado com sucesso.",
            ephemeral=True
        )

        # DM
        try:
            await dados["usuario"].send(embed=embed)
        except:
            pass

        # LOG
        canal_log = interaction.guild.get_channel(CANAL_LOG_TICKET_ID)
        if canal_log:
            await canal_log.send(embed=embed)

        await interaction.channel.delete()

class TicketStaffView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔔 Notificar membro")
    async def notificar(self, interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)
        await dados["usuario"].send(
            f"📢 Há uma atualização no seu ticket {interaction.channel.mention}"
        )
        await interaction.response.send_message("✅ Membro notificado.", ephemeral=True)

    @discord.ui.button(label="➕ Adicionar usuário")
    async def add_user(self, interaction, _):
        await interaction.response.send_modal(UsuarioTicketModal("Adicionar"))

    @discord.ui.button(label="➖ Remover usuário")
    async def remove_user(self, interaction, _):
        await interaction.response.send_modal(UsuarioTicketModal("Remover"))

    @discord.ui.button(label="✏️ Renomear ticket")
    async def renomear(self, interaction, _):
        await interaction.response.send_modal(RenomearTicketModal())

    @discord.ui.button(label="📞 Suporte via call")
    async def call(self, interaction, _):
        nome_call = f"📞・{interaction.channel.name}"
        categoria = interaction.channel.category

        call = await interaction.guild.create_voice_channel(
            name=nome_call,
            category=categoria
        )

        dados = tickets_ativos.get(interaction.channel.id)

        await call.set_permissions(interaction.guild.default_role, view_channel=False)
        await call.set_permissions(dados["usuario"], view_channel=True, connect=True)
        await call.set_permissions(dados["assumido_por"], view_channel=True, connect=True)

        await interaction.response.send_message(
            f"📞 Call criada: {call.name}",
            ephemeral=True
        )

    @discord.ui.button(label="🔙 Voltar", style=discord.ButtonStyle.danger)
    async def voltar(self, interaction, _):
        dados = tickets_ativos.get(interaction.channel.id)

        embed = discord.Embed(
            title="🎫 Ticket em Atendimento",
            description=(
                f"Motivo: **{dados['motivo']}**\n"
                f"🙋 Assumido por: {dados['assumido_por'].mention}"
            ),
            color=discord.Color.green()
        )

        await interaction.response.edit_message(
            embed=embed,
            view=TicketMainView()
        )

# ========= COMANDOS CONFIG TICKET =========
@bot.tree.command(name="ticket_opcao_add")
async def ticket_opcao_add(interaction: discord.Interaction, nome: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

    if nome in ticket_opcoes:
        return await interaction.response.send_message("⚠️ Opção já existe.", ephemeral=True)

    ticket_opcoes.append(nome)

await atualizar_painel_ticket(interaction.guild)

await interaction.response.send_message(
    f"✅ Opção **{nome}** adicionada e painel atualizado.",
    ephemeral=True
)

@bot.tree.command(name="ticket_opcao_remove")
async def ticket_opcao_remove(interaction: discord.Interaction, nome: str):
    if not is_staff(interaction.user):
        return await interaction.response.send_message("❌ Apenas staff.", ephemeral=True)

    if nome not in ticket_opcoes:
        return await interaction.response.send_message("⚠️ Opção não encontrada.", ephemeral=True)

    ticket_opcoes.remove(nome)
    await interaction.response.send_message(f"🗑️ Opção **{nome}** removida.", ephemeral=True)

ticket_opcoes.remove(nome)

await atualizar_painel_ticket(interaction.guild)

await interaction.response.send_message(
    f"🗑️ Opção **{nome}** removida e painel atualizado.",
    ephemeral=True
)


@bot.tree.command(name="ticket_opcao_list")
async def ticket_opcao_list(interaction: discord.Interaction):
    texto = "\n".join(f"• {o}" for o in ticket_opcoes)
    await interaction.response.send_message(f"📂 Opções:\n{texto}", ephemeral=True)

@bot.tree.command(name="painel_ticket", description="Envia o painel de tickets")
@app_commands.describe(canal="Canal onde o painel de tickets será enviado")
async def painel_ticket(interaction: discord.Interaction, canal: discord.TextChannel):

    if not is_staff(interaction.user):
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎫 Sistema de Atendimento",
        description=(
            "**Bem-vindo ao suporte!**\n\n"
            "Selecione abaixo o motivo do seu ticket.\n"
            "Nossa equipe irá atendê-lo o mais rápido possível.\n\n"
            "_Evite abrir tickets desnecessários._"
        ),
        color=discord.Color.dark_blue()
    )

    msg = await canal.send(embed=embed, view=TicketPanelView())

global PAINEL_TICKET_MESSAGE_ID, PAINEL_TICKET_CHANNEL_ID
PAINEL_TICKET_MESSAGE_ID = msg.id
PAINEL_TICKET_CHANNEL_ID = canal.id

    await interaction.response.send_message(
        f"✅ Painel de ticket enviado em {canal.mention}",
        ephemeral=True
    )

# ========= RUN =========
bot.run(TOKEN)




