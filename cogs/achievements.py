import discord
from discord import ui, app_commands
from discord.ext import commands
from functools import partial

# --- DADOS ---
ACHIEVEMENTS = {
    "first_message": {"title": "💬 Primeira mensagem!", "description": "Você enviou sua primeira mensagem."},
    "messages_1000": {"title": "📨 Comunicador", "description": "Você enviou 1.000 mensagens."},
    "voice_10h": {"title": "🎧 Morador da Call", "description": "Você ficou 10 horas em call."},
    "challenge_first_win": {"title": "🏅 Primeira Vitória", "description": "Você venceu seu primeiro challenge."},
    "coins_100000": {"title": "💰 Rico", "description": "Acumulou 100k de ralcoins."} 
}

ACHIEVEMENTS_BY_CATEGORY = {
    "all": ["first_message", "messages_1000", "voice_10h", "challenge_first_win", "coins_100000"],
    "xp": ["first_message"],
    "voice": ["voice_10h"],
    "challenge": ["challenge_first_win"],
    "eco": ["coins_100000"],
}

# --- VIEW V2 (LAYOUT) ---
class AchievementsView(ui.LayoutView):
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
            "eco": {"label": "Economia", "emoji": "💰"}
        }
        
        self.refresh_interface()

    def get_user_data(self):
        # Comparação explícita com 'is not None'
        if hasattr(self.cog, 'col') and self.cog.col is not None:
            return self.cog.col.find_one({"_id": self.user.id}) or {}
        return {"achievements": []}

    def refresh_interface(self):
        self.clear_items()

        info = self.tabs.get(self.active_tab, {"label": "Todas", "emoji": "🏆"})

        header = ui.Container()

        header.title = f"{info['emoji']} Categoria: {info['label']}"
        header.accent_color = discord.Color.gold()
        
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
        
        if not hasattr(bot, 'voice_times'):
            bot.voice_times = {}
            
        database = getattr(bot, "db", None)
        
        if database is not None:
            self.col = database.achievements
        else:
            self.col = None
            print("AVISO: Conexão com o banco de dados não encontrada no objeto 'bot'.")
            
    async def give_achievement(self, user_id: int, achievement_key: str):
        """Função central para registrar a conquista no banco de dados."""
        if self.col is None:
            return

        result = await self.col.update_one(
                {"_id": user_id},
                {"$addToSet": {"achievements": achievement_key}},
                upsert=True
            )

        if result.modified_count > 0 or result.upserted_id is not None:
            print(f"DEBUG: {user_id} ganhou a conquista: {achievement_key}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        await self.give_achievement(message.author.id, "first_message")
            
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Adicione o AWAIT aqui no início
        user_doc = await self.col.find_one_and_update(
            {"_id": message.author.id},
            {"$inc": {"message_count": 1}},
            upsert=True,
            return_document=True
        )

        count = user_doc.get("message_count", 0)

        if count >= 1000:
            await self.give_achievement(message.author.id, "messages_1000")
        
        if count >= 1:
            await self.give_achievement(message.author.id, "first_message")
            
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None:
            self.bot.voice_times[member.id] = discord.utils.utcnow()

        elif before.channel is not None and after.channel is None:
            join_time = self.bot.voice_times.pop(member.id, None)
            if join_time:
                duration = discord.utils.utcnow() - join_time
                seconds = duration.total_seconds()
                hours = seconds / 3600
                
                doc = await self.col.find_one_and_update(
                    {"_id": member.id},
                    {"$inc": {"voice_hours": hours}},
                    upsert=True,
                    return_document=True
                )
                
                if doc.get("voice_hours", 0) >= 10:
                    await self.give_achievement(member.id, "voice_10h")

    @app_commands.command(name="conquistas", description="Veja as conquistas de um usuário.")
    @app_commands.describe(usuario="O usuário que você deseja ver as conquistas")
    async def conquistas(self, interaction: discord.Interaction, usuario: discord.Member = None):
        alvo = usuario or interaction.user

        view = AchievementsView(cog=self, user=alvo)
        
        await interaction.response.send_message(view=view)

async def setup(bot):
    await bot.add_cog(AchievementsCog(bot))