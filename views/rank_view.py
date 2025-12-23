import discord

class RankView(discord.ui.View):
    def __init__(
        self,
        cog,
        interaction: discord.Interaction,
        page: int,
        page_size: int,
        build_func
    ):
        super().__init__(timeout=60)

        self.cog = cog
        self.interaction = interaction
        self.page = page
        self.page_size = page_size
        self.build_func = build_func


    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Apenas quem executou o comando pode usar esses botões.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message:
            await self.message.edit(view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page <= 0:
            await interaction.response.defer()
            return

        self.page -= 1
        embed = await self.build_func(interaction, self.page, self.page_size)
        await interaction.response.edit_message(embed=embed, view=self)
        
    @discord.ui.button(label="📍", style=discord.ButtonStyle.primary)
    async def my_position(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message(
                "❌ Apenas quem executou o comando pode usar.",
                ephemeral=True
            )

        # Descobre o rank do usuário
        rank = await self.get_user_rank(interaction.user)

        if rank is None:
            return await interaction.response.send_message(
                "❌ Você não está no ranking.",
                ephemeral=True
            )

        # Calcula a página
        self.page = (rank - 1) // self.page_size

        embed = await self.build_func(
            interaction,
            self.page,
            self.page_size
        )

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.interaction.user.id:
            return await interaction.response.send_message(
                "❌ Apenas quem usou o comando pode interagir.",
                ephemeral=True
            )

        self.page += 1

        embed = await self.build_func(
            interaction,
            self.page,
            self.page_size
        )

        await interaction.response.edit_message(embed=embed, view=self)

        
        
    async def get_user_rank(self, user: discord.Member):
        # RANK GLOBAL
        if self.build_func == self.cog.build_rank_embed:
            data = self.cog.col.find_one({"_id": user.id})
            if not data:
                return None

            xp = data.get("xp_global", 0)
            return self.cog.col.count_documents(
                {"xp_global": {"$gt": xp}}
            ) + 1

        # RANK LOCAL
        if self.build_func == self.cog.build_local_rank_embed:
            guild_id = str(self.interaction.guild.id)

            data = self.cog.col.find_one({"_id": user.id})
            if not data:
                return None

            xp = data.get("xp_local", {}).get(guild_id, {}).get("xp", 0)

            return self.cog.col.count_documents({
                f"xp_local.{guild_id}.xp": {"$gt": xp}
            }) + 1

        return None