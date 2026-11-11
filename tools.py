from __future__ import annotations

import html
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 StudyNotesLibrarian/1.0"
)
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))
MAX_PAGE_CHARS = int(os.getenv("MAX_PAGE_CHARS", "4500"))

BASE_DIR = Path(__file__).resolve().parent
_STUDY_DIR = Path(os.getenv("STUDY_CARDS_DIR", "study_cards"))
STUDY_CARDS_DIR = _STUDY_DIR if _STUDY_DIR.is_absolute() else BASE_DIR / _STUDY_DIR
STUDY_CARD_MAX_BYTES = int(os.getenv("STUDY_CARD_MAX_BYTES", str(1024 * 1024)))
STUDY_CARD_SUFFIXES = {
    ".md", ".markdown", ".txt", ".text", ".rst", ".org", ".csv", ".json",
    ".yaml", ".yml", ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css",
    ".c", ".h", ".cpp", ".hpp", ".java", ".rs", ".go", ".sql", ".sh",
}
STUDY_STOPWORDS = {
    "a", "an", "the", "i", "you", "me", "my", "we", "our", "it", "this",
    "that", "is", "are", "was", "were", "be", "been", "being", "do", "does",
    "did", "how", "what", "when", "where", "which", "who", "why", "to",
    "of", "in", "on", "at", "by", "with", "about", "please", "can", "could",
    "should", "would", "will", "tell", "give", "show", "explain", "need",
    "want", "using", "and", "or", "if", "then", "than",
}
TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    engine: str
    content: str = ""
    code: str = ""
    fetched: bool = False
    rank: int = field(default=0, repr=False)

    def to_dict(self, index: int) -> dict:
        data = asdict(self)
        data.pop("rank", None)
        data["id"] = index
        parsed = urlparse(self.url)
        domain = parsed.netloc.replace("www.", "")
        if self.engine == "study_cards":
            domain = "study_cards"
        elif parsed.scheme == "file":
            domain = "local file"
        data["domain"] = domain
        return data


def _clean_text(value: str) -> str:
    value = html.unescape(value or "")
    return re.sub(r"\s+", " ", value).strip()


def _normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for token in _tokens(query):
        if token in STUDY_STOPWORDS or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def _iter_study_cards(root: Path):
    try:
        paths = root.rglob("*")
    except OSError:
        return
    for path in paths:
        try:
            if not path.is_file():
                continue
            relative = path.relative_to(root)
        except (OSError, ValueError):
            continue
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.suffix.lower() not in STUDY_CARD_SUFFIXES:
            continue
        yield path, relative


def _read_study_card(path: Path) -> str | None:
    try:
        if path.stat().st_size > STUDY_CARD_MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:4096]:
        return None
    return data.decode("utf-8", errors="ignore")


def _study_card_code(content: str) -> str:
    blocks = re.findall(r"```[ \t]*[A-Za-z0-9_+#.-]*[ \t]*\r?\n(.*?)```", content, re.DOTALL)
    cleaned = [block.strip() for block in blocks if block.strip()]
    return "\n\n".join(cleaned[:3])[:MAX_PAGE_CHARS]


def search_study_cards(query: str, limit: int = 5) -> list[SearchHit]:
    if not query.strip() or not STUDY_CARDS_DIR.exists():
        return []

    terms = _query_terms(query)
    query_phrase = " ".join(_tokens(query))
    if not terms and not query_phrase:
        return []

    scored: list[tuple[float, str, Path, str, Path]] = []
    for path, relative in _iter_study_cards(STUDY_CARDS_DIR):
        content = _read_study_card(path)
        if not content:
            continue

        name_tokens = set(_tokens(path.stem))
        content_tokens = set(_tokens(content))
        matched_name = [term for term in terms if term in name_tokens]
        matched_content = [term for term in terms if term in content_tokens]
        name_phrase = " ".join(_tokens(path.stem))
        content_phrase = " ".join(_tokens(content))

        coverage_terms = [term for term in terms if len(term) >= 3] or terms
        name_coverage = (
            len([term for term in coverage_terms if term in name_tokens]) / len(coverage_terms)
            if coverage_terms
            else 0.0
        )
        total_coverage = (
            len({term for term in coverage_terms if term in name_tokens or term in content_tokens})
            / len(coverage_terms)
            if coverage_terms
            else 0.0
        )
        matched_primary_content = [
            term for term in coverage_terms if term in content_tokens
        ]

        phrase_in_name = bool(query_phrase) and query_phrase in name_phrase
        phrase_in_content = bool(query_phrase) and query_phrase in content_phrase

        matched = (
            phrase_in_name
            or phrase_in_content
            or name_coverage >= 0.5
            or (total_coverage >= 0.6 and len(matched_primary_content) >= 2)
        )
        if not matched:
            continue

        score = (
            (6 if phrase_in_name else 0)
            + (3 if phrase_in_content else 0)
            + len(matched_name) * 3
            + len(matched_content)
            + name_coverage
        )
        scored.append((score, str(relative).lower(), path, content, relative))

    scored.sort(key=lambda item: (-item[0], item[1]))

    hits: list[SearchHit] = []
    for _, _, path, content, relative in scored[:limit]:
        hits.append(
            SearchHit(
                title=relative.stem,
                url=f"/study_cards/{quote(relative.as_posix())}",
                snippet=_clean_text(content[:1600])[:280],
                engine="study_cards",
                content=content,
                code=_study_card_code(content),
                fetched=True,
            )
        )
    return hits


def _duckduckgo_html(query: str, limit: int) -> list[SearchHit]:
    response = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query},
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    hits: list[SearchHit] = []
    for block in soup.select(".result"):
        link = block.select_one(".result__a")
        if not link:
            continue
        href = link.get("href", "")
        if "uddg=" in href:
            target = parse_qs(urlparse(href).query).get("uddg")
            if target:
                href = unquote(target[0])
        snippet_node = block.select_one(".result__snippet")
        hit = SearchHit(
            title=_clean_text(link.get_text(" ", strip=True)),
            url=href,
            snippet=_clean_text(snippet_node.get_text(" ", strip=True) if snippet_node else ""),
            engine="duckduckgo",
        )
        if hit.url.startswith("http"):
            hits.append(hit)
        if len(hits) >= limit:
            break
    return hits


def duckduckgo_search(query: str, limit: int = 5) -> tuple[list[SearchHit], str | None]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            return _duckduckgo_html(query, limit), None
        except Exception as exc:
            return [], f"DuckDuckGo unavailable: {exc}"

    errors: list[str] = []
    for backend in ("html", "duckduckgo", "auto"):
        try:
            with DDGS(timeout=HTTP_TIMEOUT) as ddgs:
                rows = list(
                    ddgs.text(
                        query,
                        region="us-en",
                        safesearch="moderate",
                        max_results=limit,
                        backend=backend,
                    )
                )
            hits = [
                SearchHit(
                    title=_clean_text(str(row.get("title", ""))),
                    url=str(row.get("href") or row.get("url") or ""),
                    snippet=_clean_text(str(row.get("body") or row.get("snippet") or "")),
                    engine="duckduckgo",
                )
                for row in rows
            ]
            hits = [hit for hit in hits if hit.url.startswith("http")]
            if hits:
                return hits, None
        except Exception as exc:
            errors.append(f"{backend}: {exc}")

    try:
        hits = _duckduckgo_html(query, limit)
        if hits:
            return hits, None
    except Exception as exc:
        errors.append(f"html fallback: {exc}")
    detail = errors[0] if errors else "No results returned."
    return [], f"DuckDuckGo: {detail}"


def brave_search(query: str, limit: int = 5) -> tuple[list[SearchHit], str | None]:
    key = os.getenv("BRAVE_API_KEY", "").strip()
    if not key:
        return [], "BRAVE_API_KEY is not configured"

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={
                "q": query,
                "count": limit,
                "text_decorations": 0,
                "safesearch": "moderate",
            },
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": key,
                "User-Agent": USER_AGENT,
            },
            timeout=HTTP_TIMEOUT,
        )
        if response.status_code >= 400:
            return [], f"Brave Search returned HTTP {response.status_code}"
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        return [], f"Brave Search: {exc}"

    hits: list[SearchHit] = []
    for row in data.get("web", {}).get("results", []):
        hit = SearchHit(
            title=_clean_text(str(row.get("title", ""))),
            url=str(row.get("url", "")),
            snippet=_clean_text(str(row.get("description", ""))),
            engine="brave",
        )
        if hit.url.startswith("http"):
            hits.append(hit)
        if len(hits) >= limit:
            break
    return hits, None


def fetch_page(hit: SearchHit) -> SearchHit:
    try:
        response = requests.get(
            hit.url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
            },
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
        content_type = response.headers.get("content-type", "")
        if response.status_code >= 400 or "html" not in content_type:
            return hit

        soup = BeautifulSoup(response.content[:2_500_000], "html.parser")
        for node in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form", "button"]):
            node.decompose()

        title_node = soup.find("meta", property="og:title") or soup.find("h1") or soup.find("title")
        if title_node:
            title = title_node.get("content") if title_node.has_attr("content") else title_node.get_text(" ", strip=True)
            title = _clean_text(str(title or ""))
            if title and len(title) > 4:
                hit.title = title

        code_blocks: list[str] = []
        for pre in soup.find_all("pre"):
            text = pre.get_text("\n", strip=True)
            if 20 <= len(text) <= 2500:
                code_blocks.append(text)
            if len(code_blocks) >= 3:
                break

        root = soup.find("article") or soup.find("main") or soup.body or soup
        paragraphs: list[str] = []
        for node in root.find_all(["p", "li"]):
            text = _clean_text(node.get_text(" ", strip=True))
            if len(text) >= 60:
                paragraphs.append(text)
            if sum(len(part) for part in paragraphs) >= MAX_PAGE_CHARS:
                break

        hit.content = "\n\n".join(paragraphs)[:MAX_PAGE_CHARS]
        hit.code = "\n\n".join(code_blocks)[:MAX_PAGE_CHARS]
        hit.fetched = bool(hit.content or hit.code)
    except Exception:
        return hit
    return hit


def _interleave(groups: dict[str, list[SearchHit]], limit: int) -> list[SearchHit]:
    merged: list[SearchHit] = []
    seen: set[str] = set()
    engines = [engine for engine, hits in groups.items() if hits]
    rank = 0
    while len(merged) < limit and engines:
        progressed = False
        for engine in list(engines):
            hits = groups[engine]
            if not hits:
                engines.remove(engine)
                continue
            progressed = True
            hit = hits.pop(0)
            key = _normalize_url(hit.url)
            if key and key not in seen:
                seen.add(key)
                hit.rank = rank
                rank += 1
                merged.append(hit)
                if len(merged) >= limit:
                    break
        if not progressed:
            break
    return merged


def search_web(
    queries: list[str],
    limit: int = 5,
    max_sources: int = 6,
    fetch_top: int = 3,
) -> tuple[list[SearchHit], dict]:
    queries = [query.strip() for query in queries if query.strip()][:3]
    engine_info = {
        "duckduckgo": {"status": "skipped", "queries": queries, "count": 0, "error": None},
        "brave": {"status": "skipped", "queries": queries, "count": 0, "error": None},
    }
    if not queries:
        return [], engine_info

    groups: dict[str, list[SearchHit]] = {"duckduckgo": [], "brave": []}
    jobs = []
    with ThreadPoolExecutor(max_workers=min(6, len(queries) * 2)) as pool:
        for query in queries:
            jobs.append((pool.submit(duckduckgo_search, query, limit), "duckduckgo"))
            jobs.append((pool.submit(brave_search, query, limit), "brave"))

        for future, engine in jobs:
            try:
                hits, error = future.result()
            except Exception as exc:
                hits, error = [], str(exc)
            if error and not hits:
                engine_info[engine]["error"] = error
                engine_info[engine]["status"] = "failed"
            elif hits:
                engine_info[engine]["status"] = "done"
                engine_info[engine]["count"] += len(hits)
            groups[engine].extend(hits)

    for engine, info in engine_info.items():
        if info["status"] == "skipped" and not info["error"]:
            info["status"] = "done"
    if engine_info["brave"]["error"] == "BRAVE_API_KEY is not configured":
        engine_info["brave"]["status"] = "skipped"

    sources = _interleave(groups, max_sources)
    for index, hit in enumerate(sources):
        hit.rank = index

    fetch_targets = sources[: max(0, fetch_top)]
    if fetch_targets:
        with ThreadPoolExecutor(max_workers=min(4, len(fetch_targets))) as pool:
            futures = [pool.submit(fetch_page, hit) for hit in fetch_targets]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    pass

    return sources, engine_info
