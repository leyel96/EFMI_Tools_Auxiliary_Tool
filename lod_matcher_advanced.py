"""
고급 LOD 매칭 모듈 (EFMI-Tools 기반)

EFMI-Tools의 lod_matcher.py를 완전히 통합한 버전:
- 2단계 Prefilter 시스템 (빠른 필터링 → 정밀 매칭)
- 해시 기반 빠른 매칭
- Voxel/Point Cloud 기반 기하학적 유사도 계산
- Chamfer Distance 기반 VG 매칭
"""

import json
import time
import numpy as np
from pathlib import Path
from operator import itemgetter
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field

from mesh_parser import parse_frame_analysis_directory


@dataclass
class LODMatchResult:
    """LOD 매칭 결과"""
    full_vb0_hash: str  # 원본 메쉬 VB0 해시
    lod_vb0_hash: str  # LOD 메쉬 VB0 해시
    lod_name: str  # LOD 메쉬 이름
    similarity: float  # 유사도 (%)
    vg_map: Dict[int, int]  # VG 매핑


class ChamferMixin:
    """Chamfer Distance 계산 Mixin"""

    @staticmethod
    def calculate_linear_chamfer_distance(points_a: np.ndarray, points_b: np.ndarray) -> float:
        """대칭 Chamfer 거리 계산 (선형 거리 사용)"""
        dist1 = ChamferMixin.calculate_min_distances(points_a, points_b)
        dist2 = ChamferMixin.calculate_min_distances(points_b, points_a)
        return float(np.mean(dist1) + np.mean(dist2))

    @staticmethod
    def calculate_min_distances(
        points_a: np.ndarray, points_b: np.ndarray, chunk_size: int = 256
    ) -> np.ndarray:
        """points_a의 각 점에서 points_b까지의 최소 거리 (메모리 절약 청크 기반)"""
        cd_chunks = []
        for start in range(0, len(points_a), chunk_size):
            end = start + chunk_size
            diff_chunk = points_a[start:end, None, :] - points_b[None, :, :]
            dist_chunk = np.min(np.linalg.norm(diff_chunk, axis=2), axis=1)
            cd_chunks.append(dist_chunk)
        return np.concatenate(cd_chunks)


class GeometryMatcher(ChamferMixin):
    """기하학적 유사도 계산기 (EFMI-Tools 기반)"""

    def __init__(
        self,
        method: str = 'VOXEL',
        sensitivity: float = 0.5,
        voxel_size: float = 0.05,
        samples_count: int = 5000,
    ):
        """
        Args:
            method: 매칭 방법 ('VOXEL' 또는 'POINT_CLOUD')
            sensitivity: 민감도 (클수록 관대한 매칭)
            voxel_size: 복셀 크기 (Voxel 방식에서만 사용)
            samples_count: 샘플 수 (Point Cloud 방식에서만 사용)
        """
        self.method = method
        self.sensitivity = sensitivity
        self.voxel_size = voxel_size
        self.samples_count = samples_count

    def calculate_similarity(self, positions_a: np.ndarray, positions_b: np.ndarray) -> float:
        """두 메쉬의 기하학적 유사도 계산"""
        if self.method == 'VOXEL':
            return self.calculate_similarity_voxel(positions_a, positions_b)
        elif self.method == 'POINT_CLOUD':
            return self._calculate_similarity_point_cloud(positions_a, positions_b)
        else:
            raise ValueError(f'Unknown geometry matching method: {self.method}')

    def _calculate_similarity_point_cloud(self, positions_a: np.ndarray, positions_b: np.ndarray) -> float:
        """Point Cloud 기반 유사도 계산 (삼각형 면적 비례 샘플링)"""
        if len(positions_a) < 3 or len(positions_b) < 3:
            return 0.0

        # 단순화된 포인트 클라우드 샘플링
        points_a = self._sample_points(positions_a)
        points_b = self._sample_points(positions_b)

        if len(points_a) == 0 or len(points_b) == 0:
            return 0.0

        # Chamfer 거리 계산
        cd = self.calculate_linear_chamfer_distance(points_a, points_b)

        # 바운딩 박스 대각선으로 스케일 정규화
        scale = np.linalg.norm(positions_a.max(axis=0) - positions_a.min(axis=0))
        if scale == 0:
            return 0.0

        # 유사도 계산
        similarity = max(0.0, 1.0 - cd / (scale * self.sensitivity)) * 100.0
        return similarity

    def _sample_points(self, positions: np.ndarray) -> np.ndarray:
        """포인트 클라우드에서 균일 샘플링"""
        if len(positions) <= self.samples_count:
            return positions

        # 랜덤 샘플링
        indices = np.random.choice(len(positions), self.samples_count, replace=False)
        return positions[indices]

    def calculate_similarity_voxel(self, positions_a: np.ndarray, positions_b: np.ndarray) -> float:
        """Voxel 기반 유사도 계산 (EFMI-Tools 방식)"""
        if len(positions_a) == 0 or len(positions_b) == 0:
            return 0.0

        # 1. 각 메쉬를 개별적으로 정규화 (중심 이동 및 스케일 조정)
        points_a = self._normalize_points(positions_a)
        points_b = self._normalize_points(positions_b)

        # 2. 복셀 그리드 샘플링 (중복된 포인트 제거, 실수 좌표 유지)
        points_a_sample = self._voxel_sample_mesh(points_a)
        points_b_sample = self._voxel_sample_mesh(points_b)

        if len(points_a_sample) == 0 or len(points_b_sample) == 0:
            return 0.0

        # 3. Chamfer 거리 계산 (정규화된 실수 공간)
        d_ab = self.calculate_min_distances(points_a_sample, points_b_sample)
        d_ba = self.calculate_min_distances(points_b_sample, points_a_sample)

        mean_ab = d_ab.mean()
        mean_ba = d_ba.mean()

        chamfer = 0.5 * (mean_ab + mean_ba)
        asym = abs(mean_ab - mean_ba)

        # 4. 커버리지 계산
        coverage_tol = float(self.voxel_size)
        coverage = min(
            float(np.mean(d_ab < coverage_tol)),
            float(np.mean(d_ba < coverage_tol))
        )

        # 5. 최종 유사도 계산
        raw = chamfer + 0.5 * asym
        similarity = max(0.0, 1.0 - raw / float(self.sensitivity))
        similarity *= (0.7 + 0.3 * coverage)

        return similarity * 100.0

    def _normalize_points(self, points: np.ndarray) -> np.ndarray:
        """포인트 클라우드를 중심점으로 이동하고 유닛 스케일로 정규화"""
        center = points.mean(axis=0)
        points = points - center

        bbox = points.max(axis=0) - points.min(axis=0)
        scale = np.linalg.norm(bbox)
        if scale > 0:
            points = points / scale
        return points

    def _voxel_sample_mesh(self, points: np.ndarray) -> np.ndarray:
        """복셀 그리드를 사용하여 포인트 중복 제거 (실수 좌표 유지)"""
        # 복셀 인덱스 계산
        vox = np.floor(points / self.voxel_size).astype(np.int32)

        # 고유한 복셀 인덱스를 가진 포인트들만 선택
        _, unique_idx = np.unique(vox, axis=0, return_index=True)
        return points[unique_idx]


class VertexGroupsMatcher(ChamferMixin):
    """버텍스 그룹 매처 (EFMI-Tools 기반)"""

    def __init__(self, candidates_count: int = 3):
        """
        Args:
            candidates_count: 중심점 거리로 필터링할 후보 수
        """
        self.candidates_count = candidates_count

    def match_vertex_groups(
        self,
        positions_a: np.ndarray,
        vg_ids_a: np.ndarray,
        vg_weights_a: np.ndarray,
        positions_b: np.ndarray,
        vg_ids_b: np.ndarray,
        vg_weights_b: np.ndarray,
    ) -> Dict[int, int]:
        """
        두 메쉬의 버텍스 그룹 매핑 (Chamfer Distance 기반)

        Args:
            positions_a: (N, 3) 메쉬 A 위치
            vg_ids_a: (N, K) 메쉬 A VG IDs
            vg_weights_a: (N, K) 메쉬 A VG 가중치
            positions_b: (M, 3) 메쉬 B 위치
            vg_ids_b: (M, K) 메쉬 B VG IDs
            vg_weights_b: (M, K) 메쉬 B VG 가중치

        Returns:
            VG ID A → VG ID B 매핑
        """
        if vg_ids_a is None or len(vg_ids_a) == 0:
            return {0: 0}

        # VG 0을 가상 ID로 변경 (처리 단순화)
        vg_ids_a, zero_id_a = self._remap_zero_rows(vg_ids_a, vg_weights_a)
        vg_ids_b, zero_id_b = self._remap_zero_rows(vg_ids_b, vg_weights_b)

        # 고유 VG ID
        unique_vg_a = np.unique(vg_ids_a[vg_ids_a != 0])
        unique_vg_b = np.unique(vg_ids_b[vg_ids_b != 0])

        if len(unique_vg_b) == 0:
            return {0: 0}

        # 메쉬 B의 VG별 포인트 클라우드 및 중심점 구축
        points_list_b = []
        centroids_b = []
        for vg_b in unique_vg_b:
            mask = np.any(vg_ids_b == vg_b, axis=1)
            pts = positions_b[mask]
            points_list_b.append(pts)
            if len(pts) > 0:
                centroids_b.append(pts.mean(axis=0))
            else:
                centroids_b.append(np.array([np.inf, np.inf, np.inf]))

        centroids_b = np.array(centroids_b, dtype=np.float32)

        mapping = {}

        for vg_a in unique_vg_a:
            mask = np.any(vg_ids_a == vg_a, axis=1)
            points_a = positions_a[mask].astype(np.float32)

            if len(points_a) == 0:
                mapping[int(vg_a)] = 0
                continue

            # 메쉬 A 중심점 계산
            centroid = points_a.mean(axis=0)

            # 중심점 거리로 후보 필터링
            dists = np.linalg.norm(centroids_b - centroid, axis=1)
            candidate_indices = np.argsort(dists)[:min(self.candidates_count, len(dists))]

            best_cd = np.inf
            best_vg_b = None

            # Chamfer Distance로最佳 매칭
            for idx in candidate_indices:
                points_b = points_list_b[idx]
                if len(points_b) == 0:
                    continue

                cd = self.calculate_linear_chamfer_distance(points_a, points_b)
                if cd < best_cd:
                    best_cd = cd
                    best_vg_b = int(unique_vg_b[idx])

            vg_a_int = int(vg_a)
            vg_a_int = vg_a_int if vg_a_int != zero_id_a else 0
            best_vg_b = best_vg_b if best_vg_b != zero_id_b else 0

            mapping[vg_a_int] = best_vg_b if best_vg_b is not None else 0

        return dict(sorted(mapping.items()))

    @staticmethod
    def _remap_zero_rows(
        vg_ids: np.ndarray, vg_weights: np.ndarray
    ) -> Tuple[np.ndarray, int]:
        """VG 0을 가상 ID로 변경"""
        vg_ids = vg_ids.copy()
        virtual_id = int(vg_ids.max()) + 1

        if vg_weights is None:
            num_rows = vg_ids.shape[0]
            num_zeros = vg_ids.shape[1] - 1
            vg_weights = np.hstack([
                np.ones((num_rows, 1), dtype=np.uint8),
                np.zeros((num_rows, num_zeros), dtype=np.uint8),
            ])

        # 가중치 > 0인 곳에서 VG 0을 가상 ID로 변경
        mask = (vg_ids == 0) & (vg_weights > 0)
        vg_ids[mask] = virtual_id

        return vg_ids, virtual_id


class AdvancedLODMatcher:
    """고급 LOD 매처 (EFMI-Tools 호환)"""

    def __init__(
        self,
        full_model_dir: str,
        lod_dump_dir: str,
        output_dir: str,
        method: str = 'VOXEL',
        similarity_threshold: float = 55.0,
        voxel_size: float = 0.01,
        sensitivity: float = 0.5,
        samples_count: int = 1000,
        # Prefilter 설정
        prefilter_voxel_size: float = 0.05,
        prefilter_samples_count: int = 250,
        prefilter_candidates_count: int = 5,
        # VG Matcher 설정
        vg_candidates_count: int = 3,
    ):
        """
        Args:
            full_model_dir: 원본 메쉬 폴더 (Metadata.json 포함)
            lod_dump_dir: LOD 덤프 폴더 (FrameAnalysis)
            output_dir: 출력 폴더
            method: 매칭 방법 ('VOXEL' 또는 'POINT_CLOUD')
            similarity_threshold: 유사도 임계값 (%)
            voxel_size: 복셀 크기 (정밀 매칭)
            sensitivity: 민감도
            samples_count: 샘플 수 (정밀 매칭)
            prefilter_voxel_size: Prefilter 복셀 크기
            prefilter_samples_count: Prefilter 샘플 수
            prefilter_candidates_count: Prefilter 후보 수
            vg_candidates_count: VG 매칭 후보 수
        """
        self.full_model_dir = Path(full_model_dir)
        self.lod_dump_dir = Path(lod_dump_dir)
        self.output_dir = Path(output_dir)
        self.similarity_threshold = similarity_threshold
        self.method = method

        # 정밀 매칭용 GeometryMatcher
        self.geo_matcher = GeometryMatcher(
            method=method,
            sensitivity=sensitivity,
            voxel_size=voxel_size,
            samples_count=samples_count,
        )

        # Prefilter용 GeometryMatcher
        self.prefilter_matcher = GeometryMatcher(
            method=method,
            sensitivity=sensitivity,
            voxel_size=prefilter_voxel_size,
            samples_count=prefilter_samples_count,
        )

        # VG Matcher
        self.vg_matcher = VertexGroupsMatcher(candidates_count=vg_candidates_count)

        # Prefilter 설정
        self.prefilter_candidates_count = prefilter_candidates_count

        # 데이터 저장소
        self.full_components: Dict[int, dict] = {}  # comp_id → component data
        self.lod_meshes: Dict[Union[int, str], dict] = {}  # lod_id → mesh data
        self.matched: Dict[str, LODMatchResult] = {}  # full_vb0_hash → result

    def run(self) -> Dict[str, LODMatchResult]:
        """LOD 추출 실행"""
        start_time = time.time()
        print("=" * 60)
        print("Advanced LOD Extraction started (EFMI-Tools mode)")
        print("=" * 60)

        # 1. 원본 메타데이터 로드
        self._load_full_metadata()

        # 2. LOD 덤프 파싱
        self._load_lod_meshes()

        # 3. LOD 매칭
        self._match_lods()

        # 4. Metadata.json 업데이트 (EFMI 호환 형식)
        self._update_metadata()

        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"LOD Extraction completed in {elapsed:.1f}s")
        print(f"Matched {len(self.matched)}/{len(self.full_components)} components")
        print("=" * 60)

        return self.matched

    def _load_full_metadata(self):
        """원본 메타데이터 로드"""
        metadata_path = self.full_model_dir / "Metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata.json not found: {metadata_path}")

        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        print(f"\nLoaded metadata: {metadata.get('name', 'Unknown')}")
        print(f"Components: {len(metadata.get('components', []))}")

        # 컴포넌트 데이터 저장
        for comp_id, component in enumerate(metadata.get("components", [])):
            full_hash = component.get("vb0_hash", "")
            if full_hash:
                self.full_components[comp_id] = {
                    "hash": full_hash,
                    "data": component,
                }

    def _load_lod_meshes(self):
        """LOD 소스 로드 (덤프 폴더 또는 추출된 메쉬 폴더)"""
        print(f"\nParsing LOD source: {self.lod_dump_dir}")
        
        # 1. 이미 추출된 메쉬 폴더인지 확인 (Metadata.json 존재 여부)
        metadata_path = self.lod_dump_dir / "Metadata.json"
        if metadata_path.exists():
            print(f"  Detected extracted mesh folder (Metadata.json found)")
            self._load_extracted_lod_meshes(metadata_path)
            return

        # 2. 덤프 폴더로 파싱
        lod_meshes = parse_frame_analysis_directory(str(self.lod_dump_dir))
        print(f"  Found {len(lod_meshes)} draw calls in LOD dump")

        # 해시별로 정리
        for dc_id, mesh in lod_meshes.items():
            vb_hash = mesh.vb0_hash or mesh.vertex_shader_hash or f"{dc_id:08x}"
            if not mesh.vertices:
                continue
                
            self.lod_meshes[f"DC {dc_id:06d}"] = {
                "mesh": mesh,
                "hash": vb_hash,
                "positions": np.array([v.position for v in mesh.vertices], dtype=np.float32),
                "vg_ids": np.array([v.blendindices for v in mesh.vertices], dtype=np.uint32),
                "vg_weights": np.array([v.blendweights for v in mesh.vertices], dtype=np.float32),
            }
        print(f"  Loaded {len(self.lod_meshes)} valid meshes from dump")

    def _load_extracted_lod_meshes(self, metadata_path: Path):
        """이미 추출된 폴더에서 LOD 메쉬 로드 (EFMI-Tools 호환)"""
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            
        components = metadata.get("components", [])
        print(f"  Loading {len(components)} components from metadata")
        
        for comp_id, component in enumerate(components):
            vb_hash = component.get("vb0_hash", "")
            comp_name = f"Component {comp_id}"
            vb_path = self.lod_dump_dir / f"{comp_name}.vb"
            
            if not vb_path.exists():
                print(f"    Warning: {vb_path} not found, skipping")
                continue
                
            # 위치 데이터 로드
            positions = self._load_vb_positions(vb_path)
            if positions is None:
                print(f"    Warning: Failed to load positions for {comp_name}, skipping")
                continue
                
            # VG 데이터 로드 (필요시 - 현재는 위치 매칭 위주)
            # 일단 빈 VG 데이터 생성 (기하학 매칭용)
            self.lod_meshes[comp_name] = {
                "hash": vb_hash,
                "positions": positions,
                "vg_ids": np.zeros((len(positions), 4), dtype=np.uint32),
                "vg_weights": np.zeros((len(positions), 4), dtype=np.float32),
            }
        print(f"  Loaded {len(self.lod_meshes)} components as LOD candidates")

    def _match_lods(self):
        """LOD 매칭 실행"""
        print("\n" + "-" * 60)
        print("Starting LOD matching...")
        print(f"Similarity Threshold: {self.similarity_threshold}%")
        print(f"LOD Candidates: {len(self.lod_meshes)}")
        print("-" * 60)

        for comp_id, comp_data in sorted(self.full_components.items()):
            full_hash = comp_data["hash"]
            print(f"\n  Component {comp_id} (hash: {full_hash[:16]}...)")

            # 원본 메쉬 위치
            full_mesh_path = self.full_model_dir / f"Component {comp_id}.vb"
            if not full_mesh_path.exists():
                print(f"    ❌ VB file not found: {full_mesh_path.name}")
                continue

            # 원본 메쉬 로드
            full_positions = self._load_vb_positions(full_mesh_path)
            if full_positions is None or len(full_positions) == 0:
                print(f"    ❌ Failed to load vertex data (count: {len(full_positions) if full_positions is not None else 0})")
                continue
            
            print(f"    Vertex count: {len(full_positions)}")

            # 1단계: 해시 매칭 (빠름)
            best_result = self._match_by_hash(comp_id, full_hash, full_positions)
            if best_result:
                print(f"    ⚡ Hash match found!")
            else:
                print(f"    🔍 No hash match, trying geometry matching...")
                # 2단계: 기하학적 매칭 (정밀)
                best_result = self._match_by_geometry(comp_id, full_hash, full_positions)

            # 결과 저장
            if best_result and best_result.similarity >= self.similarity_threshold:
                self.matched[full_hash] = best_result
                print(
                    f"    ✅ Matched: {best_result.lod_name} "
                    f"(sim: {best_result.similarity:.1f}%, "
                    f"VG remapped: {sum(1 for k, v in best_result.vg_map.items() if k != v)})"
                )
            else:
                sim_text = f"{best_result.similarity:.1f}%" if best_result else "None"
                print(f"    ❌ No suitable LOD found (best similarity: {sim_text})")

    def _match_by_hash(
        self, comp_id: int, full_hash: str, full_positions: np.ndarray
    ) -> Optional[LODMatchResult]:
        """해시 기반 빠른 매칭"""
        for lod_id, lod_data in self.lod_meshes.items():
            if lod_data["hash"] == full_hash:
                # 해시 일치 - 간단 유사도 계산
                lod_positions = lod_data["positions"]

                similarity = self.geo_matcher.calculate_similarity(
                    full_positions, lod_positions
                )

                # VG 매핑
                vg_map = self._match_vg(full_positions, lod_data)

                # lod_name 형식 결정
                lod_name = str(lod_id)
                if isinstance(lod_id, int):
                    lod_name = f"DC {lod_id:06d}"

                return LODMatchResult(
                    full_vb0_hash=full_hash,
                    lod_vb0_hash=lod_data["hash"],
                    lod_name=lod_name,
                    similarity=similarity,
                    vg_map=vg_map,
                )

        return None

    def _match_by_geometry(
        self, comp_id: int, full_hash: str, full_positions: np.ndarray
    ) -> Optional[LODMatchResult]:
        """기하학적 매칭 (2단계 Prefilter)"""
        if not self.lod_meshes:
            return None

        t0 = time.time()

        # 1단계: Prefilter (빠른 필터링)
        prefilter_similarities = {}
        for dc_id, lod_data in self.lod_meshes.items():
            lod_positions = lod_data["positions"]

            # PrefilterMatcher로 빠른 유사도 계산
            similarity = self.prefilter_matcher.calculate_similarity(
                full_positions, lod_positions
            )
            prefilter_similarities[dc_id] = similarity

        # 상위 N개 후보 선택
        sorted_candidates = sorted(
            prefilter_similarities.items(), key=itemgetter(1), reverse=True
        )
        top_candidates = sorted_candidates[:min(self.prefilter_candidates_count, len(sorted_candidates))]

        if not top_candidates:
            return None

        print(f"    Prefilter: {len(prefilter_similarities)} → {len(top_candidates)} candidates")

        # 2단계: 정밀 매칭
        best_lod_id = None
        best_similarity = -1.0
        best_lod_data = None
        
        print(f"    Checking {len(top_candidates)} candidates with {self.method}...")
        for lod_id, pre_sim in top_candidates:
            lod_data = self.lod_meshes[lod_id]
            lod_positions = lod_data["positions"]

            # 정밀 유사도 계산
            similarity = self.geo_matcher.calculate_similarity(
                full_positions, lod_positions
            )
            
            print(f"      - {lod_id}: similarity {similarity:.1f}% (prefilter: {pre_sim:.1f}%)")

            if similarity > best_similarity:
                best_similarity = similarity
                best_lod_id = lod_id
                best_lod_data = lod_data

        if best_lod_id is None or best_lod_data is None:
            return None

        # VG 매핑
        vg_map = self._match_vg(full_positions, best_lod_data)

        elapsed = time.time() - t0
        print(f"    Geometry matching time: {elapsed:.2f}s")

        # lod_name 형식 결정
        lod_name = str(best_lod_id)
        if isinstance(best_lod_id, int):
            lod_name = f"DC {best_lod_id:06d}"

        return LODMatchResult(
            full_vb0_hash=full_hash,
            lod_vb0_hash=best_lod_data["hash"],
            lod_name=lod_name,
            similarity=best_similarity,
            vg_map=vg_map,
        )

    def _match_vg(self, full_positions: np.ndarray, lod_data: dict) -> Dict[int, int]:
        """VG 매칭"""
        t0 = time.time()

        vg_map = self.vg_matcher.match_vertex_groups(
            full_positions,
            lod_data["vg_ids"],
            lod_data["vg_weights"],
            lod_data["positions"],
            lod_data["vg_ids"],
            lod_data["vg_weights"],
        )

        elapsed = time.time() - t0
        print(f"    VG matching time: {elapsed:.2f}s ({sum(1 for k, v in vg_map.items() if k != v)} remapped)")

        return vg_map

    def _load_vb_positions(self, vb_path: Path) -> Optional[np.ndarray]:
        """VB 파일에서 위치 데이터 로드 (단순화: .txt 및 .fmt 지원)"""
        import struct

        # .txt 또는 .fmt 파일 찾기
        txt_path = vb_path.with_suffix(".txt")
        if not txt_path.exists():
            txt_path = vb_path.with_suffix(".fmt")
            if not txt_path.exists():
                return None

        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        stride = 0
        vertex_count = 0
        pos_offset = None

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("stride:"):
                stride = int(line.split(":")[1].strip())
            elif line.startswith("vertex count:"):
                vertex_count = int(line.split(":")[1].strip())

        if stride == 0:
            return None

        # vertex_count가 없으면 파일 크기로 계산
        if vertex_count == 0:
            vb_size = vb_path.stat().st_size
            vertex_count = vb_size // stride

        if vertex_count == 0:
            return None

        # POSITION 오프셋 찾기
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "SemanticName: POSITION" in line:
                # offset 찾기
                for j in range(i, min(i + 10, len(lines))):
                    if "AlignedByteOffset:" in lines[j]:
                        pos_offset = int(lines[j].split(":")[1].strip())
                        break
                break

        if pos_offset is None:
            return None

        with open(vb_path, "rb") as f:
            data = f.read()

        positions = np.zeros((vertex_count, 3), dtype=np.float32)
        try:
            for i in range(vertex_count):
                offset = pos_offset + i * stride
                if offset + 12 > len(data):
                    break
                pos = struct.unpack_from("<3f", data, offset)
                positions[i] = pos
        except Exception as e:
            print(f"Error unpacking VB at {vb_path}: {e}")
            return None

        return positions

    def _update_metadata(self):
        """Metadata.json 업데이트 (EFMI 호환 형식)"""
        metadata_path = self.full_model_dir / "Metadata.json"
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        # LOD 정보 추가
        for comp_id, component in enumerate(metadata.get("components", [])):
            full_hash = component.get("vb0_hash", "")

            if full_hash in self.matched:
                result = self.matched[full_hash]
                # EFMI 호환 형식: ExtractedObjectComponentLOD
                component["lods"] = [
                    {
                        "vb0_hash": result.lod_vb0_hash,
                        "vg_map": {str(k): v for k, v in result.vg_map.items()},
                    }
                ]
            elif "lods" not in component:
                component["lods"] = []

        # 저장
        output_path = self.output_dir / "Metadata.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

        print(f"\nUpdated Metadata.json: {output_path}")


def extract_lods_advanced(
    full_model_dir: str,
    lod_dump_dir: str,
    output_dir: str,
    method: str = 'VOXEL',
    similarity_threshold: float = 55.0,
    voxel_size: float = 0.01,
    sensitivity: float = 0.5,
    samples_count: int = 1000,
    prefilter_voxel_size: float = 0.05,
    prefilter_samples_count: int = 250,
    prefilter_candidates_count: int = 5,
    vg_candidates_count: int = 3,
) -> Dict[str, LODMatchResult]:
    """
    고급 LOD 추출 편의 함수

    Args:
        full_model_dir: 원본 메쉬 폴더 (Metadata.json 포함)
        lod_dump_dir: LOD 덤프 폴더
        output_dir: 출력 폴더
        method: 매칭 방법 ('VOXEL' 또는 'POINT_CLOUD')
        similarity_threshold: 유사도 임계값 (%)
        voxel_size: 복셀 크기 (정밀 매칭)
        sensitivity: 민감도
        samples_count: 샘플 수 (정밀 매칭)
        prefilter_voxel_size: Prefilter 복셀 크기
        prefilter_samples_count: Prefilter 샘플 수
        prefilter_candidates_count: Prefilter 후보 수
        vg_candidates_count: VG 매칭 후보 수

    Returns:
        매칭 결과
    """
    matcher = AdvancedLODMatcher(
        full_model_dir=full_model_dir,
        lod_dump_dir=lod_dump_dir,
        output_dir=output_dir,
        method=method,
        similarity_threshold=similarity_threshold,
        voxel_size=voxel_size,
        sensitivity=sensitivity,
        samples_count=samples_count,
        prefilter_voxel_size=prefilter_voxel_size,
        prefilter_samples_count=prefilter_samples_count,
        prefilter_candidates_count=prefilter_candidates_count,
        vg_candidates_count=vg_candidates_count,
    )
    return matcher.run()
