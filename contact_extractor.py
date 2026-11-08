"""
contact_extractor.py
--------------------
Extracts phone numbers and email addresses from business websites and social media pages.
Uses web scraping to find contact information when it's not directly available from the API.
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from video_detector import scan_html_for_video
from website_classifier import ensure_scheme, is_social_url


def _is_valid_url(url: str) -> bool:
    """Check if a URL is valid and not a social media link."""
    if not url or not isinstance(url, str):
        return False

    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False

        # Skip social media platforms (we get data from APIs for these)
        social_domains = {
            "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
            "linkedin.com", "tiktok.com", "youtube.com", "pinterest.com"
        }
        if any(domain in parsed.netloc.lower() for domain in social_domains):
            return False

        return True
    except Exception:
        return False


def _extract_phone_numbers(text: str) -> list[str]:
    """Extract phone numbers from text using regex patterns."""
    if not text:
        return []

    phone_patterns = [
        # International format: +44 20 1234 5678
        r'\+[\d\s\-\(\)]{8,20}',
        # UK format: 020 1234 5678, 07123 456789
        r'0[\d\s\-\(\)]{9,14}',
        # US format: (123) 456-7890, 123-456-7890
        r'[\d\-\(\)\s]{10,15}',
    ]

    phones = []
    for pattern in phone_patterns:
        matches = re.findall(pattern, text)
        phones.extend(matches)

    # Clean and deduplicate
    cleaned = []
    for phone in phones:
        # Remove non-digit characters except +
        cleaned_phone = re.sub(r'[^\d\+]', '', phone)
        if len(cleaned_phone) >= 10:  # Minimum valid phone length
            if cleaned_phone not in cleaned:
                cleaned.append(cleaned_phone)

    return cleaned


def _extract_emails(text: str) -> list[str]:
    """Extract email addresses from text using regex."""
    if not text:
        return []

    # Email regex pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)

    # Filter out common non-contact emails
    skip_emails = {
        'info@example.com', 'contact@example.com', 'support@example.com',
        'webmaster@', 'admin@', 'noreply@', 'no-reply@',
        'example@', 'test@', 'demo@'
    }

    cleaned = []
    for email in emails:
        email_lower = email.lower()
        if not any(skip in email_lower for skip in skip_emails):
            if email not in cleaned:
                cleaned.append(email)

    return cleaned


def _scrape_website(url: str, timeout: int = 10) -> dict[str, Any]:
    """
    Scrape a website for phone numbers and email addresses.

    Returns
    -------
    dict with keys:
        - phones: list of found phone numbers
        - emails: list of found email addresses
        - socials: list of social network links found on the page (facebook/instagram/…)
        - videos: video signals found in the page (YouTube player, TikTok link, …)
        - video_urls: direct links to the videos themselves (embeds resolved to
          watch URLs, plus links to real video posts found on the page)
        - error: error message if scraping failed
    """
    if not _is_valid_url(url):
        return {"phones": [], "emails": [], "socials": [], "videos": [],
                "video_urls": [], "error": "Invalid URL"}

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Get all text from the page
        text = soup.get_text(separator=' ', strip=True)

        # Extract phone numbers and emails
        phones = _extract_phone_numbers(text)
        emails = _extract_emails(text)

        # Social network links (footer icons, "follow us" links, JSON-LD sameAs…)
        socials: list[str] = []

        # Also check specific elements
        # Check href attributes for mailto: and tel: links
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            lower = href.lower()
            if 'mailto:' in lower:
                email = href.replace('mailto:', '').split('?')[0].strip()
                if email and '@' in email:
                    if email not in emails:
                        emails.append(email)
            elif 'tel:' in lower:
                phone = href.replace('tel:', '').split('?')[0].strip()
                if phone:
                    cleaned_phone = re.sub(r'[^\d\+]', '', phone)
                    if len(cleaned_phone) >= 10 and cleaned_phone not in phones:
                        phones.append(cleaned_phone)
            elif is_social_url(href):
                link = ensure_scheme(href)
                if link and link not in socials:
                    socials.append(link)

        # JSON-LD sameAs often lists the business's social profiles
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text() or ""
            for m in re.finditer(r"https?://[^\s\"'<>]+", raw):
                link = m.group(0).rstrip(".,);")
                if is_social_url(link) and link not in socials:
                    socials.append(link)

        # Video signals — an embedded player, og:video or a link to a real video post
        # proves the business publishes video content (feeds the 🎬 video check).
        videos, video_urls = scan_html_for_video(response.text)

        return {"phones": phones, "emails": emails, "socials": socials, "videos": videos,
                "video_urls": video_urls, "error": None}

    except requests.exceptions.Timeout:
        return {"phones": [], "emails": [], "socials": [], "videos": [], "video_urls": [], "error": "Timeout"}
    except requests.exceptions.RequestException as e:
        return {"phones": [], "emails": [], "socials": [], "videos": [], "video_urls": [], "error": str(e)}
    except Exception as e:
        return {"phones": [], "emails": [], "socials": [], "videos": [], "video_urls": [], "error": str(e)}


def extract_contact_info(
    website: str,
    social_link: str | None = None,
    max_requests: int = 3,
    delay: float = 1.0
) -> dict[str, Any]:
    """
    Extract contact information from website and social media.

    Parameters
    ----------
    website : str
        Business website URL
    social_link : str | None
        Social media page URL
    max_requests : int
        Maximum number of URLs to scrape
    delay : float
        Delay between requests in seconds

    Returns
    -------
    dict with keys:
        - phones: list of found phone numbers
        - emails: list of found email addresses
        - socials: list of social network links found on the business's own pages
        - videos: video signals found in fetched page HTML
        - video_urls: direct links to the videos themselves
        - site_ok: True when the lead's own website was fetched successfully
        - sources: dict mapping phone/email to the URL where it was found
        - error: error message if scraping failed
    """
    all_phones = []
    all_emails = []
    all_socials = []
    all_videos: list[str] = []
    all_video_urls: list[str] = []
    site_ok = False
    sources = {}

    urls_to_scrape = []
    if website and _is_valid_url(website):
        urls_to_scrape.append(("website", website))
    if social_link and _is_valid_url(social_link):
        urls_to_scrape.append(("social", social_link))

    # Limit number of requests
    urls_to_scrape = urls_to_scrape[:max_requests]

    for source_type, url in urls_to_scrape:
        if delay > 0 and urls_to_scrape.index((source_type, url)) > 0:
            time.sleep(delay)

        result = _scrape_website(url)

        if source_type == "website" and not result.get("error"):
            site_ok = True

        for phone in result["phones"]:
            if phone not in all_phones:
                all_phones.append(phone)
                sources[phone] = url

        for email in result["emails"]:
            if email not in all_emails:
                all_emails.append(email)
                sources[email] = url

        for social in result.get("socials", []):
            if social not in all_socials:
                all_socials.append(social)

        for vid in result.get("videos", []):
            if vid not in all_videos:
                all_videos.append(vid)

        for link in result.get("video_urls", []):
            if link not in all_video_urls:
                all_video_urls.append(link)

    return {
        "phones": all_phones,
        "emails": all_emails,
        "socials": all_socials,
        "videos": all_videos,
        "video_urls": all_video_urls,
        "site_ok": site_ok,
        "sources": sources,
        "error": None
    }


def format_extracted_contacts(result: dict[str, Any]) -> tuple[str, str]:
    """
    Format extracted contacts for display.

    Returns
    -------
    (phones_str, emails_str)
        Formatted strings with found phone numbers and emails
    """
    phones = result.get("phones", [])
    emails = result.get("emails", [])

    phones_str = ", ".join(phones) if phones else ""
    emails_str = ", ".join(emails) if emails else ""

    return phones_str, emails_str
