"""
lead_scanner.py
---------------
The "visit each lead's page" pass, free of Streamlit so it can run two ways:
  - inside the app (app._scan_leads wraps it with a progress bar), and
  - from the command line over leads.db:  python lead_scanner.py

Per lead it:
  1. fetches their website + best social page (one quick request each) to harvest
     every social link printed there, extra phones/emails (optional) and video
     signals (embedded YouTube/TikTok players, video links);
  2. probes the video platforms we can actually read — YouTube's public videos
     tab and TikTok's public profile — to answer "do they make videos for
     their business?" (YES / NO / UNKNOWN; Instagram/Facebook are login-walled
     so they stay UNKNOWN rather than guessed).

Fills: Extracted Phone, Extracted Email, Socials, Social Link,
Video Content, Video Sources, Video Links (direct URLs of their videos).
"""

from __future__ import annotations

import re
from typing import Callable

import pandas as pd

from contact_extractor import extract_contact_info, format_extracted_contacts
from video_detector import evaluate_video
from website_classifier import best_social, order_socials, split_socials

# progress(fraction_done 0..1, message)
Progress = Callable[[float, str], None]

# A link that opens ONE playable video vs. a channel/profile page (still useful,
# but the table's "their video" column should show a real video when we have one)
_SPECIFIC_VIDEO = (
    "watch?v=", "/shorts/", "youtu.be/", "/reel/", "/reels/", "/tv/",
    "vimeo.com/", "embed/",
)


def _is_specific_video(url: str) -> bool:
    """True when the URL opens one playable video (not a channel/profile page)."""
    low = url.lower()
    if re.search(r"tiktok\.com/@[\w.-]+/video/\d+", low):
        return True
    if "tiktok.com/@" in low or "youtube.com/@" in low:
        return False                       # profile page — useful, but not a video
    return any(p in low for p in _SPECIFIC_VIDEO)


def order_video_links(links: list[str]) -> list[str]:
    """Deduped: real playable videos first (stable), then profile/channel pages."""
    ordered: list[str] = []
    seen: set[str] = set()
    for u in links:
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    specific = [u for u in ordered if _is_specific_video(u)]
    general = [u for u in ordered if not _is_specific_video(u)]
    return specific + general


def scan_leads(
    df: pd.DataFrame,
    find_socials: bool = True,
    extract_contacts: bool = False,
    check_videos: bool = True,
    progress: Progress | None = None,
) -> pd.DataFrame:
    """Fill socials / contacts / video verdicts in `df` (modified in place)."""
    if df.empty or not (extract_contacts or find_socials or check_videos):
        return df
    for col in ("Socials", "Social Link", "Video Content", "Video Sources", "Video Links"):
        if col not in df.columns:
            df[col] = ""

    social_lists = [
        order_socials(split_socials(soc) + split_socials(link))
        for soc, link in zip(df["Socials"], df["Social Link"])
    ]

    # ---- 1 · fetch each lead's pages (site + best social page) -----------------
    websites = df["Website"].fillna("").astype(str) if "Website" in df.columns else pd.Series("", index=df.index)
    best_links = df["Social Link"].fillna("").astype(str) if "Social Link" in df.columns else pd.Series("", index=df.index)
    visit = [bool(w or s) for w, s in zip(websites, best_links)]
    n_pages = sum(visit)
    done = 0
    extracted_phones: list[str] = []
    extracted_emails: list[str] = []
    scraped_socials: list[list[str]] = []
    site_signals: list[list[str]] = []
    site_ok_flags: list[bool] = []
    site_video_urls: list[list[str]] = []

    for keep, website, social in zip(visit, websites, best_links):
        phones_str = emails_str = ""
        found: list[str] = []
        signals: list[str] = []
        vids: list[str] = []
        ok = False
        if keep:
            try:
                result = extract_contact_info(website, social, max_requests=2, delay=0.5)
                if extract_contacts:
                    phones_str, emails_str = format_extracted_contacts(result)
                found = split_socials(result.get("socials", []))
                signals = list(result.get("videos", []))
                vids = list(result.get("video_urls", []))
                ok = bool(result.get("site_ok"))
            except Exception:
                pass
            done += 1
            if progress is not None and n_pages:
                progress(done / n_pages, f"Finding socials & contacts… {done}/{n_pages}")
        extracted_phones.append(phones_str)
        extracted_emails.append(emails_str)
        scraped_socials.append(found)
        site_signals.append(signals)
        site_ok_flags.append(ok)
        site_video_urls.append(vids)

    df["Extracted Phone"] = extracted_phones
    df["Extracted Email"] = extracted_emails

    # Merge in every social found on the page (footer icons, "follow us", JSON-LD)
    if find_socials:
        social_lists = [
            order_socials(lst + found)
            for lst, found in zip(social_lists, scraped_socials)
        ]
        df["Socials"] = ["\n".join(lst) for lst in social_lists]
        df["Social Link"] = [best_social(lst) for lst in social_lists]

    # ---- 2 · do they make videos? ---------------------------------------------
    if check_videos and len(df):
        verdicts: list[str] = []
        sources: list[str] = []
        link_lists: list[str] = []
        for pos, (socials, signals, ok) in enumerate(zip(social_lists, site_signals, site_ok_flags)):
            # Probe the merged list — even when 'find socials' is off, links found on
            # the site still help answer the video question (they just aren't saved).
            verdict, note, vlinks = evaluate_video(signals, order_socials(socials + scraped_socials[pos]),
                                                   site_ok=ok, site_links=site_video_urls[pos])
            verdicts.append(verdict)
            sources.append(note)
            # Their own site's videos first, then what the platform probes returned —
            # real playable videos ahead of profile/channel pages
            merged = order_video_links(list(site_video_urls[pos]) + list(vlinks))[:6]
            link_lists.append("\n".join(merged))
            if progress is not None:
                progress((pos + 1) / len(df), f"🎬 Checking video content… {pos + 1}/{len(df)}")
        df["Video Content"] = verdicts
        df["Video Sources"] = sources
        df["Video Links"] = link_lists

    return df


# Columns a batch scan writes back into the saved table


def pending_saved(df: pd.DataFrame) -> pd.DataFrame:
    """The saved leads still missing a video verdict — or missing the video LINKS.

    Never re-do finished leads: a lead counts as done once it has any verdict —
    YES / NO / UNKNOWN — whether or not its site printed any socials. (The old
    rule also demanded socials, so leads whose site simply doesn't link any were
    re-fetched forever.) The one exception: a 🎬 YES with no link to an actual
    video is re-checked once, so the table/CSV can show what they post (leads
    scanned before Video Links existed fill in here). Leads whose fetch failed
    (blank verdict) stay pending and are retried on the next run."""
    from lead_store import load_leads

    saved = df if df is not None and not df.empty else load_leads()
    if saved.empty:
        return saved
    for col in ("Website", "Social Link", "Socials", "Video Content", "Video Sources", "Video Links"):
        saved[col] = saved[col].fillna("").astype(str) if col in saved.columns else ""
    has_page = saved["Website"].str.strip().ne("") | saved["Social Link"].str.strip().ne("")
    verdict = saved["Video Content"].str.strip().str.upper()
    checked = verdict.isin(("YES", "NO", "UNKNOWN"))
    needs_link = verdict.eq("YES") & saved["Video Links"].str.strip().eq("")
    return saved[has_page & (~checked | needs_link)].copy().reset_index(drop=True)


def scan_saved_leads(progress: Progress | None = None, save: bool = True) -> tuple[pd.DataFrame, str]:
    """
    Batch job: run the social scrape + video check over every saved lead in
    leads.db that's still missing them, write the results back (your Manual
    Email / Contacted edits live in cache.json — untouched).

    Returns (full saved table, summary message).
    """
    from lead_store import load_leads, merge_scan_results, save_leads

    saved = load_leads()
    if saved.empty:
        return saved, "No saved leads yet — run a search first."
    if "place_id" not in saved.columns:
        return saved, "⚠️ Saved leads have no place_id — cannot update them."

    todo = pending_saved(saved)
    if todo.empty:
        return saved, f"✅ Already done — all {len(saved):,} saved leads have socials + a video check."

    if progress is not None:
        progress(0.0, f"🔎 Checking {len(todo):,} of {len(saved):,} saved leads…")
    scan_leads(todo, find_socials=True, extract_contacts=False, check_videos=True, progress=progress)

    saved = merge_scan_results(saved, todo)
    if save:
        save_leads(saved)

    n_videos = int(saved["Video Content"].fillna("").astype(str).str.upper().eq("YES").sum()) \
        if "Video Content" in saved.columns else 0
    n_socials = int(saved["Socials"].fillna("").astype(str).str.strip().ne("").sum()) \
        if "Socials" in saved.columns else 0
    msg = (
        f"✅ Done — {len(todo):,} leads scanned. "
        f"🎬 {n_videos:,} make videos · 📱 {n_socials:,} have socials now."
    )
    return saved, msg


if __name__ == "__main__":
    # python lead_scanner.py   — batch-check leads.db without opening the app
    import sys

    def _print_progress(frac: float, text: str) -> None:
        sys.stdout.write(f"\r[{frac * 100:5.1f}%] {text}          ")
        sys.stdout.flush()

    _, summary = scan_saved_leads(progress=_print_progress)
    print("\n" + summary)
