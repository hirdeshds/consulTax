"""Unit tests for the QA corpus parser and TF-IDF retrieval system."""

import pytest
from pathlib import Path
from app.qa.retrieval import parse_markdown_corpus, TFIDFRetriever, DocumentChunk


def test_markdown_parser_chunks_correctly():
    """Verify that the markdown parser splits the vetted schemes corpus correctly."""
    # Locate real corpus file
    corpus_path = Path(__file__).resolve().parent.parent.parent / "config" / "qa_corpus" / "vetted_schemes.md"
    assert corpus_path.exists(), f"Vetted schemes file not found at {corpus_path}"

    chunks = parse_markdown_corpus(corpus_path)
    assert len(chunks) > 0, "No chunks parsed from the corpus file."
    
    # Check that chunks have expected fields and metadata
    for chunk in chunks:
        assert isinstance(chunk, DocumentChunk)
        assert chunk.source_title is not None
        assert chunk.snippet is not None
        assert len(chunk.snippet.strip()) > 0

    # Verify standard deduction is parsed
    std_ded_chunks = [c for c in chunks if "Standard Deduction" in c.source_title]
    assert len(std_ded_chunks) >= 2, "Standard deduction sections missing or not chunked correctly."


def test_retriever_finds_relevant_sections():
    """Test that the TFIDFRetriever retrieves relevant chunks based on user query keywords."""
    retriever = TFIDFRetriever()
    
    # Test query about 80C
    results_80c = retriever.retrieve("What is the maximum limit for 80C?", top_k=2)
    assert len(results_80c) > 0
    assert any("80C" in c.source_title for c in results_80c)
    assert any("1,50,000" in c.snippet for c in results_80c)

    # Test query about HRA
    results_hra = retriever.retrieve("how is HRA exemption calculated?", top_k=2)
    assert len(results_hra) > 0
    assert any("HRA" in c.source_title or "House Rent" in c.source_title for c in results_hra)

    # Test query about standard deduction
    results_std = retriever.retrieve("standard deduction limit for salaried in new regime", top_k=2)
    assert len(results_std) > 0
    assert any("Standard Deduction" in c.source_title for c in results_std)
    assert any("75,000" in c.snippet for c in results_std)


def test_retriever_edge_cases():
    """Verify retriever behavior with empty or out-of-vocabulary inputs."""
    retriever = TFIDFRetriever()
    
    # Empty query
    assert len(retriever.retrieve("", top_k=3)) == 0
    assert len(retriever.retrieve("   ", top_k=3)) == 0
    
    # Random query with no common tax terms
    results_rand = retriever.retrieve("xyzabcrandomterm", top_k=1)
    # Retriever defaults to top matching (or first chunks) if similarity is zero
    assert len(results_rand) > 0
