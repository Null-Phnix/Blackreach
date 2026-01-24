"""
Blackreach Knowledge Base - Domain knowledge about content sources.

This module contains knowledge about where to find specific types of content,
enabling Blackreach to make intelligent decisions about where to start searching.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import re


@dataclass
class ContentSource:
    """A known source for a specific type of content."""
    name: str
    url: str
    description: str
    content_types: List[str]  # What types of content this source has
    keywords: List[str]  # Keywords that suggest this source
    priority: int = 5  # 1-10, higher = better for this content type
    requires_search: bool = True  # Whether to search on the site or just navigate
    mirrors: List[str] = field(default_factory=list)  # Alternative URLs if primary is down


# Knowledge base of content sources
# This is Blackreach's "memory" of where to find things
CONTENT_SOURCES: List[ContentSource] = [
    # === EBOOKS / BOOKS ===
    ContentSource(
        name="Anna's Archive",
        url="https://annas-archive.li",  # Primary mirror (has DDoS-Guard protection)
        description="Largest open library with books, papers, comics, magazines",
        content_types=["ebook", "book", "epub", "pdf", "paper", "textbook"],
        keywords=["book", "ebook", "epub", "pdf", "novel", "fiction", "textbook", "read"],
        priority=9,
        requires_search=True,
        mirrors=[]  # Mirrors are unreliable, removed
    ),
    ContentSource(
        name="Project Gutenberg",
        url="https://www.gutenberg.org",
        description="Free ebooks of public domain works",
        content_types=["ebook", "book", "epub", "classic"],
        keywords=["classic", "public domain", "gutenberg", "old book", "literature"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Internet Archive Books",
        url="https://archive.org/details/texts",
        description="Digital library with millions of free books - reliable and no DDoS protection",
        content_types=["ebook", "book", "pdf", "scan", "epub"],
        keywords=["archive", "scan", "historical", "rare book", "epub", "book", "novel"],
        priority=8,  # Increased priority as reliable fallback
        requires_search=True
    ),
    ContentSource(
        name="Z-Library",
        url="https://singlelogin.re",  # Requires login, but more stable
        description="Large ebook library (requires account)",
        content_types=["ebook", "book", "epub", "pdf"],
        keywords=["zlibrary", "z-lib", "ebook", "epub", "pdf", "book", "novel"],
        priority=7,  # Lowered - requires account
        requires_search=True,
        mirrors=[]  # Mirrors are unreliable
    ),
    ContentSource(
        name="Library Genesis",
        url="https://libgen.li",  # Primary - the only working mirror
        description="Library Genesis - academic and general books",
        content_types=["ebook", "book", "textbook", "paper", "pdf"],
        keywords=["libgen", "textbook", "academic", "scientific", "epub", "pdf", "book", "novel"],
        priority=8,
        requires_search=True,
        mirrors=[]  # Other mirrors are down
    ),
    ContentSource(
        name="Standard Ebooks",
        url="https://standardebooks.org",
        description="Free, high-quality ebooks with modern formatting",
        content_types=["ebook", "epub", "classic"],
        keywords=["standard ebooks", "classic", "public domain", "well formatted"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="ManyBooks",
        url="https://manybooks.net",
        description="Free ebooks in multiple formats",
        content_types=["ebook", "book", "epub", "pdf"],
        keywords=["manybooks", "free ebook", "epub"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="Open Library",
        url="https://openlibrary.org",
        description="Internet Archive's open library project",
        content_types=["ebook", "book", "borrow"],
        keywords=["open library", "borrow", "lending library"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="PDF Drive",
        url="https://www.pdfdrive.com",
        description="PDF ebook search engine - reliable, no DDoS protection",
        content_types=["pdf", "ebook", "book", "epub"],
        keywords=["pdf", "pdf drive", "ebook pdf", "epub", "book", "novel"],
        priority=8,  # Increased priority as reliable alternative
        requires_search=True
    ),

    # === ACADEMIC PAPERS ===
    ContentSource(
        name="arXiv",
        url="https://arxiv.org",
        description="Open access archive for scientific papers",
        content_types=["paper", "preprint", "research", "pdf"],
        keywords=["arxiv", "preprint", "physics", "math", "cs", "research paper", "scientific"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="Semantic Scholar",
        url="https://www.semanticscholar.org",
        description="AI-powered research paper search",
        content_types=["paper", "research", "academic"],
        keywords=["academic", "research", "citation", "paper"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Google Scholar",
        url="https://scholar.google.com",
        description="Search engine for scholarly literature",
        content_types=["paper", "research", "academic", "citation"],
        keywords=["scholar", "academic", "research", "journal"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="Sci-Hub",
        url="https://sci-hub.se",
        description="Access to paywalled academic papers",
        content_types=["paper", "journal", "research"],
        keywords=["doi", "journal", "paywalled", "scientific"],
        priority=8,
        requires_search=True,
        mirrors=[
            "https://sci-hub.st",
            "https://sci-hub.ru",
            "https://sci-hub.ee",
        ]
    ),

    # === CODE / SOFTWARE ===
    ContentSource(
        name="GitHub",
        url="https://github.com",
        description="Code hosting and collaboration platform",
        content_types=["code", "repo", "software", "project"],
        keywords=["github", "repo", "code", "source", "git", "project", "readme"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="GitLab",
        url="https://gitlab.com",
        description="DevOps platform with code hosting",
        content_types=["code", "repo", "software"],
        keywords=["gitlab", "repo", "code"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="PyPI",
        url="https://pypi.org",
        description="Python package index",
        content_types=["package", "python", "library"],
        keywords=["python", "pip", "package", "library", "pypi"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="npm",
        url="https://www.npmjs.com",
        description="Node.js package registry",
        content_types=["package", "javascript", "node"],
        keywords=["npm", "node", "javascript", "js", "package"],
        priority=8,
        requires_search=True
    ),

    # === IMAGES / WALLPAPERS ===
    ContentSource(
        name="Unsplash",
        url="https://unsplash.com",
        description="Free high-resolution photos",
        content_types=["image", "photo", "wallpaper"],
        keywords=["photo", "stock", "free image", "hd", "unsplash"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Pexels",
        url="https://www.pexels.com",
        description="Free stock photos and videos",
        content_types=["image", "photo", "video", "wallpaper"],
        keywords=["stock photo", "free photo", "pexels"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Wallhaven",
        url="https://wallhaven.cc",
        description="Wallpaper search engine with high quality images",
        content_types=["wallpaper", "image", "desktop"],
        keywords=["wallpaper", "desktop", "background", "4k", "hd"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="Pixabay",
        url="https://pixabay.com",
        description="Free images, videos, and music",
        content_types=["image", "photo", "vector", "video"],
        keywords=["pixabay", "free image", "stock"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="DeviantArt",
        url="https://www.deviantart.com",
        description="Art community with downloadable artwork",
        content_types=["art", "image", "wallpaper", "digital art"],
        keywords=["art", "deviantart", "digital art", "fan art", "artwork"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="Alpha Coders",
        url="https://alphacoders.com",
        description="Wallpapers, art, and images in multiple resolutions",
        content_types=["wallpaper", "image", "art"],
        keywords=["wallpaper", "4k", "8k", "ultra hd", "alphacoders"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="WallpaperFlare",
        url="https://www.wallpaperflare.com",
        description="HD wallpapers with custom resolution downloads",
        content_types=["wallpaper", "image", "desktop"],
        keywords=["wallpaper", "hd", "desktop background"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="Artstation",
        url="https://www.artstation.com",
        description="Professional art platform with high-quality artwork",
        content_types=["art", "image", "digital art", "wallpaper"],
        keywords=["artstation", "concept art", "game art", "digital art"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Imgur",
        url="https://imgur.com",
        description="Image hosting and sharing platform",
        content_types=["image", "meme", "photo"],
        keywords=["imgur", "image", "meme", "gallery"],
        priority=6,
        requires_search=True
    ),

    # === COMICS / MANGA ===
    ContentSource(
        name="GetComics",
        url="https://getcomics.org",
        description="Comic book downloads",
        content_types=["comic", "cbr", "cbz", "graphic novel"],
        keywords=["comic", "comics", "cbr", "cbz", "marvel", "dc", "graphic novel"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="MangaDex",
        url="https://mangadex.org",
        description="Free manga reader",
        content_types=["manga", "comic", "webtoon"],
        keywords=["manga", "manhwa", "manhua", "webtoon", "japanese comic"],
        priority=9,
        requires_search=True
    ),

    # === AUDIO / MUSIC ===
    ContentSource(
        name="Internet Archive Audio",
        url="https://archive.org/details/audio",
        description="Free music, audiobooks, and podcasts",
        content_types=["audio", "music", "podcast", "audiobook"],
        keywords=["audio", "music", "podcast", "archive", "free music"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Bandcamp",
        url="https://bandcamp.com",
        description="Music platform with many free downloads",
        content_types=["music", "album", "audio"],
        keywords=["bandcamp", "music", "album", "indie"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="Free Music Archive",
        url="https://freemusicarchive.org",
        description="Free, legal music downloads",
        content_types=["music", "audio", "mp3"],
        keywords=["free music", "creative commons", "royalty free"],
        priority=8,
        requires_search=True
    ),

    # === VIDEO ===
    ContentSource(
        name="Internet Archive Video",
        url="https://archive.org/details/movies",
        description="Free movies, documentaries, and videos",
        content_types=["video", "movie", "documentary"],
        keywords=["video", "movie", "documentary", "film", "archive"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="YouTube",
        url="https://www.youtube.com",
        description="Video sharing platform",
        content_types=["video", "tutorial", "music video"],
        keywords=["youtube", "video", "watch", "tutorial"],
        priority=7,
        requires_search=True
    ),

    # === DATASETS ===
    ContentSource(
        name="Kaggle",
        url="https://www.kaggle.com/datasets",
        description="Data science datasets and competitions",
        content_types=["dataset", "data", "csv", "ml"],
        keywords=["kaggle", "dataset", "data", "machine learning", "csv"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="Hugging Face",
        url="https://huggingface.co/datasets",
        description="ML datasets and models",
        content_types=["dataset", "model", "ml", "ai"],
        keywords=["huggingface", "model", "dataset", "transformer", "llm"],
        priority=9,
        requires_search=True
    ),

    # === FONTS ===
    ContentSource(
        name="Google Fonts",
        url="https://fonts.google.com",
        description="Free, open-source fonts",
        content_types=["font", "ttf", "otf"],
        keywords=["font", "google font", "typeface", "typography"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="Font Squirrel",
        url="https://www.fontsquirrel.com",
        description="Free fonts for commercial use",
        content_types=["font", "ttf", "otf", "woff"],
        keywords=["font", "free font", "commercial font"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="DaFont",
        url="https://www.dafont.com",
        description="Archive of freely downloadable fonts",
        content_types=["font", "ttf"],
        keywords=["dafont", "font", "free font", "decorative font"],
        priority=7,
        requires_search=True
    ),

    # === ICONS / DESIGN ASSETS ===
    ContentSource(
        name="Flaticon",
        url="https://www.flaticon.com",
        description="Database of free icons",
        content_types=["icon", "svg", "png"],
        keywords=["icon", "flaticon", "svg icon", "free icon"],
        priority=8,
        requires_search=True
    ),
    ContentSource(
        name="Icons8",
        url="https://icons8.com",
        description="Icons, illustrations, and design tools",
        content_types=["icon", "illustration", "image"],
        keywords=["icon", "icons8", "illustration"],
        priority=7,
        requires_search=True
    ),

    # === SOFTWARE / TOOLS ===
    ContentSource(
        name="SourceForge",
        url="https://sourceforge.net",
        description="Open source software downloads",
        content_types=["software", "app", "download"],
        keywords=["sourceforge", "open source", "software", "download"],
        priority=7,
        requires_search=True
    ),
    ContentSource(
        name="AlternativeTo",
        url="https://alternativeto.net",
        description="Find alternatives to software",
        content_types=["software", "app", "alternative"],
        keywords=["alternative", "software alternative", "app like"],
        priority=6,
        requires_search=True
    ),

    # === 3D MODELS ===
    ContentSource(
        name="Thingiverse",
        url="https://www.thingiverse.com",
        description="3D printable models",
        content_types=["3d", "stl", "model", "print"],
        keywords=["3d print", "stl", "thingiverse", "3d model"],
        priority=9,
        requires_search=True
    ),
    ContentSource(
        name="Sketchfab",
        url="https://sketchfab.com",
        description="3D model platform with free downloads",
        content_types=["3d", "model", "fbx", "obj"],
        keywords=["3d model", "sketchfab", "fbx", "obj", "blender"],
        priority=8,
        requires_search=True
    ),

    # === GENERAL ===
    ContentSource(
        name="Internet Archive",
        url="https://archive.org",
        description="Digital library of websites, books, audio, video",
        content_types=["any", "archive", "wayback"],
        keywords=["archive", "wayback", "historical"],
        priority=6,
        requires_search=True
    ),
    ContentSource(
        name="Wikipedia",
        url="https://www.wikipedia.org",
        description="Free encyclopedia for information lookup",
        content_types=["info", "reference", "article"],
        keywords=["wikipedia", "wiki", "information", "what is", "who is"],
        priority=5,
        requires_search=True
    ),
]


def detect_content_type(goal: str) -> List[str]:
    """
    Analyze a goal to determine what type of content is being requested.

    Returns a list of content types in order of likelihood.
    """
    goal_lower = goal.lower()
    detected_types = []

    # Content type patterns
    type_patterns = {
        "ebook": [r'\bepub\b', r'\bebook\b', r'\be-book\b', r'\bkindle\b', r'\bmobi\b'],
        "book": [r'\bbook\b', r'\bnovel\b', r'\bread\b', r'\bstory\b', r'\bfiction\b', r'\btextbook\b'],
        "paper": [r'\bpaper\b', r'\bresearch\b', r'\bjournal\b', r'\barticle\b', r'\bstudy\b', r'\bpreprint\b'],
        "code": [r'\bcode\b', r'\brepo\b', r'\brepository\b', r'\bgithub\b', r'\bsource\b', r'\bproject\b'],
        "image": [r'\bimages?\b', r'\bpictures?\b', r'\bphotos?\b', r'\bjpg\b', r'\bpng\b'],
        "wallpaper": [r'\bwallpaper\b', r'\bdesktop\b', r'\bbackground\b', r'\b4k\b', r'\bhd\b', r'\b8k\b', r'\bultra\s*hd\b'],
        "video": [r'\bvideo\b', r'\bmovie\b', r'\bfilm\b', r'\bdocumentary\b', r'\bmp4\b'],
        "audio": [r'\baudio\b', r'\bmusic\b', r'\bsong\b', r'\bmp3\b', r'\bpodcast\b', r'\balbum\b'],
        "dataset": [r'\bdataset\b', r'\bdata\b', r'\bcsv\b', r'\btraining data\b'],
        "pdf": [r'\bpdf\b'],
        "package": [r'\bpackage\b', r'\blibrary\b', r'\bmodule\b', r'\bpip\b', r'\bnpm\b'],
        "comic": [r'\bcomic\b', r'\bcomics\b', r'\bcbr\b', r'\bcbz\b', r'\bgraphic novel\b', r'\bmarvel\b', r'\bdc\b'],
        "manga": [r'\bmanga\b', r'\bmanhwa\b', r'\bmanhua\b', r'\bwebtoon\b', r'\banime\b'],
        "font": [r'\bfont\b', r'\bfonts\b', r'\btypeface\b', r'\bttf\b', r'\botf\b', r'\btypography\b'],
        "icon": [r'\bicon\b', r'\bicons\b', r'\bsvg\b', r'\bemoji\b'],
        "3d": [r'\b3d\b', r'\bstl\b', r'\bmodel\b', r'\bfbx\b', r'\bobj\b', r'\bblender\b', r'\b3d\s*print\b'],
        "software": [r'\bsoftware\b', r'\bapp\b', r'\bapplication\b', r'\bprogram\b', r'\btool\b', r'\bdownload\b'],
    }

    for content_type, patterns in type_patterns.items():
        for pattern in patterns:
            if re.search(pattern, goal_lower):
                if content_type not in detected_types:
                    detected_types.append(content_type)
                break

    # If we detected "book" but also "ebook", prioritize ebook
    if "ebook" in detected_types and "book" in detected_types:
        detected_types.remove("book")

    # PDF could be paper or book - check context
    if "pdf" in detected_types:
        if any(word in goal_lower for word in ["research", "paper", "journal", "study"]):
            if "paper" not in detected_types:
                detected_types.append("paper")
        else:
            if "ebook" not in detected_types:
                detected_types.insert(0, "ebook")

    return detected_types if detected_types else ["general"]


def extract_subject(goal: str) -> str:
    """
    Extract the main subject/title from a goal.

    Examples:
        "find me a single epub for red rising" -> "red rising"
        "download papers about transformer architecture" -> "transformer architecture"
    """
    goal_lower = goal.lower()

    # Remove common prefixes
    prefixes = [
        r'^find\s+me\s+', r'^find\s+', r'^get\s+me\s+', r'^get\s+',
        r'^download\s+', r'^fetch\s+', r'^search\s+for\s+', r'^search\s+',
        r'^look\s+for\s+', r'^looking\s+for\s+', r'^i\s+need\s+',
        r'^i\s+want\s+', r'^can\s+you\s+find\s+', r'^please\s+find\s+',
    ]

    subject = goal_lower
    for prefix in prefixes:
        subject = re.sub(prefix, '', subject)

    # Remove common suffixes/qualifiers
    suffixes = [
        r'\s+for\s+me$', r'\s+please$', r'\s+now$',
        r'\s+as\s+soon\s+as\s+possible$', r'\s+asap$',
    ]

    for suffix in suffixes:
        subject = re.sub(suffix, '', subject)

    # Remove quantity indicators and file types
    subject = re.sub(r'\b(a\s+single|one|some|a\s+few|several|multiple)\s+', '', subject)
    subject = re.sub(r'\b(epub|pdf|mobi|mp3|mp4|jpg|png|zip|rar|cbr|cbz|stl|fbx|obj|ttf|otf|svg)\b', '', subject)
    subject = re.sub(r'\b(ebook|e-book|book|paper|image|video|file|wallpaper|comic|manga|font|icon|model)\b', '', subject)

    # Remove prepositions that might be left over
    subject = re.sub(r'\b(for|about|of|on|the|a|an)\s+', ' ', subject)

    # Clean up extra whitespace
    subject = ' '.join(subject.split())

    return subject.strip()


def find_best_sources(goal: str, max_sources: int = 3) -> List[ContentSource]:
    """
    Find the best content sources for a given goal.

    Returns sources sorted by relevance (best first).
    """
    content_types = detect_content_type(goal)
    goal_lower = goal.lower()

    # Score each source
    scored_sources = []

    for source in CONTENT_SOURCES:
        score = 0

        # Check if source handles this content type
        type_match = False
        for ct in content_types:
            if ct in source.content_types or "any" in source.content_types:
                type_match = True
                score += source.priority * 10  # Base score from priority
                break

        if not type_match:
            continue

        # Bonus for keyword matches
        for keyword in source.keywords:
            if keyword in goal_lower:
                score += 20  # Direct keyword match

        # Bonus for specific content type match
        if content_types and content_types[0] in source.content_types:
            score += 15  # Primary type match

        if score > 0:
            scored_sources.append((source, score))

    # Sort by score descending
    scored_sources.sort(key=lambda x: x[1], reverse=True)

    return [source for source, score in scored_sources[:max_sources]]


def reason_about_goal(goal: str) -> Dict:
    """
    Perform deep reasoning about a goal to determine the best approach.

    Returns a dict with:
        - content_types: What types of content we're looking for
        - subject: The main subject/title being searched
        - best_source: The recommended starting source
        - reasoning: Explanation of why this source was chosen
        - search_query: Suggested search query for the source
        - alternate_sources: Backup sources to try
    """
    content_types = detect_content_type(goal)
    subject = extract_subject(goal)
    best_sources = find_best_sources(goal)

    if not best_sources:
        # Fallback to Google
        return {
            "content_types": content_types,
            "subject": subject,
            "best_source": None,
            "start_url": "https://www.google.com",
            "reasoning": "No specific source matched - using general web search",
            "search_query": subject,
            "alternate_sources": []
        }

    best = best_sources[0]
    alternates = best_sources[1:] if len(best_sources) > 1 else []

    # Build reasoning explanation
    type_str = content_types[0] if content_types else "content"
    reasoning = f"For {type_str}, {best.name} is ideal: {best.description}"

    return {
        "content_types": content_types,
        "subject": subject,
        "best_source": best,
        "start_url": best.url,
        "reasoning": reasoning,
        "search_query": subject,
        "alternate_sources": alternates
    }


# Convenience function for agent
def get_smart_start(goal: str) -> tuple:
    """
    Get the smart starting URL and reasoning for a goal.

    Returns (url, reasoning, search_query)
    """
    result = reason_about_goal(goal)
    return (
        result["start_url"],
        result["reasoning"],
        result["search_query"]
    )


def get_all_urls_for_source(source: ContentSource) -> List[str]:
    """
    Get all possible URLs for a source (primary + mirrors).
    """
    urls = [source.url]
    if source.mirrors:
        urls.extend(source.mirrors)
    return urls


def check_url_reachable(url: str, timeout: float = 5.0) -> bool:
    """
    Quick check if a URL is reachable.
    Returns True if reachable, False otherwise.
    """
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, Exception):
        return False


def get_working_url(source: ContentSource, timeout: float = 5.0) -> Optional[str]:
    """
    Find the first working URL for a source.
    Tries primary URL first, then mirrors.

    Returns the working URL or None if all fail.
    """
    for url in get_all_urls_for_source(source):
        if check_url_reachable(url, timeout):
            return url
    return None


def check_sources_health(
    content_types: Optional[List[str]] = None,
    timeout: float = 5.0
) -> Dict[str, Dict]:
    """
    Check health status of all content sources.

    Args:
        content_types: Optional list of content types to filter (e.g., ['ebook', 'wallpaper'])
        timeout: Request timeout in seconds

    Returns:
        Dict mapping source names to their health status:
        {
            "Anna's Archive": {
                "url": "https://annas-archive.li",
                "reachable": True,
                "content_types": ["ebook", "book", ...],
                "priority": 9
            },
            ...
        }
    """
    results = {}

    for source in CONTENT_SOURCES:
        # Filter by content type if specified
        if content_types:
            if not any(ct in source.content_types for ct in content_types):
                continue

        is_reachable = check_url_reachable(source.url, timeout)

        results[source.name] = {
            "url": source.url,
            "reachable": is_reachable,
            "content_types": source.content_types,
            "priority": source.priority,
            "has_mirrors": len(source.mirrors) > 0
        }

        # If primary is down but has mirrors, check them
        if not is_reachable and source.mirrors:
            for mirror in source.mirrors:
                if check_url_reachable(mirror, timeout):
                    results[source.name]["reachable"] = True
                    results[source.name]["working_mirror"] = mirror
                    break

    return results


def get_healthy_sources(content_types: Optional[List[str]] = None, timeout: float = 5.0) -> List[ContentSource]:
    """
    Get list of currently reachable sources for given content types.

    Args:
        content_types: Optional list of content types to filter
        timeout: Request timeout in seconds

    Returns:
        List of ContentSource objects that are currently reachable
    """
    health = check_sources_health(content_types, timeout)
    healthy = []

    for source in CONTENT_SOURCES:
        if source.name in health and health[source.name]["reachable"]:
            healthy.append(source)

    return sorted(healthy, key=lambda s: s.priority, reverse=True)
