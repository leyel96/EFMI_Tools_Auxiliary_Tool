"""
FrameAnalysis 데이터 파서 v3 (NumPy 기반 고속 처리)
EndFieldModeling 프로젝트의 추출 방식을 완전히 적용

핵심 변경사항:
1. InputSlot 기반 다중 VB 자동 병합
2. TXT 메타데이터 기반 동적 포맷 감지
3. NumPy 기반 고속 벌크 처리 (EndFieldModeling 방식)
4. R32_FLOAT NORMAL 자동 스킵 + 면 법선 계산
"""

import os
import re
import struct
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ============================================================
# DXGI Format 매핑
# ============================================================

DXGI_FORMAT_MAP = {
    'R32G32B32_FLOAT':      ('float3', 12, '<3f'),
    'R32G32_FLOAT':         ('float2', 8,  '<2f'),
    'R32_FLOAT':            ('float1', 4,  '<f'),
    'R32G32B32A32_FLOAT':   ('float4', 16, '<4f'),
    'R16G16B16A16_FLOAT':   ('float4', 8,  '<4e'),
    'R16G16_FLOAT':         ('float2', 4,  '<2e'),
    'R8G8B8A8_UNORM':       ('ubyte4n', 4, '<4B'),
    'R8G8B8A8_UINT':        ('ubyte4', 4,  '<4B'),
    'R8G8B8A8_SNORM':       ('byte4n', 4,  '<4b'),
    'R8G8_UNORM':           ('ubyte2n', 2, '<2B'),
    'R8_UNORM':             ('ubyte1n', 1, '<B'),
    'R16_UINT':             ('uint16', 2,  '<H'),
    'R32_UINT':             ('uint32', 4,  '<I'),
    'R16G16B16A16_UNORM':   ('ushort4n', 8, '<4H'),
    'R16G16_UNORM':         ('ushort2n', 4, '<2H'),
    'DXGI_FORMAT_R16_UINT': ('uint16', 2,  '<H'),
}


def parse_dxgi_format(fmt_str: str) -> tuple[str, int, str]:
    """DXGI Format 문자열을 (semantic_type, byte_size, struct_format)로 변환"""
    fmt_str = fmt_str.strip().upper()
    if fmt_str in DXGI_FORMAT_MAP:
        return DXGI_FORMAT_MAP[fmt_str]
    return ('float3', 12, '<3f')


# ============================================================
# 데이터 구조체
# ============================================================

@dataclass
class VertexElement:
    """버텍스 시맨틱 요소"""
    semantic_name: str
    semantic_index: int
    format_type: str
    byte_size: int
    struct_fmt: str
    input_slot: int
    byte_offset: int


@dataclass
class VertexBufferInfo:
    """버텍스 버퍼 메타데이터"""
    byte_offset: int = 0
    stride: int = 0
    vertex_count: int = 0
    topology: str = "trianglelist"
    elements: list[VertexElement] = field(default_factory=list)


@dataclass
class IndexBufferInfo:
    """인덱스 버퍼 메타데이터"""
    byte_offset: int = 0
    index_count: int = 0
    topology: str = "trianglelist"
    format_str: str = "uint16"


@dataclass
class Vertex:
    """버텍스 데이터 (뷰어 호환용)"""
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    normal: tuple[float, float, float] = (0.0, 0.0, 0.0)
    texcoord: tuple[float, float] = (0.0, 0.0)
    texcoord1: tuple[float, float] = (0.0, 0.0)
    blendweights: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    blendindices: tuple[int, int, int, int] = (0, 0, 0, 0)
    tangent: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


@dataclass
class MeshData:
    """완성된 메쉬 데이터"""
    draw_call_id: int
    vertices: list[Vertex] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)
    vertex_shader_hash: str = ""
    pixel_shader_hash: str = ""
    ib_hash: str = ""
    vb0_hash: str = ""
    vb0_parent_hash: str = ""  # VB0 parent 해시 (좌표계 그룹 판별용)
    vb_hashes: dict[str, str] = field(default_factory=dict)
    name: str = ""


# ============================================================
# TXT 메타데이터 파싱
# ============================================================

def parse_vertex_buffer_txt(txt_path: str) -> VertexBufferInfo:
    """TXT 파일에서 버텍스 버퍼 메타데이터 파싱 (EndFieldModeling 방식)"""
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    info = VertexBufferInfo()

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('byte offset:'):
            info.byte_offset = int(line.split(':')[1].strip())
        elif line.startswith('stride:'):
            info.stride = int(line.split(':')[1].strip())
        elif line.startswith('vertex count:'):
            info.vertex_count = int(line.split(':')[1].strip())
        elif line.startswith('topology:'):
            info.topology = line.split(':')[1].strip()

    # Vertex Element 파싱
    elements = []
    seen_semantics = set()

    lines = content.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('element['):
            semantic = None
            semantic_index = 0
            fmt_type = None
            byte_size = 0
            struct_fmt = None
            slot = 0
            offset = 0

            i += 1
            while i < len(lines):
                sub_line = lines[i].strip()
                if sub_line.startswith('element[') or sub_line.startswith('byte offset:') or sub_line.startswith('stride:'):
                    break

                if sub_line.startswith('SemanticName:'):
                    semantic = sub_line.split(':', 1)[1].strip()
                elif sub_line.startswith('SemanticIndex:'):
                    try:
                        semantic_index = int(sub_line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                elif sub_line.startswith('Format:'):
                    raw_fmt = sub_line.split(':', 1)[1].strip()
                    fmt_type, byte_size, struct_fmt = parse_dxgi_format(raw_fmt)
                elif sub_line.startswith('InputSlot:'):
                    try:
                        slot = int(sub_line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                elif sub_line.startswith('AlignedByteOffset:'):
                    try:
                        offset = int(sub_line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                i += 1

            if semantic and fmt_type:
                semantic_key = f"{semantic}{semantic_index}"
                if semantic_key not in seen_semantics:
                    # R32_FLOAT NORMAL은 유효한 법선이 아님
                    if semantic == 'NORMAL' and fmt_type == 'float1':
                        pass
                    # TEXCOORD4 이상은 tangent space 등 부가 데이터
                    elif semantic == 'TEXCOORD' and semantic_index >= 4:
                        pass
                    else:
                        elements.append(VertexElement(
                            semantic_name=semantic,
                            semantic_index=semantic_index,
                            format_type=fmt_type,
                            byte_size=byte_size,
                            struct_fmt=struct_fmt,
                            input_slot=slot,
                            byte_offset=offset
                        ))
                        seen_semantics.add(semantic_key)
        else:
            i += 1

    info.elements = elements
    return info


def parse_index_buffer_txt(txt_path: str) -> IndexBufferInfo:
    """TXT 파일에서 인덱스 버퍼 메타데이터 파싱"""
    with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    info = IndexBufferInfo()

    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('byte offset:'):
            info.byte_offset = int(line.split(':')[1].strip())
        elif line.startswith('index count:'):
            info.index_count = int(line.split(':')[1].strip())
        elif line.startswith('topology:'):
            info.topology = line.split(':')[1].strip()
        elif line.startswith('format:'):
            fmt = line.split(':', 1)[1].strip().upper()
            if 'R16' in fmt:
                info.format_str = 'uint16'
            elif 'R32' in fmt:
                info.format_str = 'uint32'
            else:
                info.format_str = 'uint16'

    return info


# ============================================================
# NumPy 기반 데이터 추출 (EndFieldModeling 방식)
# ============================================================

def extract_vertices_numpy(buf_path: str, txt_path: str, target_slot: int = 0) -> dict[str, np.ndarray]:
    """
    NumPy를 사용한 고속 버텍스 데이터 추출
    EndFieldModeling의 extract_vertices() 방식

    deduped/split .buf 파일은 byte_offset이 원본 기준이므로,
    파일 크기가 offset보다 작으면 0부터 읽습니다.
    """
    info = parse_vertex_buffer_txt(txt_path)

    file_size = os.path.getsize(buf_path)
    expected_size = info.stride * info.vertex_count

    with open(buf_path, 'rb') as f:
        # byte_offset이 파일 크기보다 크면 0부터 읽기 (분할된 파일)
        if info.byte_offset + expected_size <= file_size:
            f.seek(info.byte_offset)
            data = f.read(expected_size)
        else:
            # 파일 전체 읽기 (분할된 deduped 파일)
            f.seek(0)
            data = f.read(file_size)

    result = {}
    num_verts = info.vertex_count
    stride = info.stride

    if num_verts == 0 or stride == 0:
        return result

    # 실제 데이터 크기로 버텍스 수 재계산
    actual_verts = len(data) // stride
    if actual_verts < num_verts:
        num_verts = actual_verts

    if num_verts <= 0:
        return result

    # target_slot에 해당하는 요소만 처리
    slot_elements = [e for e in info.elements if e.input_slot == target_slot]

    for elem in slot_elements:
        semantic = elem.semantic_name
        fmt = elem.format_type
        offset = elem.byte_offset  # 파일 내 상대 오프셋 사용

        try:
            if fmt == 'float3':
                arr = np.zeros((num_verts, 3), dtype=np.float32)
                for i in range(num_verts):
                    arr[i] = struct.unpack_from('<3f', data, offset + i * stride)
                result[semantic] = arr

            elif fmt == 'float2':
                arr = np.zeros((num_verts, 2), dtype=np.float32)
                for i in range(num_verts):
                    arr[i] = struct.unpack_from('<2f', data, offset + i * stride)
                result[semantic] = arr

            elif fmt == 'float4':
                arr = np.zeros((num_verts, 4), dtype=np.float32)
                for i in range(num_verts):
                    arr[i] = struct.unpack_from('<4f', data, offset + i * stride)
                result[semantic] = arr

            elif fmt == 'float1':
                arr = np.zeros((num_verts, 1), dtype=np.float32)
                for i in range(num_verts):
                    arr[i, 0] = struct.unpack_from('<f', data, offset + i * stride)[0]
                result[semantic] = arr

            elif fmt == 'ubyte4n':
                arr = np.zeros((num_verts, 4), dtype=np.float32)
                for i in range(num_verts):
                    r, g, b, a = struct.unpack_from('<4B', data, offset + i * stride)
                    arr[i] = [r/255.0, g/255.0, b/255.0, a/255.0]
                result[semantic] = arr

            elif fmt == 'ubyte4':
                arr = np.zeros((num_verts, 4), dtype=np.float32)
                for i in range(num_verts):
                    arr[i] = struct.unpack_from('<4B', data, offset + i * stride)
                result[semantic] = arr

        except Exception as e:
            pass  # silently skip elements that fail

    return result


def extract_indices_numpy(buf_path: str, txt_path: str) -> np.ndarray:
    """NumPy를 사용한 고속 인덱스 데이터 추출"""
    info = parse_index_buffer_txt(txt_path)

    file_size = os.path.getsize(buf_path)
    byte_size = 2 if info.format_str == 'uint16' else 4
    expected_size = byte_size * info.index_count

    with open(buf_path, 'rb') as f:
        if info.byte_offset + expected_size <= file_size:
            f.seek(info.byte_offset)
            data = f.read(expected_size)
        else:
            f.seek(0)
            data = f.read(file_size)

    dtype = np.uint16 if info.format_str == 'uint16' else np.uint32
    count = len(data) // byte_size
    return np.frombuffer(data, dtype=dtype, count=count)


# ============================================================
# NumPy 기반 법선 계산
# ============================================================

def compute_normals_numpy(positions: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """
    NumPy를 사용한 고속 면 법선 계산
    EndFieldModeling 방식

    Args:
        positions: (N, 3) POSITION ndarray
        indices: (M,) index array

    Returns:
        (N, 3) normal ndarray
    """
    num_verts = len(positions)
    if num_verts == 0:
        return np.zeros((0, 3), dtype=np.float32)

    normal_accum = np.zeros((num_verts, 3), dtype=np.float32)

    num_faces = len(indices) // 3
    for i in range(num_faces):
        i0 = int(indices[i * 3])
        i1 = int(indices[i * 3 + 1])
        i2 = int(indices[i * 3 + 2])

        if i0 >= num_verts or i1 >= num_verts or i2 >= num_verts:
            continue

        p0 = positions[i0]
        p1 = positions[i1]
        p2 = positions[i2]

        # 두 엣지 벡터
        e1 = p1 - p0
        e2 = p2 - p0

        # 외적 (면 법선)
        face_normal = np.cross(e1, e2)

        # 해당 버텍스에 누적
        normal_accum[i0] += face_normal
        normal_accum[i1] += face_normal
        normal_accum[i2] += face_normal

    # 정규화
    lengths = np.linalg.norm(normal_accum, axis=1, keepdims=True)
    lengths = np.maximum(lengths, 1e-8)
    normals = normal_accum / lengths

    return normals


# ============================================================
# NumPy → Vertex 리스트 변환
# ============================================================

def numpy_to_vertices(
    positions: np.ndarray,
    normals: np.ndarray,
    texcoords: np.ndarray,
) -> list[Vertex]:
    """NumPy 배열을 Vertex 리스트로 변환 (뷰어 호환용)"""
    num_verts = len(positions)
    vertices = []

    for i in range(num_verts):
        v = Vertex()
        v.position = (float(positions[i, 0]), float(positions[i, 1]), float(positions[i, 2]))

        if normals is not None and len(normals) > i:
            v.normal = (float(normals[i, 0]), float(normals[i, 1]), float(normals[i, 2]))

        if texcoords is not None and len(texcoords) > i:
            v.texcoord = (float(texcoords[i, 0]), float(texcoords[i, 1]))

        vertices.append(v)

    return vertices


# ============================================================
# 메인 파싱 함수
# ============================================================

def parse_frame_analysis_directory(directory: str) -> dict[int, MeshData]:
    """
    FrameAnalysis 디렉토리에서 모든 메쉬 데이터 파싱

    EndFieldModeling 방식:
    1. 모든 VB 슬롯(InputSlot) 자동 감지
    2. 각 슬롯에서 해당 시맨틱 데이터 추출 (NumPy 고속 처리)
    3. POSITION + TEXCOORD + 기타 데이터 자동 병합
    4. 법선은 NumPy 기반 자동 계산
    """
    meshes = {}
    files = os.listdir(directory)

    # IB와 VB 파일을 드로우 콜별로 그룹화
    ib_files = {}
    vb_files = {}

    for filename in files:
        if not filename.endswith('.txt'):
            continue

        match = re.match(r'(\d+)-', filename)
        if not match:
            continue

        dc_id = int(match.group(1))

        if '-ib=' in filename:
            ib_files[dc_id] = filename.replace('.txt', '.buf')
        elif '-vb' in filename:
            vb_match = re.search(r'-vb(\d+)=', filename)
            if vb_match:
                slot = vb_match.group(1)
                if dc_id not in vb_files:
                    vb_files[dc_id] = {}
                vb_files[dc_id][slot] = filename.replace('.txt', '.buf')

    # 각 드로우 콜 처리
    for dc_id in ib_files:
        mesh = MeshData(
            draw_call_id=dc_id,
            name=f"Mesh_{dc_id:06d}"
        )

        # 셰이더 해시 추출
        ib_filename = ib_files[dc_id]
        vs_match = re.search(r'-vs=([a-f0-9]+)', ib_filename)
        ps_match = re.search(r'-ps=([a-f0-9]+)', ib_filename)
        ib_hash_match = re.search(r'-ib=([a-f0-9]+)', ib_filename)

        if vs_match:
            mesh.vertex_shader_hash = vs_match.group(1)
        if ps_match:
            mesh.pixel_shader_hash = ps_match.group(1)
        if ib_hash_match:
            mesh.ib_hash = ib_hash_match.group(1)

        # 인덱스 버퍼 파싱 (NumPy)
        ib_buf = os.path.join(directory, ib_files[dc_id])
        ib_txt = ib_buf.replace('.buf', '.txt')
        if os.path.exists(ib_buf) and os.path.exists(ib_txt):
            try:
                indices_np = extract_indices_numpy(ib_buf, ib_txt)
                mesh.indices = indices_np.tolist()
            except Exception as e:
                print(f"Error parsing IB for DC {dc_id}: {e}")
                continue

        # vb0에서 데이터 추출 (parent 해시 추출 포함)
        vb0_parent_hash = ""
        all_positions = None
        all_normals = None
        all_texcoords = None

        if dc_id in vb_files:
            for slot_str, vb_buf_filename in sorted(vb_files[dc_id].items()):
                vb_buf = os.path.join(directory, vb_buf_filename)
                vb_txt = vb_buf.replace('.buf', '.txt')

                if not os.path.exists(vb_buf) or not os.path.exists(vb_txt):
                    continue

                # parent 해시 추출 (vb0에서만)
                if slot_str == '0':
                    parent_match = re.search(r'\(([a-f0-9]+)\)', vb_buf_filename)
                    if parent_match:
                        vb0_parent_hash = parent_match.group(1)
                    vb_hash_match = re.search(r'vb0=([a-f0-9]+)', vb_buf_filename)
                    if vb_hash_match:
                        mesh.vb0_hash = vb_hash_match.group(1)

                try:
                    slot = int(slot_str)
                    slot_data = extract_vertices_numpy(vb_buf, vb_txt, target_slot=slot)

                    if 'POSITION' in slot_data:
                        all_positions = slot_data['POSITION']

                    if 'NORMAL' in slot_data and slot_data['NORMAL'].shape[1] >= 3:
                        all_normals = slot_data['NORMAL']

                    if 'TEXCOORD' in slot_data:
                        all_texcoords = slot_data['TEXCOORD']

                except Exception as e:
                    print(f"Error parsing VB{slot_str} for DC {dc_id}: {e}")

        mesh.vb0_parent_hash = vb0_parent_hash

        # POSITION이 없으면 스킵
        if all_positions is None:
            continue

        # 좌표계 정규화: parent=1d6a6186 그룹을 parent=9a09f1f0 그룹(DC 22, 112 기준)에 맞춤
        # 변환: (x, y, z) → (x, z, -y)
        if vb0_parent_hash == '1d6a6186':
            old_y = all_positions[:, 1].copy()
            old_z = all_positions[:, 2].copy()
            all_positions[:, 1] = old_z
            all_positions[:, 2] = -old_y

        # 법선 처리: 유효한 법선이 없으면 NumPy 기반 자동 계산
        if all_normals is None or all_normals.shape[1] < 3:
            indices_np = np.array(mesh.indices, dtype=np.uint32)
            all_normals = compute_normals_numpy(all_positions, indices_np)
        elif vb0_parent_hash == '1d6a6186':
            # 법선도 동일하게 변환
            old_ny = all_normals[:, 1].copy()
            old_nz = all_normals[:, 2].copy()
            all_normals[:, 1] = old_nz
            all_normals[:, 2] = -old_ny

        # Vertex 리스트로 변환
        mesh.vertices = numpy_to_vertices(all_positions, all_normals, all_texcoords)

        if mesh.vertices and mesh.indices:
            meshes[dc_id] = mesh

    return meshes
