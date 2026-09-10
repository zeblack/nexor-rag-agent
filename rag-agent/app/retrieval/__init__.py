from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: str
    source_path: str
    chunk_index: int
    content: str
    score: float
