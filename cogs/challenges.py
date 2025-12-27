import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import time
import asyncio

# Configurações padrão
DEFAULT_INTERVAL = 100
DEFAULT_MODE = "messages"
REWARD_MIN = 1500
REWARD_MAX = 4000
CHALLENGE_TIMEOUT = 60  # Segundos

MIN_MEMBERS = 100
MIN_MESSAGES_INTERVAL = 50
MIN_TIME_INTERVAL = 600  # 10 minutos


CTRLV_MESSAGES = [
    "👀 Ei… isso aí foi Ctrl+C + Ctrl+V, né?",
    "⌨️ Digita aí, campeão. Copiar não vale 😜",
    "🤖 Meus sensores detectaram um Ctrl+V suspeito…",
    "📋 Cola aqui não, escreve com o coração ❤️",
    "🚫 Ctrl+C + Ctrl+V não aumenta QI, só digita 😉",
]


class Challenges(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # em memória -> contador de mensagens
        self.message_counters = {}
        # em memória -> desafios ativos por servidor
        self.active_challenges = {}
        
        self.warned_users = {}
        
        # timer loop (1 vez por minuto)
        self.challenge_timer.start()
        self.challenge_timeout_checker.start()

    def cog_unload(self):
        self.challenge_timer.cancel()
        self.challenge_timeout_checker.cancel()

    @property
    def col(self):
        # coleção no MongoDB
        return self.bot.get_cog("XP").col

    # ------------- CONFIG COMMAND ------------------

    @app_commands.command(
        name="challengeconfig",
        description="Configura perguntas automáticas no servidor"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        channel="Canal onde os desafios serão postados",
        enabled="Ativar ou desativar desafios",
        mode="Modo de trigger (messages/tempo)",
        interval="Valores de intervalo (mensagens ou segundos)"
    )
    async def challengeconfig(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        enabled: bool,
        mode: str,
        interval: int
    ):
        guild = interaction.guild

        if not guild:
            return await interaction.response.send_message(
                "❌ Este comando só pode ser usado em servidores.",
                ephemeral=True
            )

        # 🔒 FILTRO DE MEMBROS
        if guild.member_count < MIN_MEMBERS:
            return await interaction.response.send_message(
                f"❌ Este servidor precisa ter pelo menos **{MIN_MEMBERS} membros** "
                "para ativar os desafios.",
                ephemeral=True
            )

        if mode not in ("messages", "time"):
            return await interaction.response.send_message(
                "❌ Modo inválido! Use `messages` ou `time`.",
                ephemeral=True
            )

        # 🔒 FILTRO POR MODO
        if mode == "messages" and interval < MIN_MESSAGES_INTERVAL:
            return await interaction.response.send_message(
                f"❌ O intervalo mínimo é **{MIN_MESSAGES_INTERVAL} mensagens**.",
                ephemeral=True
            )

        if mode == "time" and interval < MIN_TIME_INTERVAL:
            return await interaction.response.send_message(
                f"❌ O intervalo mínimo é **{MIN_TIME_INTERVAL // 60} minutos**.",
                ephemeral=True
            )

        # ✅ SALVAR CONFIG
        self.col.update_one(
            {"_id": guild.id},
            {"$set": {
                "challenge_enabled": enabled,
                "challenge_channel": channel.id,
                "challenge_mode": mode,
                "challenge_interval": interval,
                "challenge_last": time.time()
            }},
            upsert=True
        )

        await interaction.response.send_message(
            "✅ **Configuração aplicada com sucesso!**\n"
            f"🔹 Canal: {channel.mention}\n"
            f"🔹 Modo: {mode}\n"
            f"🔹 Intervalo: {interval}\n"
            f"🔹 Membros: {guild.member_count}",
            ephemeral=True
        )

    @app_commands.command(
        name="challenge_rank",
        description="Ranking dos usuários que mais venceram desafios"
    )
    async def challenge_rank(self, interaction: discord.Interaction):

        users = list(
            self.col.find(
                {"challenge_wins": {"$gt": 0}},
                {"challenge_wins": 1}
            )
            .sort("challenge_wins", -1)
            .limit(10)
        )

        if not users:
            return await interaction.response.send_message(
                "❌ Ainda ninguém completou desafios.",
                ephemeral=True
            )

        desc = ""
        for i, u in enumerate(users, start=1):
            user = interaction.client.get_user(u["_id"])
            name = user.display_name if user else f"Usuário {u['_id']}"
            wins = u.get("challenge_wins", 0)

            desc += f"**#{i} — {name}** • 🧠 {wins} desafios\n"

        embed = discord.Embed(
            title="🏆 Ranking de Desafios",
            description=desc,
            color=discord.Color.purple()
        )

        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(
        name="challenge_stats",
        description="Veja estatísticas de desafios suas ou de outro usuário"
    )
    @app_commands.describe(
        user="Usuário para ver as estatísticas (opcional)"
    )
    async def challenge_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        target = user or interaction.user

        if target.bot:
            return await interaction.response.send_message(
                "❌ Bots não participam de desafios.",
                ephemeral=True
            )

        data = self.col.find_one({"_id": target.id}) or {}
        wins = data.get("challenge_wins", 0)

        # Rank global de desafios (ignora bots)
        rank = self.col.count_documents({
            "challenge_wins": {"$gt": wins},
            "_id": {"$ne": 0}  # caso use BOT_ECONOMY_ID
        }) + 1

        embed = discord.Embed(
            title="🧠 Estatísticas de Desafios",
            description=(
                f"👤 {target.mention}\n\n"
                f"🧠 **Desafios vencidos:** {wins}\n"
                f"🏆 **Rank de desafios:** #{rank}"
            ),
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

        # ********** MODO POR MENSAGENS **********
        if mode == "messages":
            key = str(message.guild.id)

            self.message_counters[key] = self.message_counters.get(key, 0) + 1
            current = self.message_counters[key]

            if current >= interval:
                self.message_counters[key] = 0
                await self.spawn_challenge(message.guild, config)

        # ********** CHECAR RESPOSTAS **********
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

        # gerar um desafio
        challenge = self.generate_challenge()

        self.active_challenges[guild.id] = {
            "answer": challenge["answer"],
            "spawned_at": time.time(),
            "token_positions": challenge.get("token_positions"),
            "solved": False
        }


        embed = discord.Embed(
            title="🧠 Desafio!",
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

        # anti ctrl+c ctrl+v
        if "\u200b" in message.content:
            key = (guild_id, message.author.id)

            if not self.warned_users.get(key):
                self.warned_users[key] = True

                warning = random.choice(CTRLV_MESSAGES)
                msg = await message.reply(warning, mention_author=False)

                # apagar depois de 5 segundos
                await asyncio.sleep(5)
                await msg.delete()

            return

        if normalize(message.content) == normalize(challenge["answer"]):
            if challenge["solved"]:
                return

            challenge["solved"] = True

            reward = random.randint(REWARD_MIN, REWARD_MAX)

            await message.add_reaction("✅")

            self.col.update_one(
                {"_id": message.author.id},
                {
                    "$inc": {
                        "coins": reward,
                        "challenge_wins": 1
                    }
                },
                upsert=True
            )


            await message.channel.send(
                f"🎉 {message.author.mention} acertou! "
                f"Você ganhou **{reward} ralcoins!**"
            )

            self.active_challenges.pop(guild_id, None)
            self.warned_users.clear()  # limpar avisos do desafio

    # ------------- GENERATE CHALLENGE -------------

    def generate_challenge(self):
        typ = random.choice(["math", "rewrite"])

        if typ == "math":
            math_type = random.choice(["add", "sub", "mul"])

            # ➕ SOMA
            if math_type == "add":
                a = random.randint(1, 50)
                b = random.randint(1, 50)
                question = f"Quanto é **{a} + {b}**?"
                answer = str(a + b)

            # ➖ SUBTRAÇÃO (nunca negativa)
            elif math_type == "sub":
                a = random.randint(1, 50)
                b = random.randint(1, 50)
                maior = max(a, b)
                menor = min(a, b)
                question = f"Quanto é **{maior} - {menor}**?"
                answer = str(maior - menor)

            # ✖️ MULTIPLICAÇÃO SIMPLES
            else:
                a = random.randint(2, 9)
                b = random.randint(2, 9)
                question = f"Quanto é **{a} × {b}**?"
                answer = str(a * b)

            return {
                "question": question,
                "answer": answer
            }

        else:
            phrases = [
                "O cavaleiro foi até a lua em seu cavalo",
                "A raposa marrom rápida pula sobre o cão preguiçoso",
                "Um rato roeu a roupa do rei de roma",
                "Dia de chuva é dia de poesia",
                "Ralsei é muito fofu",
                "Dois passos para frente, três passos para trás!",
                "Sua mão é fria como a neve e a minha queima como fogo",
                "Ralsei é meu sonho de consumo",
            ]

            phrase = random.choice(phrases)
            disguised, token_positions = add_invisible_chars(phrase)

            return {
                "question": f"Reescreva a frase exatamente:\n`{disguised}`",
                "answer": phrase,
                "token_positions": token_positions
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
