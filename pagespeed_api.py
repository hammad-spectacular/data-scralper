"""
pagespeed_api.py
----------------
Integrates Google PageSpeed Insights API to analyze website quality.
Provides performance, accessibility, SEO, and best-practice scores.
Handles blocked/inconclusive audits safely without classifying as bad websites.
"""

from __future__ import annotations

import os
import time
from typing import Any
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

# PageSpeed Insights API endpoint
BASE_URL = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"

# Maximum retries for temporary failures
MAX_RETRIES = 2
# Retry delay in seconds
RETRY_DELAY = 2
# Request timeout in seconds
REQUEST_TIMEOUT = 30


class PageSpeedError(RuntimeError):
    """Base exception for PageSpeed API errors."""
    pass


class BlockedError(PageSpeedError):
    """Raised when the website blocks automated inspection."""
    pass


class RateLimitError(PageSpeedError):
    """Raised when API rate limit is exceeded."""
    pass


def _get_api_key() -> str:
    """Get PageSpeed API key from environment."""
    key = os.getenv("PAGESPEED_API_KEY", "").strip()
    if not key:
        raise PageSpeedError(
            "PageSpeed API key not found. Add PAGESPEED_API_KEY to your .env file. "
            "Get a free key at: https://developers.google.com/speed/docs/insights/v5/get-started"
        )
    return key


def _normalize_url(url: str) -> str:
    """Ensure URL has a scheme."""
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _extract_scores(data: dict[str, Any]) -> dict[str, int]:
    """Extract scores from PageSpeed API response."""
    scores = {}
    
    # Extract scores from lighthouseResult
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    
    # Performance, Accessibility, Best Practices, SEO
    for category_key in ["performance", "accessibility", "best-practices", "seo"]:
        category = categories.get(category_key, {})
        score = category.get("score")
        if score is not None:
            # Convert 0-1 to 0-100
            scores[category_key] = int(score * 100)
    
    return scores


def _extract_issues(data: dict[str, Any]) -> list[str]:
    """Extract key issues from audits."""
    issues = []
    
    lighthouse = data.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})
    
    # Critical audits to check
    critical_audits = [
        "is-on-https",  # HTTPS not used
        "uses-http2",  # Not using HTTP/2
        "viewport",  # No viewport configured
        "content-width",  # Content wider than screen
        "color-contrast",  # Poor color contrast
        "image-alt",  # Images missing alt text
        "link-text",  # Links have no text
        "tap-targets",  # Touch targets too small
        "canonical",  # No canonical URL
        "http-status",  # Page returns error
        "robots-txt",  # No robots.txt
        "structured-data",  # Missing structured data
    ]
    
    for audit_key in critical_audits:
        audit = audits.get(audit_key, {})
        if not audit:
            continue
        
        score = audit.get("score")
        # Score of 0 means failed
        if score == 0:
            title = audit.get("title", audit_key)
            description = audit.get("description", "")
            issues.append(f"{title}: {description}")
    
    return issues[:10]  # Limit to top 10 issues


def _is_blocked(data: dict[str, Any] | None) -> bool:
    """Check if the audit was blocked or inconclusive."""
    if not data:
        return True
    
    # Check for specific error codes that indicate blocking
    status_code = data.get("statusCode")
    if status_code and status_code >= 400:
        # 403, 429 often indicate blocking or rate limiting
        if status_code in (403, 429):
            return True
    
    # Check for error message indicating blocking
    error = data.get("error", {})
    if error:
        message = error.get("message", "").lower()
        blocked_keywords = ["blocked", "captcha", "forbidden", "unauthorized"]
        if any(keyword in message for keyword in blocked_keywords):
            return True
    
    # Check if lighthouseResult is missing (inconclusive)
    if "lighthouseResult" not in data:
        return True
    
    return False


def analyze_website(
    url: str,
    strategy: str = "mobile",
    api_key: str = "",
    retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """
    Analyze a website using PageSpeed Insights API.
    
    Parameters
    ----------
    url : str
        Website URL to analyze
    strategy : str
        "mobile" or "desktop" (default: mobile)
    api_key : str
        PageSpeed API key (optional, will use env var if not provided)
    retries : int
        Number of retries for temporary failures
    
    Returns
    -------
    dict with keys:
        - url: normalized URL
        - strategy: mobile/desktop
        - scores: dict of performance/accessibility/best-practices/seo scores (0-100)
        - issues: list of detected issues
        - status: "success", "blocked", "error", "timeout"
        - error_message: error details if status is not success
        - analyzed_at: ISO timestamp
    """
    url = _normalize_url(url)
    if not url:
        return {
            "url": url,
            "strategy": strategy,
            "scores": {},
            "issues": [],
            "status": "error",
            "error_message": "Invalid URL",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    if not api_key:
        try:
            api_key = _get_api_key()
        except PageSpeedError as e:
            return {
                "url": url,
                "strategy": strategy,
                "scores": {},
                "issues": [],
                "status": "error",
                "error_message": str(e),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
    
    params = {
        "url": url,
        "strategy": strategy,
        "key": api_key,
        "category": ["performance", "accessibility", "best-practices", "seo"],
    }
    
    last_error = None
    
    for attempt in range(retries + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            
            # Check if blocked
            if _is_blocked(data):
                return {
                    "url": url,
                    "strategy": strategy,
                    "scores": {},
                    "issues": [],
                    "status": "blocked",
                    "error_message": "Website blocked automated inspection or requires verification",
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
            
            # Extract scores and issues
            scores = _extract_scores(data)
            issues = _extract_issues(data)
            
            return {
                "url": url,
                "strategy": strategy,
                "scores": scores,
                "issues": issues,
                "status": "success",
                "error_message": "",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except requests.exceptions.Timeout:
            last_error = "Request timeout"
            if attempt < retries:
                time.sleep(RETRY_DELAY)
                continue
            return {
                "url": url,
                "strategy": strategy,
                "scores": {},
                "issues": [],
                "status": "timeout",
                "error_message": last_error,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                return {
                    "url": url,
                    "strategy": strategy,
                    "scores": {},
                    "issues": [],
                    "status": "rate_limited",
                    "error_message": "API rate limit exceeded. Try again later.",
                    "analyzed_at": datetime.now(timezone.utc).isoformat(),
                }
            last_error = f"HTTP error: {e.response.status_code}"
            if attempt < retries and e.response.status_code >= 500:
                time.sleep(RETRY_DELAY)
                continue
            return {
                "url": url,
                "strategy": strategy,
                "scores": {},
                "issues": [],
                "status": "error",
                "error_message": last_error,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except requests.exceptions.RequestException as e:
            last_error = f"Network error: {str(e)}"
            if attempt < retries:
                time.sleep(RETRY_DELAY)
                continue
            return {
                "url": url,
                "strategy": strategy,
                "scores": {},
                "issues": [],
                "status": "error",
                "error_message": last_error,
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except (ValueError, KeyError) as e:
            return {
                "url": url,
                "strategy": strategy,
                "scores": {},
                "issues": [],
                "status": "error",
                "error_message": f"Invalid response: {str(e)}",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
    
    # Should not reach here, but just in case
    return {
        "url": url,
        "strategy": strategy,
        "scores": {},
        "issues": [],
        "status": "error",
        "error_message": last_error or "Unknown error",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def calculate_quality_score(audit_result: dict[str, Any]) -> int:
    """
    Calculate a website quality score from audit results (0-100).
    Separate from sales-priority score.
    
    Parameters
    ----------
    audit_result : dict
        Result from analyze_website()
    
    Returns
    -------
    int
        Quality score (0-100), or None if audit failed
    """
    if audit_result.get("status") != "success":
        return None
    
    scores = audit_result.get("scores", {})
    issues = audit_result.get("issues", [])
    
    # Weight different categories
    weights = {
        "performance": 0.35,
        "accessibility": 0.25,
        "best-practices": 0.20,
        "seo": 0.20,
    }
    
    total_score = 0
    total_weight = 0
    
    for category, weight in weights.items():
        score = scores.get(category, 0)
        total_score += score * weight
        total_weight += weight
    
    # Normalize to 0-100
    quality_score = int(total_score / total_weight) if total_weight > 0 else 0
    
    # Penalize for critical issues
    penalty = min(len(issues) * 5, 30)  # Max 30 point penalty
    quality_score = max(0, quality_score - penalty)
    
    return quality_score
