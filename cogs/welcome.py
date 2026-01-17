import discord
from discord import ui, app_commands
from discord.ext import commands

# --- MODAL PARA EDITAR A MENSAGEM ---
class WelcomeMessageModal(ui.Modal, title="Editar Mensagem de Boas-vindas"):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.message_input = ui.TextInput(
            label="Mensagem (Variáveis: {user}, {server})",
            style=discord.TextStyle.paragraph,
            placeholder="Ex: Olá {user}, bem-vindo ao {server}!",
            default=view.current_config.get("message", "Olá {user}, bem-vindo!"),
            required=True,
            max_length=2000
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_text = self.message_input.value
        self.view.cog.col.update_one(
            {"_id": interaction.guild_id},
            {"$set": {"message": new_text}},
            upsert=True
        )
        await self.view.refresh_data_and_ui(interaction)
        await interaction.followup.send("✅ Mensagem atualizada!", ephemeral=True)

# --- VIEW DO SELETOR DE CANAL ---
class ChannelSelectView(ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=60)
        self.parent_view = parent_view

    @ui.select(cls=ui.ChannelSelect, channel_types=[discord.ChannelType.text], placeholder="Selecione o canal de boas-vindas")
    async def select_channel(self, interaction: discord.Interaction, select: ui.ChannelSelect):
        channel = select.values[0]
        self.parent_view.cog.col.update_one(
            {"_id": interaction.guild_id},
            {"$set": {"channel_id": channel.id}},
            upsert=True
        )
        await self.parent_view.refresh_data_and_ui(interaction)
        await interaction.response.edit_message(content=f"✅ Canal definido para: {channel.mention}", view=None)

# --- VIEW PRINCIPAL (DASHBOARD V2) ---
class WelcomeConfigView(ui.LayoutView):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.current_config = {}
        self.refresh_data() 
        self.build_ui()    

    def refresh_data(self):
        data = self.cog.col.find_one({"_id": self.guild_id})
        self.current_config = data if data else {}

    def build_ui(self):
        self.clear_items()
        
        use_container = self.current_config.get("use_container", True)
        
        active = self.current_config.get("active", False)
        channel_id = self.current_config.get("channel_id")
        msg_text = self.current_config.get("message", "Não configurada")

        status_emoji = "🟢" if active else "🔴"
        status_text = "ATIVADO" if active else "DESATIVADO"

        status_container = ui.Container()
        status_container.accent_color = discord.Color.green() if active else discord.Color.red()
        status_container.add_item(ui.TextDisplay(f"## {status_emoji} Status do Sistema: {status_text}"))
        
        if channel_id:
            status_container.add_item(ui.TextDisplay(f"📍 **Canal:** <#{channel_id}>"))
        else:
            status_container.add_item(ui.TextDisplay(f"📍 **Canal:** ⚠️ Nenhum canal definido!"))
            
        self.add_item(status_container)

        msg_container = ui.Container()
        msg_container.accent_color = discord.Color.blurple()
        estilo = "📦 Painel (Container V2)" if use_container else "📝 Texto Simples"
        msg_container.add_item(ui.TextDisplay(f"🎨 **Estilo Atual:** {estilo}\n\n**Mensagem:**\n_{msg_text}_"))
        msg_container.add_item(ui.TextDisplay(f"📝 **Mensagem Atual:**\n_{msg_text}_"))
        self.add_item(msg_container)

        row = ui.ActionRow()
        
        btn_toggle = ui.Button(
            label="Desativar" if active else "Ativar",
            style=discord.ButtonStyle.danger if active else discord.ButtonStyle.success,
            emoji="🔌"
        )
        btn_toggle.callback = self.toggle_system
        row.add_item(btn_toggle)

        btn_channel = ui.Button(label="Definir Canal", style=discord.ButtonStyle.secondary, emoji="📢")
        btn_channel.callback = self.open_channel_select
        row.add_item(btn_channel)

        btn_edit = ui.Button(label="Editar Texto", style=discord.ButtonStyle.primary, emoji="✏️")
        btn_edit.callback = self.open_edit_modal
        row.add_item(btn_edit)
        
        btn_style = ui.Button(label="Mudar para Texto" if use_container else "Mudar para Painel", style=discord.ButtonStyle.secondary, emoji="🖼️" if use_container else "📜")
        btn_style.callback = self.toggle_style
        row.add_item(btn_style)

        btn_test = ui.Button(label="Testar", style=discord.ButtonStyle.secondary, emoji="📨")
        btn_test.callback = self.test_message
        row.add_item(btn_test)

        self.add_item(row)
        
    async def toggle_style(self, interaction: discord.Interaction):
        current_style = self.current_config.get("use_container", True)
        self.cog.col.update_one(
            {"_id": self.guild_id},
            {"$set": {"use_container": not current_style}},
            upsert=True
        )
        await self.refresh_data_and_ui(interaction)
        
    async def refresh_data_and_ui(self, interaction: discord.Interaction):
        self.refresh_data()
        self.build_ui()
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(view=self)
            else:
                await interaction.edit_original_response(view=self)
        except:
            pass

    # --- CALLBACKS DOS BOTÕES ---
    async def toggle_system(self, interaction: discord.Interaction):
        new_status = not self.current_config.get("active", False)
        self.cog.col.update_one(
            {"_id": self.guild_id},
            {"$set": {"active": new_status}},
            upsert=True
        )
        await self.refresh_data_and_ui(interaction)

    async def open_channel_select(self, interaction: discord.Interaction):
        view = ChannelSelectView(self)
        await interaction.response.send_message("Selecione o canal abaixo:", view=view, ephemeral=True)

    async def open_edit_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WelcomeMessageModal(self))

    async def test_message(self, interaction: discord.Interaction):
        active = self.current_config.get("active", False)
        channel_id = self.current_config.get("channel_id")
        
        if not channel_id:
            return await interaction.response.send_message("❌ Configure um canal primeiro!", ephemeral=True)
        
        await self.cog.send_welcome_message(interaction.user, is_test=True)
        await interaction.response.send_message("📨 Mensagem de teste enviada!", ephemeral=True)

# --- A COG PRINCIPAL ---
class WelcomeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        database = getattr(bot, "db", None)
        if database is not None:
            self.col = database.guild_config
        else:
            self.col = None

    async def send_welcome_message(self, member, is_test=False):
        if self.col is None: return

        data = self.col.find_one({"_id": member.guild.id})
        if not data: return

        if not is_test and not data.get("active", False):
            return

        channel_id = data.get("channel_id")
        channel = member.guild.get_channel(channel_id)
        if not channel: return

        raw_text = data.get("message", "Olá {user}, bem-vindo ao {server}!")
        final_text = raw_text.replace("{user}", member.mention)\
                             .replace("{server}", member.guild.name)\
                             .replace("{count}", str(member.guild.member_count))

        use_container = data.get("use_container", True)

        if use_container:
            welcome_container = ui.Container()
            welcome_container.accent_color = discord.Color.teal()
            welcome_container.add_item(ui.TextDisplay(final_text))
            
            view = ui.LayoutView()
            view.add_item(welcome_container)
            await channel.send(view=view)
        else:
            await channel.send(final_text)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.send_welcome_message(member)


    setup_group = app_commands.Group(name="setup", description="Painel de configurações do servidor")
    
    @setup_group.command(name="welcome", description="Configura as boas-vindas")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome(self, interaction: discord.Interaction):
        view = WelcomeConfigView(self, interaction.guild_id)
        await interaction.response.send_message(view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))