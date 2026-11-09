"""
website_classifier.py
---------------------
Classifies a business website URL into categories:
  - "TERRIBLE WEBSITE": real website, but PageSpeed quality < 40 (top priority)
  - "POOR WEBSITE"  : real website, PageSpeed quality 40–49 (slow, not mobile-friendly)
  - "NO WEBSITE"    : empty / null
  - "SOCIAL ONLY"   : social profile, free site-builder subdomain, or a
                      directory / booking page (not a site the business owns)
  - "HAS WEBSITE"   : a real, decent-enough business website

Returns (classification, social_link | None).
Matching is done on the URL's hostname (exact or subdomain), not substrings.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# PageSpeed quality thresholds: below TERRIBLE_QUALITY → "TERRIBLE WEBSITE",
# below POOR_QUALITY → "POOR WEBSITE" (both are "bad website" leads).
TERRIBLE_QUALITY = 40
POOR_QUALITY = 50

# Actual social networks (subset of SOCIAL_DOMAINS — no site builders / directories).
SOCIAL_NETWORKS = frozenset(
    {
        "facebook.com", "fb.com", "fb.me", "instagram.com", "tiktok.com",
        "twitter.com", "x.com", "linkedin.com", "youtube.com", "pinterest.com",
    }
)

# When several socials are known, show the most useful one first.
SOCIAL_PREFERENCE = (
    "facebook.com", "fb.com", "fb.me", "instagram.com", "linkedin.com",
    "tiktok.com", "youtube.com", "twitter.com", "x.com", "pinterest.com",
)

SOCIAL_DOMAINS = frozenset(
    {
        # social / link-in-bio
        "facebook.com", "fb.com", "fb.me", "instagram.com", "linktr.ee",
        "linkin.bio", "wa.me", "whatsapp.com", "tiktok.com", "twitter.com",
        "x.com", "linkedin.com", "youtube.com", "pinterest.com",
        # free site builders
        "wixsite.com", "business.site", "sites.google.com", "godaddysites.com",
        "weebly.com", "blogspot.com", "wordpress.com", "carrd.co", "square.site",
        # maps / directories / booking / delivery pages
        "g.page", "goo.gl", "maps.app.goo.gl", "google.com", "yell.com",
        "checkatrade.com", "trustpilot.com", "yelp.com", "tripadvisor.com",
        "tripadvisor.co.uk", "freeindex.co.uk", "bark.com", "mybuilder.com",
        "ratedpeople.com", "thomsonlocal.com", "fresha.com", "treatwell.co.uk",
        "booksy.com", "opentable.com", "ubereats.com", "just-eat.co.uk",
        "deliveroo.co.uk", "uber.com",
    }
)


def _hostname(url: str) -> str:
    u = url.strip()
    if "://" not in u:
        u = "http://" + u
    try:
        host = urlparse(u).hostname or ""
    except ValueError:
        return ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def _is_listed(host: str) -> bool:
    parts = host.split(".")
    # Check host and every parent domain: a.b.facebook.com → b.facebook.com → facebook.com
    return any(".".join(parts[i:]) in SOCIAL_DOMAINS for i in range(len(parts) - 1))


def classify_website(url: str | None) -> tuple[str, str | None]:
    """
    Classify a website URL.

    Returns
    -------
    (classification, social_link)
        classification : "NO WEBSITE" | "SOCIAL ONLY" | "HAS WEBSITE"
        social_link    : the URL if SOCIAL ONLY, else None

    Note: "POOR WEBSITE" / "TERRIBLE WEBSITE" are determined separately using
    PageSpeed analysis (see reclassify_as_poor). This function only does
    basic URL pattern matching.
    """
    if not isinstance(url, str) or not url.strip():
        return "NO WEBSITE", None

    if _is_listed(_hostname(url)):
        return "SOCIAL ONLY", url.strip()

    return "HAS WEBSITE", None


def needs_website(classification: str) -> bool:
    """Return True if the lead needs a (better) website."""
    return classification in ("TERRIBLE WEBSITE", "POOR WEBSITE", "NO WEBSITE", "SOCIAL ONLY")


def ensure_scheme(url: str | None) -> str:
    """Make a URL absolute ('facebook.com/x' / '//facebook.com/x' → 'https://…'). Empty stays empty."""
    u = (url or "").strip() if isinstance(url, str) else ""
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if "://" not in u:
        return "https://" + u
    return u


def is_social_url(url: str | None) -> bool:
    """True if the URL points at a real social network (facebook/instagram/tiktok/…)."""
    if not isinstance(url, str) or not url.strip():
        return False
    host = _hostname(url)
    if not host:
        return False
    parts = host.split(".")
    return any(".".join(parts[i:]) in SOCIAL_NETWORKS for i in range(len(parts) - 1))


def split_socials(value) -> list[str]:
    """Normalise a lead's socials (list or newline-joined string) into clean, de-duplicated URLs."""
    if isinstance(value, (list, tuple)):
        items = value
    elif isinstance(value, str) and value.strip():
        items = value.split("\n")
    else:
        return []
    out: list[str] = []
    for u in items:
        if not isinstance(u, str) or not u.strip():
            continue
        u = ensure_scheme(u.strip())
        if u and u not in out:
            out.append(u)
    return out


# Friendly button labels, matched on hostname (longest parent domain wins).
SOCIAL_LABELS = (
    ("facebook.com", "📘 Facebook"), ("fb.com", "📘 Facebook"), ("fb.me", "📘 Facebook"),
    ("instagram.com", "📸 Instagram"), ("tiktok.com", "🎵 TikTok"),
    ("linkedin.com", "💼 LinkedIn"), ("youtube.com", "▶️ YouTube"),
    ("twitter.com", "🐦 X"), ("x.com", "🐦 X"), ("pinterest.com", "📌 Pinterest"),
)


def social_label(url: str) -> str:
    """Button label for one social URL: '📘 Facebook', '🎵 TikTok', …"""
    host = _hostname(url)
    if host:
        parts = host.split(".")
        for i in range(len(parts) - 1):
            dom = ".".join(parts[i:])
            for pref, label in SOCIAL_LABELS:
                if dom == pref:
                    return label
    return "📱 Social page"


def order_socials(urls) -> list[str]:
    """Social URLs sorted by usefulness (Facebook first, Instagram next, …), de-duplicated."""
    items = split_socials(urls)

    def _key(u: str) -> int:
        host = _hostname(u)
        for i, pref in enumerate(SOCIAL_PREFERENCE):
            if host == pref or host.endswith("." + pref):
                return i
        return len(SOCIAL_PREFERENCE)

    return sorted(items, key=_key)


def best_social(urls) -> str:
    """Pick the most useful social link from a list: Facebook first, Instagram next, …"""
    ordered = order_socials(urls)
    if not ordered:
        return ""
    social = next((c for c in ordered if is_social_url(c)), "")
    return social or ordered[0]


# ---------------------------------------------------------------------------
# Link normalisation for the UI (lead table / lead card / details panel)
# ---------------------------------------------------------------------------

# Query params that only track the click — stripped before a URL is shown.
_TRACKING_PARAMS = frozenset(
    {
        "fbclid", "gclid", "dclid", "msclkid", "igshid", "mc_cid", "mc_eid",
        "_hsenc", "_hsmi", "yclid", "twclid", "ttclid", "vero_id", "wickedid",
        "ref_src", "ref_url", "mibextid", "gclsrc", "srsltid", "igshid_sg",
    }
)
_TRACKING_PREFIXES = ("utm_",)

# Values that mean "we have nothing" rather than a URL.
_JUNK_VALUES = frozenset(
    {"-", "--", "n/a", "na", "none", "null", "nil", "no website", "no site",
     "unknown", "tbc", "todo", "www", "no", "false"}
)

# Non-web schemes we never turn into a link.
_BAD_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "ftp:", "file:")


def clean_url(url) -> str:
    """
    Normalise a URL for display: add https:// when the scheme is missing,
    strip tracking parameters (utm_*, fbclid, gclid, …), and return '' for
    junk / empty / non-web values. Never invents a URL — a value that isn't
    clearly a web address comes back empty so the cell can stay blank.
    """
    if not isinstance(url, str):
        return ""
    u = url.strip().strip("<>").strip()
    if not u or any(ch.isspace() for ch in u) or u.lower() in _JUNK_VALUES:
        return ""
    if u.lower().startswith(_BAD_SCHEMES):
        return ""
    u = ensure_scheme(u)
    try:
        parts = urlparse(u)
    except ValueError:
        return ""
    if parts.scheme not in ("http", "https") or "." not in (parts.hostname or ""):
        return ""
    # Drop tracking params (social networks also use plain ref= for tracking).
    if parts.query:
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        keep = [
            (k, v) for k, v in pairs
            if k.lower() not in _TRACKING_PARAMS
            and not k.lower().startswith(_TRACKING_PREFIXES)
            and not (k.lower() == "ref" and is_social_url(u))
        ]
        query = urlencode(keep) if len(keep) != len(pairs) else parts.query
    else:
        query = ""
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, query, parts.fragment))


# Short labels for the per-platform link columns in the lead table:
# ("FB", domains that count as Facebook), …
SOCIAL_PLATFORMS = (
    ("FB", ("facebook.com", "fb.com", "fb.me")),
    ("IG", ("instagram.com",)),
    ("TT", ("tiktok.com",)),
    ("LI", ("linkedin.com",)),
    ("X", ("twitter.com", "x.com")),
    ("YT", ("youtube.com",)),
)


def socials_by_platform(urls) -> dict[str, str]:
    """
    {'FB': 'https://facebook.com/x', 'TT': 'https://tiktok.com/@y', …}
    — one cleaned URL per network (first match wins, preference order).
    Networks the lead doesn't have are simply absent — never invented.
    """
    out: dict[str, str] = {}
    for u in order_socials(urls):
        u = clean_url(u)
        if not u:
            continue
        host = _hostname(u)
        if not host:
            continue
        parts = host.split(".")
        for code, domains in SOCIAL_PLATFORMS:
            if code in out:
                continue
            if any(".".join(parts[i:]) in domains for i in range(len(parts) - 1)):
                out[code] = u
    return out


def reclassify_as_poor(classification: str, quality_score: int | None) -> str:
    """
    Reclassify a website based on its PageSpeed quality score.

    Parameters
    ----------
    classification : str
        Current classification (usually "HAS WEBSITE")
    quality_score : int | None
        Quality score from PageSpeed (0-100), or None if unavailable

    Returns
    -------
    str
        "TERRIBLE WEBSITE" if quality < 40,
        "POOR WEBSITE"     if quality < 50,
        otherwise the original classification.
    """
    if classification != "HAS WEBSITE" or quality_score is None:
        return classification

    if quality_score < TERRIBLE_QUALITY:
        return "TERRIBLE WEBSITE"
    if quality_score < POOR_QUALITY:
        return "POOR WEBSITE"

    return classification
