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

class IntervalModal(ui.Modal, title="Configurar Intervalo"):
    interval = ui.TextInput(
        label="Valor do Intervalo",
        placeholder="Ex: 50 para mensagens ou 600 para tempo...",
        min_length=1,
        max_length=5
    )

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.interval.value)
            # Validação básica baseada no modo atual da view
            if self.view.config.get("challenge_mode") == "messages" and val < 50:
                return await interaction.response.send_message("❌ Mínimo de 50 mensagens.", ephemeral=True)
            if self.view.config.get("challenge_mode") == "time" and val < 600:
                return await interaction.response.send_message("❌ Mínimo de 600 segundos (10min).", ephemeral=True)
            
            self.view.config["challenge_interval"] = val
            await self.view.save_and_refresh(interaction)
        except ValueError:
            await interaction.response.send_message("❌ Digite apenas números!", ephemeral=True)

class ChallengeConfigView(ui.LayoutView):
    def __init__(self, cog, guild, config):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.config = config

    def build_interface(self):
        self.clear_items()
        
        enabled = self.config.get("challenge_enabled", False)
        mode = self.config.get("challenge_mode", "messages")
        interval = self.config.get("challenge_interval", 100)
        channel_id = self.config.get("challenge_channel")
        channel_mention = f"<#{channel_id}>" if channel_id else "Não definido"

        status_card = ui.Container()
        status_card.title = "⚙️ Painel de Desafios"
        status_card.accent_color = discord.Color.green() if enabled else discord.Color.red()
        
        status_text = (
            f"**Status:** {'✅ Ativado' if enabled else '❌ Desativado'}\n"
            f"**Modo:** {'💬 Mensagens' if mode == 'messages' else '⏰ Tempo'}\n"
            f"**Intervalo:** `{interval}` {'msgs' if mode == 'messages' else 'segundos'}\n"
            f"**Canal:** {channel_mention}"
        )
        status_card.add_item(ui.TextDisplay(status_text))
        self.add_item(status_card)

        controls = ui.ActionRow()
        
        btn_toggle = ui.Button(
            label="Ligar" if not enabled else "Desligar",
            style=discord.ButtonStyle.success if not enabled else discord.ButtonStyle.danger
        )
        btn_toggle.callback = self.toggle_enabled
        controls.add_item(btn_toggle)

        btn_mode = ui.Button(label="Trocar Modo", style=discord.ButtonStyle.secondary, emoji="🔄")
        btn_mode.callback = self.toggle_mode
        controls.add_item(btn_mode)

        btn_int = ui.Button(label="Ajustar Intervalo", style=discord.ButtonStyle.secondary, emoji="🔢")
        btn_int.callback = self.open_interval_modal
        controls.add_item(btn_int)
        
        self.add_item(controls)

        select_row = ui.ActionRow()
        channel_select = ui.ChannelSelect(
            placeholder="Selecione o canal dos desafios...",
            channel_types=[discord.ChannelType.text]
        )
        channel_select.callback = self.select_channel
        select_row.add_item(channel_select)
        self.add_item(select_row)

    async def save_and_refresh(self, interaction: discord.Interaction):
        await self.cog.col.update_one(
            {"_id": self.guild.id},
            {"$set": self.config},
            upsert=True
        )
        self.build_interface()
        await interaction.response.edit_message(view=self)

    async def toggle_enabled(self, interaction: discord.Interaction):
        self.config["challenge_enabled"] = not self.config.get("challenge_enabled", False)
        await self.save_and_refresh(interaction)

    async def toggle_mode(self, interaction: discord.Interaction):
        current = self.config.get("challenge_mode", "messages")
        self.config["challenge_mode"] = "time" if current == "messages" else "messages"
        await self.save_and_refresh(interaction)

    async def select_channel(self, interaction: discord.Interaction):
        self.config["challenge_channel"] = interaction.data['values'][0]
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
        database = getattr(self.bot, "db", None)
        if database is not None:
            return database.xp
        return None

class ChallengeConfigView(ui.LayoutView):
    def __init__(self, cog, guild, current_config):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        # Estado local da configuração (começa com o que já tem no banco ou padrão)
        self.config = current_config or {
            "challenge_enabled": False,
            "challenge_channel": None,
            "challenge_mode": "messages",
            "challenge_interval": 100
        }

    def refresh_interface(self):
        self.clear_items()

        # 1. Header Informativo
        header = ui.Container()
        status_emoji = "✅ Ativado" if self.config["challenge_enabled"] else "❌ Desativado"
        canal_mention = f"<#{self.config['challenge_channel']}>" if self.config['challenge_channel'] else "Não definido"
        
        header.add_item(ui.TextDisplay(
            f"## ⚙️ Configuração de Desafios - {self.guild.name}\n"
            f"**Status:** {status_emoji}\n"
            f"**Canal:** {canal_mention}\n"
            f"**Modo:** `{self.config['challenge_mode']}` | **Intervalo:** `{self.config['challenge_interval']}`"
        ))
        self.add_item(header)

        # 2. Linha de Botões de Controle
        action_row = ui.ActionRow()
        
        # Botão Ligar/Desligar
        toggle_style = discord.ButtonStyle.success if not self.config["challenge_enabled"] else discord.ButtonStyle.danger
        btn_toggle = ui.Button(label="Ligar/Desligar", style=toggle_style, emoji="🔌")
        btn_toggle.callback = self.toggle_status
        action_row.add_item(btn_toggle)

        # Menu de Seleção de Canal (Select Menu V2)
        # Nota: Você pode usar um ChannelSelect para facilitar
        self.add_item(action_row)

        # 3. Botão para Salvar (Finalizar)
        save_row = ui.ActionRow()
        btn_save = ui.Button(label="Salvar Alterações", style=discord.ButtonStyle.primary, emoji="💾")
        btn_save.callback = self.save_to_db
        save_row.add_item(btn_save)
        self.add_item(save_row)

    async def toggle_status(self, interaction: discord.Interaction):
        self.config["challenge_enabled"] = not self.config["challenge_enabled"]
        self.refresh_interface()
        await interaction.response.edit_message(view=self)

    async def save_to_db(self, interaction: discord.Interaction):
        # Aqui salvamos de fato no MongoDB
        await self.cog.col.update_one(
            {"_id": self.guild.id},
            {"$set": self.config},
            upsert=True
        )
        await interaction.response.send_message("✅ Configurações salvas no banco de dados!", ephemeral=True)
        self.stop() # Fecha a view

    # ------------- CONFIG COMMAND ------------------

    @app_commands.command(
        name="challengeconfig",
        description="Painel visual de configuração dos desafios"
    )
    @app_commands.default_permissions(administrator=True)
    async def challengeconfig(self, interaction: discord.Interaction):
        if self.col is None:
            return await interaction.response.send_message("❌ Banco de dados offline.", ephemeral=True)

        if interaction.guild.member_count < MIN_MEMBERS:
            return await interaction.response.send_message(
                f"❌ Mínimo de **{MIN_MEMBERS} membros** necessário.", ephemeral=True
            )

        config = await self.col.find_one({"_id": interaction.guild.id}) or {}
        
        view = ChallengeConfigView(self, interaction.guild, config)
        view.build_interface() 
        
        await interaction.response.send_message(view=view, ephemeral=True)

    @app_commands.command(
        name="challengerank",
        description="Ranking dos usuários que mais venceram desafios"
    )
    async def challenge_rank(self, interaction: discord.Interaction):
        if self.col is None: return

        cursor = self.col.find(
                {"challenge_wins": {"$gt": 0}},
                {"challenge_wins": 1}
            ).sort("challenge_wins", -1).limit(10)
        
        users = await cursor.to_list(length=10)

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

            desc += f"**#{i} - {name}** • 📺 {wins} desafios\n"

        embed = discord.Embed(
            title="🏆 Ranking de Desafios",
            description=desc,
            color=discord.Color.purple()
        )

        await interaction.response.send_message(embed=embed)
        
    @app_commands.command(
        name="challengestats",
        description="Veja estatísticas de desafios"
    )
    @app_commands.describe(user="Usuário para ver as estatísticas (opcional)")
    async def challenge_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        if self.col is None: return
        target = user or interaction.user

        if target.bot:
            return await interaction.response.send_message(
                "❌ Bots não participam de desafios.",
                ephemeral=True
            )

        data = await self.col.find_one({"_id": target.id}) or {}

        wins = data.get("challenge_wins", 0)
        earnings = data.get("challenge_earnings", 0)

        rank = await self.col.count_documents({
            "challenge_wins": {"$gt": wins},
            "_id": {"$ne": 0}
        }) + 1

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
        if message.author.bot or not message.guild or self.col is None:
            return

        config = await self.col.find_one({"_id": message.guild.id})
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

                # Adicionado AWAIT
                await self.col.update_one(
                    {"_id": message.guild.id},
                    {"$set": {"challenge_last": time.time()}}
                )

        # ********** CHECAR RESPOSTAS **********
        await self.check_answer(message)
    # ------------- TIMER LOOP ---------------------

    @tasks.loop(seconds=60)
    async def challenge_timer(self):
        if self.col is None: 
            return
        try: 
            cursor = self.col.find({"challenge_enabled": True})
            
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
                    await self.col.update_one(
                        {"_id": config["_id"]},
                        {"$set": {"challenge_last": now}}
                    )
            
            if count == 0:
                print("DEBUG: Nenhum servidor com challenge_enabled=True no banco.")
                    
        except Exception as e:
            print("❌ ERRO NO challenge_timer:", e)
            
    @tasks.loop(seconds=5)
    async def challenge_timeout_checker(self):
        if self.col is None: return
        try:
            now = time.time()
            to_remove = []

            for guild_id, challenge in self.active_challenges.items():
                if challenge.get("solved"):
                    continue
                if now - challenge["spawned_at"] >= CHALLENGE_TIMEOUT:
                    to_remove.append(guild_id)

            for guild_id in to_remove:
                config = await self.col.find_one({"_id": guild_id})
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

        # anti ctrl+c ctrl+v
        if "\u200b" in message.content:
            key = (guild_id, message.author.id)

            if not self.warned_users.get(key):
                self.warned_users[key] = True

                warning = random.choice(CTRLV_MESSAGES)
                msg = await message.reply(warning, mention_author=False)

                # apagar depois de 7 segundos
                await asyncio.sleep(7)
                await msg.delete()

            return

        if normalize(message.content) == normalize(challenge["answer"]):
            if challenge["solved"]:
                return

            challenge["solved"] = True

            reward = random.randint(REWARD_MIN, REWARD_MAX)
            
            response_time = time.time() - challenge["spawned_at"]

            await message.add_reaction("✅")

            # Adicionado AWAIT
            await self.col.update_one(
                {"_id": message.author.id},
                {
                    "$inc": {
                        "challenge_wins": 1,
                        "challenge_earnings": reward
                    }
                },
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