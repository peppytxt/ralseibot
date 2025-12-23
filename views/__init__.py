class RankView(discord.ui.View):
    def __init__(self, cog, interaction, page, page_size, build_func):
        super().__init__(timeout=60)

        self.cog = cog
        self.interaction = interaction
        self.page = page
        self.page_size = page_size
        self.build_func = build_func

        self.message = None
