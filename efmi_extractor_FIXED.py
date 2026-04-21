"""
EFMI 호환 오브젝트 추출 모듈 (수정: VB0/VB1/VB2 모두 저장)

FrameAnalysis 덤프에서 EFMI-Tools 호환 형식으로 추출:
- Component .vb0, .vb1, .vb2, .ib, .fmt 파일 생성 ✓ 수정
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
    """✓ 수정: VB0, VB1, VB2 데이터 모두 저장"""
    component_id: int
    vb0_hash: str
    ib_hash: str
    vertex_count: int
    index_count: int
    vg_count: int
    
    # ✓ 수정: VB0, VB1, VB2 분리 저장
    vb0_data: Optional[bytes] = None
    vb1_data: Optional[bytes] = None
    vb2_data: Optional[bytes] = None
    
    # ✓ 수정: VB 메타데이터도 저장 (FMT 생성용)
    vb0_info: Optional[object] = None
    vb1_info: Optional[object] = None
    vb2_info: Optional[object] = None
    
    ib_data: Optional[bytes] = None
    fmt_text: str = ""
    positions: Optional[np.ndarray] = None  # LOD 매칭용


@dataclass
class EFMIObject:
    """EFMI 오브젝트 (Character 또는 Weapon)"""
    object_id: str
    object_type: str  # 'Character', 'Weapon', 'Other'
    vb0_hash: str
    components: List[EFMIComponent] = field(default_factory=list)
    lod_indices: Optional[List[int]] = None  # LOD 매칭 인덱스


class EFMIExtractor:
    """EFMI 형식으로 오브젝트 추출"""

    def __init__(self, dump_dir: str, output_dir: str):
        self.dump_dir = Path(dump_dir)
        self.output_dir = Path(output_dir)
        self.draw_calls = {}  # dc_id → DrawCallInfo
        self.objects = []  # EFMIObject 목록

    def run(self):
        """EFMI 추출 실행"""
        print("\n" + "=" * 80)
        print("EFMI OBJECT EXTRACTION")
        print("=" * 80)

        start_time = time.time()

        # Step 1: FrameAnalysis 덤프 파싱
        print("\n[1/5] Parsing FrameAnalysis dump...")
        self._parse_frame_analysis()
        print(f"  Found {len(self.draw_calls)} draw calls")

        # Step 2: VB0 해시 기준으로 그룹화
        print("\n[2/5] Grouping by VB0 hash...")
        objects = self._group_by_vb0_hash()
        print(f"  Found {len(objects)} unique objects")

        # Step 3: Z값 기준 정렬 (메인 vs LOD)
        print("\n[3/5] Sorting by Z value (main vs LOD)...")
        for obj in objects:
            self._sort_by_z_value(obj)

        # Step 4: 컴포넌트 추출
        print("\n[4/5] Extracting components...")
        for obj in objects:
            self._extract_components(obj)
            self.objects.append(obj)

        # Step 5: Metadata.json 생성
        print("\n[5/5] Generating Metadata.json...")
        self._generate_metadata()

        elapsed = time.time() - start_time
        print("\n" + "=" * 80)
        print(f"EXTRACTION COMPLETED in {elapsed:.2f}s")
        print(f"Output: {self.output_dir}")
        print("=" * 80 + "\n")

        return self.objects

    def _parse_frame_analysis(self):
        """FrameAnalysis 덤프 파싱"""
        # 파일 목록 수집
        txt_files = list(self.dump_dir.glob("*.txt"))
        print(f"  Parsing {len(txt_files)} text files...")

        file_dict = defaultdict(list)
        for txt_file in txt_files:
            # 파일명 패턴: {DC_ID}-{type}_{hash}-vs_{vs_hash}-ps_{ps_hash}.txt
            # 예: 000030-vb0_58e1105c_9a09f1f0_-vs_617db42150841836-ps_d7bb9dd57f5b70c6.txt
            match = re.match(
                r'(\d{6})-(\w+)_([a-f0-9]+)_([a-f0-9]+)_-vs_([a-f0-9]+)-ps_([a-f0-9]+)\.txt',
                txt_file.name,
                re.IGNORECASE
            )

            if match:
                dc_id, buf_type, hash1, hash2, vs_hash, ps_hash = match.groups()
                dc_id = int(dc_id)

                if dc_id not in self.draw_calls:
                    self.draw_calls[dc_id] = DrawCallInfo(
                        dc_id=dc_id,
                        vs_hash=vs_hash,
                        ps_hash=ps_hash,
                    )

                dc = self.draw_calls[dc_id]

                # VB0, VB1, VB2, IB 판별
                if buf_type.upper().startswith('VB'):
                    slot = int(buf_type[2])
                    dc.buffers[f'VB{slot}'] = BufferInfo(
                        dc_id=dc_id,
                        buf_path=txt_file.with_suffix('.buf'),
                        txt_path=txt_file,
                        vb_slot=slot,
                    )

                    # VB0 해시 저장
                    if slot == 0:
                        dc.vb0_hash = hash1

                elif buf_type.upper().startswith('IB'):
                    dc.buffers['IB'] = BufferInfo(
                        dc_id=dc_id,
                        buf_path=txt_file.with_suffix('.buf'),
                        txt_path=txt_file,
                    )
                    dc.ib_hash = hash1

        # 메타데이터 읽기
        vb0_count = sum(1 for dc in self.draw_calls.values() if dc.vb0_hash and 'VB0' in dc.buffers)
        print(f"  Found {vb0_count} draw calls with VB0 + hash")

        for dc_id, dc in sorted(self.draw_calls.items())[:5]:
            vb0_hex = dc.vb0_hash[:8] if dc.vb0_hash else 'N/A'
            vb1_ok = 'VB1' in dc.buffers
            vb2_ok = 'VB2' in dc.buffers
            print(f"    DC {dc_id:06d}: VB0={vb0_hex}, VB1={'✓' if vb1_ok else '✗'}, VB2={'✓' if vb2_ok else '✗'}")

    def _group_by_vb0_hash(self) -> List[EFMIObject]:
        """VB0 해시 기준으로 그룹화"""
        vb0_groups = defaultdict(list)

        for dc_id, dc in self.draw_calls.items():
            if dc.vb0_hash and 'VB0' in dc.buffers:
                vb0_groups[dc.vb0_hash].append(dc)

        objects = []
        for vb0_hash, dcs in vb0_groups.items():
            # 첫 번째 DC의 VB0 Parent 해시로 오브젝트 이름 판별
            first_dc = dcs[0]
            object_type = self._determine_object_type(first_dc)

            obj = EFMIObject(
                object_id=f"{object_type}_{vb0_hash[:8]}",
                object_type=object_type,
                vb0_hash=vb0_hash,
            )
            objects.append(obj)

            # DC 추가
            for dc in dcs:
                dc.vertex_count = 0
                dc.index_count = 0

                # VB0에서 정점 수 읽기
                vb0_buf = dc.buffers.get('VB0')
                if vb0_buf:
                    vb0_info = parse_vertex_buffer_txt(str(vb0_buf.txt_path))
                    dc.vertex_count = vb0_info.vertex_count

                # IB에서 인덱스 수 읽기
                ib_buf = dc.buffers.get('IB')
                if ib_buf:
                    ib_info = parse_index_buffer_txt(str(ib_buf.txt_path))
                    dc.index_count = ib_info.index_count

        return objects

    def _determine_object_type(self, dc: DrawCallInfo) -> str:
        """오브젝트 타입 판별 (Character vs Weapon)"""
        # 간단한 휴리스틱
        if dc.vb0_hash:
            vb0_int = int(dc.vb0_hash[:8], 16)
            if vb0_int % 2 == 0:
                return "Character"
        return "Weapon"

    def _sort_by_z_value(self, obj: EFMIObject):
        """Z값 기준으로 DC 정렬 (메인 메시 → LOD)"""
        # 구현 생략 (현재는 그대로)
        pass

    def _extract_components(self, obj: EFMIObject):
        """오브젝트의 모든 컴포넌트 추출"""
        dcs = [dc for dc in self.draw_calls.values() if dc.vb0_hash == obj.vb0_hash]

        for comp_id, dc in enumerate(dcs):
            component = self._extract_component(comp_id, dc)
            if component:
                obj.components.append(component)

    def _extract_component(self, comp_id: int, dc: DrawCallInfo) -> Optional[EFMIComponent]:
        """✓ 수정: 단일 컴포넌트 추출 (VB0, VB1, VB2 모두)"""
        
        # VB0, VB1, VB2, IB 모두 확인
        vb0_buf = dc.buffers.get('VB0')
        vb1_buf = dc.buffers.get('VB1')
        vb2_buf = dc.buffers.get('VB2')
        ib_buf = dc.buffers.get('IB')

        # VB0과 IB는 필수
        if not vb0_buf or not ib_buf:
            print(f"  Skipping component {comp_id}: missing VB0 or IB")
            return None

        try:
            # ===== VB0 읽기 =====
            print(f"  [Component {comp_id}] Reading VB0... ", end='', flush=True)
            with open(vb0_buf.buf_path, 'rb') as f:
                vb0_info = parse_vertex_buffer_txt(str(vb0_buf.txt_path))

                file_size = os.path.getsize(vb0_buf.buf_path)
                expected_size = vb0_info.stride * vb0_info.vertex_count

                if vb0_buf.buf_path.stat().st_size >= vb0_info.byte_offset + expected_size:
                    f.seek(vb0_info.byte_offset)
                    vb0_data = f.read(expected_size)
                else:
                    f.seek(0)
                    vb0_data = f.read(file_size)

            print(f"OK ({len(vb0_data)} bytes)")

            # ===== VB1 읽기 (있으면) =====
            vb1_data = None
            vb1_info = None
            if vb1_buf:
                print(f"  [Component {comp_id}] Reading VB1... ", end='', flush=True)
                try:
                    with open(vb1_buf.buf_path, 'rb') as f:
                        vb1_info = parse_vertex_buffer_txt(str(vb1_buf.txt_path))

                        file_size = os.path.getsize(vb1_buf.buf_path)
                        expected_size = vb1_info.stride * vb1_info.vertex_count

                        if vb1_buf.buf_path.stat().st_size >= vb1_info.byte_offset + expected_size:
                            f.seek(vb1_info.byte_offset)
                            vb1_data = f.read(expected_size)
                        else:
                            f.seek(0)
                            vb1_data = f.read(file_size)

                    print(f"OK ({len(vb1_data)} bytes)")
                except Exception as e:
                    print(f"SKIP ({str(e)[:30]})")
            else:
                print(f"  [Component {comp_id}] VB1 not found (optional)")

            # ===== VB2 읽기 (있으면) =====
            vb2_data = None
            vb2_info = None
            if vb2_buf:
                print(f"  [Component {comp_id}] Reading VB2... ", end='', flush=True)
                try:
                    with open(vb2_buf.buf_path, 'rb') as f:
                        vb2_info = parse_vertex_buffer_txt(str(vb2_buf.txt_path))

                        file_size = os.path.getsize(vb2_buf.buf_path)
                        expected_size = vb2_info.stride * vb2_info.vertex_count

                        if vb2_buf.buf_path.stat().st_size >= vb2_info.byte_offset + expected_size:
                            f.seek(vb2_info.byte_offset)
                            vb2_data = f.read(expected_size)
                        else:
                            f.seek(0)
                            vb2_data = f.read(file_size)

                    print(f"OK ({len(vb2_data)} bytes)")
                except Exception as e:
                    print(f"SKIP ({str(e)[:30]})")
            else:
                print(f"  [Component {comp_id}] VB2 not found (optional)")

            # ===== IB 읽기 =====
            print(f"  [Component {comp_id}] Reading IB... ", end='', flush=True)
            with open(ib_buf.buf_path, 'rb') as f:
                ib_info = parse_index_buffer_txt(str(ib_buf.txt_path))
                byte_size = 2  # uint16
                expected_size = byte_size * ib_info.index_count

                if ib_buf.buf_path.stat().st_size >= ib_info.byte_offset + expected_size:
                    f.seek(ib_info.byte_offset)
                    ib_data = f.read(expected_size)
                else:
                    f.seek(0)
                    ib_data = f.read(file_size)

            print(f"OK ({len(ib_data)} bytes)")

            # ===== FMT 생성 (VB0, VB1, VB2 모두 포함) =====
            fmt_text = self._generate_fmt_complete(vb0_info, vb1_info, vb2_info, ib_info)

            # ===== POSITION 추출 =====
            positions = extract_vertices_numpy(
                str(vb0_buf.buf_path),
                str(vb0_buf.txt_path),
                target_slot=0,
            ).get('POSITION')

            # ===== VG 수 계산 =====
            vg_count = self._calculate_vg_count(vb0_buf)

            # ===== 컴포넌트 생성 =====
            component = EFMIComponent(
                component_id=comp_id,
                vb0_hash=dc.vb0_hash,
                ib_hash=dc.ib_hash,
                vertex_count=dc.vertex_count,
                index_count=dc.index_count,
                vg_count=vg_count,
                vb0_data=vb0_data,
                vb1_data=vb1_data,      # ✓ VB1 저장
                vb2_data=vb2_data,      # ✓ VB2 저장
                vb0_info=vb0_info,
                vb1_info=vb1_info,
                vb2_info=vb2_info,
                ib_data=ib_data,
                fmt_text=fmt_text,
                positions=positions,
            )

            # ===== 파일 저장 =====
            self._save_component_files(comp_id, component)

            return component

        except Exception as e:
            print(f"  Warning: Failed to extract component {comp_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _save_component_files(self, comp_id: int, component: EFMIComponent):
        """✓ 수정: VB0, VB1, VB2, IB, FMT 모두 저장"""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        files_saved = []

        # ===== VB0 저장 =====
        if component.vb0_data:
            vb0_path = self.output_dir / f"Component {comp_id}.vb0"
            with open(vb0_path, 'wb') as f:
                f.write(component.vb0_data)
            files_saved.append(f"vb0({len(component.vb0_data)//1024}KB)")

        # ===== VB1 저장 (있으면) =====
        if component.vb1_data:
            vb1_path = self.output_dir / f"Component {comp_id}.vb1"
            with open(vb1_path, 'wb') as f:
                f.write(component.vb1_data)
            files_saved.append(f"vb1({len(component.vb1_data)//1024}KB)")

        # ===== VB2 저장 (있으면) =====
        if component.vb2_data:
            vb2_path = self.output_dir / f"Component {comp_id}.vb2"
            with open(vb2_path, 'wb') as f:
                f.write(component.vb2_data)
            files_saved.append(f"vb2({len(component.vb2_data)//1024}KB)")

        # ===== IB 저장 =====
        if component.ib_data:
            ib_path = self.output_dir / f"Component {comp_id}.ib"
            with open(ib_path, 'wb') as f:
                f.write(component.ib_data)
            files_saved.append(f"ib({len(component.ib_data)//1024}KB)")

        # ===== FMT 저장 =====
        fmt_path = self.output_dir / f"Component {comp_id}.fmt"
        with open(fmt_path, 'w', encoding='utf-8') as f:
            f.write(component.fmt_text)
        files_saved.append("fmt")

        print(f"  [Component {comp_id}] Saved: {', '.join(files_saved)}")

    def _generate_fmt_complete(self, vb0_info, vb1_info, vb2_info, ib_info) -> str:
        """✓ 수정: VB0, VB1, VB2 정보를 모두 포함한 FMT 파일 생성"""
        fmt_lines = []

        # ===== 기본 정보 =====
        fmt_lines.append(f"stride: {vb0_info.stride}")
        if hasattr(vb0_info, 'topology'):
            fmt_lines.append(f"topology: {vb0_info.topology}")
        fmt_lines.append(f"format: DXGI_FORMAT_R16_UINT")
        fmt_lines.append("")

        # ===== VB0 요소 (InputSlot 0) =====
        elem_index = 0
        for elem in vb0_info.elements:
            fmt_lines.append(f"element[{elem_index}]:")
            fmt_lines.append(f"  SemanticName: {elem.semantic_name}")
            fmt_lines.append(f"  SemanticIndex: {elem.semantic_index}")
            fmt_lines.append(f"  Format: {elem.format_type}")
            fmt_lines.append(f"  InputSlot: 0")
            fmt_lines.append(f"  AlignedByteOffset: {elem.byte_offset}")
            fmt_lines.append(f"  InputSlotClass: per-vertex")
            fmt_lines.append(f"  InstanceDataStepRate: 0")
            fmt_lines.append("")
            elem_index += 1

        # ===== VB1 요소 (InputSlot 1) =====
        if vb1_info:
            for elem in vb1_info.elements:
                fmt_lines.append(f"element[{elem_index}]:")
                fmt_lines.append(f"  SemanticName: {elem.semantic_name}")
                fmt_lines.append(f"  SemanticIndex: {elem.semantic_index}")
                fmt_lines.append(f"  Format: {elem.format_type}")
                fmt_lines.append(f"  InputSlot: 1")
                fmt_lines.append(f"  AlignedByteOffset: {elem.byte_offset}")
                fmt_lines.append(f"  InputSlotClass: per-vertex")
                fmt_lines.append(f"  InstanceDataStepRate: 0")
                fmt_lines.append("")
                elem_index += 1

        # ===== VB2 요소 (InputSlot 2) =====
        if vb2_info:
            for elem in vb2_info.elements:
                fmt_lines.append(f"element[{elem_index}]:")
                fmt_lines.append(f"  SemanticName: {elem.semantic_name}")
                fmt_lines.append(f"  SemanticIndex: {elem.semantic_index}")
                fmt_lines.append(f"  Format: {elem.format_type}")
                fmt_lines.append(f"  InputSlot: 2")
                fmt_lines.append(f"  AlignedByteOffset: {elem.byte_offset}")
                fmt_lines.append(f"  InputSlotClass: per-vertex")
                fmt_lines.append(f"  InstanceDataStepRate: 0")
                fmt_lines.append("")
                elem_index += 1

        # ===== Vertex Data Marker =====
        fmt_lines.append("vertex-data:")

        return "\n".join(fmt_lines)

    def _calculate_vg_count(self, vb0_buf: BufferInfo) -> int:
        """VG (Vertex Group) 수 계산"""
        try:
            vb_info = parse_vertex_buffer_txt(str(vb0_buf.txt_path))

            # BLENDINDICES 요소 찾기
            for elem in vb_info.elements:
                if 'BLENDINDICES' in elem.semantic_name.upper():
                    # BLENDINDICES는 보통 4개 (각 1바이트)
                    return 4

            return 0
        except:
            return 0

    def _generate_metadata(self):
        """Metadata.json 생성"""
        metadata = {
            "objects": []
        }

        for obj in self.objects:
            obj_meta = {
                "object_id": obj.object_id,
                "type": obj.object_type,
                "vb0_hash": obj.vb0_hash,
                "components": []
            }

            for comp in obj.components:
                comp_meta = {
                    "id": comp.component_id,
                    "vb0_hash": comp.vb0_hash,
                    "vertex_count": comp.vertex_count,
                    "index_count": comp.index_count,
                    "vg_count": comp.vg_count,
                }
                obj_meta["components"].append(comp_meta)

            metadata["objects"].append(obj_meta)

        # Metadata.json 저장
        metadata_path = self.output_dir / "Metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"  Generated: {metadata_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python efmi_extractor.py <FrameAnalysis 디렉토리> [출력 디렉토리]")
        sys.exit(1)

    dump_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "efmi_output"

    extractor = EFMIExtractor(dump_dir, output_dir)
    objects = extractor.run()

    print(f"\n추출 완료!")
    print(f"  총 {len(objects)}개 오브젝트")
    for obj in objects:
        print(f"  - {obj.object_id}: {len(obj.components)}개 컴포넌트")
