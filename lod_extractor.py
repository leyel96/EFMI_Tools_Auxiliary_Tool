"""
LOD(Level of Detail) 매칭 모듈

FrameAnalysis 덤프에서 LOD 메쉬를 찾아 Metadata.json에 저장
EFMI-Tools의 lod_matcher.py를 완전히 통합한 버전:
- 2단계 Prefilter 시스템 (빠른 필터링 → 정밀 매칭)
- 해시 기반 빠른 매칭
- Voxel/Point Cloud 기반 기하학적 유사도 계산
- Chamfer Distance 기반 VG 매칭
"""

# 새로운 고급 모듈 import
from lod_matcher_advanced import (
    AdvancedLODMatcher,
    extract_lods_advanced,
    LODMatchResult,
    GeometryMatcher,
    VertexGroupsMatcher,
)


# 하위 호환성을 위한 alias
LODExtractor = AdvancedLODMatcher
extract_lods = extract_lods_advanced


__all__ = [
    'AdvancedLODMatcher',
    'LODExtractor',
    'extract_lods_advanced',
    'extract_lods',
    'LODMatchResult',
    'GeometryMatcher',
    'VertexGroupsMatcher',
]
