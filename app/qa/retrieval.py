"""Lightweight local QA corpus parser and pure Python TF-IDF retriever for consulTax."""

import re
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

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


def tokenize(text: str) -> List[str]:
    """Lowercase text and extract word tokens."""
    return re.findall(r'\b\w+\b', text.lower())


class TFIDFRetriever:
    """Pure Python TF-IDF retriever (no external dependencies like scikit-learn or numpy)."""

    def __init__(self, corpus_path: Path = CORPUS_PATH):
        self.corpus_path = corpus_path
        self.chunks: List[DocumentChunk] = []
        self.idf: Dict[str, float] = {}
        self.doc_vectors: List[Dict[str, float]] = []
        self.load_and_index()

    def load_and_index(self):
        """Loads and indexes the vetted schemes corpus using pure Python TF-IDF logic."""
        self.chunks = parse_markdown_corpus(self.corpus_path)
        self.idf.clear()
        self.doc_vectors.clear()
        
        if not self.chunks:
            return
            
        doc_count = len(self.chunks)
        df: Dict[str, int] = {}
        doc_tokens: List[List[str]] = []
        
        # 1. Tokenize each document chunk
        for chunk in self.chunks:
            title = chunk.source_title or ""
            section = chunk.source_section or ""
            snippet = chunk.snippet or ""
            # Weight title and section by repeating them
            combined = f"{title} {section} {title} {section} {snippet}"
            tokens = tokenize(combined)
            doc_tokens.append(tokens)
            
            # Document frequency counting
            unique_words = set(tokens)
            for word in unique_words:
                df[word] = df.get(word, 0) + 1
                
        # 2. Compute Inverse Document Frequency (IDF)
        for word, count in df.items():
            # Inverse document frequency with smoothing
            self.idf[word] = math.log(1.0 + (doc_count / count))
            
        # 3. Compute TF-IDF vectors for each document
        for tokens in doc_tokens:
            tf: Dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
                
            doc_vector: Dict[str, float] = {}
            for token, tf_val in tf.items():
                doc_vector[token] = tf_val * self.idf[token]
            self.doc_vectors.append(doc_vector)

    def retrieve(self, query: str, top_k: int = 3) -> List[DocumentChunk]:
        """
        Retrieve the top_k matching chunks for a given query.
        Calculates cosine similarity between query and document vectors.
        """
        if not query or not query.strip() or not self.chunks:
            return []
            
        query_tokens = tokenize(query)
        if not query_tokens:
            return self.chunks[:top_k]
            
        # Build query TF vector
        query_tf: Dict[str, int] = {}
        for token in query_tokens:
            query_tf[token] = query_tf.get(token, 0) + 1
            
        # Build query TF-IDF vector
        query_vector: Dict[str, float] = {}
        for token, tf_val in query_tf.items():
            if token in self.idf:
                query_vector[token] = tf_val * self.idf[token]
                
        query_norm = math.sqrt(sum(v * v for v in query_vector.values()))
        if query_norm == 0.0:
            # Query words are not in corpus vocabulary, fallback to top chunks
            return self.chunks[:top_k]
            
        similarities: List[float] = []
        for doc_vec in self.doc_vectors:
            # Dot product
            dot_product = 0.0
            for token, q_val in query_vector.items():
                if token in doc_vec:
                    dot_product += q_val * doc_vec[token]
                    
            # Document norm
            doc_norm = math.sqrt(sum(v * v for v in doc_vec.values()))
            
            if doc_norm == 0.0:
                similarity = 0.0
            else:
                similarity = dot_product / (query_norm * doc_norm)
                
            similarities.append(similarity)
            
        # Rank the chunks
        ranked = sorted(zip(similarities, self.chunks), key=lambda x: x[0], reverse=True)
        
        # Filter chunks with positive similarity
        results = [chunk for score, chunk in ranked if score > 0.0]
        
        # Fallback if no positive similarities
        if not results:
            results = [chunk for score, chunk in ranked[:top_k]]
            
        return results[:top_k]


# Global singleton instance of the retriever
retriever = TFIDFRetriever()


def get_retriever() -> TFIDFRetriever:
    """Dependency accessor for the retriever singleton."""
    return retriever
 