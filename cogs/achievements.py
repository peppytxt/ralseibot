import discord
from discord import ui, app_commands
from discord.ext import commands
from functools import partial

# --- DADOS ---
ACHIEVEMENTS = {
    "messages_1000": {"title": "📨 Comunicador", "description": "Você enviou 1.000 mensagens."},
    "voice_10h": {"title": "🎧 Morador da Call", "description": "Você ficou 10 horas em call."},
    "challenge_first_win": {"title": "🏅 Primeira Vitória", "description": "Você venceu seu primeiro challenge."},
    "coins_10000": {"title": "💰 Rico", "description": "Acumulou 10k coins."} 
}

ACHIEVEMENTS_BY_CATEGORY = {
    "all": ["voice_10h", "challenge_first_win", "coins_10000"],
    "voice": ["voice_10h"],
    "challenge": ["challenge_first_win"],
    "eco": ["coins_10000"],
}

# --- VIEW V2 (LAYOUT) ---
class AchievementsView(ui.LayoutView): # Mudança para LayoutView
    def __init__(self, cog, user):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.active_tab = "all"
        self.user_data = self.get_user_data()

        self.tabs = {
            "all": {"label": "Todas", "emoji": "🏆"},
            "voice": {"label": "Voz", "emoji": "🎧"},
            "challenge": {"label": "Games", "emoji": "📺"},
            "eco": {"label": "Eco", "emoji": "💰"}
        }
        
        self.refresh_interface()

    def get_user_data(self):
        # Comparação explícita com 'is not None'
        if hasattr(self.cog, 'col') and self.cog.col is not None:
            return self.cog.col.find_one({"_id": self.user.id}) or {}
        return {"achievements": []}

    def refresh_interface(self):
        """Reconstrói todos os componentes da View V2"""
        self.clear_items()
        
        # 1. Container de Cabeçalho (Substitui o topo do Embed)
        info = self.tabs.get(self.active_tab, {"label": "Todas", "emoji": "🏆"})
        header = ui.Container(
            title=f"{info['emoji']} Categoria: {info['label']}",
            accent_color=discord.Color.gold()
        )
        header.add_item(ui.TextDisplay(f"Olá {self.user.display_name}, veja seu progresso abaixo:"))
        self.add_item(header)

        # 2. Container de Conteúdo (Lista de Achievements)
        unlocked = set(self.user_data.get("achievements", []))
        achievements_list = ACHIEVEMENTS_BY_CATEGORY.get(self.active_tab, [])

        content_container = ui.Container()
        
        if not achievements_list:
            content_container.add_item(ui.TextDisplay("*Nenhuma conquista aqui ainda.*"))
        else:
            for key in achievements_list:
                if key not in ACHIEVEMENTS: continue
                data = ACHIEVEMENTS[key]
                status = "✅" if key in unlocked else "🔒"
                # No V2, TextDisplay suporta Markdown
                content_container.add_item(
                    ui.TextDisplay(f"{status} **{data['title']}**\n└ {data['description']}")
                )
        
        self.add_item(content_container)

        # 3. Action Row para os Botões (Seleção de Abas)
        button_row = ui.ActionRow()
        for key, tab_info in self.tabs.items():
            is_active = (key == self.active_tab)
            btn = ui.Button(
                label=tab_info["label"],
                emoji=tab_info["emoji"],
                style=discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary,
                disabled=is_active
            )
            btn.callback = partial(self.change_tab, key)
            button_row.add_item(btn)
        
        self.add_item(button_row)

        # 4. Botão de Refresh em uma linha separada
        refresh_row = ui.ActionRow()
        refresh_btn = ui.Button(label="Atualizar Dados", style=discord.ButtonStyle.primary, emoji="🎯")
        refresh_btn.callback = self.refresh_button
        refresh_row.add_item(refresh_btn)
        self.add_item(refresh_row)

    async def change_tab(self, key, interaction: discord.Interaction):
        self.active_tab = key
        self.refresh_interface()
        await interaction.response.edit_message(view=self)

    async def refresh_button(self, interaction: discord.Interaction):
        self.user_data = self.get_user_data()
        self.refresh_interface()
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Este painel não é seu.", ephemeral=True)
            return False
        return True

# --- COG ---
class AchievementsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        database = getattr(bot, "db", None)
        
        if database is not None:
            self.col = database.achievements
        else:
            self.col = None
            print("AVISO: Conexão com o banco de dados não encontrada no objeto 'bot'.")

    @app_commands.command(name="conquistas", description="Conquistas feitas pelo usuário")
    async def conquistas(self, interaction: discord.Interaction):
        view = AchievementsView(cog=self, user=interaction.user)
        # No V2, não enviamos mais Embed, enviamos apenas a View que contém os Containers
        await interaction.response.send_message(view=view)

async def setup(bot):
    await bot.add_cog(AchievementsCog(bot))