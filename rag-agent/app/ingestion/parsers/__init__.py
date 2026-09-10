from dataclasses import dataclass


@dataclass
class ParsedDocument:
    text: str
    parser_used: str
