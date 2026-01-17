import discord
from discord import ui, app_commands
from discord.ext import commands
from functools import partial

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

# --- A VIEW (INTERFACE) ---
class AchievementsView(discord.ui.View):
    def __init__(self, cog, user):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.active_tab = "all"
        
        self.user_data = self.get_user_data()

        self.tabs = {
            "all": {"label": "Todas", "emoji": "🏆"},
            "xp": {"label": "XP", "emoji": "💬"},
            "voice": {"label": "Voz", "emoji": "🎧"},
            "challenge": {"label": "Games", "emoji": "🧠"},
            "eco": {"label": "Eco", "emoji": "💰"}
        }
        self.create_tab_buttons()

    def get_user_data(self):
        if hasattr(self.cog, 'col'):
            return self.cog.col.find_one({"_id": self.user.id}) or {}
        return {}

    def create_tab_buttons(self):
        self.clear_items()
        for key, info in self.tabs.items():
            button = ui.Button(
                label=info["label"],
                emoji=info["emoji"],
                style=discord.ButtonStyle.success if key == self.active_tab else discord.ButtonStyle.secondary,
                custom_id=f"tab:{key}"
            )
            button.callback = partial(self.change_tab, key)
            self.add_item(button)
        
        refresh_btn = ui.Button(label="Atualizar", style=discord.ButtonStyle.primary, emoji="🎯", row=1)
        refresh_btn.callback = self.refresh_button
        self.add_item(refresh_btn)

    async def change_tab(self, key, interaction: discord.Interaction):
        self.active_tab = key
        self.update_button_styles()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def refresh_button(self, interaction: discord.Interaction):
        self.user_data = self.get_user_data()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    def update_button_styles(self):
        for child in self.children:
            if isinstance(child, ui.Button) and child.custom_id and child.custom_id.startswith("tab:"):
                tab_key = child.custom_id.split(":")[1]
                child.style = discord.ButtonStyle.success if tab_key == self.active_tab else discord.ButtonStyle.secondary
                child.disabled = (tab_key == self.active_tab)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ Apenas você pode usar este painel.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

    def build_embed(self):
        category = self.active_tab
        info = self.tabs.get(category, {"label": "Desconhecido"})
        
        embed = discord.Embed(
            title=f"{info['emoji']} Conquistas: {info['label']}",
            color=discord.Color.gold()
        )
        
        unlocked = set(self.user_data.get("achievements", []))
        achievements_list = ACHIEVEMENTS_BY_CATEGORY.get(category, [])
        
        if not achievements_list:
            embed.description = "*Nenhuma conquista encontrada nesta categoria.*"
            return embed

        texto_conquistas = []
        for key in achievements_list:
            if key not in ACHIEVEMENTS: continue
            title, desc = ACHIEVEMENTS[key].values()

            if key in unlocked:
                texto_conquistas.append(f"✅ **{title}**\n└ {desc}")
            else:
                texto_conquistas.append(f"🔒 **{title}**\n└ ||Bloqueado||")
        
        full_text = "\n\n".join(texto_conquistas)
        
        embed.description = full_text
        embed.set_footer(text=f"Solicitado por {self.user.display_name}", icon_url=self.user.display_avatar.url)
        return embed

class AchievementsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = None

    @app_commands.command(name="conquistas", description="Exibe suas conquistas e medalhas.")
    async def conquistas(self, interaction: discord.Interaction):
        view = AchievementsView(cog=self, user=interaction.user)
        embed = view.build_embed()
        
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(AchievementsCog(bot))