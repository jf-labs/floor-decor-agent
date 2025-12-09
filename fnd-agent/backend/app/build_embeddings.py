"""
Helper script to regenerate the product embedding index.

Usage:
    cd fnd-agent/backend
    python -m app.build_embeddings
"""

from .embedding_store import build_embedding_index


def main():
    build_embedding_index()


if __name__ == "__main__":
    main()

