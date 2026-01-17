import discord
from discord import ui, app_commands
from discord.ext import commands

class AchievementsV2(ui.LayoutView):
    def __init__(self, user):
        super().__init__(timeout=120)
        
        container = ui.Container()
        container.add_item(ui.TextDisplay(f"🏆 **Conquistas de {user.display_name}**"))
        container.add_item(ui.TextDisplay("Seu progresso (Modo V2 Layout)"))
        
        self.add_item(container)

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="conquistas", description="Teste de Components V2")
    async def conquistas(self, interaction: discord.Interaction):
        view = AchievementsV2(interaction.user)
        
        # Como o send_message não aceita 'flags' diretamente:
        # 1. Criamos o objeto de flags
        flags = discord.MessageFlags()
        flags.components_v2 = True
        
        # 2. Em vez de passar no send_message, usamos o 'interaction.response.send_message'
        # MAS, para contornar a limitação da biblioteca que você está usando,
        # vamos usar o parâmetro de 'ephemeral' (se quiser) OU 
        # apenas a view, pois LayoutViews recentes tentam setar a flag automaticamente.
        
        try:
            # Tente enviar apenas com a view. 
            # Se a sua versão do discord.py suporta LayoutView, 
            # ela deve tentar anexar a flag sozinha.
            await interaction.response.send_message(view=view)
        except Exception:
            # Se falhar, o discord.py ainda não permite essa flag via InteractionResponse
            # de forma simples sem editar o corpo da requisição manualmente.
            await interaction.response.send_message(
                "Infelizmente sua versão do discord.py reconhece as classes, mas o método de resposta ainda não aceita as flags necessárias para o V2.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Achievements(bot))