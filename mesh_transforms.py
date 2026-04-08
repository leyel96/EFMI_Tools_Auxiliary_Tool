"""
메쉬별 사용자 정의 변환 설정
특정 메쉬에 대해 추가 위치/회전 변환을 적용

Blender 기준:
- 위치: 미터(m) 단위
- 회전: 도(degree) 단위
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class MeshTransform:
    """메쉬 변환 설정"""
    # 위치 이동 (Blender 기준, 미터)
    position_x: float = 0.0
    position_y: float = 0.0
    position_z: float = 0.0
    
    # 회전 (Blender 기준, 도)
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0


# 메쉬별 변환 설정
# 키: 메쉬 이름 또는 DC ID
MESH_TRANSFORMS = {
    # DC 23, 24, 32, 33, 39, 40, 95, 96, 103, 13, 14
    "Mesh_000023": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000024": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000032": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000033": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000039": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000040": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000095": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000096": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    "Mesh_000103": MeshTransform(
        position_x=0.001,
        position_y=-0.052,
        position_z=1.49,
        rotation_x=-95.3,
        rotation_y=1.5,
        rotation_z=-3.5
    ),
    # Mesh_000013, Mesh_000014
    # 주의: Blender에서 "Set Origin to Geometry" 적용 후 위치 이동
    # position_y: 1.485, position_z: 0.055는 Blender에서 수동 적용
    "Mesh_000013": MeshTransform(
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        rotation_x=-95.3,
        rotation_y=-4.0,
        rotation_z=-1.0
    ),
    "Mesh_000014": MeshTransform(
        position_x=0.0,
        position_y=0.0,
        position_z=0.0,
        rotation_x=-95.3,
        rotation_y=-4.0,
        rotation_z=-1.0
    ),
}


def get_mesh_transform(mesh_name: str, dc_id: Optional[int] = None) -> Optional[MeshTransform]:
    """
    메쉬에 대한 변환 설정 조회
    
    Args:
        mesh_name: 메쉬 이름 (예: "Mesh_000023")
        dc_id: DC ID (예: 23)
    
    Returns:
        MeshTransform 객체 또는 None
    """
    # 메쉬 이름으로 검색
    if mesh_name in MESH_TRANSFORMS:
        return MESH_TRANSFORMS[mesh_name]
    
    # DC ID로 검색
    if dc_id is not None:
        dc_key = f"Mesh_{dc_id:06d}"
        if dc_key in MESH_TRANSFORMS:
            return MESH_TRANSFORMS[dc_key]
    
    return None


def has_custom_transform(mesh_name: str, dc_id: Optional[int] = None) -> bool:
    """메쉬에 사용자 정의 변환이 있는지 확인"""
    return get_mesh_transform(mesh_name, dc_id) is not None
