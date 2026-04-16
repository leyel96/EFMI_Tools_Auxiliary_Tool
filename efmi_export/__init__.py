"""
EFMI (Endfield Model Importer) Export Module

Arknights: Endfield 게임 모드 내보내기 도구
EFMI-Tools의 Export Mod 기능을 독립 구현

핵심 기능:
- MeshData를 EFMI 형식 버퍼(.buf)로 변환
- mod.ini 자동 생성 (3DMigoto 호환)
- TBN(탄젠트/바이탄젠트/노멀) 10-10-10-2 인코딩
- Metadata.json 기반 LOD 및 VG 매핑 처리
"""

__version__ = "0.1.0"
__author__ = "yein"

from .exporter import EFMIExporter, ExportConfig
from .metadata import ExtractedObject, read_metadata
from .data_model import (
    Semantic,
    AbstractSemantic,
    BufferSemantic,
    BufferLayout,
    DXGIFormat,
    NumpyBuffer,
)

__all__ = [
    "EFMIExporter",
    "ExportConfig",
    "ExtractedObject",
    "read_metadata",
    "Semantic",
    "AbstractSemantic",
    "BufferSemantic",
    "BufferLayout",
    "DXGIFormat",
    "NumpyBuffer",
]
