"""
TBN (Tangent/Bitangent/Normal) 인코딩 모듈

EFMI-Tools의 10-10-10-2 비트 패킹 방식을 구현
- X(10비트): 옥타헤드럴 인코딩된 노멀
- Y(10비트): 옥타헤드럴 인코딩된 노멀
- Z(10비트): 인코딩된 탄젠트
- W(2비트): 플래그 (packed flag + bitangent sign)
"""

import numpy as np
from typing import Tuple


def oct_encode_vector(normals: np.ndarray) -> np.ndarray:
    """
    벡터를 옥타헤드럴 인코딩으로 압축 (x,y,z → x,y)

    Args:
        normals: (N, 3) 정규화된 벡터 배열

    Returns:
        (N, 2) 옥타헤드럴 인코딩된 벡터
    """
    assert normals.ndim == 2 and normals.shape[1] == 3, "Normals must be (N, 3)"

    # L1 정규화 (옥타헤드럴 투영)
    n = normals / np.sum(np.abs(normals), axis=1, keepdims=True)

    # 음수 hemisphere 폴딩
    mask = n[:, 2] < 0
    n_fold = n.copy()
    n_fold[mask, 0] = (1.0 - np.abs(n[mask, 1])) * np.sign(n[mask, 0])
    n_fold[mask, 1] = (1.0 - np.abs(n[mask, 0])) * np.sign(n[mask, 1])

    return n_fold[:, :2]


def oct_decode_vector(data: np.ndarray) -> np.ndarray:
    """
    옥타헤드럴 인코딩된 벡터 디코딩 (x,y → x,y,z)

    Args:
        data: (N, 2) 옥타헤드럴 인코딩된 벡터

    Returns:
        (N, 3) 정규화된 벡터
    """
    assert data.ndim == 2 and data.shape[1] == 2, "Data must be (N, 2)"

    x, y = data.T

    # 음수 hemisphere 언폴딩
    z = 1.0 - np.abs(x) - np.abs(y)
    mask = z < 0.0

    old_x = x.copy()
    x[mask] = (1.0 - np.abs(y[mask])) * np.sign(old_x[mask])
    y[mask] = (1.0 - np.abs(old_x[mask])) * np.sign(y[mask])

    # 벡터 구성 및 정규화
    result = np.stack([x, y, z], axis=1)
    result /= np.linalg.norm(result, axis=1, keepdims=True).clip(1e-8)

    return result


def encode_tangents(tangents: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """
    탄젠트를 각도 기반으로 인코딩

    Args:
        tangents: (N, 3) 탄젠트 벡터
        normals: (N, 3) 노멀 벡터

    Returns:
        (N) 인코딩된 탄젠트 값 [0, 1] 범위
    """
    # 참조 탄젠트 R = (Ny - Nz, Nz - Nx, Nx - Ny)
    R = np.stack([
        normals[:, 1] - normals[:, 2],
        normals[:, 2] - normals[:, 0],
        normals[:, 0] - normals[:, 1]
    ], axis=1)

    R_norm = np.linalg.norm(R, axis=1, keepdims=True)
    small_mask = R_norm[:, 0] < 1e-6

    # 퇴케 케이스 처리
    if np.any(small_mask):
        helper = np.where(np.abs(normals[:, 0:1]) < 0.9, np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
        v_perp = np.cross(normals, helper)
        v_perp /= np.linalg.norm(v_perp, axis=1, keepdims=True)
        R = np.where(small_mask[:, None], v_perp, R / R_norm)

    # 바이탄젠트 B = cross(R, N)
    B = np.cross(R, normals)

    # 탄젠트를 {R, B} 기저에 투영
    cos_theta = np.sum(tangents * R, axis=1)
    sin_theta = np.sum(tangents * B, axis=1)

    # 클램핑
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    sin_theta = np.clip(sin_theta, -1.0, 1.0)

    # 파라미터 t 계산 [0, 1]
    denom = np.abs(cos_theta) + np.abs(sin_theta)
    u_t = cos_theta / denom
    t = 1 - (1 - u_t) / 2.0

    # sin 부호 적용
    s = np.where(sin_theta == 0.0, 1.0, np.sign(sin_theta))
    t = np.copysign(t, s)

    return t


def encode_10_10_10_2(data: np.ndarray) -> np.ndarray:
    """
    5개 float 값을 R10G10B10A2_UINT로 패킹

    Args:
        data: (N, 5) 배열 [x, y, z, flag1, flag2]

    Returns:
        (N) uint32 패킹된 값
    """
    assert data.ndim == 2 and data.shape[1] == 5, "Data must be (N, 5)"
    assert np.issubdtype(data.dtype, np.floating), "Data must be float"

    flags = data[:, 3:].astype(np.int32)
    values = data[:, 0:3]

    # 10비트 양자화 (스케일: 1/511)
    values = np.rint(values * 511).astype(np.int32)
    values = np.clip(values, -511, 511)
    values &= 0x3FF  # unsigned로 변환

    # 비트 패킹
    packed = (values[:, 0] |
              (values[:, 1] << 10) |
              (values[:, 2] << 20) |
              (flags[:, 0] << 30) |
              (flags[:, 1] << 31))

    return packed.astype(np.uint32)


def decode_10_10_10_2(data: np.ndarray) -> np.ndarray:
    """
    R10G10B10A2_UINT를 5개 float로 언패킹

    Args:
        data: (N) uint32 패킹된 값

    Returns:
        (N, 5) 배열 [x, y, z, flag1, flag2]
    """
    assert data.ndim == 1, "Data must be 1D"
    assert data.dtype == np.uint32, "Data must be uint32"

    # 10비트 컴포넌트 추출
    x = data & 0x3FF
    y = (data >> 10) & 0x3FF
    z = (data >> 20) & 0x3FF

    # 부호 확장 (10비트 signed)
    def sign_extend_10bit(v):
        v = v.astype(np.int32)
        return np.where(v >= 512, v - 1024, v)

    x_s, y_s, z_s = sign_extend_10bit(x), sign_extend_10bit(y), sign_extend_10bit(z)

    # float 스케일링
    scale = 1 / 511

    # 플래그 추출
    bit_30 = ((data >> 30) & 1).astype(np.float32)
    bit_31 = ((data >> 31) & 1).astype(np.float32)

    return np.stack([x_s * scale, y_s * scale, z_s * scale, bit_30, bit_31], axis=1)


def encode_tbn_data_10_10_10_2(
    normals: np.ndarray,
    tangents: np.ndarray,
    bitangent_signs: np.ndarray
) -> np.ndarray:
    """
    노멀, 탄젠트, 바이탄젠트 사인을 10-10-10-2로 인코딩

    Args:
        normals: (N, 3) 노멀 벡터
        tangents: (N, 3) 탄젠트 벡터
        bitangent_signs: (N) 바이탄젠트 사인 (-1 또는 1)

    Returns:
        (N) uint32 인코딩된 데이터
    """
    assert normals.ndim == 2 and normals.shape[1] == 3
    assert tangents.ndim == 2 and tangents.shape[1] == 3
    assert bitangent_signs.ndim == 1

    # 옥타헤드럴 노멀 인코딩
    encoded_normals = oct_encode_vector(normals)

    # 탄젠트 인코딩
    encoded_tangents = encode_tangents(tangents, normals)

    # 플래그 구성
    packed_flags = np.ones(len(bitangent_signs), dtype=np.float32)  # packed data flag
    sign_flags = (bitangent_signs + 1) * 0.5  # -1→0, 1→1

    # 데이터 스택 구성
    data = np.stack([
        encoded_normals[:, 0],
        encoded_normals[:, 1],
        encoded_tangents,
        packed_flags,
        sign_flags
    ], axis=1)

    return encode_10_10_10_2(data)


def decode_tbn_data_10_10_10_2(data: np.ndarray, debug: bool = False) -> np.ndarray:
    """
    10-10-10-2 인코딩된 데이터에서 TBN 디코딩

    Args:
        data: (N) uint32 인코딩된 데이터
        debug: True면 노멀, 탄젠트, 바이탄젠트 사인 모두 반환

    Returns:
        normals: (N, 3) 또는 (normals, encoded_tangents, bitangent_signs)
    """
    decoded = decode_10_10_10_2(data)

    # packed flag 확인 (bit 30)
    packed_flags = decoded[:, 3]
    assert np.all(packed_flags == 1), "NORMAL0 data is not 10-10-10-2 encoded!"

    # 노멀 디코딩
    normals = oct_decode_vector(decoded[:, :2])

    if debug:
        encoded_tangents = decoded[:, 2]
        bitangent_signs = np.where(decoded[:, 4] == 1, 1, -1)
        return normals, encoded_tangents, bitangent_signs

    return normals
