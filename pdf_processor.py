import logging
import re
from pathlib import Path
from typing import Any, Dict, List
import fitz  # PyMuPDF
from models import ExtractedDocument, OrganizedContent

logger = logging.getLogger(__name__)
MAX_CHARS_PER_DOC = 80_000

class PDFProcessor:
    async def extract(self, file_path: str) -> ExtractedDocument:
        path = Path(file_path)
        try:
            doc = fitz.open(str(path))
            metadata = doc.metadata or {}
            pages = [page.get_text("text").strip() for page in doc if len(page.get_text("text").strip()) > 50]
            full_text = "\n\n".join(pages)
            doc.close()
            
            truncated = full_text[:MAX_CHARS_PER_DOC] if len(full_text) > MAX_CHARS_PER_DOC else full_text
            
            return ExtractedDocument(
                filename=path.name,
                total_pages=len(pages),
                text_length=len(full_text),
                topics=[], 
                raw_text=truncated,
                metadata=metadata,
            )
        except Exception as exc:
            raise ValueError(f"Failed to process {path.name}: {exc}")

    def organize(self, documents: List[ExtractedDocument]) -> OrganizedContent:
        all_topics = []
        total_pages = sum(d.total_pages for d in documents)
        return OrganizedContent(
            documents=documents,
            combined_topics=all_topics,
            total_pages=total_pages,
            course_name_guess=Path(documents[0].filename).stem.replace("_", " ").title() if documents else "New Course"
        )