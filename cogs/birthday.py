import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo
import asyncio

BIRTHDAY_PAGE_SIZE = 10

class BirthdayView(discord.ui.View):
    def __init__(self, cog, interaction, month, page):
        super().__init__(timeout=60)
        self.cog = cog
        self.interaction = interaction
        self.month = month
        self.page = page
        self.author_id = interaction.user.id
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Apenas quem executou o comando pode usar.",
                ephemeral=True
            )
            return False
        return True

    async def update(self, interaction):
        embed = await self.cog.build_birthday_embed(
            interaction,
            self.month,
            self.page,
            BIRTHDAY_PAGE_SIZE
        )
        await interaction.response.edit_message(embed=embed, view=self)

    # ⬅️ Página anterior
    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction, button):
        if self.page > 0:
            self.page -= 1
        await self.update(interaction)

    # ➡️ Próxima página
    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction, button):
        self.page += 1
        await self.update(interaction)

    # 📅 Dropdown de meses
    @discord.ui.select(
        placeholder="📅 Escolha um mês",
        row=1,
        options=[
            discord.SelectOption(label=f"{i:02d}", value=str(i))
            for i in range(1, 13)
        ]
    )
    async def select_month(self, interaction, select):
        self.month = int(select.values[0])
        self.page = 0
        await self.update(interaction)
        

class BirthdayDMView(discord.ui.View):
    def __init__(self, cog, user_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id

    @discord.ui.button(label="Ativar DMs", style=discord.ButtonStyle.success)
    async def enable(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.col.update_one(
            {"_id": self.user_id},
            {"$set": {"birthday_dm": True}},
            upsert=True
        )
        await interaction.response.edit_message(
            content="📬 DMs de aniversário **ativadas**!",
            view=None
        )

    @discord.ui.button(label="Desativar DMs", style=discord.ButtonStyle.danger)
    async def disable(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.col.update_one(
            {"_id": self.user_id},
            {"$set": {"birthday_dm": False}},
            upsert=True
        )
        await interaction.response.edit_message(
            content="📪 DMs de aniversário **desativadas**!",
            view=None
        )

class Birthday(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.col = bot.get_cog("XP").col   
        self.config_col = bot.db.birthday_config 
        self.birthday_check.start()

    @tasks.loop(minutes=60)
    async def birthday_check(self):
        await self.bot.wait_until_ready()

        try:
            now = datetime.now(ZoneInfo("America/Sao_Paulo"))
            current_hour = now.hour
            day = now.day
            month = now.month

            users = self.col.find({
                "birthday.day": day,
                "birthday.month": month
            })

            for user_data in users:
                user_id = user_data["_id"]

                for guild in self.bot.guilds:
                    member = guild.get_member(user_id)
                    if not member:
                        continue

                    config = self.config_col.find_one({"_id": guild.id})
                    if not config:
                        continue

                    if config.get("hour") != current_hour:
                        continue

                    channel_id = config.get("channel_id")
                    if not channel_id:
                        continue

                    channel = guild.get_channel(channel_id)
                    if not channel:
                        continue

                    role = guild.get_role(config.get("role_id"))

                    message = config.get(
                        "message",
                        "🎉 Feliz aniversário, {user}! 🎂"
                    ).replace("{user}", member.mention)

                    await channel.send(message)

                    if role:
                        try:
                            await member.add_roles(role)
                            asyncio.create_task(self.remove_role_later(member, role))
                        except discord.Forbidden:
                            pass

                    if user_data.get("birthday_dm", True):
                        try:
                            await member.send(
                                f"🎂 Feliz aniversário, {member.mention}! Que seu dia seja incrível 💖"
                            )
                        except discord.Forbidden:
                            pass

        except Exception as e:
            print(f"[Birthday Task ERROR] {e}")


    # =========================
    # 🎂 GROUP /birthday
    # =========================
    birthday = app_commands.Group(
        name="birthday",
        description="Sistema de aniversários"
    )

    # -------------------------
    # /birthday set
    # -------------------------
    @birthday.command(name="set", description="Definir ou atualizar seu aniversário")
    async def birthday_set(
        self,
        interaction: discord.Interaction,
        day: app_commands.Range[int, 1, 31],
        month: app_commands.Range[int, 1, 12]
    ):
        self.col.update_one(
            {"_id": interaction.user.id},
            {"$set": {"birthday": {"day": day, "month": month}}},
            upsert=True
        )

        await interaction.response.send_message(
            f"🎂 Seu aniversário foi definido para **{day:02d}/{month:02d}**!"
        )

    # -------------------------
    # /birthday view
    # -------------------------
    @birthday.command(name="view", description="Ver aniversário de alguém")
    async def birthday_view(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None
    ):
        user = user or interaction.user
        data = self.col.find_one({"_id": user.id})

        if not data or "birthday" not in data:
            return await interaction.response.send_message(
                "❌ Esse usuário não definiu aniversário."
            )

        b = data["birthday"]
        await interaction.response.send_message(
            f"🎉 Aniversário de **{user.display_name}**: **{b['day']:02d}/{b['month']:02d}**"
        )

    # -------------------------
    # /birthday list
    # -------------------------
    @birthday.command(name="list", description="Listar aniversariantes de um mês")
    @app_commands.describe(month="Mês do aniversário (1–12)")
    async def birthday_list(
        self,
        interaction: discord.Interaction,
        month: app_commands.Range[int, 1, 12]
    ):
        page = 0

        embed = await self.build_birthday_embed(
            interaction,
            month,
            page,
            BIRTHDAY_PAGE_SIZE
        )

        view = BirthdayView(
            cog=self,
            interaction=interaction,
            month=month,
            page=page
        )

        await interaction.response.send_message(
            embed=embed,
            view=view
        )

        view.message = await interaction.original_response()


    async def build_birthday_embed(
        self,
        interaction: discord.Interaction,
        month: int,
        page: int,
        page_size: int
    ):
        skip = page * page_size

        users = list(
            self.col.find({"birthday.month": month})
            .sort("birthday.day", 1)
            .skip(skip)
            .limit(page_size)
        )

        embed = discord.Embed(
            title=f"🎂 Aniversariantes do mês {month:02d}",
            color=discord.Color.pink()
        )

        if not users:
            embed.description = "❌ Nenhum aniversário encontrado para este mês."
            return embed

        for u in users:
            member = interaction.guild.get_member(u["_id"])
            if member:
                embed.add_field(
                    name=member.display_name,
                    value=f"📅 {u['birthday']['day']:02d}/{month:02d}",
                    inline=False
                )

        embed.set_footer(text=f"Página {page + 1}")
        return embed


    # -------------------------
    # /birthday remove
    # -------------------------
    @birthday.command(name="remove", description="Remover seu aniversário")
    async def birthday_remove(self, interaction: discord.Interaction):
        self.col.update_one(
            {"_id": interaction.user.id},
            {"$unset": {"birthday": ""}}
        )

        await interaction.response.send_message(
            "🗑️ Seu aniversário foi removido."
        )

    # -------------------------
    # /birthday config (ADMIN)
    # -------------------------
    @birthday.command(name="config", description="Configurar sistema de aniversário")
    @app_commands.checks.has_permissions(administrator=True)
    async def birthday_config(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        hour: app_commands.Range[int, 0, 23],
        role: discord.Role | None = None,
        message: str | None = None
    ):
        
        await interaction.response.defer(ephemeral=True)

        self.config_col.update_one(
            {"_id": interaction.guild.id},
            {"$set": {
                "channel_id": channel.id,
                "role_id": role.id if role else None,
                "hour": hour,
                "message": message or "🎉 Feliz aniversário, {user}! 🎂"
            }},
            upsert=True
        )

        await interaction.followup.send(
            f"⚙️ Aniversário configurado para **{hour:02d}:00** com sucesso!"
        )


async def setup(bot):
    await bot.add_cog(Birthday(bot))
