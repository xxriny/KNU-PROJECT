"""
RAG Pipeline Schemas — PROJECT_RAG 테이블 정의서 준수
"""

from pydantic import BaseModel


class CodeChunk(BaseModel):
    chunk_id: str        # "{session_id}_{file_hash}_{func_name}"
    session_id: str
    version: str = "v1.0"
    feature_id: str = ""
    file_path: str
    func_name: str       # 함수/클래스명; 슬라이딩 윈도우 청크는 "FILE_CHUNK_{n}"
    content_text: str    # 실제 코드 본문 (최대 6000자)
    lang: str            # "python" | "javascript" | "unknown"


class RAGIngestOutput(BaseModel):
    session_id: str
    chunks_ingested: int
    status: str          # "success" | "partial" | "empty" | "skipped"


class RAGQueryResult(BaseModel):
    chunk_id: str
    file_path: str
    func_name: str
    content_text: str
    similarity: float
