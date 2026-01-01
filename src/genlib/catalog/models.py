from dataclasses import dataclass
from typing import Optional

@dataclass
class CatalogItem:
    id: int
    name: str
    type: str
    base_model: Optional[str]
    tags: list[str]
    download_url: Optional[str]
z