from langchain_core.documents import Document;
from langchain_text_splitters import RecursiveCharacterTextSplitter;
import re;

# Matches a heading like "9.68.060   Relocation assistance..."
# Generic (\d+\.\d+\.\d+) so it works for any city's code.
# The 2+ spaces requirement stops mid-sentence cross-references such as
# "see Section 9.68.050 for..." from being read as headings.
SECTION_RE = re.compile(
    r"(?m)^\s*"
    # Optional prefix used by some codes: "§ 8.52.030", "Sec. 12-45", "Section 9.68.060"
    r"(?:§\s*|Sec\.?\s+|Section\s+)?"
    # 2 to 4 parts, dot- or hyphen-separated: 9.68.060, 12-45, 37.02.010
    r"(?P<num>\d+(?:[.-]\d+){1,3})"
    r"\s{2,}(?P<title>[A-Z][^\n]*)"
)

# ~1000 chars keeps each chunk inside all-MiniLM-L6-v2's 256-token window.
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)

def chunk_documents(docs: list[Document]) -> list[Document]:
    """Section-aware chunking with a size-based fallback."""
    full_text = "\n".join(d.page_content for d in docs)
    source = docs[0].metadata.get("source_file", "unknown")

    sections = _split_sections(full_text, source)
    if not sections:
        # No section numbering — plain recursive splitting.
        return _splitter.split_documents(docs)

    return _enforce_size(sections)

def _split_sections(text: str, source: str) -> list[Document]:
    matches = list(SECTION_RE.finditer(text))
    if not matches:
        return []

    # Each section number appears twice: once in the table of contents, once as
    # the real heading. Keeping the LAST match per number drops the TOC copy.
    headings = sorted(
        {m.group("num"): m for m in matches}.values(), key=lambda m: m.start()
    )

    out = []
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = _tidy(text[match.start() : end])

        if len(body) < 200:  # leftover TOC fragment — title with no rule text
            continue

        out.append(
            Document(
                page_content=body,
                metadata={
                    "source_file": source,
                    "section": match.group("num"),
                    "title": match.group("title").strip().rstrip("."),
                },
            )
        )
    return out

def _enforce_size(sections: list[Document]) -> list[Document]:
    """Sub-split oversized sections, keeping each piece's section metadata."""
    out = []
    for doc in sections:
        if len(doc.page_content) <= 1000:
            doc.metadata["part"] = 1
            doc.metadata["parts"] = 1
            out.append(doc)
            continue

        pieces = _splitter.split_documents([doc])
        for n, piece in enumerate(pieces, start=1):
            # metadata is copied by the splitter, so section/title survive.
            piece.metadata["part"] = n
            piece.metadata["parts"] = len(pieces)
            out.append(piece)
    return out

def _tidy(text: str) -> str:
    """Light cleanup only — deliberately does NOT collapse runs of spaces, since
    the 9.68.060 dollar table may rely on spacing to pair bedrooms with amounts."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
