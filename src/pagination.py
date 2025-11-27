#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

from collections.abc import Callable

import discord


class Pagination(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, get_page: Callable):
        self.interaction = interaction
        self.get_page = get_page
        self.total_pages: int | None = None
        self.index = 1
        super().__init__(timeout=100)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        emb = discord.Embed(
            description="Only the author of the command can perform this action.",
            color=16711680
        )
        await interaction.response.send_message(embed=emb)
        return False

    async def navegate(self):
        emb, self.total_pages = await self.get_page(self.index)
        if self.total_pages == 1:
            await self.interaction.response.send_message(embed=emb, ephemeral=True)
        elif self.total_pages > 1:
            self.update_buttons()
            await self.interaction.response.send_message(embed=emb, view=self, ephemeral=True)

    async def edit_page(self, interaction: discord.Interaction):
        emb, self.total_pages = await self.get_page(self.index)
        self.update_buttons()
        await interaction.response.edit_message(embed=emb, view=self)

    def update_buttons(self):
        if self.total_pages is None:
            return
        if self.index > self.total_pages // 2:
            self.children[2].emoji = "⏮️"  # type: ignore[attr-defined]
        else:
            self.children[2].emoji = "⏭️"  # type: ignore[attr-defined]
        self.children[0].disabled = self.index == 1  # type: ignore[attr-defined]
        self.children[1].disabled = self.index == self.total_pages  # type: ignore[attr-defined]

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)  # type: ignore[arg-type]
    async def previous(self, interaction: discord.Interaction, button: discord.Button):
        self.index -= 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)  # type: ignore[arg-type]
    async def next(self, interaction: discord.Interaction, button: discord.Button):
        self.index += 1
        await self.edit_page(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.blurple)  # type: ignore[arg-type]
    async def end(self, interaction: discord.Interaction, button: discord.Button):
        if self.total_pages is None:
            return
        if self.index <= self.total_pages//2:
            self.index = self.total_pages
        else:
            self.index = 1
        await self.edit_page(interaction)

    async def on_timeout(self):
        # remove buttons on timeout
        message = await self.interaction.original_response()
        await message.edit(view=None)

    @staticmethod
    def compute_total_pages(total_results: int, results_per_page: int) -> int:
        return ((total_results - 1) // results_per_page) + 1
