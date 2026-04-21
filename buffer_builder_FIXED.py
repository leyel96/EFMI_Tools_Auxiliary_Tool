"""
버퍼 빌더 모듈 (수정: VB0/VB1/VB2 모두 지원)

MeshData를 EFMI 형식 .buf 파일로 변환
- Index Buffer (IB)
- Vertex Buffer 0 (VB0): Position + EncodedData
- Vertex Buffer 1 (VB1): TexCoord + Color
- Vertex Buffer 2 (VB2): BlendWeights + BlendIndices
"""

import numpy as np
from typing import Dict, Tuple, Optional
from pathlib import Path

from data_model import (
    Semantic,
    AbstractSemantic,
    BufferSemantic,
    BufferLayout,
    DXGIFormat,
    NumpyBuffer,
)
from tbn_encoding import encode_tbn_data_10_10_10_2
from mesh_parser import MeshData


class BufferBuilder:
    """EFMI 형식 버퍼 빌더"""

    def __init__(self, mirror_mesh: bool = False, flip_texcoord_v: bool = True):
        """
        Args:
            mirror_mesh: 메쉬 좌우 반전 여부
            flip_texcoord_v: UV V좌표 반전 여부
        """
        self.mirror_mesh = mirror_mesh
        self.flip_texcoord_v = flip_texcoord_v

    def build_buffers(
        self,
        mesh: MeshData,
        component_id: int = 0,
        index_offset: int = 0,
    ) -> Dict[str, NumpyBuffer]:
        """
        ✓ 수정: MeshData에서 EFMI 버퍼들 생성 (VB0, VB1, VB2)

        Args:
            mesh: 메쉬 데이터
            component_id: 컴포넌트 ID
            index_offset: 인덱스 오프셋

        Returns:
            버퍼 이름 → NumpyBuffer 딕셔너리
        """
        buffers = {}

        # 1. Index Buffer 빌드
        buffers[f'Component{component_id}_IB'] = self._build_index_buffer(
            mesh, component_id
        )

        # 2. Vertex Buffer 0 (Position + EncodedData)
        buffers[f'Component{component_id}_VB0'] = self._build_vb0(mesh, component_id)

        # ✓ 3. Vertex Buffer 1 (TexCoord + Color)
        buffers[f'Component{component_id}_VB1'] = self._build_vb1(mesh, component_id)

        # ✓ 4. Vertex Buffer 2 (BlendWeights + BlendIndices) - 스킨 정보 있으면
        if mesh.vertices and self._has_skin_data(mesh.vertices):
            buffers[f'Component{component_id}_VB2'] = self._build_vb2(mesh, component_id)

        return buffers

    def _build_index_buffer(self, mesh: MeshData, component_id: int) -> NumpyBuffer:
        """인덱스 버퍼 빌드 (R16_UINT × 3)"""
        indices = np.array(mesh.indices, dtype=np.uint16)

        # Triangle list로 재구성 (3개씩)
        # EFMI는 triangle list만 지원
        layout = BufferLayout([
            BufferSemantic(
                AbstractSemantic(Semantic.Index, 0),
                DXGIFormat.from_name("R16_UINT"),
                stride=6  # 2바이트 × 3
            )
        ])

        buffer = NumpyBuffer(layout, size=len(indices) // 3)
        buffer.data['INDEX'] = indices.reshape(-1, 3)

        return buffer

    def _build_vb0(self, mesh: MeshData, component_id: int) -> NumpyBuffer:
        """
        ✓ Vertex Buffer 0 빌드
        - POSITION0: R32G32B32_FLOAT (12바이트)
        - ENCODEDDATA0: R32_UINT (4바이트) - 인코딩된 TBN
        """
        vertex_count = len(mesh.vertices)

        # 위치 데이터 추출
        positions = np.array([v.position for v in mesh.vertices], dtype=np.float32)

        # 좌우 반전
        if self.mirror_mesh:
            positions[:, 0] *= -1

        # 노멀 데이터 추출
        normals = np.array([v.normal for v in mesh.vertices], dtype=np.float32)
        if self.mirror_mesh:
            normals[:, 0] *= -1

        # 탄젠트 데이터 (있는 경우)
        tangents = None
        bitangent_signs = None

        if mesh.vertices and len(mesh.vertices[0].tangent) == 4:
            tangents = np.array([v.tangent[:3] for v in mesh.vertices], dtype=np.float32)
            if self.mirror_mesh:
                tangents[:, 0] *= -1
            # 바이탄젠트 사인은 탄젠트 W성분에서 추출 (또는 계산)
            bitangent_signs = np.array([v.tangent[3] for v in mesh.vertices], dtype=np.float32)
            bitangent_signs = np.where(bitangent_signs >= 0, 1.0, -1.0)
        else:
            # 탄젠트가 없으면 노멀로부터 계산
            tangents, bitangent_signs = self._compute_tangents(normals)

        # TBN 인코딩 (10-10-10-2)
        if self.flip_texcoord_v:
            tangents[:, 0] *= -1  # UV V반전 보정

        encoded_data = encode_tbn_data_10_10_10_2(normals, tangents, bitangent_signs)

        # 버퍼 레이아웃
        layout = BufferLayout([
            BufferSemantic(
                AbstractSemantic(Semantic.Position, 0),
                DXGIFormat.from_name("R32G32B32_FLOAT"),
            ),
            BufferSemantic(
                AbstractSemantic(Semantic.EncodedData, 0),
                DXGIFormat.from_name("R32_UINT"),
            ),
        ])

        buffer = NumpyBuffer(layout, size=vertex_count)
        buffer.data['POSITION'] = positions
        buffer.data['ENCODEDDATA'] = encoded_data

        return buffer

    def _build_vb1(self, mesh: MeshData, component_id: int) -> NumpyBuffer:
        """
        ✓ Vertex Buffer 1 빌드
        - TEXCOORD0: R32G32_FLOAT (8바이트)
        - COLOR0: R8G8B8A8_SNORM (4바이트)
        """
        vertex_count = len(mesh.vertices)

        # UV 좌표
        texcoords = np.array([v.texcoord for v in mesh.vertices], dtype=np.float32)

        # V좌표 반전
        if self.flip_texcoord_v:
            texcoords[:, 1] = 1.0 - texcoords[:, 1]

        # 색상 (기본값)
        # COLOR는 R8G8B8A8_SNORM이므로 -1~1 범위
        # EFMI에서는 기본적으로 0값 (검정) 사용
        colors = np.zeros((vertex_count, 4), dtype=np.int8)

        # 버퍼 레이아웃
        layout = BufferLayout([
            BufferSemantic(
                AbstractSemantic(Semantic.TexCoord, 0),
                DXGIFormat.from_name("R32G32_FLOAT"),
            ),
            BufferSemantic(
                AbstractSemantic(Semantic.Color, 0),
                DXGIFormat.from_name("R8G8B8A8_SNORM"),
            ),
        ])

        buffer = NumpyBuffer(layout, size=vertex_count)
        buffer.data['TEXCOORD.xy'] = texcoords
        buffer.data['COLOR'] = colors

        return buffer

    def _build_vb2(self, mesh: MeshData, component_id: int) -> NumpyBuffer:
        """
        ✓ Vertex Buffer 2 빌드
        - BLENDWEIGHTS0: R16_UNORM × 4 (8바이트)
        - BLENDINDICES0: R8_UINT × 4 (4바이트)
        """
        vertex_count = len(mesh.vertices)

        # 블렌딩 가중치
        blendweights = np.array(
            [v.blendweights for v in mesh.vertices],
            dtype=np.float32
        )

        # 16비트 UNORM으로 양자화 (0~65535)
        blendweights_u16 = np.clip(blendweights * 65535.0, 0, 65535).astype(np.uint16)

        # 블렌딩 인덱스
        blendindices = np.array(
            [v.blendindices for v in mesh.vertices],
            dtype=np.uint8
        )

        # 버퍼 레이아웃
        layout = BufferLayout([
            BufferSemantic(
                AbstractSemantic(Semantic.Blendweights, 0),
                DXGIFormat.from_name("R16_UNORM"),
                stride=8,  # 2바이트 × 4
            ),
            BufferSemantic(
                AbstractSemantic(Semantic.Blendindices, 0),
                DXGIFormat.from_name("R8_UINT"),
                stride=4,  # 1바이트 × 4
            ),
        ])

        buffer = NumpyBuffer(layout, size=vertex_count)
        buffer.data['BLENDWEIGHTS'] = blendweights_u16.reshape(-1, 4)
        buffer.data['BLENDINDICES'] = blendindices.reshape(-1, 4)

        return buffer

    def _has_skin_data(self, vertices) -> bool:
        """메시가 스킨 정보를 가지고 있는지 확인"""
        if not vertices:
            return False

        for v in vertices[:10]:  # 처음 10개만 확인
            if any(w > 0 for w in v.blendweights):
                return True

        return False

    def _compute_tangents(
        self,
        normals: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        노멀로부터 탄젠트와 바이탄젠트 사인 계산

        Args:
            normals: (N, 3) 노멀 벡터

        Returns:
            (tangents, bitangent_signs)
        """
        # 기본 탄젠트 생성 (노멀과 직교하는 벡터)
        # 간단한 휴리스틱: 노멀의 최소 성분과 직교하는 벡터 사용
        abs_normals = np.abs(normals)
        min_axis = np.argmin(abs_normals, axis=1)

        tangents = np.zeros_like(normals)

        # X축이 최소인 경우
        mask_x = min_axis == 0
        tangents[mask_x] = np.array([0.0, 1.0, 0.0])

        # Y축이 최소인 경우
        mask_y = min_axis == 1
        tangents[mask_y] = np.array([1.0, 0.0, 0.0])

        # Z축이 최소인 경우
        mask_z = min_axis == 2
        tangents[mask_z] = np.array([1.0, 0.0, 0.0])

        # 그램-슈미트 직교화
        dot = np.sum(tangents * normals, axis=1, keepdims=True)
        tangents = tangents - dot * normals
        tangents /= np.linalg.norm(tangents, axis=1, keepdims=True).clip(1e-8)

        # 바이탄젠트 사인 (기본값: 1)
        bitangent_signs = np.ones(len(normals), dtype=np.float32)

        return tangents, bitangent_signs

    def write_buffers(
        self,
        buffers: Dict[str, NumpyBuffer],
        output_dir: Path
    ):
        """
        ✓ 수정: 버퍼들을 .buf 파일로 저장 (VB0, VB1, VB2 모두)

        Args:
            buffers: 버퍼 딕셔너리
            output_dir: 출력 디렉토리
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        for buffer_name, buffer in buffers.items():
            buf_path = output_dir / f"{buffer_name}.buf"
            with open(buf_path, 'wb') as f:
                f.write(buffer.get_bytes())
            print(f"Written: {buf_path} ({len(buffer)} entries, {buffer.layout.stride} stride)")
