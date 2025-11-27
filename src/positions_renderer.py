"""
Positions Renderer - Generate PNG images of stock and option positions

Renders current positions (stocks and options) as professional-looking PNG images
with color coding for P/L, similar to ScannerRenderer.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import logging
import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

import constants as const


logger = logging.getLogger(__name__)


class PositionsRenderer:
    """
    Renders positions data as formatted PNG images with color coding.
    Shows both stock holdings and open options with P/L highlighting.
    """

    # Color scheme (matching scanner style)
    BG_COLOR = "#1a1d29"  # Dark background
    HEADER_BG = "#2a2d39"  # Slightly lighter for header
    ALT_ROW_BG = "#1e2129"  # Very subtle alternating row background
    TEXT_COLOR = "#ffffff"  # White text
    RED_TEXT = "#ff4444"  # Red for losses
    GREEN_TEXT = "#44ff44"  # Green for profits
    YELLOW_TEXT = "#ffff44"  # Yellow for moderate values
    GRID_COLOR = "#2a2d39"  # Very subtle grid lines

    def __init__(self, output_dir=None):
        """
        Initialize the renderer

        Args:
            output_dir: Optional output directory. Defaults to DOWNLOADS_DIR if not specified.
        """
        self.output_dir = output_dir if output_dir else const.DOWNLOADS_DIR
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def _get_cell_color(self, value, column_name):
        """
        Determine text color based on value and column.

        Args:
            value: The cell value
            column_name: Name of the column

        Returns:
            Color string for the text
        """
        # Handle non-numeric values
        if pd.isna(value) or isinstance(value, str):
            return self.TEXT_COLOR

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            return self.TEXT_COLOR

        # Color coding rules based on column
        if "P/L" in column_name or "Unreal" in column_name:
            # Profit/Loss: green for positive, red for negative
            if numeric_value > 0:
                return self.GREEN_TEXT
            if numeric_value < 0:
                return self.RED_TEXT
            return self.TEXT_COLOR

        if "Mkt Value" in column_name or "Premium" in column_name:
            # Market value and premium: yellow for large positions
            if abs(numeric_value) >= 10000:
                return self.YELLOW_TEXT
            return self.TEXT_COLOR

        # Default color
        return self.TEXT_COLOR

    def _format_cell_value(self, value, column_name):
        """
        Format cell value for display.

        Args:
            value: The cell value
            column_name: Name of the column

        Returns:
            Formatted string
        """
        if pd.isna(value):
            return "-"

        # String values (like dates, symbols)
        if isinstance(value, str):
            return value

        try:
            numeric_value = float(value)

            # Format based on column type
            if column_name in ["Symbol", "Strike", "Exp"]:
                return str(value)
            if "Shares" in column_name or "Contracts" in column_name or "DTE" in column_name:
                return f"{int(numeric_value):,}"
            if "Cost" in column_name or "Current" in column_name or "Price" in column_name:
                return f"${numeric_value:.2f}"
            if "Value" in column_name or "Premium" in column_name or "P/L" in column_name or "Unreal" in column_name:
                # Format large numbers with parentheses for negatives
                if numeric_value < 0:
                    return f"(${abs(numeric_value):,.0f})"
                return f"${numeric_value:,.0f}"
            return str(value)
        except (ValueError, TypeError):
            return str(value)

    def render(self, stock_df: pd.DataFrame, options_df: pd.DataFrame,
               username: str | None = None, symbol_filter: str | None = None, account: str | None = None) -> str | None:
        """
        Render positions as a PNG image.

        Args:
            stock_df: DataFrame with stock positions (columns: symbol, shares, avg_cost, current_price, market_value, unrealized_pl)
            options_df: DataFrame with option positions (columns: symbol, strike, expiration_date, net_contracts, entry_premium, dte, unrealized_pl)
            username: Optional username for filename prefix
            symbol_filter: Optional symbol filter applied
            account: Optional account filter applied

        Returns:
            Path to the generated PNG file, or None if no positions
        """
        if stock_df.empty and options_df.empty:
            logger.warning("No positions to render")
            return None

        # Set up the figure with dark theme
        plt.style.use("dark_background")

        # Calculate totals before formatting DataFrames
        total_stock_value = stock_df["market_value"].sum() if not stock_df.empty else 0
        total_stock_pl = stock_df["unrealized_pl"].sum() if not stock_df.empty else 0
        total_option_premium = options_df["entry_premium"].sum() if not options_df.empty else 0

        # Prepare display DataFrames
        sections = []
        section_titles = []

        if not stock_df.empty:
            # Calculate total cost basis (shares × avg_cost)
            cost_basis = stock_df["shares"] * stock_df["avg_cost"]

            display_stock_df = pd.DataFrame({
                "Symbol": stock_df["symbol"],
                "Shares": stock_df["shares"],
                "Avg Cost": stock_df["avg_cost"],
                "Cost": cost_basis,
                "Current": stock_df["current_price"],
                "Mkt Value": stock_df["market_value"],
                "Unreal. P/L": stock_df["unrealized_pl"]
            })
            sections.append(display_stock_df)
            section_titles.append("Stocks")

        if not options_df.empty:
            display_options_df = pd.DataFrame({
                "Symbol": options_df["symbol"],
                "Strike": options_df["strike"],
                "Exp": options_df["expiration_date"].apply(lambda x: datetime.strptime(x, "%Y-%m-%d").strftime("%m/%d")),
                "Contracts": options_df["net_contracts"],
                "Premium": options_df["entry_premium"],
                "DTE": options_df["dte"],
                "Unreal. P/L": options_df["unrealized_pl"]
            })
            sections.append(display_options_df)
            section_titles.append("Options")

        # Find max column count across all sections
        max_cols = max(len(df.columns) for df in sections)

        # Calculate figure size based on total rows
        total_rows = sum(len(df) for df in sections)
        n_sections = len(sections)

        # Add extra rows for section titles and column headers
        effective_rows = total_rows + (n_sections * 2)  # Title + headers per section
        fig_height = max(4, effective_rows * 0.25 + 2.5)
        fig_width = 10  # Narrower width for tighter columns

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.set_facecolor(self.BG_COLOR)
        fig.patch.set_facecolor(self.BG_COLOR)

        # Hide axes
        ax.axis("off")
        ax.axis("tight")

        # Build combined display with section headers
        combined_rows = []

        for section_idx, (df, section_title) in enumerate(zip(sections, section_titles)):
            # Add section header as a separator row (padded to max_cols)
            separator_row = [""] * max_cols
            separator_row[0] = section_title
            combined_rows.append(separator_row)

            # Add column headers for this section (padded to max_cols)
            header_row = list(df.columns)
            header_row.extend([""] * (max_cols - len(header_row)))
            combined_rows.append(header_row)

            # Add data rows (padded to max_cols)
            for _, row in df.iterrows():
                formatted_row = [self._format_cell_value(row[col], col) for col in df.columns]
                # Pad with empty strings to match max_cols
                formatted_row.extend([""] * (max_cols - len(formatted_row)))
                combined_rows.append(formatted_row)

        # Don't add summary rows to table - will use footer instead

        # Create the table with max_cols columns and no top-level header
        table = ax.table(
            cellText=combined_rows,
            colLabels=None,
            cellLoc="left",
            loc="center",
            bbox=[0, 0, 1, 1]  # type: ignore[arg-type]
        )

        # Style the table - compact like scanner
        table.auto_set_font_size(False)
        table.set_fontsize(7)  # Smaller font like scanner
        table.scale(0.85, 0.8)  # Very tight horizontal scale

        # Calculate relative column widths based on content (excluding section title rows)
        # Use aggressive multiplier to make columns tighter
        col_widths = {}
        section_title_set = set(section_titles)  # "Stocks", "Options"

        for i in range(max_cols):
            # Check all rows for max width in this column, excluding section titles
            data_lens = []
            for row in combined_rows:
                # Skip section title rows
                if str(row[0]) not in section_title_set:
                    data_lens.append(len(str(row[i])))

            max_len = max(data_lens) if data_lens else 1
            # Apply 0.7 multiplier to make columns tighter (compensate for matplotlib padding)
            col_widths[i] = max_len * 0.7

        # Normalize widths to relative proportions
        total_width = sum(col_widths.values())
        for i in col_widths:
            col_widths[i] = col_widths[i] / total_width

        # Apply column widths to all cells
        for i in range(max_cols):
            width = col_widths[i]
            for row_num in range(len(combined_rows)):
                cell = table[(row_num, i)]
                cell.set_width(width)

        # Style all rows
        row_offset = 0
        for section_idx, (df, section_title) in enumerate(zip(sections, section_titles)):
            # Section title row - first cell has text, others are empty but styled to span
            for j in range(max_cols):
                cell = table[(row_offset, j)]
                cell.set_facecolor(self.HEADER_BG)
                if j == 0:
                    cell.set_text_props(weight="bold", color=self.YELLOW_TEXT, ha="left", fontsize=9)
                else:
                    # Hide borders on empty cells to create spanning effect
                    cell.set_edgecolor(self.HEADER_BG)
                cell.set_height(0.03)  # Compact like scanner
                cell.set_linewidth(0.3 if j == 0 else 0)

            row_offset += 1

            # Column header row
            for j in range(max_cols):
                cell = table[(row_offset, j)]
                cell.set_facecolor(self.HEADER_BG)
                # Left align first column (Symbol), right align numbers
                ha = "left" if j == 0 else "right"
                cell.set_text_props(weight="bold", color=self.TEXT_COLOR, ha=ha, fontsize=7)
                cell.set_height(0.03)  # Compact like scanner
                cell.set_edgecolor(self.TEXT_COLOR)
                cell.set_linewidth(0.5)

            row_offset += 1

            # Data rows for this section
            for i in range(len(df)):
                for j in range(max_cols):
                    cell = table[(row_offset + i, j)]

                    # Alternating row colors
                    if i % 2 == 0:
                        cell.set_facecolor(self.ALT_ROW_BG)
                    else:
                        cell.set_facecolor(self.BG_COLOR)

                    # Get cell value and apply color (only for actual data columns)
                    if j < len(df.columns):
                        col = df.columns[j]
                        value = df.iloc[i, j]
                        text_color = self._get_cell_color(value, col)
                        # Left align Symbol column, right align all others
                        ha = "left" if col == "Symbol" else "right"
                    else:
                        text_color = self.TEXT_COLOR
                        ha = "left"

                    cell.set_text_props(color=text_color, ha=ha, fontsize=7)
                    cell.set_height(0.025)  # Very compact rows like scanner
                    cell.set_edgecolor(self.TEXT_COLOR)
                    cell.set_linewidth(0.3)

            row_offset += len(df)

        # Add title with timestamp above the table
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build filter string for symbol and/or account
        filters = []
        if account:
            filters.append(account)
        if symbol_filter:
            filters.append(symbol_filter)
        filter_str = f" ({' - '.join(filters)})" if filters else ""

        title_text = f"Current Positions{filter_str} - {timestamp_str}"
        plt.title(title_text, color=self.TEXT_COLOR, fontsize=14, fontweight="bold", pad=20)

        # Adjust layout first to position table - leave space at bottom for footer
        plt.tight_layout(rect=[0, 0.08, 1, 0.95])  # type: ignore[arg-type]

        # Add footer with summary - positioned below table
        pl_str = f"${total_stock_pl:,.0f}" if total_stock_pl >= 0 else f"(${abs(total_stock_pl):,.0f})"
        footer_text = f"Total Stock Value: ${total_stock_value:,.0f} | Total Stock P/L: {pl_str} | Total Option Premium: ${total_option_premium:,.0f}"
        plt.figtext(0.5, 0.03, footer_text, ha="center", fontsize=9, color=self.TEXT_COLOR)

        # Save to file with optional username prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if username:
            filename = f"{username}_positions_{timestamp}.png"
        else:
            filename = f"positions_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)

        plt.savefig(filepath, facecolor=self.BG_COLOR, edgecolor="white",
                   dpi=150, bbox_inches="tight", pad_inches=0.05)
        plt.close()

        logger.info(f"Positions image saved to {filepath}")
        return filepath


def main():
    """Test the renderer with sample data"""
    from db import Db
    from positions import Positions
    from shares import Shares
    from trades import Trades

    db = Db()
    shares = Shares(db)
    trades = Trades(db)
    positions = Positions(db, shares, trades)

    # Test with real data
    username = "testuser"
    stock_df, options_df = positions.as_df(username, account=None)

    renderer = PositionsRenderer()
    output_path = renderer.render(stock_df, options_df, username=username)

    if output_path:
        print(f"Test image generated: {output_path}")
    else:
        print("No positions to render")


if __name__ == "__main__":
    main()
