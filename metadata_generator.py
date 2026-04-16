"""
Metadata.json 생성 모듈

FrameAnalysis 파싱 결과(MeshData)에서 EFMI 호환 Metadata.json 생성
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from mesh_parser import MeshData


def extract_texture_hashes(mesh: MeshData) -> List[str]:
    """
    메쉬에서 사용된 텍스처 해시 추출
    파일명에서 패턴으로 추출
    """
    hashes = set()
    
    # VS/PS 해시에서 텍스처 슬롯 해시 추출 시도
    if mesh.pixel_shader_hash:
        hashes.add(mesh.pixel_shader_hash[:8])
    
    # VB 해시들
    for key, val in mesh.vb_hashes.items():
        if val:
            hashes.add(val[:8])
    
    return list(hashes)


def extract_vg_mapping(mesh: MeshData) -> Dict[int, str]:
    """
    버텍스 그룹 매핑 추출
    현재는 인덱스 기반으로 더미 매핑 생성
    실제 본 이름은 .fmt 파일 파싱 시 추출 가능
    """
    vg_map = {}
    
    if mesh.vertices:
        # 사용된 VG 인덱스 수집
        used_vgs = set()
        for vertex in mesh.vertices:
            for i, weight in enumerate(vertex.blendweights):
                if weight > 0:
                    vg_idx = vertex.blendindices[i]
                    used_vgs.add(vg_idx)
        
        # 더미 본 이름 매핑
        for vg_idx in sorted(used_vgs):
            vg_map[vg_idx] = f"Bone_{vg_idx:03d}"
    
    return vg_map


def generate_metadata(
    meshes: Dict[int, MeshData],
    output_path: Path,
    object_name: str = "ExtractedObject"
) -> Path:
    """
    Metadata.json 생성
    
    Args:
        meshes: DC ID → MeshData 딕셔너리
        output_path: 출력 폴더 경로
        object_name: 오브젝트 이름
        
    Returns:
        생성된 Metadata.json 경로
    """
    if not meshes:
        raise ValueError("No meshes to generate metadata from")
    
    # 전체 통계
    total_vertices = sum(len(m.vertices) for m in meshes.values())
    total_indices = sum(len(m.indices) for m in meshes.values())
    
    # 대표 메쉬 (가장 큰 메쉬)
    primary_mesh = max(meshes.values(), key=lambda m: len(m.vertices))
    
    # 오브젝트 해시 (VB0 해시 사용)
    object_hash = primary_mesh.vb0_hash or primary_mesh.vertex_shader_hash or "unknown"
    
    # 컴포넌트 생성
    components = []
    for dc_id, mesh in sorted(meshes.items()):
        vg_map = extract_vg_mapping(mesh)
        texture_hashes = extract_texture_hashes(mesh)
        
        component = {
            "id": len(components),
            "vb0_hash": mesh.vb0_hash or mesh.vb_hashes.get("vb0", "")[:8] or f"{dc_id:08x}",
            "vertex_count": len(mesh.vertices),
            "index_count": len(mesh.indices),
            "vg_count": len(vg_map),
            "vg_map": {str(k): v for k, v in vg_map.items()},
            "lods": [],  # LOD는 별도 덤프에서 추출
            "textures": texture_hashes
        }
        components.append(component)
    
    # Metadata 구성
    metadata = {
        "hash": object_hash[:16],
        "name": object_name,
        "vertex_count": total_vertices,
        "index_count": total_indices,
        "rotation": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0
        },
        "components": components,
        "shapekeys": {
            "offsets_hash": "",
            "shapekey_offsets": []
        },
        "export_format": {
            "Position": {
                "semantics": [{"name": "POSITION", "format": "R32G32B32_FLOAT"}]
            },
            "TexCoord": {
                "semantics": [{"name": "TEXCOORD", "format": "R32G32_FLOAT"}]
            },
            "Blend": {
                "semantics": [
                    {"name": "BLENDWEIGHTS", "format": "R16_UNORM"},
                    {"name": "BLENDINDICES", "format": "R8_UINT"}
                ]
            }
        }
    }
    
    # 파일 저장
    output_path.mkdir(parents=True, exist_ok=True)
    metadata_path = output_path / "Metadata.json"
    
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"Metadata.json generated: {metadata_path}")
    print(f"  Object: {object_name}")
    print(f"  Components: {len(components)}")
    print(f"  Total vertices: {total_vertices}")
    print(f"  Total indices: {total_indices}")
    
    return metadata_path


def generate_metadata_from_directory(
    input_dir: str,
    output_dir: str,
    object_name: str = "ExtractedObject"
) -> Path:
    """
    FrameAnalysis 디렉토리에서 직접 Metadata.json 생성
    
    Args:
        input_dir: FrameAnalysis 폴더 경로
        output_dir: 출력 폴더 경로
        object_name: 오브젝트 이름
        
    Returns:
        생성된 Metadata.json 경로
    """
    from mesh_parser import parse_frame_analysis_directory
    
    print(f"Parsing FrameAnalysis directory: {input_dir}")
    meshes = parse_frame_analysis_directory(input_dir)
    
    if not meshes:
        raise ValueError(f"No meshes found in {input_dir}")
    
    print(f"Found {len(meshes)} meshes")
    
    return generate_metadata(meshes, Path(output_dir), object_name)
