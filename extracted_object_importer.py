import os
import json, re
import numpy as np
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from mesh_parser import MeshData, Vertex, compute_normals_numpy
from obj_exporter import export_meshes_combined_obj

class ExtractedObjectImporter:
    """
    추출된 EFMI 오브젝트(.vb, .ib, .fmt, Metadata.json)를 불러와서
    MeshData 객체로 변환하고 OBJ로 내보내는 클래스
    """

    def __init__(self, coordinate_system: str = 'reference'):
        self.metadata = {}
        self.coordinate_system = coordinate_system

    def import_from_folder(self, folder_path: str) -> List[MeshData]:
        """폴더에서 추출된 오브젝트 로드"""
        folder = Path(folder_path)
        metadata_path = folder / "Metadata.json"
        
        # Metadata.json이 없어도 .fmt 파일들이 있으면 시도
        if not metadata_path.exists():
            print(f"Error: Metadata.json not found in {folder_path}")
            # Metadata.json이 없어도 .fmt 파일들이 있으면 시도
            fmt_files = list(folder.glob("Component *.fmt"))
            if not fmt_files:
                raise FileNotFoundError(f"No Component *.fmt files found in {folder_path}")
            
            components = []
            for fmt_file in fmt_files:
                match = re.search(r'Component (\d+)', fmt_file.name)
                if match:
                    components.append({"id": int(match.group(1))})
        else:
            with open(metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
            components = self.metadata.get("components", [])

        meshes = []
        for comp_meta in components:
            comp_id = comp_meta.get("id")
            mesh = self._load_component(folder, comp_id)
            if mesh:
                mesh.name = f"Component_{comp_id}"
                if "vb0_hash" in comp_meta:
                    mesh.name += f"_{comp_meta['vb0_hash']}"
                meshes.append(mesh)

        return meshes

    def _load_component(self, folder: Path, comp_id: int) -> Optional[MeshData]:
        """개별 컴포넌트 로드 (.fmt, .vb, .ib)"""
        fmt_path = folder / f"Component {comp_id}.fmt"
        vb_path = folder / f"Component {comp_id}.vb"
        ib_path = folder / f"Component {comp_id}.ib"

        if not (fmt_path.exists() and vb_path.exists() and ib_path.exists()):
            return None

        # 1. FMT 파싱
        fmt_info = self._parse_fmt(fmt_path)
        stride = fmt_info['stride']
        elements = fmt_info['elements']
        ib_format = fmt_info['ib_format']

        # 2. IB 로드
        with open(ib_path, "rb") as f:
            ib_data = f.read()
        
        if 'R16_UINT' in ib_format.upper():
            indices = np.frombuffer(ib_data, dtype=np.uint16)
        else:
            indices = np.frombuffer(ib_data, dtype=np.uint32)
        
        # 3. VB 로드
        with open(vb_path, "rb") as f:
            vb_data = f.read()
        
        if stride == 0:
            return None
            
        vertex_count = len(vb_data) // stride
        
        positions = np.zeros((vertex_count, 3), dtype=np.float32)
        normals = None
        texcoords = np.zeros((vertex_count, 2), dtype=np.float32)
        
        # 요소별 데이터 추출
        for elem in elements:
            name = elem.get('SemanticName', '').upper()
            offset = int(elem.get('AlignedByteOffset', 0))
            fmt = elem.get('Format', '').lower()
            
            try:
                if name == 'POSITION':
                    if 'float3' in fmt:
                        positions = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float32, (3,))
                    elif 'float4' in fmt:
                        p_data = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float32, (4,))
                        positions = p_data[:, :3]
                    elif 'half4' in fmt or 'r16g16b16a16_float' in fmt:
                        p_data = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float16, (4,))
                        positions = p_data[:, :3].astype(np.float32)
                    elif 'half3' in fmt:
                        p_data = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float16, (3,))
                        positions = p_data.astype(np.float32)
                
                elif (name == 'NORMAL' or name == 'ENCODEDDATA' or name == 'TANGENT'):
                    if 'r10g10b10a2' in fmt or '10_10_10_2' in fmt:
                        if normals is None or name == 'NORMAL':
                            packed_data = self._extract_numpy(vb_data, offset, stride, vertex_count, np.uint32, (1,))
                            normals = self._decode_10_10_10_2_batch(packed_data.flatten())
                    elif 'float3' in fmt:
                        if normals is None or name == 'NORMAL':
                            normals = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float32, (3,))

                elif name == 'TEXCOORD':
                    if 'float2' in fmt:
                        texcoords = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float32, (2,))
                    elif 'half2' in fmt or 'r16g16_float' in fmt:
                        # NumPy float16 supports 'half' (e)
                        h_data = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float16, (2,))
                        texcoords = h_data.astype(np.float32)
                    elif 'float1' in fmt:
                        # Sometimes UV is split or single
                        t_data = self._extract_numpy(vb_data, offset, stride, vertex_count, np.float32, (1,))
                        texcoords[:, 0] = t_data.flatten()
            except Exception as e:
                print(f"Warning: Failed to extract {name} from component {comp_id}: {e}")

        # 법선이 없으면 계산
        if normals is None:
            normals = compute_normals_numpy(positions, indices)

        # 메타데이터 회전 적용
        if self.metadata and 'rotation' in self.metadata:
            rot = self.metadata['rotation']
            if any(rot.get(k, 0.0) != 0.0 for k in ['x', 'y', 'z']):
                positions, normals = self._apply_rotation(positions, normals, rot)

        # MeshData 생성
        mesh = MeshData(draw_call_id=comp_id)
        mesh.indices = indices.flatten().astype(int).tolist()
        
        # Vertex 리스트 생성 (뷰어/호환성용)
        from mesh_parser import numpy_to_vertices
        mesh.vertices = numpy_to_vertices(positions, normals, texcoords)
        
        return mesh

    def _apply_rotation(self, positions: np.ndarray, normals: np.ndarray, rotation: Dict[str, float]):
        """오일러 회전 적용 (XYZ 순서, 라디안 기준)"""
        # EFMI-Tools는 라디안을 기대함
        rx = float(rotation.get('x', 0.0))
        ry = float(rotation.get('y', 0.0))
        rz = float(rotation.get('z', 0.0))
        
        # 회전 행렬 (XYZ 순서: R = Rz * Ry * Rx)
        def rotation_matrix(axis, angle):
            c = np.cos(angle)
            s = np.sin(angle)
            if axis == 'x':
                return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)
            elif axis == 'y':
                return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)
            elif axis == 'z':
                return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float32)
            return np.eye(3, dtype=np.float32)

        R = rotation_matrix('z', rz) @ rotation_matrix('y', ry) @ rotation_matrix('x', rx)
        
        new_positions = positions @ R.T
        new_normals = normals @ R.T
        
        return new_positions, new_normals

    def _extract_numpy(self, buffer: bytes, offset: int, stride: int, count: int, dtype: Any, shape: tuple):
        """바이너리 버퍼에서 NumPy 스트라이드 뷰를 사용하여 데이터 추출"""
        dtype_item = np.dtype(dtype)
        item_size = dtype_item.itemsize * np.prod(shape)
        
        # np.ndarray를 직접 사용하면 메모리 복사 없이 효율적임
        # 하지만 stride가 아이템 크기보다 클 경우 copy()가 필요할 수 있음
        arr = np.ndarray(
            shape=(count, *shape),
            dtype=dtype,
            buffer=buffer,
            offset=offset,
            strides=(stride, dtype_item.itemsize)
        )
        return arr.copy()

    def _parse_fmt(self, fmt_path: Path) -> Dict[str, Any]:
        """.fmt 파일 파싱"""
        info = {'stride': 0, 'ib_format': 'DXGI_FORMAT_R16_UINT', 'elements': []}
        try:
            with open(fmt_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(fmt_path, "r", encoding="cp949", errors="ignore") as f:
                lines = f.readlines()
            
        current_elem = None
        for line in lines:
            line = line.strip()
            if not line: continue
            
            if line.startswith('stride:'):
                info['stride'] = int(line.split(':')[1].strip())
            elif line.startswith('format:'):
                info['ib_format'] = line.split(':')[1].strip()
            elif line.startswith('element['):
                current_elem = {}
                info['elements'].append(current_elem)
            elif current_elem is not None and ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    key, val = parts
                    current_elem[key.strip()] = val.strip()
        
        return info

    def _decode_10_10_10_2_batch(self, packed_array: np.ndarray) -> np.ndarray:
        """10-10-10-2 일괄 디코딩 (NumPy 최적화)"""
        x = packed_array & 0x3FF
        y = (packed_array >> 10) & 0x3FF
        z = (packed_array >> 20) & 0x3FF
        
        # Sign extension
        x = np.where(x >= 512, x - 1024, x).astype(np.float32)
        y = np.where(y >= 512, y - 1024, y).astype(np.float32)
        z = np.where(z >= 512, z - 1024, z).astype(np.float32)
        
        scale = 1.0 / 511.0
        decoded = np.stack([x * scale, y * scale, z * scale], axis=1)
        
        # 정규화 (법선인 경우 필수)
        norms = np.linalg.norm(decoded, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-8)
        return decoded / norms

    def export_combined(self, meshes: List[MeshData], output_path: str):
        """여러 MeshData를 하나의 OBJ로 결합하여 내보냄"""
        if not meshes:
            return []
        
        mesh_dict = {m.draw_call_id: m for m in meshes}
        return export_meshes_combined_obj(mesh_dict, output_path, coord_system=self.coordinate_system)

    def export_individual(self, meshes: List[MeshData], output_dir: str):
        """여러 MeshData를 각각의 OBJ 파일로 내보냄"""
        if not meshes:
            return []
        
        mesh_dict = {m.draw_call_id: m for m in meshes}
        from obj_exporter import export_all_meshes_to_obj
        return export_all_meshes_to_obj(mesh_dict, output_dir, coord_system=self.coordinate_system)

