import discord
from discord import app_commands
from discord.ext import commands
import random

TAX_RATE = 0.05  # Taxa de 5% 

BOT_ECONOMY_ID = 0

class RPSView(discord.ui.View):
    def __init__(self, cog, game_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.game_id = game_id

    async def on_timeout(self):
        game = self.cog.ongoing_games.get(self.game_id)
        if not game:
            return

        channel = game.get("channel")
        if not channel:
            del self.cog.ongoing_games[self.game_id]
            return

        userA = game["userA"]
        userB = game["userB"]

        await channel.send(
            f"⏰ **Tempo esgotado!**\n"
            f"{userA.mention} ou {userB.mention} não respondeu a tempo.\n"
            "A partida foi cancelada."
        )

        del self.cog.ongoing_games[self.game_id]


class RockPaperScissors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ongoing_games = {}

    def get_winner(self, a, b):
        if a == b:
            return None
        rules = {
            "pedra": "tesoura",
            "tesoura": "papel",
            "papel": "pedra"
        }

        return "A" if rules[a] == b else "B"

    @app_commands.command(name="rps", description="Desafiar alguém para Pedra Papel Tesoura e apostar ralcoins!")
    async def rps(
        self,
        interaction: discord.Interaction,
        oponente: discord.Member,
        quantidade: int
    ):
        await interaction.response.defer()
        if oponente.id == interaction.user.id:
            return await interaction.followup.send("Você não pode desafiar você mesmo!", ephemeral=True)

        db = self.bot.get_cog("XP").col
        user_data = db.find_one({"_id": interaction.user.id}) or {}
        opp_data = db.find_one({"_id": oponente.id}) or {}

        MIN_BET = 100

        if quantidade < MIN_BET:
            return await interaction.followup.send(
                f"❌ A aposta mínima é de **{MIN_BET} ralcoins**!",
                ephemeral=True
            )

        if user_data.get("coins", 0) < quantidade:
            return await interaction.followup.send("Você não tem ralcoins suficientes!", ephemeral=True)
        if opp_data.get("coins", 0) < quantidade:
            return await interaction.followup.send(f"{oponente.display_name} não tem ralcoins suficientes!", ephemeral=True)

        game_id = f"{interaction.user.id}_{oponente.id}"
        if game_id in self.ongoing_games:
            return await interaction.followup.send("Já existe uma partida entre vocês!", ephemeral=True)

        self.ongoing_games[game_id] = {
            "A": None,
            "B": None,
            "userA": interaction.user,
            "userB": oponente,
            "amount": quantidade,
            "channel": interaction.channel 
        }

        view = RPSView(self, game_id)

        choices = {
            "🪨": "pedra",
            "📄": "papel",
            "✂": "tesoura"
        }

        for emoji, value in choices.items():
            btn = discord.ui.Button(
                emoji=emoji,
                style=discord.ButtonStyle.secondary,
                custom_id=f"rps|{game_id}|{value}"
            )

            view.add_item(btn)

        await interaction.followup.send(
            f"{interaction.user.mention} desafiou {oponente.mention} para uma aposta de **{quantidade} ralcoins**!\n"
            f"🏦 Taxa do bot: **5%** sobre o valor ganho\n\n"
            "🪨 📄 ✂ Escolha sua jogada!",
            view=view
        )


    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):

        # Certifica que é botão
        if interaction.data.get("component_type") != 2:
            return

        cid = interaction.data.get("custom_id", "")
        if not cid.startswith("rps|"):
            return

        # ID no formato: rps|<game_id>|<choice>
        parts = cid.split("|")
        if len(parts) != 3:
            return

        _, game_id, choice = parts

        if game_id not in self.ongoing_games:
            return await interaction.response.send_message(
                "Partida expirada ou inválida!",
                ephemeral=True
            )

        game = self.ongoing_games[game_id]

        # Verifica se quem clicou faz parte da partida
        if interaction.user.id not in (game["userA"].id, game["userB"].id):
            return await interaction.followup.send(
                "❌ Você não faz parte dessa partida!",
                ephemeral=True
            )

        side = "A" if interaction.user.id == game["userA"].id else "B"

        if game[side] is not None:
            return await interaction.response.send_message(
                "Você já escolheu!",
                ephemeral=True
            )

        # Salva a escolha
        game[side] = choice

        await interaction.response.send_message(
            f"✅ {interaction.user.display_name} escolheu **{choice}**!",
            ephemeral=True
        )

        # Se os dois já escolheram, calcula o resultado
        if game["A"] and game["B"]:
            winner = self.get_winner(game["A"], game["B"])
            db = self.bot.get_cog("XP").col
            amount = game["amount"]
            tax = int(amount * TAX_RATE)
            reward = amount - tax
            userA = game["userA"]
            userB = game["userB"]

            text = (
                f"🪨📄✂ **Resultado!**\n"
                f"{userA.mention} jogou **{game['A']}**\n"
                f"{userB.mention} jogou **{game['B']}**\n"
            )

            if winner is None:
                text += "\n➡️ **Empate!** Ninguém perde ralcoins!"
            elif winner == "A":
                text += (f"\n🎉 {userA.mention} **venceu** e ganhou **{reward} ralcoins**!\n🏦 Taxa do bot (5%): **{tax} ralcoins**\n")
                db.update_one({"_id": userA.id}, {"$inc": {"coins": reward}})
                db.update_one({"_id": userB.id}, {"$inc": {"coins": -amount}})
                db.update_one(
                    {"_id": BOT_ECONOMY_ID},
                    {"$inc": {"coins": tax}}
                )

            else:
                text += (f"\n🎉 {userB.mention} **venceu** e ganhou **{reward} ralcoins**!\n🏦 Taxa do bot (5%): **{tax} ralcoins**\n")
                db.update_one({"_id": userB.id}, {"$inc": {"coins": reward}})
                db.update_one({"_id": userA.id}, {"$inc": {"coins": -amount}})
                db.update_one(
                    {"_id": BOT_ECONOMY_ID},
                    {"$inc": {"coins": tax}}
                )


            del self.ongoing_games[game_id]
            await interaction.followup.send(text)

async def setup(bot):
    await bot.add_cog(RockPaperScissors(bot))