from enum import StrEnum

from pydantic import BaseModel


class ArtifactSource(StrEnum):
    ARXIV = "arxiv"
    PDF = "pdf"


class Artifact(BaseModel):
    source: ArtifactSource
    url: str
    title: str
    text: str
