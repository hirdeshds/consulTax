"""Script to trigger reindexing of the QA corpus config file."""

from app.qa.retrieval import get_retriever

def main():
    print("Reindexing vetted schemes QA corpus...")
    retriever = get_retriever()
    retriever.load_and_index()
    print(f"Successfully reindexed {len(retriever.chunks)} chunks.")

if __name__ == "__main__":
    main()
