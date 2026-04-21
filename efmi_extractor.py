"""
EFMI 호환 오브젝트 추출 모듈

FrameAnalysis 덤프에서 EFMI-Tools 호환 형식으로 추출:
- Component .vb, .ib, .fmt 파일 생성
- Metadata.json 생성 (vb0_hash, VG 정보 포함)
- LOD 매칭 준비 완료
"""

import os
import re
import json
import struct
import hashlib
import time
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from mesh_parser import (
    parse_vertex_buffer_txt,
    parse_index_buffer_txt,
    extract_vertices_numpy,
    extract_indices_numpy,
)


@dataclass
class BufferInfo:
    """버퍼 정보"""
    dc_id: int
    buf_path: Path
    txt_path: Path
    vb_slot: Optional[int] = None  # VB 슬롯 번호 (0, 1, 2)
    vb_hash: str = ""  # VB0 해시


@dataclass
class DrawCallInfo:
    """드로우 콜 정보"""
    dc_id: int
    vs_hash: str = ""
    ps_hash: str = ""
    ib_hash: str = ""
    vb0_hash: str = ""
    vb0_parent_hash: str = ""
    vertex_count: int = 0
    index_count: int = 0
    buffers: Dict[str, BufferInfo] = field(default_factory=dict)  # slot → BufferInfo


@dataclass
class EFMIComponent:
    """EFMI 컴포넌트"""
    component_id: int
    vb0_hash: str
    ib_hash: str
    vertex_count: int
    index_count: int
    vg_count: int
    vb_data: Optional[bytes] = None
    ib_data: Optional[bytes] = None
    fmt_text: str = ""
    positions: Optional[np.ndarray] = None  # LOD 매칭용


@dataclass
class EFMIObject:
    """EFMI 오브젝트 (여러 컴포넌트 포함)"""
    object_id: str  # "Character 12345" or "Weapon 6789"
    vb0_hash: str  # 대표 VB0 해시
    components: List[EFMIComponent] = field(default_factory=list)
    total_vertices: int = 0
    total_indices: int = 0


class EFMIExtractor:
    """EFMI 호환 오브젝트 추출기"""

    def __init__(self, dump_dir: str, output_dir: str):
        """
        Args:
            dump_dir: FrameAnalysis 덤프 폴더
            output_dir: 추출 결과 저장 폴더
        """
        self.dump_dir = Path(dump_dir)
        self.output_dir = Path(output_dir)
        self.draw_calls: Dict[int, DrawCallInfo] = {}
        self.objects: List[EFMIObject] = []

    def run(self) -> List[EFMIObject]:
        """추출 실행"""
        start_time = time.time()
        print("=" * 60)
        print("EFMI Object Extraction started")
        print("=" * 60)

        # 1. FrameAnalysis 덤프 파싱
        print("\n[1/4] Parsing FrameAnalysis dump...")
        self._parse_dump()
        print(f"  Found {len(self.draw_calls)} draw calls")

        # 2. VB0 해시 기준으로 그룹화
        print("\n[2/4] Grouping by VB0 hash...")
        objects_data = self._group_by_vb0_hash()
        print(f"  Found {len(objects_data)} unique objects")

        # 3. 컴포넌트 생성 및 파일 저장
        print("\n[3/4] Extracting components...")
        self._extract_components(objects_data)
        print(f"  Extracted {sum(len(obj.components) for obj in self.objects)} components")

        # 4. Metadata.json 생성
        print("\n[4/4] Generating Metadata.json...")
        self._save_metadata()

        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"Extraction completed in {elapsed:.1f}s")
        print(f"Output: {self.output_dir}")
        print(f"Objects: {len(self.objects)}")
        print("=" * 60)

        return self.objects

    def _parse_dump(self):
        """FrameAnalysis 덤프 파싱"""
        files = os.listdir(self.dump_dir)

        # 파일 그룹화 by draw call ID
        dc_files: Dict[int, Dict[str, Path]] = defaultdict(dict)

        for filename in files:
            if not filename.endswith('.txt'):
                continue

            # Draw call ID 추출
            match = re.match(r'(\d+)-', filename)
            if not match:
                continue

            dc_id = int(match.group(1))

            if '-ib=' in filename:
                dc_files[dc_id]['ib'] = Path(filename.replace('.txt', '.buf'))
            elif '-vb' in filename:
                vb_match = re.search(r'-vb(\d+)=', filename)
                if vb_match:
                    slot = int(vb_match.group(1))
                    dc_files[dc_id][f'vb{slot}'] = Path(filename.replace('.txt', '.buf'))

        print(f"  Found {len(dc_files)} draw calls with .txt files")

        # 각 draw call 처리
        for dc_id, file_dict in dc_files.items():
            dc = DrawCallInfo(dc_id=dc_id)

            # IB 파일
            if 'ib' in file_dict:
                ib_buf = self.dump_dir / file_dict['ib']
                ib_txt = ib_buf.with_suffix('.txt')
                if ib_buf.exists() and ib_txt.exists():
                    # IB 메타데이터 파싱
                    try:
                        ib_info = parse_index_buffer_txt(str(ib_txt))
                        dc.index_count = ib_info.index_count
                        dc.buffers['IB'] = BufferInfo(
                            dc_id=dc_id,
                            buf_path=ib_buf,
                            txt_path=ib_txt,
                        )
                    except Exception as e:
                        print(f"  Warning: Failed to parse IB for DC {dc_id}: {e}")

            # VB 파일 (슬롯 0, 1, 2)
            for slot in [0, 1, 2]:
                vb_key = f'vb{slot}'
                if vb_key in file_dict:
                    vb_buf = self.dump_dir / file_dict[vb_key]
                    vb_txt = vb_buf.with_suffix('.txt')
                    if vb_buf.exists() and vb_txt.exists():
                        try:
                            vb_info = parse_vertex_buffer_txt(str(vb_txt))
                            if slot == 0:
                                dc.vertex_count = vb_info.vertex_count

                            dc.buffers[f'VB{slot}'] = BufferInfo(
                                dc_id=dc_id,
                                buf_path=vb_buf,
                                txt_path=vb_txt,
                                vb_slot=slot,
                            )
                        except Exception as e:
                            print(f"  Warning: Failed to parse VB{slot} for DC {dc_id}: {e}")

            # 해시 추출 (각 파일명에서)
            # IB 파일에서 VS/PS 해시 추출
            ib_filename = file_dict.get('ib', '')
            if ib_filename:
                ib_name = str(ib_filename)
                vs_match = re.search(r'-vs=([a-f0-9]+)', ib_name)
                ps_match = re.search(r'-ps=([a-f0-9]+)', ib_name)
                ib_hash_match = re.search(r'-ib=([a-f0-9]+)', ib_name)
                
                if vs_match:
                    dc.vs_hash = vs_match.group(1)
                if ps_match:
                    dc.ps_hash = ps_match.group(1)
                if ib_hash_match:
                    dc.ib_hash = ib_hash_match.group(1)
            
            # VB0 파일에서 VB0 해시 및 Parent 해시 추출
            vb0_filename = file_dict.get('vb0', '')
            if vb0_filename:
                vb0_name = str(vb0_filename)
                # 패턴: -vb0=HASH(PARENT) 또는 -vb0=HASH
                vb0_hash_match = re.search(r'-vb0=([a-f0-9]+)', vb0_name)
                vb0_parent_match = re.search(r'-vb0=[a-f0-9]+\(([a-f0-9]+)\)', vb0_name)
                
                if vb0_hash_match:
                    dc.vb0_hash = vb0_hash_match.group(1)
                if vb0_parent_match:
                    dc.vb0_parent_hash = vb0_parent_match.group(1)

            self.draw_calls[dc_id] = dc

        # 디버깅: 파싱 결과 출력
        vb0_count = sum(1 for dc in self.draw_calls.values() if dc.vb0_hash and 'VB0' in dc.buffers)
        print(f"  Parsed {len(self.draw_calls)} draw calls total")
        print(f"  Found {vb0_count} draw calls with VB0 + hash")
        
        # 샘플 출력
        for dc_id, dc in sorted(self.draw_calls.items())[:3]:
            print(f"    DC {dc_id:06d}: VB0={dc.vb0_hash[:8] if dc.vb0_hash else 'N/A'}, "
                  f"Parent={dc.vb0_parent_hash[:8] if dc.vb0_parent_hash else 'N/A'}, "
                  f"Verts={dc.vertex_count}")

    def _group_by_vb0_hash(self) -> Dict[str, List[DrawCallInfo]]:
        """VB0 해시 기준으로 Draw Call 그룹화"""
        groups: Dict[str, List[DrawCallInfo]] = defaultdict(list)

        for dc_id, dc in sorted(self.draw_calls.items()):
            if dc.vb0_hash and 'VB0' in dc.buffers:
                groups[dc.vb0_hash].append(dc)

        return groups

    def _extract_components(self, objects_data: Dict[str, List[DrawCallInfo]]):
        """컴포넌트 추출 및 파일 저장 (모든 파일을 출력 폴더에 한번에)"""
        # 출력 폴더 생성
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 글로벌 컴포넌트 ID (여러 오브젝트 통합)
        global_comp_id = 0
        
        for vb0_hash, draw_calls in objects_data.items():
            if not draw_calls:
                continue

            # 오브젝트 ID 결정 (최대 Z 기준으로 정렬)
            sorted_dcs = self._sort_dcs_by_position(draw_calls)
            object_id = self._determine_object_id(sorted_dcs)

            # 오브젝트 생성
            efm_obj = EFMIObject(
                object_id=object_id,
                vb0_hash=vb0_hash,
            )

            # 컴포넌트 추출
            for dc in sorted_dcs:
                component = self._extract_component(global_comp_id, dc)
                if component:
                    efm_obj.components.append(component)
                    efm_obj.total_vertices += component.vertex_count
                    efm_obj.total_indices += component.index_count
                    global_comp_id += 1  # 글로벌 ID 증가

            if efm_obj.components:
                self.objects.append(efm_obj)
        
        print(f"  Saved all components to: {self.output_dir}")

    def _sort_dcs_by_position(self, draw_calls: List[DrawCallInfo]) -> List[DrawCallInfo]:
        """Draw Call을 Z 기준으로 정렬 (높은 Z가 먼저)"""
        dc_with_z = []

        for dc in draw_calls:
            vb0_buf = dc.buffers.get('VB0')
            if vb0_buf:
                try:
                    positions = extract_vertices_numpy(
                        str(vb0_buf.buf_path),
                        str(vb0_buf.txt_path),
                        target_slot=0,
                    ).get('POSITION')

                    if positions is not None and len(positions) > 0:
                        max_z = float(positions[:, 2].max())
                        dc_with_z.append((max_z, dc))
                    else:
                        dc_with_z.append((0.0, dc))
                except Exception:
                    dc_with_z.append((0.0, dc))
            else:
                dc_with_z.append((0.0, dc))

        # Z 기준으로 내림차순 정렬
        dc_with_z.sort(key=lambda x: x[0], reverse=True)
        return [dc for _, dc in dc_with_z]

    def _determine_object_id(self, sorted_dcs: List[DrawCallInfo]) -> str:
        """오브젝트 ID 결정 (Character/Weapon 구분)"""
        if not sorted_dcs:
            return "Unknown"

        # 첫 번째 DC의 VB0 Parent 해시로 판별
        first_dc = sorted_dcs[0]

        # VB0 Parent 해시가 특정 패턴이면 Weapon으로 판단
        # (실제 게임 데이터에 따라 조정 필요)
        if first_dc.vb0_parent_hash in ['1d6a6186']:
            # Weapon 패턴 (예시)
            total_verts = sum(dc.vertex_count for dc in sorted_dcs)
            return f"Weapon {total_verts}"
        else:
            total_verts = sum(dc.vertex_count for dc in sorted_dcs)
            return f"Character {total_verts}"

    def _read_slot_data(self, buf_info: BufferInfo, expected_vertex_count: int) -> Optional[Tuple[bytes, int]]:
        """
        특정 VB 슬롯의 바이너리 데이터를 읽기
        
        Returns:
            (raw_data, stride) 또는 None
        """
        try:
            slot_info = parse_vertex_buffer_txt(str(buf_info.txt_path))
            # 해당 슬롯의 stride 계산 (슬롯별 element의 byte_size 합)
            slot_stride = slot_info.stride
            file_size = os.path.getsize(buf_info.buf_path)
            expected_size = slot_stride * expected_vertex_count

            with open(buf_info.buf_path, 'rb') as f:
                if file_size >= slot_info.byte_offset + expected_size:
                    f.seek(slot_info.byte_offset)
                    data = f.read(expected_size)
                else:
                    f.seek(0)
                    data = f.read(file_size)

            return data, slot_stride
        except Exception as e:
            print(f"  Warning: Failed to read slot data: {e}")
            return None

    def _merge_vb_slots(self, dc: DrawCallInfo) -> Tuple[bytes, int, list]:
        """
        VB0 + VB1 + VB2를 하나의 인터리빙된 VB로 병합
        
        Returns:
            (merged_data, merged_stride, merged_elements)
        """
        vb0_buf = dc.buffers.get('VB0')
        vb0_info = parse_vertex_buffer_txt(str(vb0_buf.txt_path))
        vertex_count = vb0_info.vertex_count

        # 각 슬롯의 데이터와 stride 수집
        slot_data = {}  # slot -> (data, stride)
        slot_strides = {}  # slot -> stride

        for slot_key in ['VB0', 'VB1', 'VB2']:
            buf_info = dc.buffers.get(slot_key)
            if buf_info:
                result = self._read_slot_data(buf_info, vertex_count)
                if result:
                    slot_num = int(slot_key[2])  # 'VB0' -> 0
                    slot_data[slot_num] = result
                    slot_strides[slot_num] = result[1]

        # 병합 stride 계산
        merged_stride = sum(slot_strides.get(s, 0) for s in sorted(slot_data.keys()))

        # 각 슬롯의 element를 수집하고 offset 재계산
        merged_elements = []
        cumulative_offset = 0

        for slot_num in sorted(slot_data.keys()):
            slot_key = f'VB{slot_num}'
            buf_info = dc.buffers.get(slot_key)
            if not buf_info:
                continue

            slot_info = parse_vertex_buffer_txt(str(buf_info.txt_path))

            for elem in slot_info.elements:
                if elem.input_slot != slot_num:
                    continue
                # 새 element를 만들되, InputSlot=0, offset 재계산
                new_elem = type(elem)(
                    semantic_name=elem.semantic_name,
                    semantic_index=elem.semantic_index,
                    format_type=elem.format_type,
                    byte_size=elem.byte_size,
                    struct_fmt=elem.struct_fmt,
                    input_slot=0,  # 모두 slot 0으로 통합
                    byte_offset=cumulative_offset + elem.byte_offset,
                )
                merged_elements.append(new_elem)

            cumulative_offset += slot_strides[slot_num]

        # vertex 단위로 인터리빙
        merged_bytes = bytearray()
        for v_idx in range(vertex_count):
            for slot_num in sorted(slot_data.keys()):
                data, stride = slot_data[slot_num]
                start = v_idx * stride
                end = start + stride
                if end <= len(data):
                    merged_bytes.extend(data[start:end])
                else:
                    # 데이터 부족 시 0으로 채움
                    merged_bytes.extend(b'\x00' * stride)

        return bytes(merged_bytes), merged_stride, merged_elements

    def _extract_component(self, comp_id: int, dc: DrawCallInfo) -> Optional[EFMIComponent]:
        """단일 컴포넌트 추출 (VB0+VB1+VB2 병합)"""
        vb0_buf = dc.buffers.get('VB0')
        ib_buf = dc.buffers.get('IB')

        if not vb0_buf or not ib_buf:
            return None

        try:
            # VB 슬롯 병합 (VB0 + VB1 + VB2 → 단일 인터리빙 VB)
            vb_data, merged_stride, merged_elements = self._merge_vb_slots(dc)

            # IB 파일 읽기
            with open(ib_buf.buf_path, 'rb') as f:
                ib_info = parse_index_buffer_txt(str(ib_buf.txt_path))
                byte_size = 2  # uint16
                expected_size = byte_size * ib_info.index_count
                file_size = os.path.getsize(ib_buf.buf_path)

                if ib_buf.buf_path.stat().st_size >= ib_info.byte_offset + expected_size:
                    f.seek(ib_info.byte_offset)
                    ib_data = f.read(expected_size)
                else:
                    f.seek(0)
                    ib_data = f.read(file_size)

            # FMT 텍스트 생성 (병합된 레이아웃 기준)
            vb0_info = parse_vertex_buffer_txt(str(vb0_buf.txt_path))
            fmt_text = self._generate_fmt_merged(
                merged_stride, merged_elements, vb0_info.topology, ib_info
            )

            # POSITION 추출 (LOD 매칭용)
            positions = extract_vertices_numpy(
                str(vb0_buf.buf_path),
                str(vb0_buf.txt_path),
                target_slot=0,
            ).get('POSITION')

            # VG 수 계산 (VB2에서)
            vg_count = self._calculate_vg_count_from_dc(dc)

            component = EFMIComponent(
                component_id=comp_id,
                vb0_hash=dc.vb0_hash,
                ib_hash=dc.ib_hash,
                vertex_count=dc.vertex_count,
                index_count=dc.index_count,
                vg_count=vg_count,
                vb_data=vb_data,
                ib_data=ib_data,
                fmt_text=fmt_text,
                positions=positions,
            )

            # 파일 저장
            self._save_component_files(comp_id, component)

            return component

        except Exception as e:
            print(f"  Warning: Failed to extract component {comp_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_fmt_merged(self, merged_stride: int, merged_elements: list,
                             topology: str, ib_info) -> str:
        """병합된 VB 레이아웃 기준 FMT 텍스트 생성"""
        fmt_lines = []
        fmt_lines.append(f"stride: {merged_stride}")
        fmt_lines.append(f"topology: {topology}")

        # IB 포맷
        ib_format = "DXGI_FORMAT_R16_UINT"
        fmt_lines.append(f"format: {ib_format}")

        # VB 요소 (모두 InputSlot=0)
        for i, elem in enumerate(merged_elements):
            fmt_lines.append(f"element[{i}]:")
            fmt_lines.append(f"  SemanticName: {elem.semantic_name}")
            fmt_lines.append(f"  SemanticIndex: {elem.semantic_index}")
            fmt_lines.append(f"  Format: {elem.format_type}")
            fmt_lines.append(f"  InputSlot: 0")
            fmt_lines.append(f"  AlignedByteOffset: {elem.byte_offset}")
            fmt_lines.append(f"  InputSlotClass: per-vertex")
            fmt_lines.append(f"  InstanceDataStepRate: 0")

        return "\n".join(fmt_lines) + "\n"

    def _calculate_vg_count(self, vb0_buf: BufferInfo) -> int:
        """VG 수 계산 (BLENDINDICES에서) - 하위 호환용"""
        try:
            vb_data = extract_vertices_numpy(
                str(vb0_buf.buf_path),
                str(vb0_buf.txt_path),
                target_slot=0,
            )

            blendindices = vb_data.get('BLENDINDICES')
            if blendindices is not None:
                return int(blendindices.max()) + 1
        except Exception:
            pass

        return 0

    def _calculate_vg_count_from_dc(self, dc: DrawCallInfo) -> int:
        """VG 수 계산 - Draw Call의 VB2 슬롯에서 BLENDINDICES 추출"""
        # VB2에서 BLENDINDICES 추출 시도
        vb2_buf = dc.buffers.get('VB2')
        if vb2_buf:
            try:
                vb_data = extract_vertices_numpy(
                    str(vb2_buf.buf_path),
                    str(vb2_buf.txt_path),
                    target_slot=2,
                )
                blendindices = vb_data.get('BLENDINDICES')
                if blendindices is not None:
                    return int(blendindices.max()) + 1
            except Exception:
                pass

        # VB0에서도 시도 (일부 모델은 단일 VB)
        vb0_buf = dc.buffers.get('VB0')
        if vb0_buf:
            return self._calculate_vg_count(vb0_buf)

        return 0

    def _save_component_files(self, comp_id: int, component: EFMIComponent):
        """컴포넌트 파일 저장 (.vb, .ib, .fmt) - 출력 폴더에 직접 저장"""
        # VB 파일
        vb_path = self.output_dir / f"Component {comp_id}.vb"
        with open(vb_path, 'wb') as f:
            f.write(component.vb_data)

        # IB 파일
        ib_path = self.output_dir / f"Component {comp_id}.ib"
        with open(ib_path, 'wb') as f:
            f.write(component.ib_data)

        # FMT 파일
        fmt_path = self.output_dir / f"Component {comp_id}.fmt"
        with open(fmt_path, 'w', encoding='utf-8') as f:
            f.write(component.fmt_text)

    def _save_metadata(self):
        """Metadata.json 저장 (EFMI 호환 형식)"""
        if not self.objects:
            return

        metadata = {
            "hash": self.objects[0].vb0_hash[:16] if self.objects else "unknown",
            "name": self.objects[0].object_id if self.objects else "Unknown",
            "vertex_count": sum(obj.total_vertices for obj in self.objects),
            "index_count": sum(obj.total_indices for obj in self.objects),
            "rotation": {"x": 0, "y": 0, "z": 0},
            "components": [],
            "shapekeys": {
                "offsets_hash": "",
                "shapekey_offsets": [],
            },
            "export_format": {
                "Position": {
                    "semantics": [{"name": "POSITION", "format": "R32G32B32_FLOAT"}]
                },
                "TexCoord": {
                    "semantics": [{"name": "TEXCOORD", "format": "R32G32_FLOAT"}]
                },
                "Blend": {
                    "semantics": [
                        {"name": "BLENDWEIGHTS", "format": "R16_UNORM"},
                        {"name": "BLENDINDICES", "format": "R8_UINT"},
                    ]
                },
            },
        }

        for obj in self.objects:
            for comp in obj.components:
                component_data = {
                    "id": comp.component_id,
                    "vb0_hash": comp.vb0_hash,
                    "ib_hash": comp.ib_hash,
                    "vertex_count": comp.vertex_count,
                    "index_count": comp.index_count,
                    "vg_count": comp.vg_count,
                    "vg_map": {},
                    "lods": [],  # LOD는 별도 추출
                }
                metadata["components"].append(component_data)

        # 저장
        metadata_path = self.output_dir / "Metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

        print(f"  Saved: {metadata_path}")


def extract_efmi_objects(
    dump_dir: str,
    output_dir: str,
) -> List[EFMIObject]:
    """
    EFMI 호환 오브젝트 추출 편의 함수

    Args:
        dump_dir: FrameAnalysis 덤프 폴더
        output_dir: 출력 폴더

    Returns:
        추출된 오브젝트 목록
    """
    extractor = EFMIExtractor(
        dump_dir=dump_dir,
        output_dir=output_dir,
    )
    return extractor.run()
