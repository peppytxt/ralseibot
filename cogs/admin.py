import discord
from discord import app_commands, ui
from discord.ext import commands

class EmbedEditorModal(ui.Modal, title="📝 Criar/Editar Embed"):
    embed_title = ui.TextInput(
        label="Título do Embed",
        placeholder="Digite o título aqui...",
        max_length=256,
        required=True
    )
    embed_desc = ui.TextInput(
        label="Descrição",
        placeholder="Use Markdown para formatar (ex: **negrito**)",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.current_embed.title = self.embed_title.value
        self.view.current_embed.description = self.embed_desc.value
        await self.view.update_preview(interaction)

class EmbedControlView(ui.View):
    def __init__(self, user):
        super().__init__(timeout=600)
        self.user = user
        self.current_embed = discord.Embed(
            title="Título Exemplo",
            description="Esta é uma prévia do seu embed.",
            color=discord.Color.blue()
        )

    async def update_preview(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.current_embed, view=self)

    @ui.button(label="Editar Texto", style=discord.ButtonStyle.primary, emoji="✍️")
    async def edit_text(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(EmbedEditorModal(self))

    @ui.button(label="Trocar Cor", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def change_color(self, interaction: discord.Interaction, button: ui.Button):
        self.current_embed.color = discord.Color.random()
        await self.update_preview(interaction)

    @ui.button(label="Enviar no Canal", style=discord.ButtonStyle.success, emoji="🚀")
    async def send_to_channel(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.channel.send(embed=self.current_embed)
        await interaction.response.edit_message(content="✅ Embed enviado com sucesso!", embed=None, view=None)
        self.stop()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Apenas o autor do comando pode usar este painel.", ephemeral=True)
            return False
        return True

# --- COG PRINCIPAL ---
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="embedpanel", description="Abre o painel de criação de embeds (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def embed_panel(self, interaction: discord.Interaction):
        view = EmbedControlView(interaction.user)
        await interaction.response.send_message(
            "🛠️ **Painel de Edição de Embed**\nUse os botões abaixo para configurar.",
            embed=view.current_embed,
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(Admin(bot))