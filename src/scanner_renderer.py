#!/usr/bin/env python3
"""
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


class ScannerRenderer:
    """
    Renders scanner DataFrame results as a formatted PNG image with color coding.
    Based on the visual style of professional options scanning tools.
    """

    # Color scheme (matching the example image style)
    BG_COLOR = "#1a1d29"  # Dark background
    HEADER_BG = "#2a2d39"  # Slightly lighter for header
    ALT_ROW_BG = "#1e2129"  # Very subtle alternating row background
    TEXT_COLOR = "#ffffff"  # White text
    RED_TEXT = "#ff4444"  # Red for negative values
    GREEN_TEXT = "#44ff44"  # Green for positive/good values
    YELLOW_TEXT = "#ffff44"  # Yellow for moderate values
    GRID_COLOR = "#2a2d39"  # Very subtle grid lines (same as header)

    def __init__(self, output_dir=None):
        """
        Initialize the renderer

        Args:
            output_dir: Optional output directory. Defaults to OPTIONS_DATA_DIR if not specified.
        """
        self.output_dir = output_dir if output_dir else const.OPTIONS_DATA_DIR
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
        if column_name in ["Moneyness", "Mon%"]:
            # For premium sellers (selling PUTs/CALLs):
            # Green: -5% to -15% (sweet spot - decent premium with reasonable safety)
            # Yellow: -15% to -25% (safe but far OTM - lower premium)
            # White: < -25% (very far OTM - minimal premium)
            # Red: >= 0% (ATM or ITM - risky, high assignment risk)
            if numeric_value >= 0:
                return self.RED_TEXT
            if -15 <= numeric_value < -5:
                return self.GREEN_TEXT
            if -25 <= numeric_value < -15:
                return self.YELLOW_TEXT
            return self.TEXT_COLOR

        if column_name in ["Return %", "Ret%"]:
            # Return percentage: green for good, yellow for moderate
            if numeric_value >= 2.0:
                return self.GREEN_TEXT
            if numeric_value >= 1.0:
                return self.YELLOW_TEXT
            return self.TEXT_COLOR

        if column_name in ["Annual %", "Ann%"]:
            # Annualized return: green for high returns
            if numeric_value >= 100:
                return self.GREEN_TEXT
            if numeric_value >= 50:
                return self.YELLOW_TEXT
            return self.TEXT_COLOR

        if column_name in ["Delta", "Dlt"]:
            # Delta values are typically negative for puts, positive for calls
            return self.TEXT_COLOR

        if column_name in ["Theta", "Tht"]:
            # Theta - no color coding (always white)
            return self.TEXT_COLOR

        if column_name in ["IV"]:
            # Conservative seller perspective:
            # Green: 60-100% (sweet spot - good premium without extreme risk)
            # Yellow: 100%+ (high premium but very volatile/risky)
            # White: 40-60% (moderate)
            # Red: < 40% (not worth the risk/capital)
            if numeric_value < 40:
                return self.RED_TEXT
            if 60 <= numeric_value <= 100:
                return self.GREEN_TEXT
            if numeric_value > 100:
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
            if column_name in ["Price", "Pr", "Strike", "Str", "Bid", "Ask"]:
                return f"${numeric_value:.2f}"
            if column_name in ["Moneyness", "Mon%", "Return %", "Ret%"]:
                return f"{numeric_value:.1f}%"
            if column_name in ["Annual %", "Ann%"]:
                return f"{numeric_value:.0f}%"
            if column_name in ["Delta", "Dlt", "Theta", "Tht", "Gamma", "Gma"]:
                return f"{numeric_value:.2f}"
            if column_name in ["IV"]:
                return f"{numeric_value:.0f}"
            if column_name in ["Vol", "Open Int", "OI"]:
                return f"{int(numeric_value):,}"
            return str(value)
        except (ValueError, TypeError):
            return str(value)

    def render(self, df: pd.DataFrame, title: str = "Options Scanner Results", chain_type: str = "PUT",
               username: str | None = None, delta_min: float | None = None, delta_max: float | None = None, max_days: int | None = None) -> str | None:
        """
        Render DataFrame as a PNG image.

        Args:
            df: DataFrame with scanner results
            title: Title for the image
            chain_type: "PUT" or "CALL"
            username: Optional username for filename prefix
            delta_min: Minimum delta filter value
            delta_max: Maximum delta filter value
            max_days: Maximum days to expiration filter

        Returns:
            Path to the generated PNG file
        """
        if df.empty:
            logger.warning("Empty DataFrame provided to renderer")
            return None

        # Check if DataFrame has lowercase columns (raw data) or Title Case columns (already styled)
        # Scanner.as_df() returns lowercase, Scanner.styled_df() returns Title Case
        has_lowercase = any(col.islower() or col == "open_interest" for col in df.columns)

        if has_lowercase:
            # DataFrame has raw lowercase columns - convert to display format
            # Map lowercase to Title Case display names
            column_map = {
                "symbol": "Symbol",
                "market_price": "Price",
                "strike": "Strike",
                "moneyness": "Moneyness",
                "expiration": "Exp Date",
                "bid": "Bid",
                "ask": "Ask",
                "volume": "Vol",
                "open_interest": "Open Int",
                "delta": "Delta",
                "iv": "IV",
                "theta": "Theta",
                "gamma": "Gamma",
                "return_pct": "Return %",
                "delta_estimated": "Comment"
            }

            # Select and rename columns that exist in the DataFrame
            display_cols = {old: new for old, new in column_map.items() if old in df.columns}
            df = df[list(display_cols.keys())].rename(columns=display_cols)

            # Format expiration date from YYYY-MM-DD to MM/DD
            if "Exp Date" in df.columns:
                df["Exp Date"] = pd.to_datetime(df["Exp Date"]).dt.strftime("%m/%d")

            # Convert delta_estimated boolean to comment text
            if "Comment" in df.columns:
                df["Comment"] = df["Comment"].apply(lambda x: "Δ Est." if x else "")
        else:
            # DataFrame already has Title Case columns (backwards compatibility)
            display_cols = [col for col in df.columns if col[0].isupper() or " " in col]  # type: ignore[assignment]
            df = df[display_cols]

        # Set up the figure with dark theme
        plt.style.use("dark_background")

        # Calculate figure size based on data dimensions
        n_rows = len(df)
        n_cols = len(df.columns)

        # Adjust figure size (width, height in inches) - very compact like example
        fig_width = max(10, n_cols * 0.65)  # Tighter column spacing
        fig_height = max(4, n_rows * 0.20 + 1.8)  # Add extra space for title and footer

        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.set_facecolor(self.BG_COLOR)
        fig.patch.set_facecolor(self.BG_COLOR)

        # Hide axes
        ax.axis("off")
        ax.axis("tight")

        # Create table data with formatted values
        table_data = []
        for idx, row in df.iterrows():
            formatted_row = [self._format_cell_value(row[col], col) for col in df.columns]
            table_data.append(formatted_row)

        # Create the table
        table = ax.table(
            cellText=table_data,
            colLabels=df.columns,
            cellLoc="right",
            loc="center",
            bbox=[0, 0, 1, 1]  # type: ignore[arg-type]
        )

        # Style the table - much more compact like example
        table.auto_set_font_size(False)
        table.set_fontsize(7)  # Smaller font like example
        table.scale(0.95, 0.8)  # Tighter width and height for very compact layout

        # Calculate relative column widths based on content
        col_widths = {}
        for i, col in enumerate(df.columns):
            # Get max width of content in this column (header + all data)
            header_len = len(str(col))
            data_lens = [len(self._format_cell_value(df.iloc[j, i], col)) for j in range(len(df))]
            max_len = max([header_len] + data_lens)
            col_widths[i] = max_len

        # Normalize widths to relative proportions
        total_width = sum(col_widths.values())
        for i in col_widths:
            col_widths[i] = col_widths[i] / total_width  # type: ignore[assignment]

        # Apply column widths
        for i, col in enumerate(df.columns):
            width = col_widths[i]
            for j in range(-1, len(df)):  # -1 for header, then all data rows
                cell = table[(j + 1, i)]
                cell.set_width(width)

        # Style header and cells
        for i, col in enumerate(df.columns):
            # Header styling with thin white bottom border
            cell = table[(0, i)]
            cell.set_facecolor(self.HEADER_BG)
            cell.set_text_props(weight="bold", color=self.TEXT_COLOR, ha="right", fontsize=7)
            cell.set_height(0.03)  # Very compact header
            cell.set_edgecolor(self.TEXT_COLOR)  # White borders
            cell.set_linewidth(0.5)

        # Style data rows
        for i in range(len(df)):
            for j, col in enumerate(df.columns):
                cell = table[(i + 1, j)]

                # Very subtle alternating row colors
                if i % 2 == 0:
                    cell.set_facecolor(self.ALT_ROW_BG)
                else:
                    cell.set_facecolor(self.BG_COLOR)

                # Get cell value and apply color
                value = df.iloc[i, j]
                text_color = self._get_cell_color(value, col)
                cell.set_text_props(color=text_color, ha="right", fontsize=7)
                cell.set_height(0.025)  # Very compact rows - reduced from 0.035

                # Thin white borders for rows
                cell.set_edgecolor(self.TEXT_COLOR)
                cell.set_linewidth(0.3)

        # Add title with timestamp
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title_text = f"{chain_type.capitalize()} Options - {title} - {timestamp_str}"
        plt.title(title_text, color=self.TEXT_COLOR, fontsize=14, fontweight="bold", pad=20)

        # Add footer with scanner parameters - positioned below table with whitespace
        footer_parts = []
        if delta_min is not None:
            footer_parts.append(f"Delta Min: {delta_min:.2f}")
        if delta_max is not None:
            footer_parts.append(f"Delta Max: {delta_max:.2f}")
        if max_days is not None:
            footer_parts.append(f"Max DTE: {max_days}")

        # Adjust layout first to position table - leave space at bottom for footer
        plt.tight_layout(rect=[0, 0.08, 1, 0.95])  # type: ignore[arg-type]

        if footer_parts:
            footer_text = " | ".join(footer_parts)
            # Position footer below the table with proper spacing
            plt.figtext(0.5, 0.03, footer_text, ha="center", fontsize=9, color=self.TEXT_COLOR)

        # Save to file with optional username prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if username:
            filename = f"{username}_scanner_{chain_type.lower()}_{timestamp}.png"
        else:
            filename = f"scanner_{chain_type.lower()}_{timestamp}.png"
        filepath = os.path.join(self.output_dir, filename)

        # Save with white border around the entire image
        plt.savefig(filepath, facecolor=self.BG_COLOR, edgecolor="white",
                   dpi=150, bbox_inches="tight", pad_inches=0.05)
        plt.close()

        logger.info(f"Scanner image saved to {filepath}")
        return filepath


def main():
    """Test the renderer with sample data"""
    # Create sample data
    data = {
        "Symbol": ["TSLL", "MSTU", "BITX"] * 3,
        "Price": [124.19, 17.97, 52.75] * 3,
        "Strike": [110.0, 16.0, 50.0] * 3,
        "Moneyness": [-11.38, -11.00, -5.20] * 3,
        "Exp Date": ["10/17", "10/17", "10/17"] * 3,
        "Bid": [0.20, 0.20, 0.68] * 3,
        "Ask": [0.40, 0.40, 0.90] * 3,
        "Vol": [110, 110, 1834] * 3,
        "Open Int": [1640, 1640, 1379] * 3,
        "Delta": [-0.21, -0.21, -0.26] * 3,
        "IV": [172.0, 172.0, 102.0] * 3,
        "Theta": [-0.13, -0.13, -0.26] * 3,
        "Gamma": [0.10, 0.10, 0.07] * 3,
        "Return %": [1.7, 1.7, 1.5] * 3,
        "Annual %": [305.0, 305.0, 273.0] * 3,
    }

    df = pd.DataFrame(data)

    renderer = ScannerRenderer()
    output_path = renderer.render(df, title="Watchlist Scan", chain_type="PUT")
    print(f"Test image generated: {output_path}")


if __name__ == "__main__":
    main()
