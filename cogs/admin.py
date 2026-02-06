import discord
from discord import app_commands, ui
from discord.ext import commands

class EmbedEditorModal(ui.Modal, title="📝 Criar/Editar Embed"):
    embed_title = ui.TextInput(
        label="Título do Embed",
        placeholder="Digite o título aqui...",
        max_length=256,
        required=False
    )
    embed_desc = ui.TextInput(
        label="Descrição",
        placeholder="Use Markdown para formatar...",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True
    )
    embed_color = ui.TextInput(
        label="Cor Hex (Ex: #7289DA)",
        placeholder="Deixe vazio para azul padrão",
        min_length=7,
        max_length=7,
        required=False
    )
    embed_image = ui.TextInput(
        label="Link da Imagem",
        placeholder="https://exemplo.com/imagem.png",
        required=False
    )

    def __init__(self, view):
        super().__init__()
        self.view = view
        self.embed_title.default = self.view.current_embed.title
        self.embed_desc.default = self.view.current_embed.description
        if self.view.current_embed.image:
            self.embed_image.default = self.view.current_embed.image.url

    async def on_submit(self, interaction: discord.Interaction):
        self.view.current_embed.title = self.embed_title.value
        self.view.current_embed.description = self.embed_desc.value
        
        if self.embed_color.value:
            try:
                hex_value = self.embed_color.value.lstrip('#')
                self.view.current_embed.color = discord.Color(int(hex_value, 16))
            except ValueError:
                return await interaction.response.send_message("❌ Formato de cor inválido! Use #RRGGBB.", ephemeral=True)

        if self.embed_image.value:
            if self.embed_image.value.startswith(("http://", "https://")):
                self.view.current_embed.set_image(url=self.embed_image.value)
            else:
                return await interaction.response.send_message("❌ Link de imagem inválido!", ephemeral=True)
        else:
            self.view.current_embed.set_image(url=None)
        
        await self.view.update_preview(interaction)

class EmbedControlView(ui.View):
    def __init__(self, user):
        super().__init__(timeout=600)
        self.user = user
        self.current_embed = discord.Embed(
            title="Título Exemplo",
            description="Use o botão editar para começar.",
            color=discord.Color.blue()
        )

    async def update_preview(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.current_embed, view=self)

    @ui.button(label="Configurar Embed", style=discord.ButtonStyle.primary, emoji="⚙️")
    async def edit_embed(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(EmbedEditorModal(self))

    @ui.button(label="Enviar no Canal", style=discord.ButtonStyle.success, emoji="🚀")
    async def send_to_channel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.channel.send(embed=self.current_embed)
        await interaction.response.edit_message(content="✅ Embed enviado!", embed=None, view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
            return False
        return True

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embedpanel", description="Abre o painel de criação de embeds (Admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def embed_panel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Apenas administradores podem usar este painel!", 
                ephemeral=True
            )
        
        view = EmbedControlView(interaction.user)
        await interaction.response.send_message(
            "🛠️ **Painel de Edição de Embed**\nUse os botões abaixo para configurar.",
            embed=view.current_embed,
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Admin(bot))