"""
EFMI 데이터 모델 및 DXGI 포맷 정의

EFMI-Tools의 data_model/byte_buffer.py를 참고하여 독립 구현
"""

import numpy as np
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Union


# ============================================================
# DXGI Format 정의
# ============================================================

class DXGIType(Enum):
    FLOAT = "FLOAT"
    UINT = "UINT"
    UNORM = "UNORM"
    SNORM = "SNORM"


@dataclass
class DXGIFormat:
    """DXGI 포맷 정의"""
    name: str
    dxgi_type: DXGIType
    components: int  # 컴포넌트 수 (예: R32G32B32 = 3)
    bits_per_component: int  # 비트 수 (예: 32, 16, 8)
    byte_width: int  # 총 바이트 수

    # 자주 사용되는 포맷들
    R32G32B32_FLOAT: 'DXGIFormat' = None
    R32G32_FLOAT: 'DXGIFormat' = None
    R32_FLOAT: 'DXGIFormat' = None
    R32G32B32A32_FLOAT: 'DXGIFormat' = None
    R16G16B16A16_FLOAT: 'DXGIFormat' = None
    R16G16_FLOAT: 'DXGIFormat' = None
    R16_UINT: 'DXGIFormat' = None
    R32_UINT: 'DXGIFormat' = None
    R8G8B8A8_UNORM: 'DXGIFormat' = None
    R8G8B8A8_SNORM: 'DXGIFormat' = None
    R16_UNORM: 'DXGIFormat' = None
    R8_UINT: 'DXGIFormat' = None

    @classmethod
    def from_name(cls, name: str) -> 'DXGIFormat':
        """포맷 이름으로 DXGIFormat 객체 생성"""
        name = name.strip().upper()
        if name.startswith("DXGI_FORMAT_"):
            name = name[len("DXGI_FORMAT_"):]

        formats = {
            "R32G32B32_FLOAT": cls("R32G32B32_FLOAT", DXGIType.FLOAT, 3, 32, 12),
            "R32G32_FLOAT": cls("R32G32_FLOAT", DXGIType.FLOAT, 2, 32, 8),
            "R32_FLOAT": cls("R32_FLOAT", DXGIType.FLOAT, 1, 32, 4),
            "R32G32B32A32_FLOAT": cls("R32G32B32A32_FLOAT", DXGIType.FLOAT, 4, 32, 16),
            "R16G16B16A16_FLOAT": cls("R16G16B16A16_FLOAT", DXGIType.FLOAT, 4, 16, 8),
            "R16G16_FLOAT": cls("R16G16_FLOAT", DXGIType.FLOAT, 2, 16, 4),
            "R16_UINT": cls("R16_UINT", DXGIType.UINT, 1, 16, 2),
            "R32_UINT": cls("R32_UINT", DXGIType.UINT, 1, 32, 4),
            "R8G8B8A8_UNORM": cls("R8G8B8A8_UNORM", DXGIType.UNORM, 4, 8, 4),
            "R8G8B8A8_SNORM": cls("R8G8B8A8_SNORM", DXGIType.SNORM, 4, 8, 4),
            "R16_UNORM": cls("R16_UNORM", DXGIType.UNORM, 1, 16, 2),
            "R8_UINT": cls("R8_UINT", DXGIType.UINT, 1, 8, 1),
            "R16G16B16A16_UNORM": cls("R16G16B16A16_UNORM", DXGIType.UNORM, 4, 16, 8),
            "R16G16_UNORM": cls("R16G16_UNORM", DXGIType.UNORM, 2, 16, 4),
            "R8G8_UNORM": cls("R8G8_UNORM", DXGIType.UNORM, 2, 8, 2),
            "R8_UNORM": cls("R8_UNORM", DXGIType.UNORM, 1, 8, 1),
        }

        if name not in formats:
            raise ValueError(f"Unknown DXGI format: {name}")

        return formats[name]

    @property
    def numpy_dtype(self) -> np.dtype:
        """NumPy dtype 반환"""
        if self.dxgi_type == DXGIType.FLOAT:
            if self.bits_per_component == 32:
                return np.float32
            elif self.bits_per_component == 16:
                return np.float16
        elif self.dxgi_type == DXGIType.UINT:
            if self.bits_per_component == 32:
                return np.uint32
            elif self.bits_per_component == 16:
                return np.uint16
            elif self.bits_per_component == 8:
                return np.uint8
        elif self.dxgi_type == DXGIType.UNORM:
            if self.bits_per_component == 16:
                return np.uint16
            elif self.bits_per_component == 8:
                return np.uint8
        elif self.dxgi_type == DXGIType.SNORM:
            if self.bits_per_component == 8:
                return np.int8

        return np.uint8  # 기본값

    def get_numpy_type(self) -> Union[type, tuple]:
        """NumPy 타입 반환 (다중 컴포넌트인 경우 tuple)"""
        base = self.numpy_dtype
        if self.components > 1:
            return (base, self.components)
        return base

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"DXGIFormat({self.name})"


# ============================================================
# Semantic 정의
# ============================================================

class Semantic(Enum):
    """버텍스 시맨틱 열거형"""
    VertexId = "VERTEXID"
    Index = "INDEX"
    Tangent = "TANGENT"
    BitangentSign = "BITANGENTSIGN"
    Normal = "NORMAL"
    TexCoord = "TEXCOORD"
    Color = "COLOR"
    Position = "POSITION"
    Blendindices = "BLENDINDICES"
    Blendweights = "BLENDWEIGHTS"
    ShapeKey = "SHAPEKEY"
    RawData = "RAWDATA"
    EncodedData = "ENCODEDDATA"
    Attribute = "ATTRIBUTE"

    def __str__(self):
        return self.value

    def __hash__(self):
        return hash(self.value)


@dataclass
class AbstractSemantic:
    """추상 시맨틱 (이름 + 인덱스)"""
    enum: Semantic
    index: int = 0

    def __hash__(self):
        return hash((self.enum, self.index))

    def __str__(self):
        return f"{self.enum.value}_{self.index}"

    def get_name(self) -> str:
        """시맨틱 이름 반환 (예: TEXCOORD0 → TEXCOORD.xy)"""
        name = self.enum.value
        if self.index > 0:
            name += str(self.index)
        if self.enum == Semantic.TexCoord:
            name += ".xy"
        return name

    def __eq__(self, other):
        if isinstance(other, AbstractSemantic):
            return self.enum == other.enum and self.index == other.index
        return False


# ============================================================
# Buffer Semantic 및 Layout
# ============================================================

@dataclass
class BufferSemantic:
    """버퍼 시맨틱 정의"""
    abstract: AbstractSemantic
    format: DXGIFormat
    stride: int = 0
    offset: int = 0
    input_slot: int = 0

    def __post_init__(self):
        if self.stride == 0:
            self.stride = self.format.byte_width

    def __hash__(self):
        return hash((self.abstract, self.input_slot, self.format.name, self.stride, self.offset))

    def get_name(self) -> str:
        return self.abstract.get_name()

    def get_num_values(self) -> int:
        return self.format.components


@dataclass
class BufferLayout:
    """버퍼 레이아웃 정의"""
    semantics: List[BufferSemantic] = field(default_factory=list)
    stride: int = 0
    auto_stride: bool = True
    auto_offsets: bool = True

    def __post_init__(self):
        if self.auto_stride and self.stride == 0:
            self.fill_stride()
            if self.auto_offsets:
                self.fill_offsets()

    def fill_stride(self):
        self.stride = sum(s.stride for s in self.semantics)

    def fill_offsets(self):
        offset = 0
        for semantic in self.semantics:
            semantic.offset = offset
            offset += semantic.stride

    def add_element(self, semantic: BufferSemantic):
        """시맨틱 추가"""
        # 중복 체크
        for existing in self.semantics:
            if existing.abstract == semantic.abstract:
                return
        semantic = BufferSemantic(
            abstract=semantic.abstract,
            format=semantic.format,
            stride=semantic.stride,
            offset=semantic.offset,
            input_slot=semantic.input_slot,
        )
        if self.auto_offsets:
            semantic.offset = self.stride
        if self.auto_stride:
            self.stride += semantic.stride
        self.semantics.append(semantic)

    def get_element(self, element: Union[AbstractSemantic, Semantic, str, int]) -> Optional[BufferSemantic]:
        """시맨틱 조회"""
        if isinstance(element, str):
            for s in self.semantics:
                if s.get_name() == element:
                    return s
            return None

        if isinstance(element, int):
            if element >= len(self.semantics):
                return None
            return self.semantics[element]

        if isinstance(element, Semantic):
            element = AbstractSemantic(element)

        if isinstance(element, AbstractSemantic):
            for s in self.semantics:
                if s.abstract == element:
                    return s

        return None

    def get_numpy_type(self) -> np.dtype:
        """NumPy dtype 반환"""
        dtype = np.dtype([])
        for semantic in self.semantics:
            dtype = np.dtype(dtype.descr + [(semantic.get_name(), (semantic.format.get_numpy_type()))])
        return dtype


# ============================================================
# NumpyBuffer
# ============================================================

class NumpyBuffer:
    """NumPy 기반 버퍼"""
    layout: BufferLayout
    data: np.ndarray

    def __init__(self, layout: BufferLayout, size: int = 0):
        self.layout = layout
        if size > 0:
            self.data = np.zeros(size, dtype=layout.get_numpy_type())
        else:
            self.data = np.array([], dtype=layout.get_numpy_type())

    def set_field(self, field_name: Union[str, AbstractSemantic], data: np.ndarray):
        """필드 데이터 설정"""
        if isinstance(field_name, AbstractSemantic):
            field_name = field_name.get_name()
        semantic = self.layout.get_element(field_name)
        if semantic is None:
            raise ValueError(f"Semantic {field_name} not found in layout")
        self.data[field_name] = data

    def get_field(self, field_name: Union[str, AbstractSemantic]) -> Optional[np.ndarray]:
        """필드 데이터 조회"""
        if isinstance(field_name, AbstractSemantic):
            field_name = field_name.get_name()
        semantic = self.layout.get_element(field_name)
        if semantic is None:
            return None
        return self.data[field_name]

    def get_bytes(self) -> bytes:
        """버퍼 데이터를 바이트로 변환"""
        return self.data.tobytes()

    def __len__(self) -> int:
        return len(self.data)
