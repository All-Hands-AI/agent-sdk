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
    if abs(value) >= 0.01:
        # Normal rounding for typical amounts
        return f"${value:.2f}"
    elif abs(value) >= 0.001:
        # Round small numbers to 2 significant figures
        return f"${value:.2g}"
    else:
        # Use scientific notation for very small numbers
        return f"${value:.1e}"
