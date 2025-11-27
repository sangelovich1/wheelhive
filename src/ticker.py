"""
Ticker model

Represents a valid ticker symbol (S&P 500, DOW, or custom additions)

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""



class Ticker:
    """Single ticker symbol with metadata"""

    def __init__(
        self,
        ticker: str,
        company_name: str | None = None,
        exchange: str | None = None,
        sector: str | None = None,
        is_active: bool = True
    ):
        """
        Initialize a ticker

        Args:
            ticker: Ticker symbol (e.g., 'AAPL', 'MSFT')
            company_name: Full company name
            exchange: Exchange (e.g., 'NASDAQ', 'NYSE', 'DOW')
            sector: Business sector
            is_active: Whether ticker is currently active/not delisted
        """
        self.ticker = ticker.upper()
        self.company_name = company_name
        self.exchange = exchange
        self.sector = sector
        self.is_active = is_active

    def to_tuple(self) -> tuple:
        """Convert to tuple for database insertion"""
        return (
            self.ticker,
            self.company_name,
            self.exchange,
            self.sector,
            self.is_active
        )

    def __repr__(self) -> str:
        return f"Ticker({self.ticker}, {self.company_name}, {self.exchange})"

    def __str__(self) -> str:
        active_str = "" if self.is_active else " [INACTIVE]"
        return f"{self.ticker} - {self.company_name or 'N/A'} ({self.exchange or 'N/A'}){active_str}"
