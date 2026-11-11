from __future__ import annotations

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from .rag import is_official_url


SOURCE_DOCUMENTS_PATH = Path(__file__).resolve().parent / "fontes"
MIN_SOURCE_DOCUMENTS = 20
MAX_SOURCE_BYTES = 8_000_000
SOURCE_TIMEOUT_SECONDS = 35


@dataclass(frozen=True)
class OfficialSourceDocument:
    url: str
    title: str
    text: str
    retrieved_at: str


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"head", "script", "style", "noscript", "nav", "header", "footer", "svg"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in {
            "br",
            "div",
            "h1",
            "h2",
            "h3",
            "li",
            "p",
            "tr",
        }:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"head", "script", "style", "noscript", "nav", "header", "footer", "svg"}:
            if self._ignored_depth:
                self._ignored_depth -= 1
        elif not self._ignored_depth and tag in {
            "br",
            "div",
            "h1",
            "h2",
            "h3",
            "li",
            "p",
            "tr",
        }:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self._parts.append(data)


def extract_official_html(raw: bytes, charset: str | None = None) -> str:
    decoded = raw.decode(charset or "utf-8", errors="replace")
    parser = _VisibleTextParser()
    parser.feed(decoded)
    text = "\n".join(
        line
        for line in (
            re.sub(r"\s+", " ", part).strip()
            for part in "".join(parser._parts).splitlines()
        )
        if line
    )
    if len(text) < 500 or not re.search(
        r"\b(?:art\.|artigo)\s*\d+", text, re.IGNORECASE
    ):
        raise ValueError("A página não contém texto legislativo integral reconhecível.")
    if re.search(r"gateway time[- ]out|access denied|page not found", text, re.IGNORECASE):
        raise ValueError("A página oficial retornou uma mensagem de erro, não o documento.")
    return text


def source_filename(url: str) -> str:
    return f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:20]}.md"


def source_title_from_url(url: str, fallback: str) -> str:
    path = unquote(urlparse(url).path)
    match = re.search(
        r"/(?P<kind>lei|decreto|decreto-lei|leicomplementar)-"
        r"(?P<number>\d+)-\d{1,2}-[^/]+?-(?P<year>\d{4})-\d+",
        path,
        re.IGNORECASE,
    )
    if not match:
        return fallback.strip() or url

    number = f"{int(match.group('number')):,}".replace(",", ".")
    kind = {
        "decreto-lei": "Decreto-Lei",
        "leicomplementar": "Lei Complementar",
        "lei": "Lei",
        "decreto": "Decreto",
    }[match.group("kind").lower()]
    return f"{kind} nº {number}/{match.group('year')}"


def _serialize_source(document: OfficialSourceDocument) -> str:
    metadata = {
        "url": document.url,
        "title": document.title,
        "retrieved_at": document.retrieved_at,
    }
    return (
        "---SOURCE-METADATA---\n"
        + json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        + "\n---SOURCE-TEXT---\n"
        + document.text
        + "\n"
    )


def read_source_documents(
    source_dir: Path = SOURCE_DOCUMENTS_PATH,
) -> list[OfficialSourceDocument]:
    if not source_dir.exists():
        return []

    documents: list[OfficialSourceDocument] = []
    seen_urls: set[str] = set()
    for path in sorted(source_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        try:
            metadata_text, text = content.split("\n---SOURCE-TEXT---\n", maxsplit=1)
            metadata = json.loads(metadata_text.removeprefix("---SOURCE-METADATA---\n"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"O arquivo de fonte '{path.name}' tem formato inválido.") from exc

        url = metadata.get("url")
        title = metadata.get("title")
        retrieved_at = metadata.get("retrieved_at")
        if (
            not isinstance(url, str)
            or not is_official_url(url)
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(retrieved_at, str)
            or not text.strip()
        ):
            raise ValueError(f"O arquivo de fonte '{path.name}' tem metadados inválidos.")
        if len(text) < 500 or not re.search(
            r"\b(?:art\.|artigo)\s*\d+", text, re.IGNORECASE
        ):
            raise ValueError(f"O arquivo de fonte '{path.name}' não contém texto integral.")
        if url in seen_urls:
            raise ValueError(f"A URL oficial '{url}' aparece em mais de um arquivo de fonte.")
        seen_urls.add(url)
        documents.append(
            OfficialSourceDocument(
                url=url,
                title=title.strip(),
                text=text.strip(),
                retrieved_at=retrieved_at,
            )
        )
    return documents


def _fetch_source(url: str, title: str) -> OfficialSourceDocument:
    request = Request(
        url,
        headers={"User-Agent": "AssistenteVirtualDF/1.0 (official-source-indexer)"},
    )
    with urlopen(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type != "text/html":
            raise ValueError(
                f"Formato {content_type} não suportado; é necessário fornecer uma página HTML."
            )
        raw = response.read(MAX_SOURCE_BYTES + 1)
        if len(raw) > MAX_SOURCE_BYTES:
            raise ValueError(f"A fonte excede o limite de {MAX_SOURCE_BYTES} bytes.")
        text = extract_official_html(raw, response.headers.get_content_charset())

    return OfficialSourceDocument(
        url=url,
        title=title,
        text=text,
        retrieved_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def download_official_sources(
    rows: list[dict[str, str]],
    source_dir: Path = SOURCE_DOCUMENTS_PATH,
) -> tuple[int, list[str]]:
    source_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        url = row.get("url_fonte_legislacao", "").strip()
        if not url:
            continue
        if not is_official_url(url):
            raise ValueError(f"A URL da legislação não é oficial: {url}")
        source_rows.setdefault(url, row)

    source_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(
                _fetch_source,
                url,
                source_title_from_url(
                    url,
                    row.get("legislacao_base", "").strip() or row["programa"],
                ),
            ): url
            for url, row in source_rows.items()
        }
        for future in as_completed(futures):
            url = futures[future]
            try:
                document = future.result()
            except (OSError, URLError, TimeoutError, ValueError) as exc:
                failures.append(f"{url}: {exc}")
                continue
            path = source_dir / source_filename(document.url)
            path.write_text(_serialize_source(document), encoding="utf-8")

    available_urls = {
        document.url
        for document in read_source_documents(source_dir)
        if document.url in source_rows
    }
    return len(available_urls), failures
