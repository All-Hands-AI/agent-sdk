#!/usr/bin/env python3

"""
Utility function to format cost values with appropriate precision.
"""


def format_cost(value):
    """
    Format cost with smart precision to show meaningful values even for small amounts.

    Args:
        cost: The cost value to format

    Returns:
        Formatted cost string with appropriate precision
    """
    # Handle non-numeric input
    if not isinstance(value, (int, float)):
        try:
            value = float(value)
        except (ValueError, TypeError):
            return str(value)  # Return as-is if can't convert to number

    # Handle NaN or infinite values
    if not (isinstance(value, (int, float)) and abs(value) < float("inf")):
        return str(value)

    if abs(value) >= 0.01:
        # Normal rounding for typical amounts
        return f"${value:.2f}"
    elif abs(value) >= 0.001:
        # Round small numbers to 2 significant figures
        return f"${value:.2g}"
    else:
        # Use scientific notation for very small numbers
        return f"${value:.1e}"
