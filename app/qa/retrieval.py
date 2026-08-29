"""Lightweight local QA corpus parser and TF-IDF retriever for consulTax."""

import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Resolve path to vetted_schemes.md
CORPUS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "qa_corpus" / "vetted_schemes.md"


class DocumentChunk(BaseModel):
    """Domain model representing a retrieved snippet of text with metadata."""
    source_title: str
    source_section: Optional[str] = None
    snippet: str
    url: Optional[str] = None


def parse_markdown_corpus(file_path: Path) -> List[DocumentChunk]:
    """
    Parses vetted_schemes.md line-by-line into structured chunks.
    Chunks are demarcated by second-level headings (##) and third-level headings (###).
    """
    chunks = []
    if not file_path.exists():
        return chunks
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.splitlines()
    current_title = "General"
    current_section_name = None
    current_text_lines = []
    
    def add_chunk(title: str, section: Optional[str], text_lines: List[str]):
        text = "\n".join(text_lines).strip()
        if text:
            # Strip markdown horizontal rules or trailing spaces
            text = re.sub(r'^---\s*$', '', text, flags=re.MULTILINE)
            text = text.strip()
            if text:
                chunks.append(DocumentChunk(
                    source_title=title,
                    source_section=section,
                    snippet=text
                ))

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            add_chunk(current_title, current_section_name, current_text_lines)
            current_title = stripped[3:].strip()
            current_section_name = None
            current_text_lines = []
        elif stripped.startswith("### "):
            add_chunk(current_title, current_section_name, current_text_lines)
            current_section_name = stripped[4:].strip()
            current_text_lines = []
        elif stripped.startswith("# ") and not stripped.startswith("## "):
            # Ignore primary document header
            pass
        else:
            current_text_lines.append(line)
            
    # Add the remaining text chunk
    add_chunk(current_title, current_section_name, current_text_lines)
    
    return chunks


class TFIDFRetriever:
    """TF-IDF vector space model retriever for tax corpus search."""

    def __init__(self, corpus_path: Path = CORPUS_PATH):
        self.corpus_path = corpus_path
        self.chunks: List[DocumentChunk] = []
        self.vectorizer = TfidfVectorizer(stop_words='english')
        self.tfidf_matrix = None
        self.load_and_index()

    def load_and_index(self):
        """Loads and indexes the vetted schemes corpus using TF-IDF."""
        self.chunks = parse_markdown_corpus(self.corpus_path)
        if not self.chunks:
            return
            
        corpus_texts = []
        for chunk in self.chunks:
            title = chunk.source_title or ""
            section = chunk.source_section or ""
            snippet = chunk.snippet or ""
            # Weight the title and section slightly more by repeating them
            combined = f"{title} {section} {title} {section} {snippet}"
            corpus_texts.append(combined)
            
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus_texts)

    def retrieve(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        """
        Retrieve the top_k matching chunks for a given query.
        Returns empty list if no chunks or query is empty.
        """
        if not query or not query.strip() or not self.chunks or self.tfidf_matrix is None:
            return []
            
        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # Sort in descending order of similarity score
        top_indices = np.argsort(similarities)[::-1]
        
        results = []
        for idx in top_indices[:top_k]:
            if similarities[idx] > 0.0:
                results.append(self.chunks[idx])
                
        # Fallback to the top index if all similarities are zero (e.g. out of vocabulary)
        if not results and len(self.chunks) > 0:
            for idx in top_indices[:top_k]:
                results.append(self.chunks[idx])
                
        return results


# Global singleton instance of the retriever
retriever = TFIDFRetriever()


def get_retriever() -> TFIDFRetriever:
    """Dependency accessor for the retriever singleton."""
    return retriever
