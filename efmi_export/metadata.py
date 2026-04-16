"""
Metadata.json 파서

EFMI-Tools에서 추출한 오브젝트 메타데이터를 파싱
- 컴포넌트 정보 (VB0 해시, 버텍스 수, 인덱스 수)
- LOD 데이터
- 버텍스 그룹 매핑
- 텍스처 해시
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class LODMesh:
    """LOD 메쉬 정보"""
    vb0_hash: str = ""
    vg_map: Dict[str, int] = field(default_factory=dict)  # VG ID 매핑


@dataclass
class ComponentData:
    """컴포넌트 데이터"""
    id: int = 0
    vb0_hash: str = ""
    vertex_count: int = 0
    index_count: int = 0
    vg_count: int = 0
    vg_map: Dict[int, str] = field(default_factory=dict)  # VG ID → 본 이름
    lods: List[LODMesh] = field(default_factory=list)
    textures: List[str] = field(default_factory=list)  # 텍스처 해시 목록


@dataclass
class ShapeKeysData:
    """쉐이프키 데이터"""
    offsets_hash: str = ""
    shapekey_offsets: List[float] = field(default_factory=list)


@dataclass
class ExtractedObject:
    """추출된 오브젝트 정보"""
    hash: str = ""
    name: str = ""
    vertex_count: int = 0
    index_count: int = 0
    components: List[ComponentData] = field(default_factory=list)
    shapekeys: ShapeKeysData = field(default_factory=ShapeKeysData)
    rotation: Optional[dict] = None  # {"x": 0.0, "y": 0.0, "z": 0.0}
    export_format: Optional[dict] = None  # 버퍼 포맷 정보


def parse_component_data(data: dict) -> ComponentData:
    """컴포넌트 데이터 파싱"""
    component = ComponentData()

    component.id = data.get("id", 0)
    component.vb0_hash = data.get("vb0_hash", "")
    component.vertex_count = data.get("vertex_count", 0)
    component.index_count = data.get("index_count", 0)
    component.vg_count = data.get("vg_count", 0)

    # VG 매핑
    vg_map_data = data.get("vg_map", {})
    for vg_id, bone_name in vg_map_data.items():
        component.vg_map[int(vg_id)] = bone_name

    # LOD 데이터
    lods_data = data.get("lods", [])
    for lod_data in lods_data:
        lod = LODMesh()
        lod.vb0_hash = lod_data.get("vb0_hash", "")
        lod.vg_map = {str(k): v for k, v in lod_data.get("vg_map", {}).items()}
        component.lods.append(lod)

    # 텍스처
    component.textures = data.get("textures", [])

    return component


def read_metadata(metadata_path: Path) -> ExtractedObject:
    """
    Metadata.json 파일 읽기

    Args:
        metadata_path: Metadata.json 파일 경로

    Returns:
        ExtractedObject 객체

    Raises:
        FileNotFoundError: 파일이 없을 경우
        ValueError: JSON 파싱 오류
    """
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata.json not found: {metadata_path}")

    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    obj = ExtractedObject()

    obj.hash = data.get("hash", "")
    obj.name = data.get("name", "")
    obj.vertex_count = data.get("vertex_count", 0)
    obj.index_count = data.get("index_count", 0)

    # 컴포넌트 데이터
    components_data = data.get("components", [])
    for comp_data in components_data:
        component = parse_component_data(comp_data)
        obj.components.append(component)

    # 쉐이프키 데이터
    shapekeys_data = data.get("shapekeys", {})
    obj.shapekeys.offsets_hash = shapekeys_data.get("offsets_hash", "")
    obj.shapekeys.shapekey_offsets = shapekeys_data.get("shapekey_offsets", [])

    # 회전 정보
    rotation_data = data.get("rotation", None)
    if rotation_data:
        obj.rotation = {
            "x": rotation_data.get("x", 0.0),
            "y": rotation_data.get("y", 0.0),
            "z": rotation_data.get("z", 0.0),
        }

    # 익스포트 포맷
    export_format_data = data.get("export_format", None)
    if export_format_data:
        obj.export_format = export_format_data

    return obj


def read_metadata_from_string(json_string: str) -> ExtractedObject:
    """
    JSON 문자열에서 메타데이터 읽기

    Args:
        json_string: JSON 문자열

    Returns:
        ExtractedObject 객체
    """
    data = json.loads(json_string)
    obj = ExtractedObject()

    obj.hash = data.get("hash", "")
    obj.name = data.get("name", "")
    obj.vertex_count = data.get("vertex_count", 0)
    obj.index_count = data.get("index_count", 0)

    components_data = data.get("components", [])
    for comp_data in components_data:
        component = parse_component_data(comp_data)
        obj.components.append(component)

    shapekeys_data = data.get("shapekeys", {})
    obj.shapekeys.offsets_hash = shapekeys_data.get("offsets_hash", "")
    obj.shapekeys.shapekey_offsets = shapekeys_data.get("shapekey_offsets", [])

    rotation_data = data.get("rotation", None)
    if rotation_data:
        obj.rotation = {
            "x": rotation_data.get("x", 0.0),
            "y": rotation_data.get("y", 0.0),
            "z": rotation_data.get("z", 0.0),
        }

    export_format_data = data.get("export_format", None)
    if export_format_data:
        obj.export_format = export_format_data

    return obj
