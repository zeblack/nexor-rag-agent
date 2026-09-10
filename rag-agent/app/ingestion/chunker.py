from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter

_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=100)  # ~10% overlap


def chunk_text(text: str) -> list[str]:
    if not text.strip():
        return []
    nodes = _splitter.get_nodes_from_documents([Document(text=text)])
    return [node.get_content() for node in nodes]
