"""
OBJ 파일 직접 변환 스크립트
Mesh_000013.obj, Mesh_000014.obj를 다음 순서로 변환:

1. 지오메트리 중심으로 오리진 설정 (모든 정점에서 중심값 빼기)
2. 위치 이동: Y +1.485m, Z +0.055m
"""

import os


def read_obj(filepath):
    """OBJ 파일에서 정점 데이터 읽기"""
    vertices = []
    normals = []
    texcoords = []
    faces = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if parts[0] == 'v':
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == 'vn':
                normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == 'vt':
                texcoords.append((float(parts[1]), float(parts[2])))
            elif parts[0] == 'f':
                faces.append(line)

    return vertices, normals, texcoords, faces


def write_obj(filepath, vertices, normals, texcoords, faces, header_comment=""):
    """OBJ 파일 저장"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(header_comment)
        f.write("\n")

        # 정점
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        f.write("\n")

        # 법선
        for n in normals:
            f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")

        f.write("\n")

        # UV
        for vt in texcoords:
            f.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")

        f.write("\n")

        # 페이스
        for face in faces:
            f.write(f"{face}\n")


def set_origin_to_geometry(vertices):
    """지오메트리 중심으로 오리진 설정 (바운딩 박스 중심)"""
    # 바운딩 박스 계산
    min_x = min(v[0] for v in vertices)
    max_x = max(v[0] for v in vertices)
    min_y = min(v[1] for v in vertices)
    max_y = max(v[1] for v in vertices)
    min_z = min(v[2] for v in vertices)
    max_z = max(v[2] for v in vertices)

    # 중심점 계산
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    center_z = (min_z + max_z) / 2.0

    print(f"  지오메트리 중심: ({center_x:.6f}, {center_y:.6f}, {center_z:.6f})")

    # 모든 정점에서 중심값 빼기
    new_vertices = []
    for v in vertices:
        new_vertices.append((
            v[0] - center_x,
            v[1] - center_y,
            v[2] - center_z
        ))

    return new_vertices


def translate_vertices(vertices, delta_x=0.0, delta_y=0.0, delta_z=0.0):
    """정점 위치 이동"""
    new_vertices = []
    for v in vertices:
        new_vertices.append((
            v[0] + delta_x,
            v[1] + delta_y,
            v[2] + delta_z
        ))
    return new_vertices


def process_obj(filepath):
    """OBJ 파일 변환 처리"""
    filename = os.path.basename(filepath)
    print(f"\n처리 중: {filename}")
    print("=" * 60)

    # 1. OBJ 파일 읽기
    print("[1/4] OBJ 파일 읽는 중...")
    vertices, normals, texcoords, faces = read_obj(filepath)
    print(f"  정점: {len(vertices)}개, 페이스: {len(faces)}개")

    # 2. 지오메트리 중심으로 오리진 설정
    print("[2/4] 오리진을 지오메트리로 설정 중...")
    vertices = set_origin_to_geometry(vertices)

    # 3. 위치 이동 (Y: +1.485, Z: +0.055)
    print("[3/4] 위치 이동 적용 중...")
    vertices = translate_vertices(vertices, delta_y=1.485, delta_z=0.055)
    print(f"  이동 완료: Y +1.485, Z +0.055")

    # 4. 파일 저장 (원본 덮어쓰기)
    print("[4/4] 파일 저장 중...")
    header = f"# Modified: Origin to Geometry + Translate Y:1.485 Z:0.055\n# Original: {filename}"
    write_obj(filepath, vertices, normals, texcoords, faces, header)
    print(f"  저장 완료: {filepath}")

    print("=" * 60)


def main():
    # 처리할 OBJ 파일 목록
    obj_files = [
        r"C:\Users\yein\PycharmProjects\엔드필드메쉬추출시도4\Extracted_Meshes\Mesh_000013.obj",
        r"C:\Users\yein\PycharmProjects\엔드필드메쉬추출시도4\Extracted_Meshes\Mesh_000014.obj",
    ]

    print("=" * 60)
    print("OBJ 파일 직접 변환")
    print("=" * 60)
    print("변환 순서:")
    print("  1. 오리진 → 지오메트리 중심")
    print("  2. 위치 이동: Y +1.485m, Z +0.055m")
    print()

    for obj_file in obj_files:
        if os.path.exists(obj_file):
            process_obj(obj_file)
        else:
            print(f"\n[경고] 파일을 찾을 수 없습니다: {obj_file}")

    print("\n" + "=" * 60)
    print("모든 변환 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
