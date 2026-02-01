import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
import random
import time
import asyncio

# Configurações padrão
DEFAULT_INTERVAL = 100
DEFAULT_MODE = "messages"
REWARD_MIN = 1500
REWARD_MAX = 4000
CHALLENGE_TIMEOUT = 60

MIN_MEMBERS = 100
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
    interval = ui.TextInput(
        label="Quantidade de mensagens",
        placeholder="Ex: 100",
        min_length=1,
        max_length=4
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.interval.value)
            if val < 10:
                return await interaction.response.send_message("❌ O intervalo deve ser pelo menos 10.", ephemeral=True)
            
            self.view.config["challenge_interval"] = val
            await self.view.save_and_refresh(interaction)
        except ValueError:
            await interaction.response.send_message("❌ Digite um número válido.", ephemeral=True)
    
class ChallengeConfigView(ui.View):
    def __init__(self, cog, guild, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.config = config or {
            "challenge_enabled": False, 
            "challenge_interval": 100
        }

    def build_interface(self):
        self.clear_items()
        
        enabled = self.config.get("challenge_enabled", False)
        interval = self.config.get("challenge_interval", 100)

        embed = discord.Embed(
            title="⚙️ Painel de Controle: Desafios",
            description="Configure a frequência e o estado dos desafios automáticos.",
            color=discord.Color.green() if enabled else discord.Color.red()
        )
        embed.add_field(name="Status", value="✅ Ativado" if enabled else "❌ Desativado", inline=True)
        embed.add_field(name="Intervalo", value=f"`{interval}` mensagens", inline=True)
        embed.set_footer(text=f"Servidor: {self.guild.name}")

        btn_toggle = ui.Button(
            label="Desligar" if enabled else "Ligar",
            style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success,
            emoji="🔌"
        )
        btn_toggle.callback = self.toggle_enabled
        self.add_item(btn_toggle)

        btn_int = ui.Button(
            label="Ajustar Mensagens", 
            style=discord.ButtonStyle.secondary, 
            emoji="🔢"
        )
        btn_int.callback = self.open_interval_modal
        self.add_item(btn_int)

        return embed

    async def save_and_refresh(self, interaction: discord.Interaction):
        if self.cog.col is not None:
            self.cog.col.update_one(
                {"_id": self.guild.id},
                {"$set": self.config},
                upsert=True
            )
        
        embed = self.build_interface()
        await interaction.response.edit_message(embed=embed, view=self)
        
    async def toggle_enabled(self, interaction: discord.Interaction):
        self.config["challenge_enabled"] = not self.config.get("challenge_enabled", False)
        await self.save_and_refresh(interaction)

    async def open_interval_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(IntervalModal(self))


class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        self.message_counters = {}
        self.active_challenges = {}
        
        self.warned_users = {}

        self.challenge_timer.start()
        self.challenge_timeout_checker.start()

    def cog_unload(self):
        self.challenge_timer.cancel()
        self.challenge_timeout_checker.cancel()
        
    async def send_speed_message(self, channel, user, response_time):
        await asyncio.sleep(30)

        await channel.send(
            f"💡 **Você sabia?**\n"
            f"{user.mention} respondeu corretamente em "
            f"**{response_time:.2f} segundos** ⌨️⚡"
        )
    

    @property
    def col(self):
        xp_cog = self.bot.get_cog("XP")
        if xp_cog:
            return xp_cog.col
        return None

    # ------------- CONFIG COMMAND ------------------
    @app_commands.command(
        name="challengeconfig",
        description="Painel visual de configuração dos desafios"
    )
    @app_commands.default_permissions(administrator=True)
    async def challengeconfig(self, interaction: discord.Interaction):
        if self.col is None:
            return await interaction.response.send_message("❌ Banco de dados offline.", ephemeral=True)

        config = self.col.find_one({"_id": interaction.guild.id})
        if config is None:
            config = {}
        
        view = ChallengeConfigView(self, interaction.guild, config)
        embed = view.build_interface()
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(
        name="challengerank",
        description="Ranking dos usuários que mais venceram desafios"
    )
    async def challenge_rank(self, interaction: discord.Interaction):
        cursor = self.col.find(
            {"challenge_wins": {"$gt": 0}},
            {"challenge_wins": 1}
        ).sort("challenge_wins", -1).limit(10)

        users = list(cursor)

        if not users:
            return await interaction.response.send_message("❌ Ainda ninguém completou desafios.", ephemeral=True)

        desc = ""
        for i, u in enumerate(users, start=1):
            user = self.bot.get_user(u["_id"]) or await self.bot.fetch_user(u["_id"])
            name = user.display_name if user else f"Usuário {u['_id']}"
            wins = u.get("challenge_wins", 0)
            desc += f"**#{i} - {name}** • 📺 {wins} desafios\n"

        embed = discord.Embed(title="🏆 Ranking de Desafios", description=desc, color=discord.Color.purple())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="challengestats",
        description="Veja estatísticas de desafios"
    )
    async def challenge_stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        target = user or interaction.user
        if target.bot:
            return await interaction.response.send_message("❌ Bots não participam.", ephemeral=True)

        data = self.col.find_one({"_id": target.id}) or {}
        wins = data.get("challenge_wins", 0)
        earnings = data.get("challenge_earnings", 0)

        rank = self.col.count_documents({"challenge_wins": {"$gt": wins}, "_id": {"$ne": 0}}) + 1

        embed = discord.Embed(
            title="📺 Estatísticas",
            description=f"👤 {target.mention}\n\n📺 **Vitórias:** {wins}\n💰 **Ganhos:** {earnings}\n🏆 **Rank:** #{rank}",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed)


    # ------------- ON MESSAGE ---------------------

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        config = self.col.find_one({"_id": message.guild.id})
        if not config or not config.get("challenge_enabled"):
            return

        mode = config.get("challenge_mode", DEFAULT_MODE)
        interval = config.get("challenge_interval", DEFAULT_INTERVAL)

        if mode == "messages":
            key = str(message.guild.id)
            self.message_counters[key] = self.message_counters.get(key, 0) + 1
            
            if self.message_counters[key] >= interval:
                self.message_counters[key] = 0
                await self.spawn_challenge(message.guild, config)

                self.col.update_one(
                    {"_id": message.guild.id},
                    {"$set": {"challenge_last": time.time()}}
                )

        await self.check_answer(message)

    # ------------- TIMER LOOP ---------------------

    @tasks.loop(seconds=60)
    async def challenge_timer(self):
        try: 
            for config in self.col.find({"challenge_enabled": True}):
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
                    self.col.update_one(
                        {"_id": config["_id"]},
                        {"$set": {"challenge_last": now}}
                    )
                    
        except Exception as e:
            print("❌ ERRO NO challenge_timer:", e)
            
    @tasks.loop(seconds=5)
    async def challenge_timeout_checker(self):
        try:
            now = time.time()

            to_remove = []

            for guild_id, challenge in self.active_challenges.items():
                if challenge.get("solved"):
                    continue
                    
                if now - challenge["spawned_at"] >= CHALLENGE_TIMEOUT:
                    to_remove.append(guild_id)

            for guild_id in to_remove:
                config = self.col.find_one({"_id": guild_id})
                if not config:
                    continue

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue

                channel = guild.get_channel(config.get("challenge_channel"))
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

        channel_id = config.get("challenge_channel")
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

        embed.set_footer(text="Responda corretamente para ganhar pontos!")
        await channel.send(embed=embed)

    # ------------- CHECK ANSWER -------------

    async def check_answer(self, message):
        guild_id = message.guild.id
        challenge = self.active_challenges.get(guild_id)
        if not challenge:
            return

        if "\u200b" in message.content:
            key = (guild_id, message.author.id)

            if not self.warned_users.get(key):
                self.warned_users[key] = True

                warning = random.choice(CTRLV_MESSAGES)
                msg = await message.reply(warning, mention_author=False)

                await asyncio.sleep(7)
                await msg.delete()

            return

        if normalize(message.content) == normalize(challenge["answer"]):
            challenge["solved"] = True
            reward = random.randint(REWARD_MIN, REWARD_MAX)
            response_time = time.time() - challenge["spawned_at"]

            try:
                await message.add_reaction("✅")
            except discord.Forbidden:
                print(f"⚠️ Não foi possível reagir à mensagem de {message.author} (Bot bloqueado ou falta de permissão).")
            except Exception as e:
                print(f"⚠️ Erro ao adicionar reação: {e}")

            self.col.update_one(
                {"_id": message.author.id},
                {"$inc": {"challenge_wins": 1, "challenge_earnings": reward}},
                upsert=True
            )


            await message.channel.send(
                f"🎉 {message.author.mention} acertou! "
                f"Você ganhou **{reward} ralcoins!**"
            )

            asyncio.create_task(
                self.send_speed_message(
                    message.channel,
                    message.author,
                    response_time
                )
            )

            achievements_cog = self.bot.get_cog("AchievementsCog") 
            if achievements_cog:
                await achievements_cog.give_achievement(message.author.id, "challenge_first_win")
            self.active_challenges.pop(guild_id, None)
            self.warned_users.clear()

# ------------- GENERATE CHALLENGE -------------

    def generate_challenge(self):
        typ = random.choice(["math", "rewrite", "guess"])

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
            phrases = [
                "O cavaleiro foi até a lua em seu cavalo",
                "A raposa marrom rápida pula sobre o cão preguiçoso",
                "Um rato roeu a roupa do rei de roma",
                "Dia de chuva é dia de poesia",
                "Ralsei é muito fofu",
                "Dois passos para frente, três passos para trás!",
                "Sua mão é fria como a neve e a minha queima como fogo",
                "Ralsei é meu sonho de consumo",
                "Ralsei adora fazer bolos",
                "Eu prefiro morrer do que perder a vida",
                "Correndo sempre da saudade, por isso que eu sempre me movo",
                "Bebam água, faz bem a saúde",
                "Fiquei envergonhado de mim mesmo quando percebi que a vida era uma festa à fantasia, e eu participei com meu rosto verdadeiro",
                "Explorando o dark world!"
            ]

            phrase = random.choice(phrases)
            disguised, token_positions = add_invisible_chars(phrase)

            return {
                "question": f"Reescreva a frase exatamente:\n`{disguised}`",
                "answer": phrase,
                "token_positions": token_positions
            }
        else:
            min_num = random.randint(1, 50)
            max_num = min_num + random.randint(5, 7)
            secret = random.randint(min_num, max_num)

            return {
                "question": f"Entre **{min_num} e {max_num}** qual número estou pensando?",
                "answer": str(secret)
            }

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
    return (
        text.lower()
        .replace("\u200b", "")
        .strip()
    )

async def setup(bot):
    await bot.add_cog(Challenges(bot))