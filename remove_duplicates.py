"""
중복 메쉬 제거 도구
MeshData에서 중복된 메쉬를 감지하고 제거

중복 판별 기준:
1. 동일한 vertex position (모든 버텍스 위치가 정확히 일치)
2. 동일한 index 패턴
3. 동일한 vertex 수와 index 수
"""

import numpy as np
from mesh_parser import MeshData


def get_mesh_fingerprint(mesh: MeshData) -> str:
    """
    메쉬의 고유 지문 생성
    vertex positions와 indices를 기반으로 해시 생성
    """
    if not mesh.vertices or not mesh.indices:
        return ""
    
    # vertex positions를 플랫한 배열로 변환
    positions = []
    for v in mesh.vertices:
        positions.extend(v.position)
    
    # indices도 포함
    indices = mesh.indices
    
    # numpy 배열로 변환하여 바이트로 직렬화
    pos_array = np.array(positions, dtype=np.float32)
    idx_array = np.array(indices, dtype=np.uint32)
    
    # 해시 생성 (positions + indices 조합)
    combined = np.concatenate([pos_array, idx_array])
    
    # MD5 해시로 지문 생성
    import hashlib
    hash_obj = hashlib.md5(combined.tobytes())
    return hash_obj.hexdigest()


def find_duplicate_meshes(meshes: dict[int, MeshData]) -> dict[str, list[int]]:
    """
    중복 메쉬 찾기
    
    Returns:
        fingerprint -> [dc_id, dc_id, ...] 매핑
        (여러 dc_id가 같은 fingerprint를 가지면 중복)
    """
    fingerprint_map = {}
    
    for dc_id, mesh in meshes.items():
        fp = get_mesh_fingerprint(mesh)
        if fp:
            if fp not in fingerprint_map:
                fingerprint_map[fp] = []
            fingerprint_map[fp].append(dc_id)
    
    # 중복만 필터링
    duplicates = {fp: dc_ids for fp, dc_ids in fingerprint_map.items() if len(dc_ids) > 1}
    
    return duplicates


def remove_duplicate_meshes(meshes: dict[int, MeshData], keep_first: bool = True) -> tuple[dict[int, MeshData], list[int]]:
    """
    중복 메쉬 제거
    
    Args:
        meshes: 메쉬 데이터 딕셔너리
        keep_first: True면 중복 중 첫 번째 메쉬 유지, False면 마지막 메쉬 유지
    
    Returns:
        (정리된 meshes, 제거된 dc_id 목록)
    """
    duplicates = find_duplicate_meshes(meshes)
    
    if not duplicates:
        print("중복된 메쉬가 없습니다.")
        return meshes, []
    
    removed_ids = []
    meshes_to_remove = set()
    
    print(f"\n중복 메쉬 감지: {len(duplicates)}개 그룹")
    print("=" * 80)
    
    for fp, dc_ids in duplicates.items():
        print(f"\n중복 그룹 ({len(dc_ids)}개 메쉬):")
        for dc_id in dc_ids:
            mesh = meshes[dc_id]
            print(f"  - DC {dc_id:06d}: {mesh.name} ({len(mesh.vertices)} vertices, {len(mesh.indices)//3} faces)")
        
        # 유지할 메쉬 선택
        if keep_first:
            keep_ids = [dc_ids[0]]
            remove_ids = dc_ids[1:]
        else:
            keep_ids = [dc_ids[-1]]
            remove_ids = dc_ids[:-1]
        
        print(f"  → 유지: DC {keep_ids[0]:06d}")
        print(f"  → 제거: {', '.join(f'DC {dc_id:06d}' for dc_id in remove_ids)}")
        
        meshes_to_remove.update(remove_ids)
        removed_ids.extend(remove_ids)
    
    # 중복 메쉬 제거
    cleaned_meshes = {dc_id: mesh for dc_id, mesh in meshes.items() if dc_id not in meshes_to_remove}
    
    print(f"\n{'=' * 80}")
    print(f"결과: {len(meshes)}개 → {len(cleaned_meshes)}개 메쉬 ({len(removed_ids)}개 제거)")
    
    return cleaned_meshes, sorted(removed_ids)


def print_mesh_statistics(meshes: dict[int, MeshData]):
    """메쉬 통계 정보 출력"""
    if not meshes:
        print("메쉬가 없습니다.")
        return
    
    total_vertices = sum(len(m.vertices) for m in meshes.values())
    total_faces = sum(len(m.indices) // 3 for m in meshes.values())
    
    print(f"\n메쉬 통계:")
    print(f"  총 메쉬 수: {len(meshes)}개")
    print(f"  총 버텍스 수: {total_vertices:,}")
    print(f"  총 페이스 수: {total_faces:,}")
    
    # VB0 parent 해시별 그룹화
    parent_groups = {}
    for dc_id, mesh in meshes.items():
        parent = mesh.vb0_parent_hash or "unknown"
        if parent not in parent_groups:
            parent_groups[parent] = []
        parent_groups[parent].append(dc_id)
    
    if len(parent_groups) > 1:
        print(f"\nVB0 Parent 해시별 그룹:")
        for parent, dc_ids in sorted(parent_groups.items()):
            print(f"  {parent}: {len(dc_ids)}개 메쉬")


if __name__ == "__main__":
    import sys
    import os
    
    # 커맨드라인에서 디렉토리 경로 받기
    if len(sys.argv) < 2:
        print("사용법: python remove_duplicates.py <FrameAnalysis 디렉토리 경로>")
        sys.exit(1)
    
    directory = sys.argv[1]
    
    if not os.path.exists(directory):
        print(f"오류: 디렉토리를 찾을 수 없습니다: {directory}")
        sys.exit(1)
    
    # 메쉬 파싱
    from mesh_parser import parse_frame_analysis_directory
    print(f"메쉬 로딩 중: {directory}")
    meshes = parse_frame_analysis_directory(directory)
    print(f"{len(meshes)}개 메쉬 로드 완료")
    
    # 통계 출력
    print_mesh_statistics(meshes)
    
    # 중복 제거
    print("\n" + "=" * 80)
    cleaned, removed = remove_duplicate_meshes(meshes, keep_first=True)
    
    # 결과 통계
    print_mesh_statistics(cleaned)
    
    # 제거된 메쉬 목록 저장
    if removed:
        output_file = os.path.join(directory, "removed_duplicates.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# 제거된 중복 메쉬 목록\n")
            f.write(f"# 총 {len(removed)}개 메쉬 제거\n\n")
            for dc_id in removed:
                f.write(f"DC {dc_id:06d}\n")
        print(f"\n제거된 메쉬 목록 저장: {output_file}")
