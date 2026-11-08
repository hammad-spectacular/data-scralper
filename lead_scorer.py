"""
lead_scorer.py
--------------
Computes a Lead Score (0–100) for each business based on:
  - Rating           : 0–5 stars → up to 20 pts
  - Review count     : log-scaled → up to 30 pts
  - Website opportunity : TERRIBLE WEBSITE = 30 pts, POOR WEBSITE = 25.5,
                          NO WEBSITE = 21, SOCIAL ONLY = 15, HAS WEBSITE = 0
  - Contactable      : has a phone number = 20 pts

Providers without reputation data (e.g. Geoapify has no ratings/reviews) are
scored on website status + contactability only, rescaled to 0–100.
Permanently closed businesses always score 0.

Every lead also gets a 'Priority' column encoding the sales priority:
  1 = MAKES VIDEOS + NO WEBSITE (posts video but has no site — contact first)
  2 = TERRIBLE WEBSITE  (has a site, it's terrible — best pitch)
  3 = POOR WEBSITE      (has a site, it's bad)
  4 = NO WEBSITE        (no site at all)
  5 = SOCIAL ONLY       (public socials, no real site)
  6 = HAS WEBSITE       (a working site)
Leads that make videos also earn a small Lead Score bump, so they win ties
inside their own priority tier (the website tier itself is never overridden
by ratings/reviews).
Use sort_by_priority() to order results: Priority first, then Lead Score.

Higher score = better prospect for selling a website.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Score weights (must sum to 100)
# ---------------------------------------------------------------------------
W_RATING = 20      # max points from star rating
W_REVIEWS = 30     # max points from review count
W_WEBSITE = 30     # max points from website status
W_CONTACT = 20     # points for having a phone number
W_EMAIL = 10       # extra points for a public email (sources without ratings only)

SCORE_WEIGHTS = {
    "Rating": W_RATING,
    "Reviews (log-scaled)": W_REVIEWS,
    "Website opportunity (terrible 100% → working 0%)": W_WEBSITE,
    "Has phone number": W_CONTACT,
    "Has email (when there are no ratings)": W_EMAIL,
}

# Review count at which a business earns the full review points
REVIEWS_SCALE = 200.0

# Sales priority: lower number = contact first. Never overridden by rating/reviews.
# Video-makers without a real website jump in front of everything (priority 1),
# so every other status is shifted down by one slot.
WEBSITE_PRIORITY = {
    "TERRIBLE WEBSITE": 2,
    "POOR WEBSITE": 3,
    "NO WEBSITE": 4,
    "SOCIAL ONLY": 5,
    "HAS WEBSITE": 6,
}
VIDEO_FIRST_PRIORITY = 1        # makes videos + (NO WEBSITE | SOCIAL ONLY)
_UNKNOWN_PRIORITY = 7           # anything we don't know goes last
_VIDEO_SCORE_BUMP = 6           # small tie-break edge within the same priority tier

# How much of the 30 website points each status earns (mirrors WEBSITE_PRIORITY)
_WEBSITE_FACTOR = {
    "TERRIBLE WEBSITE": 1.0,
    "POOR WEBSITE": 0.85,
    "NO WEBSITE": 0.7,
    "SOCIAL ONLY": 0.5,
    "HAS WEBSITE": 0.0,
}


def _numeric(df: pd.DataFrame, col: str) -> pd.Series:
    """Column as float with NaN for missing/invalid values."""
    if col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").astype("float64")


def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add / overwrite integer 'Lead Score' (0–100) and 'Priority' columns
    (vectorised, NaN-safe). Uses columns: Rating, Reviews, Website Status,
    Phone, Business Status, Video Content.
    """
    if df.empty:
        df["Lead Score"] = pd.Series(dtype="int64")
        df["Priority"] = pd.Series(dtype="int64")
        return df

    rating = _numeric(df, "Rating")
    reviews = _numeric(df, "Reviews")
    # Reputation data exists per *source* (Google has ratings, Geoapify/Companies House don't),
    # so judge each source separately — important when saved leads from several sources are mixed.
    has_data = rating.notna() | reviews.notna()
    if "Source" in df.columns:
        has_reputation = has_data.groupby(df["Source"].fillna("")).transform("any")
    else:
        has_reputation = pd.Series(bool(has_data.any()), index=df.index)

    rating_pts = rating.fillna(0).clip(0, 5) / 5.0 * W_RATING
    review_pts = (
        np.minimum(np.log1p(reviews.fillna(0).clip(lower=0)) / math.log(REVIEWS_SCALE + 1), 1.0)
        * W_REVIEWS
    )

    status = df["Website Status"] if "Website Status" in df.columns else pd.Series("", index=df.index)
    website_pts = status.map(_WEBSITE_FACTOR).fillna(0.0) * W_WEBSITE

    phone = df["Phone"] if "Phone" in df.columns else pd.Series("", index=df.index)
    contact_pts = phone.fillna("").astype(str).str.strip().ne("") * float(W_CONTACT)

    email = (
        df["Email"].fillna("").astype(str).str.contains("@")
        if "Email" in df.columns else pd.Series(False, index=df.index)
    )
    email_pts = email * float(W_EMAIL)

    full = rating_pts + review_pts + website_pts + contact_pts
    rescaled = (website_pts + contact_pts + email_pts) / (W_WEBSITE + W_CONTACT + W_EMAIL) * 100.0
    total = full.where(has_reputation, rescaled)

    if "Business Status" in df.columns:
        closed = df["Business Status"].fillna("").astype(str).str.upper().str.startswith("CLOSED")
        total = total.mask(closed, 0.0)

    # 🎬 Do they make video content for their business? (filled by _scan_leads)
    makes_video = (
        df["Video Content"].fillna("").astype(str).str.strip().str.upper().eq("YES")
        if "Video Content" in df.columns
        else pd.Series(False, index=df.index)
    )

    df["Lead Score"] = total.round().astype("int64")
    # Video-makers get a small edge inside their own tier — the website priority
    # itself is never overridden (ratings/reviews don't move it either).
    df["Lead Score"] = (
        df["Lead Score"] + makes_video.astype("int64") * _VIDEO_SCORE_BUMP
    ).clip(0, 100).astype("int64")

    # Priority 1 = makes videos AND has no real website — everyone else shifts down.
    base_priority = status.map(WEBSITE_PRIORITY).fillna(_UNKNOWN_PRIORITY)
    no_real_site = status.isin(("NO WEBSITE", "SOCIAL ONLY"))
    df["Priority"] = np.where(
        makes_video & no_real_site, VIDEO_FIRST_PRIORITY, base_priority
    ).astype("int64")
    return df


def sort_by_priority(df: pd.DataFrame) -> pd.DataFrame:
    """
    Order leads the way they should be worked: sales priority first
    (1 = makes videos + no website … 6 = working website), then Lead Score
    descending. Deterministic (stable sort), resets the index — safe for
    row-position callbacks.
    """
    if "Priority" in df.columns and "Lead Score" in df.columns and not df.empty:
        out = df.sort_values(["Priority", "Lead Score"], ascending=[True, False], kind="stable")
    elif "Lead Score" in df.columns and not df.empty:
        out = df.sort_values("Lead Score", ascending=False, kind="stable")
    else:
        out = df
    return out.reset_index(drop=True)
