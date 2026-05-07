"""
Adaptive Browser Router — decides which browser mode to use per URL.

Problem: launching full stealth for every URL is wasteful.
Wikipedia doesn't need anti-bot. Cloudflare login portals do.

Solution: lightweight scan of URL to score bot-protection risk.
Low risk -> httpx GET (fastest, ~200ms).
Medium risk -> headless Playwright with basic anti-detection (~8s).
High risk -> full CDP stealth + captcha fallback (~20s).

Usage:
    plan = scan_url("https://some-site.com")
    if plan.mode == BrowserMode.LIGHTWEIGHT:
        html = BulkFetcher().fetch(plan.url)
    else:
        browser.full_stealth_goto(plan.url)
"""

import hashlib
import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class BrowserMode(Enum):
    """How aggressive the browser setup needs to be."""
    LIGHTWEIGHT = "lightweight"   # httpx GET, no JS, fastest
    HEADLESS = "headless"         # chromium --headless=new, basic stealth
    FULL_STEALTH = "full_stealth" # your current full Hand setup, CDP optional


@dataclass
class RoutePlan:
    """The decision for a specific URL."""
    url: str
    mode: BrowserMode
    confidence: float              # 0.0-1.0
    reasons: List[str] = field(default_factory=list)
    estimated_cost_ms: int = 0
    suggested_headers: Dict[str, str] = field(default_factory=dict)
    proxy_recommended: bool = False
    captcha_expected: bool = False
    js_required: bool = False


# Known bot-heavy signatures
_BOT_PATTERNS = {
    "cloudflare": re.compile(r"cloudflare|cf[-_]ch[ae]llenge|cf-browser-verification", re.I),
    "datadome": re.compile(r"datadome|dd[-_]key|dd-request-id", re.I),
    "perimeterx": re.compile(r"perimeterx|px[-_]cap[tp]cha|px_captcha", re.I),
    "akamai": re.compile(r"akamai|botman[-_]challenge|ak_ch", re.I),
    "reCaptcha": re.compile(r"google.*recaptcha|g-recaptcha[-]", re.I),
    "hCaptcha": re.compile(r"hcaptcha|captcha.*challenge", re.I),
    "incapsula": re.compile(r"incapsula|visid.*incap", re.I),
    "fingerprintjs": re.compile(r"fingerprintjs|fpjs[-]", re.I),
    "distil": re.compile(r"distil[-]networks|distil[-]", re.I),
    "kasada": re.compile(r"kasada|/_k\b", re.I),
}

# Domains known to be heavily protected
_KNOWN_HARD_SITES = {
    "linkedin.com", "twitter.com", "x.com", "instagram.com",
    "facebook.com", "tiktok.com", "amazon.com", "ebay.com",
    "nike.com", "adidas.com", "zillow.com", "reddit.com",
    "booking.com", "expedia.com", "airbnb.com",
}

# Domains known to be static / bot-friendly
_KNOWN_LIGHT_SITES = {
    "wikipedia.org", "wikimedia.org", "arxiv.org", "pubmed.ncbi.nlm.nih.gov",
    "stackoverflow.com", "github.com", "docs.python.org", "devdocs.io",
    "archive.org", "gutenberg.org", "un.org", "worldbank.org",
    "biorxiv.org", "medrxiv.org", "osf.io",
}


def _domain_only(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _url_path(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).path.lower()
    except Exception:
        return ""


class BrowserRouter:
    """
    Scans a URL before deciding how to browse it.
    Three passes:
      1. Static analysis (domain reputation, URL pattern)
      2. HEAD probe (response headers, challenge page detection)
      3. robots.txt check
    """

    def __init__(self, cache_path: Optional[Path] = None, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[RoutePlan, float]] = {}
        self.ttl = ttl_seconds
        self.cache_file = cache_path or (Path.home() / ".blackreach" / "route_cache.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan_for(self, url: str, force_refresh: bool = False) -> RoutePlan:
        """Main entry point. Scan a URL and return the browsing plan."""
        cache_key = self._key(url)
        if not force_refresh:
            cached = self._cache.get(cache_key)
            if cached:
                plan, ts = cached
                if (time.time() - ts) < self.ttl:
                    return plan

        plan = self._scan(url)
        self._cache[cache_key] = (plan, time.time())
        self._save_cache()
        return plan

    def get_mode_name(self, url: str) -> str:
        return self.plan_for(url).mode.value

    def is_hard(self, url: str) -> bool:
        return self.plan_for(url).mode == BrowserMode.FULL_STEALTH

    # ------------------------------------------------------------------
    # Scan passes
    # ------------------------------------------------------------------

    def _scan(self, url: str) -> RoutePlan:
        domain = _domain_only(url)
        path = _url_path(url)
        reasons: List[str] = []
        risk_score = 0.0

        # --- PASS 1: Domain reputation ---
        lower_domain = domain.lower()

        if any(s in lower_domain for s in _KNOWN_LIGHT_SITES):
            risk_score -= 0.4
            reasons.append("known-light-domain")

        for hard in _KNOWN_HARD_SITES:
            if hard in lower_domain:
                risk_score += 0.5
                reasons.append(f"known-hard-site: {hard}")
                break

        # API endpoints are usually static
        if "/api/" in path or "/api/v" in path or path.endswith(".json"):
            risk_score -= 0.3
            reasons.append("api-endpoint")

        # Login / auth paths
        if any(kw in path for kw in ("/login", "/auth", "/signin", "/sso", "/oauth", "/account")):
            risk_score += 0.3
            reasons.append("auth-path")

        # --- PASS 2: Header probe ---
        header_score, header_reasons = self._probe_headers(url)
        risk_score += header_score
        reasons.extend(header_reasons)

        # --- PASS 3: robots.txt check ---
        robots_score, robots_reasons = self._check_robots(domain)
        risk_score += robots_score
        reasons.extend(robots_reasons)

        # --- Decide ---
        mode = self._mode_from_score(risk_score)
        confidence = min(abs(risk_score) + 0.3, 1.0)

        captcha_expected = any(r.startswith("bot-sig") for r in reasons)
        proxy_recommended = risk_score > 0.5
        js_required = mode in (BrowserMode.HEADLESS, BrowserMode.FULL_STEALTH)

        return RoutePlan(
            url=url,
            mode=mode,
            confidence=round(confidence, 2),
            reasons=reasons,
            estimated_cost_ms=self._estimate_cost(mode),
            suggested_headers=self._suggest_headers(mode, domain),
            proxy_recommended=proxy_recommended,
            captcha_expected=captcha_expected,
            js_required=js_required,
        )

    def _probe_headers(self, url: str) -> Tuple[float, List[str]]:
        """Lightweight HEAD request. Returns (risk_delta, reasons)."""
        try:
            req = urllib.request.Request(url, method="HEAD", headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive",
            })
            resp = urllib.request.urlopen(req, timeout=10)

            score = 0.0
            reasons: List[str] = []
            headers = {k.lower(): v for k, v in dict(resp.headers).items()}

            server = headers.get("server", "")
            if "cloudflare" in server.lower():
                score += 0.3
                reasons.append("cf-server-header")

            x_protected = headers.get("x-protected-by", "")
            if any(waf in x_protected.lower() for waf in ("cloudflare", "akamai", "sucuri")):
                score += 0.3
                reasons.append(f"waf-shield: {x_protected}")

            cookies = headers.get("set-cookie", "")
            if any(s in cookies.lower() for s in ("__cfduid", "__cfruid", "cf_clearance")):
                score += 0.2
                reasons.append("cf-cookie")

            if headers.get("x-datadome-cid") or headers.get("x-perimeterx"):
                score += 0.4
                reasons.append("bot-management-header")

            if resp.status >= 400:
                score += 0.4
                reasons.append(f"http-{resp.status}-on-head")

            # Sniff body for bot signatures
            body = resp.read(4096).decode("utf-8", errors="ignore")
            for name, pat in _BOT_PATTERNS.items():
                if pat.search(body):
                    score += 0.35
                    reasons.append(f"bot-sig: {name}")

            return score, reasons

        except urllib.error.HTTPError as e:
            if e.code in (403, 418, 429, 503):
                return 0.5, [f"blocked-on-head: {e.code}"]
            return 0.2, [f"http-error: {e.code}"]
        except Exception:
            return 0.0, ["probe-failed"]

    def _check_robots(self, domain: str) -> Tuple[float, List[str]]:
        if not domain:
            return 0.0, []
        reasons: List[str] = []
        score = 0.0
        try:
            req = urllib.request.Request(
                f"https://{domain}/robots.txt",
                headers={"User-Agent": "Mozilla/5.0 (compatible; Blackreach/5.0)"},
            )
            resp = urllib.request.urlopen(req, timeout=5)
            body = resp.read().decode("utf-8", errors="ignore")

            if "crawl-delay" in body.lower():
                score += 0.2
                reasons.append("robots-crawl-delay")

            if "disallow: /" in body.lower():
                score += 0.1
                reasons.append("robots-broad-disallow")

            if any(bot in body.lower() for bot in ("gptbot", "chatgpt-user", "scrapers", "crawlers", "data-scrapers")):
                score += 0.2
                reasons.append("robots-explicit-bot-ban")

            if len(body) > 5000:
                score += 0.1
                reasons.append("robots-verbose")
        except Exception:
            pass

        return score, reasons

    @staticmethod
    def _mode_from_score(score: float) -> BrowserMode:
        if score < 0.3:
            return BrowserMode.LIGHTWEIGHT
        elif score <= 0.7:
            return BrowserMode.HEADLESS
        else:
            return BrowserMode.FULL_STEALTH

    @staticmethod
    def _estimate_cost(mode: BrowserMode) -> int:
        return {
            BrowserMode.LIGHTWEIGHT: 200,
            BrowserMode.HEADLESS: 8000,
            BrowserMode.FULL_STEALTH: 20000,
        }.get(mode, 10000)

    @staticmethod
    def _suggest_headers(mode: BrowserMode, domain: str) -> Dict[str, str]:
        base = {
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "identity",
            "Referer": f"https://{domain}/",
            "DNT": "1",
            "Sec-GPC": "1",
            "Connection": "keep-alive",
        }
        if mode == BrowserMode.FULL_STEALTH:
            base.update({
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            })
        return base

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def _load_cache(self) -> None:
        if not self.cache_file.exists():
            return
        try:
            raw = json.loads(self.cache_file.read_text())
            for key, (plan_dict, ts) in raw.items():
                plan = RoutePlan(**plan_dict)
                if plan_dict.get("mode"):
                    plan.mode = BrowserMode(plan_dict["mode"])
                self._cache[key] = (plan, ts)
        except Exception:
            self._cache = {}

    def _save_cache(self) -> None:
        try:
            out = {
                k: ({
                    "url": p.url,
                    "mode": p.mode.value,
                    "confidence": p.confidence,
                    "reasons": p.reasons,
                    "estimated_cost_ms": p.estimated_cost_ms,
                    "suggested_headers": p.suggested_headers,
                    "proxy_recommended": p.proxy_recommended,
                    "captcha_expected": p.captcha_expected,
                    "js_required": p.js_required,
                }, ts)
                for k, (p, ts) in self._cache.items()
            }
            self.cache_file.write_text(json.dumps(out, indent=2))
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Shortcuts
# ---------------------------------------------------------------------------

def get_router() -> BrowserRouter:
    if not hasattr(get_router, "_instance"):
        get_router._instance = BrowserRouter()
    return get_router._instance


def scan_url(url: str) -> RoutePlan:
    """One-liner: scan a URL and return the routing plan."""
    return get_router().plan_for(url)
