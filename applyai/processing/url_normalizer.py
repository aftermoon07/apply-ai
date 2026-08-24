"""
Deterministic URL normalization — zero LLM usage.

Uses urllib.parse exclusively. Goals:
  - Make equivalent URLs produce the same string for deduplication.
  - Preserve the semantic destination of the URL (never change where it points).
  - Remove known tracking parameters only (not arbitrary query parameters).
  - Do NOT aggressively strip query params — job platforms use them for routing.

Known tracking parameters that are safe to remove:
  utm_source, utm_medium, utm_campaign, utm_term, utm_content,
  fbclid, gclid, msclkid, ref (social referral only), mc_cid, mc_eid
"""

from __future__ import annotations

import logging
from urllib.parse import (
    ParseResult,
    parse_qs,
    urlencode,
    urlparse,
    urlunparse,
)

logger = logging.getLogger(__name__)

# ── Known tracking query parameters — safe to remove ─────────────────────────
# These parameters add tracking metadata but do not change the destination page.
# Only parameters with confirmed tracking-only semantics are listed here.
TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",      # Facebook click ID
        "gclid",       # Google Ads click ID
        "msclkid",     # Microsoft Ads click ID
        "mc_cid",      # Mailchimp campaign ID
        "mc_eid",      # Mailchimp email ID
        "_ga",         # Google Analytics
        "_gl",         # Google Analytics cross-domain
    }
)

# ── Default ports — remove when present (they are implicit) ──────────────────
DEFAULT_PORTS: dict[str, int] = {
    "http": 80,
    "https": 443,
    "ftp": 21,
}


def normalize_url(url: str | None) -> str | None:
    """
    Normalize a URL for deduplication and display.

    Operations performed:
      1. Strip leading/trailing whitespace
      2. Lowercase scheme and host
      3. Remove default port (80 for http, 443 for https)
      4. Remove fragment (#section) — fragments are client-side only
      5. Remove known tracking query parameters
      6. Sort remaining query parameters (stable ordering)
      7. Remove trailing slash from path (unless path is just '/')
      8. Preserve all other query parameters and path structure

    Returns None if url is None or empty.
    Returns the original url (with a warning) if parsing fails.
    """
    if not url:
        return None

    url = url.strip()
    if not url:
        return None

    try:
        parsed: ParseResult = urlparse(url)

        # Require a scheme and netloc to proceed
        if not parsed.scheme or not parsed.netloc:
            logger.debug("URL missing scheme or netloc, returning as-is: %s", url)
            return url

        scheme = parsed.scheme.lower()
        netloc = _normalize_netloc(parsed.netloc, scheme)
        path = _normalize_path(parsed.path)
        query = _normalize_query(parsed.query)

        # Fragment is always removed (client-side anchor, irrelevant for job identity)
        normalized = urlunparse((scheme, netloc, path, parsed.params, query, ""))
        return normalized

    except Exception as exc:
        logger.warning("URL normalization failed for %r: %s", url, exc)
        return url


def _normalize_netloc(netloc: str, scheme: str) -> str:
    """Lowercase host; strip default port."""
    if ":" in netloc:
        host, port_str = netloc.rsplit(":", 1)
        try:
            port = int(port_str)
            if DEFAULT_PORTS.get(scheme) == port:
                return host.lower()
        except ValueError:
            pass
        return f"{host.lower()}:{port_str}"
    return netloc.lower()


def _normalize_path(path: str) -> str:
    """Remove trailing slash unless path is root '/'."""
    if path.endswith("/") and len(path) > 1:
        return path.rstrip("/")
    return path


def _normalize_query(query: str) -> str:
    """Remove tracking parameters; sort remaining parameters for stable ordering."""
    if not query:
        return ""

    params = parse_qs(query, keep_blank_values=True)
    # Remove tracking params (case-insensitive key comparison)
    cleaned = {
        k: v
        for k, v in params.items()
        if k.lower() not in TRACKING_PARAMS
    }

    if not cleaned:
        return ""

    # Sort for stable ordering (same params in different order = same URL)
    return urlencode(sorted(cleaned.items()), doseq=True)


def urls_are_equivalent(url_a: str | None, url_b: str | None) -> bool:
    """Return True if two URLs normalize to the same string."""
    if url_a is None and url_b is None:
        return True
    if url_a is None or url_b is None:
        return False
    return normalize_url(url_a) == normalize_url(url_b)
