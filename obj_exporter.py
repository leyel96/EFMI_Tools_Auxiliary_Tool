"""
OBJ 파일 내보내기
MeshData를 표준 OBJ 형식으로 변환

좌표계 옵션:
- 'reference': Reference OBJ (chen.obj)와 동일한 Z-up 좌표계
- 'blender': Blender 호환 Y-up 좌표계
- 'original': 원본 DirectX 좌표계 (변환 없음)
"""

import os
import math
from mesh_parser import MeshData
from mesh_transforms import get_mesh_transform, has_custom_transform


def transform_vertex_reference(vertex):
    """
    추출 메쉬를 Reference OBJ (chen.obj) 좌표계로 변환
    현재 Y-up → Z-up 변환: (x, y, z) → (x, z, -y)
    좌우 반전 적용: x → -x
    """
    px, py, pz = vertex.position
    nx, ny, nz = vertex.normal
    tx, ty = vertex.texcoord

    # 위치: Y-up → Z-up + 좌우 반전
    new_position = (-px, pz, -py)
    # 법선: 동일하게 변환 + 좌우 반전
    new_normal = (-nx, nz, -ny)
    # UV: V 좌표 반전
    new_texcoord = (tx, 1.0 - ty)

    new_vertex = type(vertex)(
        position=new_position,
        normal=new_normal,
        texcoord=new_texcoord,
        texcoord1=vertex.texcoord1,
        blendweights=vertex.blendweights,
        blendindices=vertex.blendindices,
        tangent=vertex.tangent
    )
    return new_vertex


def transform_vertex_blender(vertex):
    """
    DirectX 좌표계를 Blender 좌표계로 변환
    X축 180° 회전: Y→-Y, Z→-Z
    좌우 반전 적용: x → -x
    """
    px, py, pz = vertex.position
    nx, ny, nz = vertex.normal
    tx, ty = vertex.texcoord

    new_position = (-px, -py, -pz)
    new_normal = (-nx, -ny, -nz)
    new_texcoord = (tx, 1.0 - ty)

    new_vertex = type(vertex)(
        position=new_position,
        normal=new_normal,
        texcoord=new_texcoord,
        texcoord1=vertex.texcoord1,
        blendweights=vertex.blendweights,
        blendindices=vertex.blendindices,
        tangent=vertex.tangent
    )
    return new_vertex


def apply_custom_transform(vertex, transform):
    """
    메쉬에 사용자 정의 위치/회전 변환 적용
    
    Blender 기준 좌표계에서 적용:
    - 위치: 미터(m)
    - 회전: 도(degree) - XYZ 오일러 각
    """
    px, py, pz = vertex.position
    nx, ny, nz = vertex.normal
    tx, ty = vertex.texcoord
    
    # 회전을 라디안으로 변환
    rx = math.radians(transform.rotation_x)
    ry = math.radians(transform.rotation_y)
    rz = math.radians(transform.rotation_z)
    
    # 회전 행렬 적용 (XYZ 오일러 각)
    # X축 회전
    cos_x, sin_x = math.cos(rx), math.sin(rx)
    py, pz = py * cos_x - pz * sin_x, py * sin_x + pz * cos_x
    ny, nz = ny * cos_x - nz * sin_x, ny * sin_x + nz * cos_x
    
    # Y축 회전
    cos_y, sin_y = math.cos(ry), math.sin(ry)
    px, pz = px * cos_y + pz * sin_y, -px * sin_y + pz * cos_y
    nx, nz = nx * cos_y + nz * sin_y, -nx * sin_y + nz * cos_y
    
    # Z축 회전
    cos_z, sin_z = math.cos(rz), math.sin(rz)
    px, py = px * cos_z - py * sin_z, px * sin_z + py * cos_z
    nx, ny = nx * cos_z - ny * sin_z, nx * sin_z + ny * cos_z
    
    # 위치 이동
    px += transform.position_x
    py += transform.position_y
    pz += transform.position_z
    
    new_vertex = type(vertex)(
        position=(px, py, pz),
        normal=(nx, ny, nz),
        texcoord=(tx, ty),
        texcoord1=vertex.texcoord1,
        blendweights=vertex.blendweights,
        blendindices=vertex.blendindices,
        tangent=vertex.tangent
    )
    return new_vertex


def transform_vertices_with_custom(mesh, coord_system='reference'):
    """
    좌표계 변환 + 사용자 정의 변환을 순차적으로 적용
    
    Args:
        mesh: MeshData 객체
        coord_system: 좌표계 ('reference', 'blender', 'original')
    
    Returns:
        변환된 버텍스 리스트
    """
    vertices = mesh.vertices
    
    # 1. 좌표계 변환
    if coord_system == 'reference':
        vertices = [transform_vertex_reference(v) for v in vertices]
    elif coord_system == 'blender':
        vertices = [transform_vertex_blender(v) for v in vertices]
    
    # 2. 사용자 정의 변환 적용 (해당 메쉬만)
    transform = get_mesh_transform(mesh.name, mesh.draw_call_id)
    if transform:
        vertices = [apply_custom_transform(v, transform) for v in vertices]
    
    return vertices


def export_mesh_to_obj(mesh: MeshData, output_path: str, include_normals: bool = True, include_uv: bool = True, coord_system: str = 'reference') -> str:
    """
    MeshData를 OBJ 파일로 내보내기

    Args:
        mesh: 내보낼 메쉬 데이터
        output_path: 출력 OBJ 파일 경로
        include_normals: 법선 포함 여부
        include_uv: UV 좌표 포함 여부
        coord_system: 좌표계 ('reference', 'blender', 'original')

    Returns:
        출력 파일 경로
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    # 좌표계 변환 + 사용자 정의 변환 적용
    vertices = transform_vertices_with_custom(mesh, coord_system)
    
    # 좌표계 주석
    if coord_system == 'reference':
        coord_comment = "# Coords: Reference OBJ (Z-up, matching chen.obj)"
    elif coord_system == 'blender':
        coord_comment = "# Coords: Blender (Y-up, X-axis 180° rotation)"
    else:
        coord_comment = "# Coords: Original DirectX (Y-up, left-handed)"
    
    # 사용자 정의 변환 적용 여부 확인
    has_transform = has_custom_transform(mesh.name, mesh.draw_call_id)
    if has_transform:
        coord_comment += " + Custom Transform"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"# Mesh: {mesh.name}\n")
        f.write(f"# Draw Call: {mesh.draw_call_id:06d}\n")
        f.write(f"# Vertices: {len(vertices)}\n")
        f.write(f"# Indices: {len(mesh.indices)}\n")
        f.write(f"# VS Hash: {mesh.vertex_shader_hash}\n")
        f.write(f"# PS Hash: {mesh.pixel_shader_hash}\n")
        f.write(f"{coord_comment}\n")
        f.write("\n")

        # 버텍스 위치
        for vertex in vertices:
            f.write(f"v {vertex.position[0]:.6f} {vertex.position[1]:.6f} {vertex.position[2]:.6f}\n")

        # 법선
        if include_normals:
            for vertex in vertices:
                f.write(f"vn {vertex.normal[0]:.6f} {vertex.normal[1]:.6f} {vertex.normal[2]:.6f}\n")

        # UV 좌표
        if include_uv:
            for vertex in vertices:
                f.write(f"vt {vertex.texcoord[0]:.6f} {vertex.texcoord[1]:.6f}\n")

        f.write("\n")

        # 페이스 (인덱스 기반)
        num_faces = len(mesh.indices) // 3
        for i in range(num_faces):
            idx0 = mesh.indices[i * 3] + 1
            idx1 = mesh.indices[i * 3 + 1] + 1
            idx2 = mesh.indices[i * 3 + 2] + 1

            # 좌표계에 따라 인덱스 순서 조정
            if coord_system == 'blender':
                idx1, idx2 = idx2, idx1  # CW → CCW

            if include_normals and include_uv:
                f.write(f"f {idx0}/{idx0}/{idx0} {idx1}/{idx1}/{idx1} {idx2}/{idx2}/{idx2}\n")
            elif include_normals:
                f.write(f"f {idx0}//{idx0} {idx1}//{idx1} {idx2}//{idx2}\n")
            elif include_uv:
                f.write(f"f {idx0}/{idx0} {idx1}/{idx1} {idx2}/{idx2}\n")
            else:
                f.write(f"f {idx0} {idx1} {idx2}\n")

    return output_path


def export_all_meshes_to_obj(meshes: dict[int, MeshData], output_dir: str, coord_system: str = 'reference') -> list[str]:
    """
    모든 메쉬를 개별 OBJ 파일로 내보내기

    Args:
        meshes: 메쉬 데이터 딕셔너리
        output_dir: 출력 디렉토리
        coord_system: 좌표계 ('reference', 'blender', 'original')

    Returns:
        생성된 파일 목록
    """
    os.makedirs(output_dir, exist_ok=True)
    files = []

    for dc_id, mesh in meshes.items():
        filename = f"{mesh.name}.obj"
        filepath = os.path.join(output_dir, filename)
        export_mesh_to_obj(mesh, filepath, coord_system=coord_system)
        files.append(filepath)
        print(f"Exported: {filepath} ({len(mesh.vertices)} vertices, {len(mesh.indices)//3} faces)")

    return files


def export_meshes_combined_obj(meshes: dict[int, MeshData], output_path: str, coord_system: str = 'reference') -> str:
    """
    모든 메쉬를 하나의 OBJ 파일로 결합

    Args:
        meshes: 메쉬 데이터 딕셔너리
        output_path: 출력 OBJ 파일 경로
        coord_system: 좌표계 ('reference', 'blender', 'original')

    Returns:
        출력 파일 경로
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

    if coord_system == 'reference':
        coord_comment = "# Coords: Reference OBJ (Z-up, matching chen.obj)"
    elif coord_system == 'blender':
        coord_comment = "# Coords: Blender (Y-up, X-axis 180° rotation)"
    else:
        coord_comment = "# Coords: Original DirectX (Y-up, left-handed)"

    vertex_offset = 0
    total_vertices = 0
    total_faces = 0

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Combined Mesh Export\n")
        f.write(f"# Total Meshes: {len(meshes)}\n")
        f.write(f"{coord_comment}\n")
        f.write("\n")

        # 모든 버텍스 쓰기 (좌표계 + 사용자 정의 변환 적용)
        for dc_id, mesh in meshes.items():
            f.write(f"# Mesh: {mesh.name} (DC {dc_id:06d})")
            
            # 사용자 정의 변환 적용 여부 확인
            has_transform = has_custom_transform(mesh.name, dc_id)
            if has_transform:
                f.write(" [Custom Transform Applied]")
            f.write("\n")
            
            # 변환 적용
            vertices = transform_vertices_with_custom(mesh, coord_system)
            
            for vertex in vertices:
                f.write(f"v {vertex.position[0]:.6f} {vertex.position[1]:.6f} {vertex.position[2]:.6f}\n")
                f.write(f"vn {vertex.normal[0]:.6f} {vertex.normal[1]:.6f} {vertex.normal[2]:.6f}\n")
                f.write(f"vt {vertex.texcoord[0]:.6f} {vertex.texcoord[1]:.6f}\n")
            f.write("\n")

        # 모든 페이스 쓰기
        vertex_offset = 0
        for dc_id, mesh in meshes.items():
            f.write(f"# Mesh: {mesh.name}\n")
            num_faces = len(mesh.indices) // 3
            for i in range(num_faces):
                idx0 = mesh.indices[i * 3] + 1 + vertex_offset
                idx1 = mesh.indices[i * 3 + 1] + 1 + vertex_offset
                idx2 = mesh.indices[i * 3 + 2] + 1 + vertex_offset

                if coord_system == 'blender':
                    idx1, idx2 = idx2, idx1

                f.write(f"f {idx0}/{idx0}/{idx0} {idx1}/{idx1}/{idx1} {idx2}/{idx2}/{idx2}\n")
            vertex_offset += len(mesh.vertices)
            total_faces += num_faces

        total_vertices = sum(len(m.vertices) for m in meshes.values())

    print(f"Exported combined: {output_path} ({total_vertices} vertices, {total_faces} faces)")
    return output_path
