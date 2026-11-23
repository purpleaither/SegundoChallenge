"""Prepare the current RAG index once, rebuilding only after corpus/code changes."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Dados-RAG'))
from RAG.rag import DATASET_VERSION, VECTOR_DB_PATH, KnowledgeBase


def corpus_fingerprint() -> str:
    digest = hashlib.sha256(DATASET_VERSION.encode())
    folder = ROOT / 'Dados-RAG'
    paths = [folder / 'programas_sociais_legislacao_links_oficiais.csv']
    paths += [folder / 'RAG' / name for name in ['dataset.py', 'rag.py', 'fontes.py', 'ingestao.py']]
    paths += sorted((folder / 'RAG/fontes').glob('*.md'))
    for path in paths:
        digest.update(str(path.relative_to(folder)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def ensure_index() -> None:
    marker = VECTOR_DB_PATH / '.guia-corpus-sha256'
    fingerprint = corpus_fingerprint()
    kb = KnowledgeBase()
    try:
        ready = kb._collection.count() > 0 and marker.exists() and marker.read_text().strip() == fingerprint
    finally:
        kb.close()
    if ready:
        print('Índice RAG atual pronto.', flush=True)
        return
    subprocess.run([sys.executable, str(ROOT / 'Dados-RAG/RAG/ingestao.py')], cwd=ROOT, check=True)
    marker.write_text(fingerprint)


if __name__ == '__main__':
    ensure_index()
