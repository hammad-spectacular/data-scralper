"""
video_detector.py
-----------------
Answers one question per lead: "Do they actually make video content for their
business?" (TikTok videos, Instagram Reels, YouTube uploads…)

Signals used, from strongest to weakest:

  1. Their own website   — an embedded YouTube/TikTok/Vimeo player, og:video or a
                           JSON-LD VideoObject proves they publish video. Zero
                           extra requests: the HTML is already fetched while
                           harvesting socials (contact_extractor._scrape_website).
  2. YouTube             — their public /videos tab: real uploads + latest title/age
                           (the old RSS endpoint now 404s for everyone).
  3. TikTok              — public mobile profile JSON: exact video count.
  4. Instagram/Facebook  — login walls block scrapers, so a profile alone is
                           reported as UNKNOWN — never guessed as "no".

Verdicts: "YES" (we saw videos) / "NO" (checked everything we can, zero videos) /
"UNKNOWN" (blocked or unverifiable) / "" (nothing to check).
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}
# TikTok's desktop site answers bot UAs with a WAF stub — the mobile page works.
HEADERS_MOBILE = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 10

# Social networks whose content we cannot see without logging in.
LOGIN_WALLED = ("instagram.com", "facebook.com", "fb.com", "fb.me")


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return ""


def is_video_network(url: str) -> bool:
    """True for profiles we can actually probe (YouTube / TikTok) or that are login-walled."""
    host = _host(url)
    if not host:
        return False
    return any(
        host == d or host.endswith("." + d)
        for d in ("youtube.com", "tiktok.com", "youtu.be", *LOGIN_WALLED)
    )


def _get(url: str, headers: dict[str, str] | None = None) -> requests.Response | None:
    try:
        r = requests.get(url, headers=headers or HEADERS, timeout=TIMEOUT, allow_redirects=True)
        return r
    except requests.exceptions.RequestException:
        return None


# ---------------------------------------------------------------------------
# YouTube — read the channel's public /videos tab
# ---------------------------------------------------------------------------

def check_youtube(url: str) -> tuple[str, str, list[str]]:
    """(verdict, note, video links) for one YouTube URL. Free: reads their public
    /videos tab (the old RSS feed endpoint now returns 404 for everyone)."""
    low = url.lower()
    # A link straight to a video = proof they made one
    if "watch?v=" in low or "youtu.be/" in low or "/shorts/" in low:
        return "YES", "YouTube video", [url]

    # Watch their videos tab — it lists actual uploads (empty for channels with none)
    base = url.split("?")[0].rstrip("/")
    target = base if base.lower().endswith("/videos") else base + "/videos"

    page = _get(target)
    if page is not None and page.status_code != 200 and target != base:
        target = base                              # some channel URL forms refuse the suffix
        page = _get(target)
    if page is None:
        return "UNKNOWN", "YouTube unreachable", []
    if page.status_code == 404:
        return "NO", "YouTube channel not found", []
    if page.status_code in (401, 403, 429):
        return "UNKNOWN", "YouTube blocked the check", []

    text = page.text
    if len(text) < 50_000:
        return "UNKNOWN", "YouTube returned a stub page", []

    # Uploads render as lockup/video items on the channel's videos tab.
    # Count only the MAIN content — anything past the sidebar belongs to other channels.
    sidebar = text.find('"sidebar":')
    main = text[:sidebar] if sidebar > -1 else text
    n_videos = main.count('"lockupViewModel"') + main.count('"videoRenderer"')
    if n_videos <= 0:
        return "NO", "YouTube channel has no videos", []

    # Real links to the actual uploads (videoId on the channel's videos tab)
    links: list[str] = []
    for vid in re.findall(r'"videoId"\s*:\s*"([\w-]{6,})"', main):
        link = f"https://www.youtube.com/watch?v={vid}"
        if link not in links:
            links.append(link)
        if len(links) >= 6:
            break

    # Latest upload's title + age (first lockup on the videos tab)
    pos = main.find("lockupViewModel")
    note = f"YouTube — {n_videos}+ video(s)"
    if pos > -1:
        chunk = text[pos:pos + 4000]
        mt = re.search(r'"title"\s*:\s*\{\s*"content"\s*:\s*"([^"]{3,80})"', chunk) \
            or re.search(r'"title"\s*:\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"([^"]{3,80})"', chunk)
        age = re.search(r'"(?:publishedTimeText|date)"\s*:\s*\{\s*"(?:content|simpleText)"\s*:\s*"([^"]{1,30})"', chunk)
        if age:
            note += f", last {age.group(1)}"
        if mt:
            note += f": {mt.group(1)[:40]}"
    return "YES", note, links


# ---------------------------------------------------------------------------
# TikTok — the public profile page embeds the exact video count
# ---------------------------------------------------------------------------

def check_tiktok(url: str) -> tuple[str, str, list[str]]:
    """(verdict, note, video links) for one TikTok profile URL (1 request, no key).

    The mobile page embeds the profile's exact stats — including videoCount —
    plus the permalinks of recent posts (/@user/video/1234567890)."""
    page = _get(url, headers=HEADERS_MOBILE)
    if page is None:
        return "UNKNOWN", "TikTok unreachable", []
    if page.status_code in (401, 403, 429):
        return "UNKNOWN", "TikTok blocked the check", []
    if page.status_code == 404:
        return "NO", "TikTok profile not found", []

    m = re.search(r'"(?:videoCount|itemCount)"\s*:\s*(\d+)', page.text)
    if not m:
        # WAF stub or layout change — say so rather than guess
        return "UNKNOWN", "TikTok video count hidden", []
    n = int(m.group(1))
    if n <= 0:
        return "NO", "TikTok profile has no videos", []

    # Recent upload permalinks as seen in the profile's item list
    links: list[str] = []
    for path in re.findall(r'/@[\w.-]+/video/\d+', page.text):
        link = "https://www.tiktok.com" + path
        if link not in links:
            links.append(link)
        if len(links) >= 6:
            break
    if not links:
        # TikTok renders its item list client-side only, so individual permalinks
        # aren't in the HTML. Their profile page IS the feed of all N videos —
        # that's still the fastest way to see what they post.
        links = [url]
    return "YES", f"TikTok — {n} videos", links


# ---------------------------------------------------------------------------
# Combine every signal for one lead
# ---------------------------------------------------------------------------

def evaluate_video(
    site_signals: list[str] | None,
    socials: list[str],
    site_ok: bool = False,
    max_probes: int = 2,
    site_links: list[str] | None = None,
) -> tuple[str, str, list[str]]:
    """
    One lead's video verdict.

    Parameters
    ----------
    site_signals : video embeds spotted in their own website's HTML
                   (None = we couldn't fetch the site)
    socials      : all of the lead's social URLs
    site_ok      : did the website fetch succeed? (decides NO vs "" at the end)
    max_probes   : cap on remote profile checks (each is 1–2 requests)
    site_links   : direct links to videos found on their own site

    Returns
    -------
    (verdict, sources, links) — verdict in {"YES", "NO", "UNKNOWN", ""} and
    links = actual video URLs (site embeds + recent uploads), deduped, capped.
    """
    notes: list[str] = []
    links: list[str] = []

    def _add_links(urls: list[str] | None) -> None:
        for u in urls or []:
            if u and u not in links:
                links.append(u)
        del links[7:]                       # keep the table light: 6 videos max + slack

    _add_links(site_links)

    # 1. Videos embedded on their own site = strongest, free signal
    for s in site_signals or []:
        if s not in notes:
            notes.append(s)
    if notes:
        return "YES", " · ".join(notes[:4]), links

    # 2. Probe the profiles we can actually read (YouTube videos tab / TikTok stats)
    probes = 0
    probe_ran = False
    for url in socials:
        if not is_video_network(url):
            continue
        host = _host(url)
        if any(host == d or host.endswith("." + d) for d in LOGIN_WALLED):
            label = "Instagram" if "instagram" in host else "Facebook"
            if f"{label} profile (can't verify — login wall)" not in notes:
                notes.append(f"{label} profile (can't verify — login wall)")
            continue
        if probes >= max_probes:
            continue
        probes += 1
        probe_ran = True
        if "tiktok.com" in host:
            verdict, note, plinks = check_tiktok(url)
        else:
            verdict, note, plinks = check_youtube(url)
        _add_links(plinks)
        if note and note not in notes:
            notes.append(note)
        if verdict == "YES":
            return "YES", " · ".join(notes[:4]), links

    if any("login wall" in n for n in notes):
        return "UNKNOWN", " · ".join(notes[:4]), links
    if probe_ran:
        return "NO", " · ".join(notes[:4]) if notes else "No videos on their profiles", links
    if site_ok:
        # Site fetched fine: no video players on it, no video-platform profile linked
        return "NO", "No videos found", links
    return "", "", links


# ---------------------------------------------------------------------------
# Helpers used by contact_extractor to spot embeds in already-fetched HTML
# ---------------------------------------------------------------------------

_IFRAME_RE = re.compile(r"<iframe[^>]+src=[\"']([^\"']+)[\"']", re.I)
_VIDEO_IFRAME: tuple[tuple[str, str], ...] = (
    ("youtube.com/embed", "YouTube video on site"),
    ("youtube-nocookie.com/embed", "YouTube video on site"),
    ("player.vimeo.com", "Vimeo video on site"),
    ("tiktok.com/embed", "TikTok video on site"),
    ("instagram.com/embed", "Instagram video on site"),
    ("facebook.com/plugins/video", "Facebook video on site"),
    ("videodelivery.net", "video player on site"),
    ("wistia.com", "video player on site"),
)
# <a href> to an actual video (their own channel, a Reel, a Short, a TikTok post)
_VIDEO_LINK = re.compile(
    r"https?://(?:www\.)?(?:youtu\.be/[\w-]+|youtube\.com/(?:watch\?v=|shorts/|@)[\w-]+"
    r"|www\.tiktok\.com/@[\w./-]+|tiktok\.com/@[\w./-]+"
    r"|(?:www\.)?instagram\.com/(?:reel|reels|tv)/[\w.-]+)",
    re.I,
)
_VIDEO_META = re.compile(r"property=[\"']og:video(?::\w+)?[\"']|itemtype=[\"'].*VideoObject", re.I)


def _video_permalink(src: str) -> str:
    """Turn an embed/player URL into a link a human can open and watch.

    youtube.com/embed/ABC123  ->  youtube.com/watch?v=ABC123
    player.vimeo.com/video/7  ->  vimeo.com/7
    Anything else (direct video URLs, reels, tiktok posts) passes through.
    """
    s = src.strip()
    m = re.search(r"youtube(?:-nocookie)?\.com/embed/([\w-]{6,})", s, re.I)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.search(r"player\.vimeo\.com/video/(\d+)", s, re.I)
    if m:
        return f"https://vimeo.com/{m.group(1)}"
    m = re.search(r"tiktok\.com/embed/(?:v/|video/)?(\d+)", s, re.I)
    if m:
        return f"https://www.tiktok.com/embed/video/{m.group(1)}"
    if re.match(r"https?://", s, re.I):
        return s
    return ""


def scan_html_for_video(html: str) -> tuple[list[str], list[str]]:
    """Video signals + direct video links in a page's raw HTML: real players
    (iframes), og:video, JSON-LD VideoObject, and links to actual video posts.

    Returns (signals, urls) — both deduplicated, in order."""
    if not html:
        return [], []
    found: list[str] = []
    urls: list[str] = []

    def _add(label: str) -> None:
        if label not in found:
            found.append(label)

    def _add_url(u: str) -> None:
        u = _video_permalink(u)
        if u and u not in urls:
            urls.append(u)

    for src in _IFRAME_RE.findall(html):
        low = src.lower()
        for needle, label in _VIDEO_IFRAME:
            if needle in low:
                _add(label)
                _add_url(_video_permalink(src))
                break
    if _VIDEO_META.search(html):
        _add("embedded video on site")
        m = re.search(
            r"property=[\"']og:video(?::\w+)?[\"'][^>]*content=[\"'](https?://[^\"']+)"
            r"|content=[\"'](https?://[^\"']+)[\"'][^>]*property=[\"']og:video",
            html, re.I,
        )
        if m:
            _add_url(m.group(1) or m.group(2))
    if '"VideoObject"' in html or "VideoObject" in html and "schema.org" in html:
        _add("video on their site (structured data)")
        # <link href="…"> / "embedUrl" / "contentUrl" inside the VideoObject
        m = re.search(r'"(?:embedUrl|contentUrl|name)"\s*:\s*"(https?://[^"]+)"', html)
        if m and ("youtu" in m.group(1) or "vimeo" in m.group(1) or "/video" in m.group(1)):
            _add_url(m.group(1))
    for m in _VIDEO_LINK.finditer(html):
        u = m.group(0)
        low = u.lower()
        if "tiktok" in low:
            _add("TikTok link on site")
        elif "instagram" in low:
            _add("Instagram Reel link on site")
        else:
            _add("YouTube link on site")
        _add_url(u)
        if len(found) >= 4:
            break
    return found, urls[:8]
