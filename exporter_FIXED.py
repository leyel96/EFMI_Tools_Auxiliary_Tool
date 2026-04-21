"""
EFMI 메인 익스포터 클래스 (수정: VB0/VB1/VB2 모두 처리)

모든 모듈을 통합하여 최종 모드 내보내기 실행
"""

import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from metadata import ExtractedObject, read_metadata
from buffer_builder import BufferBuilder
from ini_template import INIGenerator, ModInfo, BufferInfo, TextureInfo, ComponentDrawInfo
from mesh_parser import MeshData


@dataclass
class ExportConfig:
    """익스포트 설정"""
    # 필수 입력
    object_source_folder: Path  # Metadata.json이 있는 폴더
    mod_output_folder: Path  # 모드 출력 폴더

    # 모드 정보
    mod_name: str = "Unnamed Mod"
    mod_author: str = "Unknown Author"
    mod_desc: str = ""
    mod_link: str = ""
    mod_logo: Optional[Path] = None

    # 옵션
    mirror_mesh: bool = False  # 메쉬 좌우 반전
    copy_textures: bool = True  # 텍스처 복사
    comment_ini: bool = False  # mod.ini 주석 포함
    skip_known_cubemaps: bool = True  # 알려진 큐브맵 텍스처 제외

    # 디버그
    remove_temp_files: bool = True  # 임시 파일 정리


class EFMIExporter:
    """EFMI 모드 익스포터 (수정: VB0/VB1/VB2 모두 처리)"""

    def __init__(self, config: ExportConfig):
        """
        Args:
            config: 익스포트 설정
        """
        self.config = config
        self.meshes_path = config.mod_output_folder / 'Meshes'
        self.textures_path = config.mod_output_folder / 'Textures'

    def export(self, meshes: Dict[int, MeshData]) -> bool:
        """
        ✓ 수정: 모드 내보내기 실행 (VB0/VB1/VB2 모두 처리)

        Args:
            meshes: DC ID → MeshData 딕셔너리

        Returns:
            성공 여부
        """
        start_time = time.time()
        print(f"EFMI Export started for '{self.config.mod_name}'")

        try:
            # 1. Metadata.json 로드
            metadata_path = self.config.object_source_folder / 'Metadata.json'
            extracted_object = read_metadata(metadata_path)
            print(f"Loaded metadata: {extracted_object.name} ({extracted_object.vertex_count} vertices)")

            # 2. 출력 디렉토리 생성
            self.meshes_path.mkdir(parents=True, exist_ok=True)
            self.textures_path.mkdir(parents=True, exist_ok=True)

            # 3. 버퍼 빌더 초기화
            buffer_builder = BufferBuilder(
                mirror_mesh=self.config.mirror_mesh,
                flip_texcoord_v=True
            )

            # 4. 컴포넌트별 처리
            all_buffers = {}
            component_draw_infos = []
            index_offset = 0

            for component_id, component in enumerate(extracted_object.components):
                print(f"\nProcessing Component {component_id}...")

                # 해당 컴포넌트의 메쉬 찾기
                # VB0 해시로 매칭
                component_mesh = self._find_mesh_for_component(meshes, component)

                if component_mesh is None:
                    print(f"  Warning: No mesh found for Component {component_id}")
                    # 빈 컴포넌트 추가
                    component_draw_infos.append(ComponentDrawInfo(
                        component_id=component_id,
                        vb0_hash=component.vb0_hash,
                        index_count=0,
                        index_offset=0,
                        vertex_count=0,
                    ))
                    continue

                # ✓ 버퍼 빌드 (VB0, VB1, VB2 모두)
                buffers = buffer_builder.build_buffers(
                    component_mesh,
                    component_id=component_id,
                    index_offset=index_offset
                )

                # LOD 정보 확인
                has_lod = len(component.lods) > 0 and component.lods[0].vb0_hash != component.vb0_hash
                lod_vb0_hash = component.lods[0].vb0_hash if has_lod else ""

                # 드로우 정보 구성
                draw_info = ComponentDrawInfo(
                    component_id=component_id,
                    vb0_hash=component.vb0_hash,
                    index_count=len(component_mesh.indices),
                    index_offset=index_offset,
                    vertex_count=len(component_mesh.vertices),
                    # ✓ VB1, VB2 확인
                    has_vb1=f'Component{component_id}_VB1' in buffers,
                    has_vb2=f'Component{component_id}_VB2' in buffers,
                    has_lod=has_lod,
                    lod_vb0_hash=lod_vb0_hash,
                )
                component_draw_infos.append(draw_info)

                # 버퍼 병합
                all_buffers.update(buffers)

                # 인덱스 오프셋 업데이트
                index_offset += len(component_mesh.indices)

                print(f"  Component {component_id}: {draw_info.vertex_count} vertices, {draw_info.index_count} indices")
                print(f"    Buffers: VB0 ✓, VB1 {'✓' if draw_info.has_vb1 else '✗'}, VB2 {'✓' if draw_info.has_vb2 else '✗'}")

            # 5. 텍스처 수집
            textures = self._collect_textures(extracted_object)

            # 6. mod.ini 생성
            mod_info = ModInfo(
                mod_name=self.config.mod_name,
                mod_author=self.config.mod_author,
                mod_desc=self.config.mod_desc,
                mod_link=self.config.mod_link,
                mod_logo_path=self.config.mod_logo,
            )

            ini_generator = INIGenerator(
                mod_info=mod_info,
                object_guid=extracted_object.index_count,
                mesh_vertex_count=sum(c.vertex_count for c in component_draw_infos),
                required_efmi_version="1.1.0",
                comment_ini=self.config.comment_ini,
            )

            # ✓ 버퍼 추가 (VB0, VB1, VB2 모두)
            for buffer_name, buffer in all_buffers.items():
                if 'IB' in buffer_name:
                    buffer_info = BufferInfo(
                        name=buffer_name,
                        stride=buffer.layout.stride,
                        filename=f"{buffer_name}.buf",
                        format_str="R16_UINT",
                    )
                elif 'VB0' in buffer_name or 'VB1' in buffer_name or 'VB2' in buffer_name:
                    buffer_info = BufferInfo(
                        name=buffer_name,
                        stride=buffer.layout.stride,
                        filename=f"{buffer_name}.buf",
                        format_str=None,
                    )
                else:
                    continue

                ini_generator.add_buffer(buffer_info)
                print(f"  Added buffer: {buffer_name}")

            # 텍스처 추가
            for texture in textures:
                ini_generator.add_texture(texture)

            # 컴포넌트 추가
            for draw_info in component_draw_infos:
                ini_generator.add_component(draw_info)

            # mod.ini 쓰기
            ini_path = self.config.mod_output_folder / 'mod.ini'
            ini_generator.write(ini_path)

            # 7. ✓ 버퍼 파일 쓰기 (VB0, VB1, VB2 모두)
            for buffer_name, buffer in all_buffers.items():
                buf_path = self.meshes_path / f"{buffer_name}.buf"
                with open(buf_path, 'wb') as f:
                    f.write(buffer.get_bytes())
                print(f"  Written buffer: {buf_path} ({len(buffer)} vertices)")

            print(f"\nWritten {len(all_buffers)} buffer files")

            # 8. 텍스처 복사
            if self.config.copy_textures:
                copied_count = self._copy_textures(textures)
                print(f"Copied {copied_count} textures")

            # 9. 로고 복사
            if self.config.mod_logo and self.config.mod_logo.is_file():
                logo_dest = self.textures_path / 'Logo.dds'
                shutil.copy(self.config.mod_logo, logo_dest)
                print(f"Copied logo to {logo_dest}")

            elapsed = time.time() - start_time
            print(f"\nEFMI Export completed in {elapsed:.3f}s")
            print(f"Output folder: {self.config.mod_output_folder}")

            return True

        except Exception as e:
            print(f"\nEFMI Export failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _find_mesh_for_component(
        self,
        meshes: Dict[int, MeshData],
        component
    ) -> Optional[MeshData]:
        """
        컴포넌트에 해당하는 메쉬 찾기

        VB0 해시로 매칭하거나, 첫 번째 메쉬 반환
        """
        # VB0 해시로 매칭 시도
        for dc_id, mesh in meshes.items():
            if mesh.vb0_hash == component.vb0_hash:
                return mesh

        # 매칭 실패 시 첫 번째 메쉬 반환
        if meshes:
            return list(meshes.values())[0]

        return None

    def _collect_textures(self, extracted_object: ExtractedObject) -> List[TextureInfo]:
        """
        텍스처 수집

        Args:
            extracted_object: 추출된 오브젝트 정보

        Returns:
            텍스처 정보 목록
        """
        textures = []
        exclude_hashes = {'af26db30', '1320a071', '10d7937d', '87505b2b'} if self.config.skip_known_cubemaps else set()

        # 오브젝트 폴더에서 텍스처 검색
        for texture_filename in os.listdir(self.config.object_source_folder):
            if not (texture_filename.endswith(".dds") or texture_filename.endswith(".jpg")):
                continue

            # 해시 추출
            import re
            hash_pattern = re.compile(r'.*t=([a-f0-9]{8}).*')
            result = hash_pattern.findall(texture_filename.lower())

            if len(result) != 1:
                # 구 포맷
                hash_pattern = re.compile(r'.*component_\d-ps-t\d-([a-f0-9]{8}).*')
                result = hash_pattern.findall(texture_filename.lower())
                if len(result) != 1:
                    continue

            texture_hash = result[0]

            # 제외 해시 필터링
            if texture_hash in exclude_hashes:
                continue

            textures.append(TextureInfo(
                hash=texture_hash,
                filename=texture_filename,
                path=self.config.object_source_folder / texture_filename,
            ))

        return textures

    def _copy_textures(self, textures: List[TextureInfo]) -> int:
        """
        텍스처 복사

        Args:
            textures: 텍스처 정보 목록

        Returns:
            복사된 텍스처 수
        """
        copied = 0
        for texture in textures:
            dest_path = self.textures_path / texture.filename
            if dest_path.is_file():
                continue  # 이미 존재하면 스킵

            if texture.path.is_file():
                shutil.copy(texture.path, dest_path)
                copied += 1

        return copied
