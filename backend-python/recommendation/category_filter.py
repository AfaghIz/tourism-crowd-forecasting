"""
Optional whitelist filtering on ``category_clean`` (or another column).
"""

from __future__ import annotations

import pandas as pd

from recommendation.data_loader import COL_CATEGORY


def filter_by_categories(
    df: pd.DataFrame,
    allowed_categories: list[str] | set[str] | None,
    *,
    category_column: str = COL_CATEGORY,
) -> pd.DataFrame:
    """
    Keep only rows whose category appears in ``allowed_categories``.

    Parameters
    ----------
    df
        POI table.
    allowed_categories
        If ``None`` or empty, returns ``df`` unchanged (no filtering).
        Otherwise categories are compared case-insensitively after strip.
    category_column
        Column name for the category label (default OTM ``category_clean``).

    Returns
    -------
    pandas.DataFrame
        A filtered copy; empty if nothing matches.
    """
    if allowed_categories is None or len(allowed_categories) == 0:
        return df.copy()

    allow = {str(x).strip().lower() for x in allowed_categories if str(x).strip()}
    if not allow:
        return df.copy()

    if category_column not in df.columns:
        return df.iloc[0:0].copy()

    cats = df[category_column].astype("string").str.strip().str.lower()
    mask = cats.isin(allow)
    return df.loc[mask].copy()
