"""
Search Intelligence System (v2.3.0)

Provides intelligent search query formulation, result analysis,
and query optimization based on learning from past searches.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from enum import Enum
import re
from urllib.parse import quote as url_quote, urlparse


class SearchEngine(Enum):
    """Known search engines with their specifics."""
    GOOGLE = "google"
    DUCKDUCKGO = "duckduckgo"
    BING = "bing"
    SITE_SPECIFIC = "site_specific"  # Site's own search


@dataclass
class SearchQuery:
    """Represents a search query with metadata."""
    original: str           # Original user goal
    query: str              # Optimized search query
    engine: SearchEngine
    modifiers: List[str] = field(default_factory=list)  # e.g., ["filetype:pdf", "site:arxiv.org"]
    alternatives: List[str] = field(default_factory=list)  # Alternative queries to try


@dataclass
class SearchResult:
    """Represents a search result."""
    title: str
    url: str
    snippet: str
    position: int           # Position in results (1-based)
    relevance_score: float  # 0-1 computed relevance
    clicked: bool = False
    led_to_download: bool = False


@dataclass
class SearchSession:
    """Tracks a search session."""
    query: SearchQuery
    results: List[SearchResult] = field(default_factory=list)
    clicks: List[int] = field(default_factory=list)  # Positions clicked
    successful: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


class QueryFormulator:
    """Formulates optimized search queries."""

    # Common words that add noise to searches
    STOP_WORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "must", "can",
        "i", "me", "my", "we", "our", "you", "your", "he", "she",
        "it", "they", "them", "this", "that", "these", "those",
        "find", "get", "want", "need", "looking", "search", "for",
        "download", "please", "help"
    }

    # Patterns for extracting key information
    PATTERNS = {
        "book_title": re.compile(r'"([^"]+)"|\u201c([^\u201d]+)\u201d', re.I),
        "author": re.compile(r'\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', re.I),
        "year": re.compile(r'\b(19|20)\d{2}\b'),
        "isbn": re.compile(r'\b(?:ISBN[:\s]*)?(97[89][-\s]?\d{10}|\d{9}[\dX])\b', re.I),
        "file_type": re.compile(r'\b(pdf|epub|mobi|azw3?|djvu|txt)\b', re.I),
        "resolution": re.compile(r'\b(\d{3,4}[xX]\d{3,4}|\d{3,4}p|4k|hd|uhd)\b', re.I),
    }

    # Content type specific modifiers
    CONTENT_MODIFIERS = {
        "ebook": ["epub", "pdf", "free download", "download"],
        "paper": ["arxiv", "pdf", "research paper"],
        "image": ["high resolution", "wallpaper", "download"],
        "music": ["mp3", "flac", "download", "free"],
        "video": ["720p", "1080p", "download"],
        "software": ["download", "free", "portable"],
    }

    def __init__(self):
        self.successful_queries: Dict[str, List[str]] = {}  # subject -> queries that worked
        self.failed_queries: Dict[str, List[str]] = {}      # subject -> queries that failed

    def formulate(self, goal: str, content_type: str = "") -> SearchQuery:
        """Create an optimized search query from a goal."""
        # Extract key components
        extracted = self._extract_components(goal)

        # Build base query
        base_query = self._build_base_query(goal, extracted)

        # Determine search engine
        engine = self._choose_engine(content_type, extracted)

        # Add modifiers based on content type
        modifiers = self._get_modifiers(content_type, extracted)

        # Build full query
        query_parts = [base_query]
        query_parts.extend(modifiers)
        full_query = " ".join(query_parts)

        # Generate alternatives
        alternatives = self._generate_alternatives(base_query, extracted, content_type)

        return SearchQuery(
            original=goal,
            query=full_query,
            engine=engine,
            modifiers=modifiers,
            alternatives=alternatives
        )

    def _extract_components(self, goal: str) -> Dict[str, str]:
        """Extract key components from goal."""
        components = {}

        # Extract quoted titles
        title_match = self.PATTERNS["book_title"].search(goal)
        if title_match:
            components["title"] = title_match.group(1) or title_match.group(2)

        # Extract author
        author_match = self.PATTERNS["author"].search(goal)
        if author_match:
            components["author"] = author_match.group(1)

        # Extract year
        year_match = self.PATTERNS["year"].search(goal)
        if year_match:
            components["year"] = year_match.group()

        # Extract ISBN
        isbn_match = self.PATTERNS["isbn"].search(goal)
        if isbn_match:
            components["isbn"] = isbn_match.group(1)

        # Extract file type
        file_match = self.PATTERNS["file_type"].search(goal)
        if file_match:
            components["file_type"] = file_match.group(1).lower()

        # Extract resolution
        res_match = self.PATTERNS["resolution"].search(goal)
        if res_match:
            components["resolution"] = res_match.group(1)

        return components

    def _build_base_query(self, goal: str, extracted: Dict) -> str:
        """Build the base search query."""
        # If we have an ISBN, that's the most specific
        if "isbn" in extracted:
            return extracted["isbn"]

        # If we have a title, prioritize that
        if "title" in extracted:
            base = f'"{extracted["title"]}"'
            if "author" in extracted:
                base += f' {extracted["author"]}'
            return base

        # Otherwise, clean up the goal text
        words = goal.lower().split()
        cleaned = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]
        return " ".join(cleaned[:8])  # Limit to 8 most important words

    def _choose_engine(self, content_type: str, extracted: Dict) -> SearchEngine:
        """Choose the best search engine for this query."""
        # ISBN searches work better on Google
        if "isbn" in extracted:
            return SearchEngine.GOOGLE

        # Most content types work well with Google
        return SearchEngine.GOOGLE

    def _get_modifiers(self, content_type: str, extracted: Dict) -> List[str]:
        """Get search modifiers for content type."""
        modifiers = []

        # Add file type modifier if specified
        if "file_type" in extracted:
            modifiers.append(f"filetype:{extracted['file_type']}")

        # Add content-type specific modifiers
        if content_type in self.CONTENT_MODIFIERS:
            # Pick first modifier that's not already in the query
            for mod in self.CONTENT_MODIFIERS[content_type][:2]:
                if mod not in str(extracted.values()).lower():
                    modifiers.append(mod)
                    break

        return modifiers

    def _generate_alternatives(
        self,
        base_query: str,
        extracted: Dict,
        content_type: str
    ) -> List[str]:
        """Generate alternative search queries."""
        alternatives = []

        # Add variation with "free download"
        alternatives.append(f"{base_query} free download")

        # Add variation with content type
        if content_type:
            alternatives.append(f"{base_query} {content_type}")

        # Add variation with just title if we have author
        if "title" in extracted and "author" in extracted:
            alternatives.append(f'"{extracted["title"]}"')

        # Add variation with year if available
        if "year" in extracted:
            alternatives.append(f"{base_query} {extracted['year']}")

        return alternatives[:3]  # Limit to 3 alternatives

    def record_success(self, query: str, subject: str):
        """Record a successful query."""
        if subject not in self.successful_queries:
            self.successful_queries[subject] = []
        if query not in self.successful_queries[subject]:
            self.successful_queries[subject].append(query)

    def record_failure(self, query: str, subject: str):
        """Record a failed query."""
        if subject not in self.failed_queries:
            self.failed_queries[subject] = []
        if query not in self.failed_queries[subject]:
            self.failed_queries[subject].append(query)

    def get_proven_query(self, subject: str) -> Optional[str]:
        """Get a previously successful query for similar subject."""
        if subject in self.successful_queries:
            return self.successful_queries[subject][0]
        return None


class ResultAnalyzer:
    """Analyzes search results for quality and relevance."""

    # Patterns indicating high-quality results
    QUALITY_INDICATORS = {
        "official": 0.2,        # Official sites
        "download": 0.15,       # Download pages
        "free": 0.1,           # Free resources
        "pdf": 0.1,            # PDF files
        "epub": 0.1,           # EPUB files
        "archive": 0.1,        # Archive sites
        "library": 0.1,        # Library sites
    }

    # Patterns indicating low-quality results
    SPAM_INDICATORS = {
        "signup": -0.2,         # Requires signup
        "premium": -0.15,       # Paid content
        "trial": -0.15,         # Trial offers
        "ads": -0.1,           # Ad pages
        "survey": -0.2,         # Survey walls
        "captcha": -0.1,       # Captcha walls
    }

    # Known high-quality domains for different content types
    TRUSTED_DOMAINS = {
        "ebook": [
            "annas-archive", "libgen", "zlibrary", "archive.org",
            "gutenberg.org", "standard-ebooks.org"
        ],
        "paper": [
            "arxiv.org", "scholar.google", "semanticscholar",
            "researchgate.net", "academia.edu"
        ],
        "image": [
            "unsplash.com", "pexels.com", "pixabay.com",
            "wallhaven.cc", "flickr.com"
        ],
    }

    def analyze_result(
        self,
        result: SearchResult,
        query: SearchQuery,
        content_type: str = ""
    ) -> float:
        """Analyze a single result and compute relevance score."""
        score = 0.5  # Start at neutral

        text = f"{result.title} {result.snippet}".lower()
        url_lower = result.url.lower()

        # Check quality indicators
        for indicator, boost in self.QUALITY_INDICATORS.items():
            if indicator in text or indicator in url_lower:
                score += boost

        # Check spam indicators
        for indicator, penalty in self.SPAM_INDICATORS.items():
            if indicator in text or indicator in url_lower:
                score += penalty  # penalty is negative

        # Check trusted domains
        if content_type in self.TRUSTED_DOMAINS:
            for domain in self.TRUSTED_DOMAINS[content_type]:
                if domain in url_lower:
                    score += 0.3
                    break

        # Boost if query terms appear in title
        query_words = set(query.query.lower().split())
        title_words = set(result.title.lower().split())
        overlap = len(query_words & title_words) / max(len(query_words), 1)
        score += overlap * 0.2

        # Position boost (earlier results slightly preferred)
        if result.position <= 3:
            score += 0.1
        elif result.position <= 5:
            score += 0.05

        return min(1.0, max(0.0, score))

    def rank_results(
        self,
        results: List[SearchResult],
        query: SearchQuery,
        content_type: str = ""
    ) -> List[SearchResult]:
        """Rank results by computed relevance."""
        for result in results:
            result.relevance_score = self.analyze_result(result, query, content_type)

        return sorted(results, key=lambda r: r.relevance_score, reverse=True)

    def should_try_alternative(
        self,
        results: List[SearchResult],
        threshold: float = 0.5
    ) -> bool:
        """Determine if we should try an alternative query."""
        if not results:
            return True

        # Check if top results are good enough
        top_scores = [r.relevance_score for r in results[:3]]
        avg_top = sum(top_scores) / len(top_scores) if top_scores else 0

        return avg_top < threshold


class SearchIntelligence:
    """Main class coordinating search intelligence."""

    def __init__(self, persistent_memory=None):
        self.persistent_memory = persistent_memory
        self.formulator = QueryFormulator()
        self.analyzer = ResultAnalyzer()
        self.sessions: List[SearchSession] = []

    def create_search(self, goal: str, content_type: str = "") -> SearchQuery:
        """Create an optimized search query for a goal."""
        return self.formulator.formulate(goal, content_type)

    def get_search_url(self, query: SearchQuery) -> str:
        """Get the search URL for a query."""
        encoded_query = url_quote(query.query)

        if query.engine == SearchEngine.GOOGLE:
            return f"https://www.google.com/search?q={encoded_query}"
        elif query.engine == SearchEngine.DUCKDUCKGO:
            return f"https://duckduckgo.com/?q={encoded_query}"
        elif query.engine == SearchEngine.BING:
            return f"https://www.bing.com/search?q={encoded_query}"
        else:
            return f"https://www.google.com/search?q={encoded_query}"

    def start_session(self, query: SearchQuery) -> SearchSession:
        """Start a new search session."""
        session = SearchSession(query=query)
        self.sessions.append(session)
        return session

    def analyze_results(
        self,
        session: SearchSession,
        results: List[Dict],
        content_type: str = ""
    ) -> List[SearchResult]:
        """Analyze and rank search results."""
        parsed_results = []
        for i, r in enumerate(results):
            parsed_results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("snippet", ""),
                position=i + 1,
                relevance_score=0.0
            ))

        ranked = self.analyzer.rank_results(parsed_results, session.query, content_type)
        session.results = ranked
        return ranked

    def record_click(self, session: SearchSession, position: int):
        """Record that a result was clicked."""
        session.clicks.append(position)
        for result in session.results:
            if result.position == position:
                result.clicked = True
                break

    def record_success(self, session: SearchSession, position: int):
        """Record that a click led to successful download."""
        session.successful = True
        for result in session.results:
            if result.position == position:
                result.led_to_download = True
                break

        # Learn from success
        self.formulator.record_success(
            session.query.query,
            session.query.original
        )

    def should_reformulate(self, session: SearchSession) -> bool:
        """Check if we should try a different query."""
        if not session.results:
            return True

        if len(session.clicks) >= 3 and not session.successful:
            return True

        return self.analyzer.should_try_alternative(session.results)

    def get_next_query(self, session: SearchSession) -> Optional[str]:
        """Get the next query to try."""
        if session.query.alternatives:
            return session.query.alternatives.pop(0)
        return None

    def get_best_result_url(self, session: SearchSession) -> Optional[str]:
        """Get the URL of the best result."""
        if session.results:
            # Find highest scored unclicked result
            for result in session.results:
                if not result.clicked:
                    return result.url
            # If all clicked, return the top result
            return session.results[0].url
        return None

    def export_learnings(self) -> Dict:
        """Export learned query patterns."""
        return {
            "successful": self.formulator.successful_queries,
            "failed": self.formulator.failed_queries
        }

    def import_learnings(self, data: Dict):
        """Import previously learned query patterns."""
        self.formulator.successful_queries = data.get("successful", {})
        self.formulator.failed_queries = data.get("failed", {})


# Global instance
_search_intel: Optional[SearchIntelligence] = None


def get_search_intel(persistent_memory=None) -> SearchIntelligence:
    """Get the global search intelligence instance."""
    global _search_intel
    if _search_intel is None:
        _search_intel = SearchIntelligence(persistent_memory)
    return _search_intel
