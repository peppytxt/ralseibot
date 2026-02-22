import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import random
import time
import asyncio
import json
import unicodedata

DEFAULT_INTERVAL = 100
DEFAULT_MODE = "messages"
REWARD_MIN = 1500
REWARD_MAX = 4000
CHALLENGE_TIMEOUT = 60

MIN_MESSAGES_INTERVAL = 50
MIN_TIME_INTERVAL = 600 


CTRLV_MESSAGES = [
    "👀 Ei… isso aí foi Ctrl+C + Ctrl+V, né?",
    "⌨️ Digita aí, campeão. Copiar não vale 😜",
    "🤖 Meus sensores detectaram um Ctrl+V suspeito…",
    "📋 Cola aqui não, escreve com o coração ❤️",
    "🚫 Ctrl+C + Ctrl+V não aumenta QI, só digita 😉",
]

class IntervalModal(ui.Modal, title="Ajustar Intervalo"):
    intervalo = ui.TextInput(
        label="Número de mensagens",
        placeholder="Ex: 100",
        min_length=1,
        max_length=4
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            valor = int(self.intervalo.value)
            
            if valor < 50:
                return await interaction.response.send_message(
                  "⚠️ O intervalo mínimo permitido é de **50 mensagens**.",                      ephemeral=True
                )
            
            self.view.config["interval"] = valor
            await self.view.save_and_refresh(interaction)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Digite apenas números inteiros válidos.", 
                ephemeral=True
            )

class ChallengeConfigView(ui.LayoutView):
    def __init__(self, cog, guild, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.config = {
            "enabled": config.get("challenge_enabled", False),
            "interval": config.get("challenge_interval", 100),
            "channel_id": config.get("challenge_channel_id", None)
        }

    def build_interface(self):
        self.clear_items()

        enabled = self.config.get("enabled", False)
        color = discord.Color.green() if enabled else discord.Color.red()
        container = ui.Container(accent_color=color)
        
        status_str = "✅ **Ativado**" if enabled else "❌ **Desativado**"
        canal_obj = self.guild.get_channel(self.config["channel_id"])
        canal_str = canal_obj.mention if canal_obj else "`Canal Atual`"
        
        container.add_item(ui.TextDisplay(
            f"## ⚙️ Configuração de Desafios\n"
            f"Status: {status_str}\n"
            f"Intervalo: `{self.config['interval']}` mensagens\n"
            f"Canal: {canal_str}"
        ))
        
        row_btns = ui.ActionRow()
        btn_toggle = ui.Button(
            label="Desativar" if enabled else "Ativar",
            style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success,
            emoji="🔌"
        )
        btn_toggle.callback = self.toggle_enabled
        
        btn_int = ui.Button(label="Intervalo", style=discord.ButtonStyle.secondary, emoji="🔢")
        btn_int.callback = self.open_interval_modal
        
        row_btns.add_item(btn_toggle)
        row_btns.add_item(btn_int)
        container.add_item(row_btns)

        row_select = ui.ActionRow()
        select_canal = ui.ChannelSelect(
            placeholder="Selecione o canal para os desafios...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        select_canal.callback = self.update_channel
        row_select.add_item(select_canal)

        self.add_item(container)
        self.add_item(row_select)

    async def update_channel(self, interaction: discord.Interaction):
        canal_id = int(interaction.data['values'][0])
        self.config["channel_id"] = canal_id

        await self.cog.col_config.update_one(
            {"_id": self.guild.id},
            {"$set": {"challenge_channel_id": canal_id}},
            upsert=True
        )

        self.build_interface()
        await interaction.response.edit_message(view=self)

    async def toggle_enabled(self, interaction: discord.Interaction):
        self.config["enabled"] = not self.config["enabled"]

        await self.cog.col_config.update_one(
            {"_id": self.guild.id},
            {"$set": {"challenge_enabled": self.config["enabled"]}},
            upsert=True
        )
        
        self.build_interface()
        await interaction.response.edit_message(view=self)

    async def save_and_refresh(self, interaction: discord.Interaction):
        await self.cog.col_config.update_one(
            {"_id": self.guild.id},
            {"$set": {"challenge_interval": self.config["interval"]}},
            upsert=True
        )

        self.build_interface()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    async def open_interval_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(IntervalModal(self))

class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counters = {}
        self.active_challenges = {}
        self.warned_users = {}
        self.locks = {}
        self.challenge_timeout_checker.start()
        self.load_quiz_data()

    def load_quiz_data(self):
        try:
            with open("cogs/quiz.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                self.quiz_questions = data.get("quiz_questions", [])
                self.rewrite_phrases = data.get("rewrite_phrases", [])
        except FileNotFoundError:
            self.quiz_questions = []
            self.rewrite_phrases = []
            print("⚠️ Arquivo quiz.json não encontrado!")

    def cog_unload(self):
        self.challenge_timeout_checker.cancel()
        
    async def send_speed_message(self, channel, user, response_time):
        await asyncio.sleep(30)

        await channel.send(
            f"💡 **Você sabia?**\n"
            f"{user.mention} respondeu corretamente em "
            f"**{response_time:.2f} segundos** ⌨️⚡"
        )
    
    @property
    def col_users(self):
        database = getattr(self.bot, "db", None)
        return database.users if database is not None else None

    @property
    def col_config(self):
        database = getattr(self.bot, "db", None)
        return database.xp if database is not None else None

    # ------------- CONFIG COMMAND ------------------

    @app_commands.command(name="challengeconfig", description="Configura os desafios")
    @app_commands.checks.has_permissions(administrator=True)
    async def challengeconfig(self, interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ Apenas administradores podem usar este painel!", 
                ephemeral=True
            )
        
        human_count = count_human_members(interaction.guild)
        if human_count < 50:
            return await interaction.response.send_message(
                f"Este servidor possui apenas `{human_count}` membros :(\n"
                "Para ativar os desafios, o servidor precisa de pelo menos **50 membros** (sem contar bots).",
                ephemeral=True
            )

        config = await self.col_config.find_one({"_id": interaction.guild.id}) or {}
        view = ChallengeConfigView(self, interaction.guild, config)
        view.build_interface()

        await interaction.response.send_message(view=view, ephemeral=True)

        

    rank_group = app_commands.Group(name="challengerank", description="Ranking de desafios")

    @rank_group.command(name="global", description="Ranking global de vitórias")
    async def rank_global(self, interaction: discord.Interaction):
        if self.col_users is None: 
            return await interaction.response.send_message("❌ Banco de dados offline.", ephemeral=True)
            
        await interaction.response.defer()

        cursor = self.col_users.find(
            {"challenge_wins": {"$gt": 0}}
        ).sort("challenge_wins", -1).limit(10)
        
        data_list = await cursor.to_list(length=10)

        if not data_list:
            return await interaction.followup.send("Ainda ninguém completou desafios globais :(")

        desc = await self._build_rank_description(data_list, "challenge_wins")
        
        embed = discord.Embed(title="🏆 Ranking Global de Desafios", description=desc, color=0x5865F2)
        await interaction.followup.send(embed=embed)

    @rank_group.command(name="local", description="Ranking de vitórias neste servidor")
    async def rank_local(self, interaction: discord.Interaction):
        database = getattr(self.bot, "db", None)
        if database is None:
            return await interaction.response.send_message("Banco de dados offline.", ephemeral=True)
            
        await interaction.response.defer()

        cursor = database.member_challenges.find(
            {"guild_id": interaction.guild.id, "local_wins": {"$gt": 0}}
        ).sort("local_wins", -1).limit(10)
        
        data_list = await cursor.to_list(length=10)

        if not data_list:
            return await interaction.followup.send("Ninguém venceu desafios neste servidor ainda :(")
        
        desc = await self._build_rank_description(data_list, "local_wins", is_local=True)

        embed = discord.Embed(title=f"🏆 Ranking Local - {interaction.guild.name}", description=desc, color=0x2ecc71)
        await interaction.followup.send(embed=embed)

    async def _build_rank_description(self, data_list, win_field, is_local=False):
        desc = ""
        for i, data in enumerate(data_list, 1):
            user_id = data["user_id"] if is_local else data["_id"]
            wins = data.get(win_field, 0)

            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if user and not user.bot:
                desc += f"**#{i} - {user.display_name}** • 📺 {wins} vitórias\n"
        return desc
        
    @app_commands.command(
        name="challengestats",
        description="Veja estatísticas de desafios"
    )
    @app_commands.describe(user="Usuário para ver as estatísticas")
    async def challenge_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        if self.col_users is None: 
            return await interaction.response.send_message("❌ Banco de dados offline.", ephemeral=True)
            
        target = user or interaction.user

        if target.bot:
            return await interaction.response.send_message(
                "❌ Bots não participam de desafios.",
                ephemeral=True
            )

        data = await self.col_users.find_one({"_id": target.id}) or {}

        wins = data.get("challenge_wins", 0)
        earnings = data.get("challenge_earnings", 0)

        rank = await self.col_users.count_documents({"challenge_wins": {"$gt": wins}}) + 1

        embed = discord.Embed(
            title="📺 Estatísticas de Desafios",
            description=(
                f"👤 {target.mention}\n\n"
                f"📺 **Vitórias:** {wins}\n"
                f"💰 **Ralcoins ganhos:** {earnings}\n"
                f"🏆 **Rank de vitórias:** #{rank}"
            ),
            color=discord.Color.blurple()
        )

        await interaction.response.send_message(embed=embed)

    # ------------- ON MESSAGE ---------------------

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or self.col_config is None:
            return
        
        config = await self.col_config.find_one({"_id": message.guild.id})
        if not config or not config.get("challenge_enabled"):
            return

        key = str(message.guild.id)
        interval = config.get("challenge_interval", DEFAULT_INTERVAL)

        self.message_counters[key] = self.message_counters.get(key, 0) + 1
        current = self.message_counters[key]

        if self.message_counters[key] >= interval:
            self.message_counters[key] = 0
            await self.spawn_challenge(message.guild, config)

            await self.col_config.update_one(
                {"_id": message.guild.id},
                {"$set": {"challenge_last": time.time()}}
            )

        await self.check_answer(message)
    # ------------- TIMER LOOP ---------------------

    @tasks.loop(seconds=60)
    async def challenge_timer(self):
        if self.col_config is None: 
            return
        try: 
            cursor = self.col_config.find({"challenge_enabled": True})
            
            count = 0
            async for config in cursor:
                count += 1
                guild = self.bot.get_guild(config["_id"])
                if not guild:
                    continue

                mode = config.get("challenge_mode", DEFAULT_MODE)
                
                if mode != "time":
                    continue

                last = config.get("challenge_last", 0)
                interval = config.get("challenge_interval", DEFAULT_INTERVAL)
                now = time.time()

                if now - last >= interval:
                    await self.spawn_challenge(guild, config)
                    await self.col_config.update_one(
                        {"_id": config["_id"]},
                        {"$set": {"challenge_last": now}}
                    )
            
            if count == 0:
                print("DEBUG: Nenhum servidor com challenge_enabled=True no banco.")
                    
        except Exception as e:
            print("❌ ERRO NO challenge_timer:", e)
            
    @tasks.loop(seconds=5)
    async def challenge_timeout_checker(self):
        if self.col_users is None: return
        try:
            now = time.time()
            to_remove = []

            for guild_id, challenge in self.active_challenges.items():
                if challenge.get("solved"):
                    continue
                if now - challenge["spawned_at"] >= CHALLENGE_TIMEOUT:
                    to_remove.append(guild_id)

            for guild_id in to_remove:
                config = await self.col_config.find_one({"_id": guild_id})
                if not config:
                    continue

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                channel_id = config.get("challenge_channel_id") or config.get("challenge_channel")
                channel = guild.get_channel(channel_id)
                if channel:
                    await channel.send(
                        "⏰ **Tempo esgotado!**\n"
                        "Ninguém respondeu o desafio a tempo 😢"
                    )

                self.active_challenges.pop(guild_id, None)     
                    
        except Exception as e:
            print("❌ ERRO NO challenge_timeout_checker:", e)


    # ------------- SPAWN CHALLENGE -------------

    async def spawn_challenge(self, guild, config):
        if guild.id in self.active_challenges:
            return

        channel_id = config.get("challenge_channel_id") or config.get("challenge_channel")
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        challenge = self.generate_challenge()

        self.active_challenges[guild.id] = {
            "answer": challenge["answer"],
            "spawned_at": time.time(),
            "token_positions": challenge.get("token_positions"),
            "solved": False
        }

        embed = discord.Embed(
            title="📺 IT'S TV TIME!!",
            description=challenge["question"],
            color=discord.Color.blue()
        )

        if challenge.get("author_name"):
            embed.set_footer(
                text=f"Sugerido por {challenge['author_name']}",
                icon_url=challenge.get("author_icon")
            )
        else:
            embed.set_footer(text="Responda corretamente para ganhar pontos!")

        await channel.send(embed=embed)

    # ------------- CHECK ANSWER -------------

    async def check_answer(self, message):
        guild_id = message.guild.id
        challenge = self.active_challenges.get(guild_id)
        if not challenge or challenge.get("solved"):
            return
        
        if guild_id not in self.locks:
            self.locks[guild_id] = asyncio.Lock()

        if "\u200b" in message.content:
            key = (guild_id, message.author.id)

            if not self.warned_users.get(key):
                self.warned_users[key] = True

                warning = random.choice(CTRLV_MESSAGES)
                msg = await message.reply(warning, mention_author=False)

                await asyncio.sleep(7)
                await msg.delete()

            return

        async with self.locks[guild_id]:
            if challenge.get("solved"):
                return
            
            respostas_permitidas = challenge["answer"]

            if isinstance(respostas_permitidas, str):
                respostas_permitidas = [respostas_permitidas]

            user_answer = normalize(message.content)

            if any(user_answer == normalize(r) for r in respostas_permitidas):
                challenge["solved"] = True

                reward = random.randint(REWARD_MIN, REWARD_MAX)
                response_time = time.time() - challenge["spawned_at"]

                await message.add_reaction("✅")

                await self.col_users.update_one(
                    {"_id": message.author.id},
                    {"$inc": {"challenge_wins": 1, "challenge_earnings": reward, "coins": reward}},
                    upsert=True
                )

                database = getattr(self.bot, "db", None)
                if database is not None:
                    await database.member_challenges.update_one(
                        {
                            "guild_id": message.guild.id, 
                            "user_id": message.author.id
                        },
                        {"$inc": {"local_wins": 1}},
                        upsert=True
                    )

                await message.channel.send(
                    f"🎉 {message.author.mention} acertou! "
                    f"Você ganhou **{reward} ralcoins!**"
                )

                self.active_challenges.pop(guild_id, None)
                self.warned_users.clear()

                asyncio.create_task(self.send_speed_message(message.channel, message.author, response_time))

                achievements_cog = self.bot.get_cog("AchievementsCog") 
                if achievements_cog:
                    await achievements_cog.give_achievement(message.author.id, "challenge_first_win")

    # ------------- GENERATE CHALLENGE -------------

    def generate_challenge(self):
        typ = random.choice(["math", "rewrite", "guess", "quiz"])

        if typ == "math":
            math_type = random.choice(["add", "sub", "mul"])

            if math_type == "add":
                a = random.randint(1, 50)
                b = random.randint(1, 50)
                question = f"Quanto é **{a} + {b}**?"
                answer = str(a + b)

            elif math_type == "sub":
                a = random.randint(1, 50)
                b = random.randint(1, 50)
                maior = max(a, b)
                menor = min(a, b)
                question = f"Quanto é **{maior} - {menor}**?"
                answer = str(maior - menor)

            else:
                a = random.randint(2, 9)
                b = random.randint(2, 9)
                question = f"Quanto é **{a} × {b}**?"
                answer = str(a * b)

            return {
                "question": question,
                "answer": answer
            }

        elif typ == "rewrite":
            if not self.rewrite_phrases:
                phrase = "Ralsei é muito fofinho!"
            else:
                phrase = random.choice(self.rewrite_phrases)

            disguised, token_positions = add_invisible_chars(phrase)

            return {
                "question": f"⌨️ **Reescreva** a frase exatamente:\n`{disguised}`",
                "answer": phrase,
                "token_positions": token_positions
            }
        elif typ == "guess":
            min_num = random.randint(1, 100)
            max_num = min_num + random.randint(5, 7)
            secret = random.randint(min_num, max_num)

            return {
                "question": f"Entre **{min_num} e {max_num}**, qual número estou pensando? :3",
                "answer": str(secret)
            }
        elif typ == "quiz":
            item = random.choice(self.quiz_questions)
            return {
                "question": f"**Pergunta:** {item['question']}",
                "answer": item['answer'],
                "author_name": item.get("author_name")
            }

def count_human_members(guild: discord.Guild) -> int:
    return len([m for m in guild.members if not m.bot])

def add_invisible_chars(text: str):
    ZERO_WIDTH = "\u200b"
    token_positions = set()
    result = ""

    for i, char in enumerate(text):
        result += char
        if char != " " and random.random() < 0.15:
            result += ZERO_WIDTH
            token_positions.add(i)

    return result, token_positions

def normalize(text: str) -> str:
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return (
        text.lower()
        .replace("\u200b", "")
        .strip()
    )

async def setup(bot):
    await bot.add_cog(Challenges(bot))