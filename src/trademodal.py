#!/usr/bin/env python3
"""
Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
from datetime import datetime

import discord

import constants as const
from brokers.parsefactory import ParseFactory
from deposits import Deposits
from dividends import Dividends
from shares import Shares
from trades import Trades


# Get a logger instance
logger = logging.getLogger(__name__)

class TradeModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        dt_str = datetime.now().strftime("%m/%d/%Y")
        self.transaction_date_input: discord.ui.TextInput = discord.ui.TextInput(label="Transaction Date (format: m/d/YYYY)", default=dt_str, style=discord.TextStyle.short)

        placeholder = "Enter each trade on a new line.\n" \
                      "STO 2x TSLL 7/18 $10P @ $.28\n" \
                      "BTC 1x TSLL 7/25 $10P @ $.01"

        # Create a TextInput for trades
        self.trades_input: discord.ui.TextInput = discord.ui.TextInput(label="Trades (Syntax: STO 1x TSLL 7/18 $10P @ $.15)", placeholder=placeholder, style=discord.TextStyle.long)

        # Account selection
        self.account_input: discord.ui.TextInput = discord.ui.TextInput(label="Account (default, IRA, Roth, etc.)", default="default", style=discord.TextStyle.short)

        # Allow trades to be publicly visible
        self.public_trade_input: discord.ui.TextInput = discord.ui.TextInput(label="Share Trade (True/False)", default="False", style=discord.TextStyle.short)

        self.add_item(self.transaction_date_input)
        self.add_item(self.trades_input)
        self.add_item(self.account_input)
        self.add_item(self.public_trade_input)

        self.trades = None

    def set_trades(self, trades: Trades, dividends: Dividends, deposits: Deposits, shares: Shares):
        self.trades = trades  # type: ignore[assignment]
        self.dividends = dividends
        self.deposits = deposits
        self.shares = shares


    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Trade Information", color=discord.Color.blue())
        embed.add_field(name="Transaction Date", value=self.transaction_date_input.value)
        embed.add_field(name="Trades", value=self.trades_input.value)
        embed.add_field(name="Public Trade", value=self.public_trade_input.value)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Access and process the submitted data
        transaction_date = self.transaction_date_input.value
        trades = self.trades_input.value
        account = self.account_input.value.strip() if self.account_input.value.strip() else "default"
        public_trade = self.public_trade_input.value.lower() == "true"
        user = interaction.user.name

        # Capture guild_id from the Discord interaction
        guild_id = interaction.guild.id if interaction.guild else None

        # dstr = datetime.strptime(trasaction_date, "%m/%d/%Y").strftime("%Y-%m-%d")
        logger.info(f"Transaction Date: {transaction_date}, Trades: {trades}, Guild ID: {guild_id}, Account: {account}")

        pf = ParseFactory(user, transaction_date, self.trades, self.dividends, self.deposits, self.shares, guild_id=guild_id, account=account)  # type: ignore[arg-type]

        trades_list = trades.splitlines()
        status_list = list()
        valid = True
        for trade_str in trades_list:
            parser, impl = pf.factory(trade_str)
            if parser is None:
                status_list.append(f"{trade_str}: Validated: False")
                valid = False
                continue

            parser.parse()
            status = parser.is_valid()
            status_list.append(f"{trade_str}: Validated: {status}")
            if not status:
                valid = False

        if not valid:
            s1 = "\n".join(status_list)
            logger.info(f"Validation failed\n {s1}")
            await interaction.response.send_message(f"Invalid trade:\n```{s1}```", ephemeral=True)
            return


        ephemeral = not public_trade
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)
        # If validation passes, save trades to the database
        status_list = list()
        for trade_str in trades_list:
            parser, impl = pf.factory(trade_str)
            if parser is None or impl is None:
                continue
            # mypy doesn't understand that continue means impl is not None
            assert impl is not None
            parser.parse()
            status = parser.is_valid()
            nt = parser.as_named_tuple()
            impl.insert(nt)  # type: ignore[attr-defined]
            status_list.append(f"{trade_str}")

        s1 = "\n".join(status_list)


        logger.info(f"{user} public_trade: {public_trade}\ntrades.\n{s1}")
        await interaction.followup.send( f"{user} trades.\n```{s1}```" , ephemeral=ephemeral
        # await interaction.response.send_message( f"{user} trades.\n```{s1}```" , ephemeral=ephemeral
        )

def main():
    logger.info("main")
    username = "sangelovich"
    transaction_date = datetime.now().strftime("%d/%m/%Y")

    for trade_str in const.TEST_TRADES:
        print(trade_str)


if __name__ == "__main__":
    main()
