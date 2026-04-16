"""
mod.ini 템플릿 및 생성 모듈

EFMI-Tools의 Jinja2 템플릿 방식을 참고하여 Python 문자열 포맷으로 구현
3DMigoto 호환 mod.ini 생성
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class ModInfo:
    """모드 정보"""
    mod_name: str = "Unnamed Mod"
    mod_author: str = "Unknown Author"
    mod_desc: str = ""
    mod_link: str = ""
    mod_logo_path: Optional[Path] = None


@dataclass
class BufferInfo:
    """버퍼 정보"""
    name: str
    stride: int
    filename: str
    format_str: Optional[str] = None  # IB 포맷 (예: R16_UINT)


@dataclass
class TextureInfo:
    """텍스처 정보"""
    hash: str
    filename: str
    path: Path


@dataclass
class ComponentDrawInfo:
    """컴포넌트 드로우 정보"""
    component_id: int
    vb0_hash: str
    index_count: int
    index_offset: int
    vertex_count: int
    has_vb2: bool = False
    has_lod: bool = False
    lod_vb0_hash: str = ""


class INIGenerator:
    """mod.ini 생성기"""

    def __init__(
        self,
        mod_info: ModInfo,
        object_guid: int,
        mesh_vertex_count: int,
        required_efmi_version: str = "1.1.0",
        comment_ini: bool = False,
    ):
        """
        Args:
            mod_info: 모드 정보
            object_guid: 원본 오브젝트 인덱스 수
            mesh_vertex_count: 커스텀 메쉬 버텍스 수
            required_efmi_version: 요구 EFMI 버전
            comment_ini: 주석 포함 여부
        """
        self.mod_info = mod_info
        self.object_guid = object_guid
        self.mesh_vertex_count = mesh_vertex_count
        self.required_efmi_version = required_efmi_version
        self.comment_ini = comment_ini

        self.buffers: List[BufferInfo] = []
        self.textures: List[TextureInfo] = []
        self.components: List[ComponentDrawInfo] = []

    def add_buffer(self, buffer: BufferInfo):
        """버퍼 추가"""
        self.buffers.append(buffer)

    def add_texture(self, texture: TextureInfo):
        """텍스처 추가"""
        self.textures.append(texture)

    def add_component(self, component: ComponentDrawInfo):
        """컴포넌트 추가"""
        self.components.append(component)

    def _note(self, text: str) -> str:
        """주석 생성 (comment_ini 설정에 따라)"""
        if self.comment_ini:
            return f"; {text}"
        else:
            return ";DEL"

    def generate(self) -> str:
        """mod.ini 문자열 생성"""
        lines = []

        lines.append("; EFMI ALPHA-5 INI")
        lines.append("")

        # 1. 모드 정보
        lines.extend(self._generate_mod_info())
        lines.append("")

        # 2. Constants
        lines.extend(self._generate_constants())
        lines.append("")

        # 3. Present
        lines.extend(self._generate_present())
        lines.append("")

        # 4. CommandListRegisterMod
        lines.extend(self._generate_register_mod())
        lines.append("")

        # 5. 컴포넌트별 드로우 커맨드
        lines.extend(self._generate_draw_commands())
        lines.append("")

        # 6. TextureOverride (풀 모델)
        lines.extend(self._generate_texture_overrides())
        lines.append("")

        # 7. TextureOverride (LOD 모델)
        lines.extend(self._generate_lod_overrides())
        lines.append("")

        # 8. 텍스처 리소스
        lines.extend(self._generate_texture_resources())
        lines.append("")

        # 9. 버퍼 리소스
        lines.extend(self._generate_buffer_resources())
        lines.append("")

        # 10. 푸터
        lines.extend(self._generate_footer())

        # SHA256 체크섬 추가
        result = '\n'.join(lines)
        result = self._add_checksum(result)

        return result

    def _generate_mod_info(self) -> List[str]:
        """모드 정보 섹션 생성"""
        lines = []

        lines.append("; Mod Info -------------------------")
        lines.append("")

        # Mod Name
        lines.append(self._note("Name of mod"))
        lines.append("[ResourceModName]")
        if self.mod_info.mod_name.strip():
            lines.append(f'type = Buffer')
            lines.append(f'data = "{self.mod_info.mod_name}"')
        else:
            lines.append('; type = Buffer')
            lines.append('; data = "Unknown Mod Name"')
        lines.append("")

        # Mod Author
        lines.append(self._note("Name of mod author"))
        lines.append("[ResourceModAuthor]")
        if self.mod_info.mod_author.strip():
            lines.append(f'type = Buffer')
            lines.append(f'data = "{self.mod_info.mod_author}"')
        else:
            lines.append('; type = Buffer')
            lines.append('; data = "Unknown Mod Author"')
        lines.append("")

        # Mod Desc
        lines.append(self._note("Mod description"))
        lines.append("[ResourceModDesc]")
        if self.mod_info.mod_desc.strip():
            lines.append(f'type = Buffer')
            lines.append(f'data = "{self.mod_info.mod_desc}"')
        else:
            lines.append('; type = Buffer')
            lines.append('; data = "Empty Mod Description"')
        lines.append("")

        # Mod Link
        lines.append(self._note("Link to mod repository"))
        lines.append("[ResourceModLink]")
        if self.mod_info.mod_link.strip():
            lines.append(f'type = Buffer')
            lines.append(f'data = "{self.mod_info.mod_link}"')
        else:
            lines.append('; type = Buffer')
            lines.append('; data = "Empty Mod Link"')
        lines.append("")

        # Mod Logo
        lines.append(self._note("Texture file with 512x512 .dds (BC7 SRGB) mod logo"))
        lines.append("[ResourceModLogo]")
        if self.mod_info.mod_logo_path and self.mod_info.mod_logo_path.is_file():
            lines.append('filename = Textures/Logo.dds')
        else:
            lines.append('; filename = Textures/Logo.dds')

        return lines

    def _generate_constants(self) -> List[str]:
        """Constants 섹션 생성"""
        lines = []

        lines.append("; Mod State -------------------------")
        lines.append("")
        lines.append(self._note("Global variables used by entire mod"))
        lines.append("[Constants]")

        lines.append(self._note("Allows EFMI to safely disable incompatible mod and notify user about it"))
        lines.append(f"global $required_efmi_version = {self.required_efmi_version}")

        lines.append(self._note("Number of indices in original model"))
        lines.append(f"global $object_guid = {self.object_guid}")

        lines.append(self._note("Number of vertices in custom model"))
        lines.append(f"global $mesh_vertex_count = {self.mesh_vertex_count}")

        lines.append(self._note("ID assigned to our mod by EFMI"))
        lines.append("global $mod_id = -1000")

        lines.append(self._note("Controls whether our mod is enabled"))
        lines.append(self._note("Prevents user from being crash-locked in case of incompatible EFMI version"))
        lines.append("global $mod_enabled = 0")

        lines.append(self._note("Indicates if our object was detected in previous frame"))
        lines.append("global $object_detected = 0")

        lines.append(self._note("Indicates if our object has LoDs applied"))
        lines.append("global $lod_detected = 0")

        return lines

    def _generate_present(self) -> List[str]:
        """Present 섹션 생성"""
        lines = []

        lines.append("")
        lines.append(self._note("List of commands executed for every frame"))
        lines.append("[Present]")
        lines.append("if $object_detected")
        lines.append("    if $mod_enabled")
        lines.append("        post $object_detected = 0")
        lines.append("    else")
        lines.append(self._note("Check if our mod is compatible with installed EFMI version"))
        lines.append("        if $mod_id == -1000")
        lines.append("            run = CommandListRegisterMod")
        lines.append("        endif")
        lines.append("    endif")
        lines.append("endif")

        return lines

    def _generate_register_mod(self) -> List[str]:
        """CommandListRegisterMod 섹션 생성"""
        lines = []

        lines.append("")
        lines.append(self._note("Contacts EFMI to check whether installed version is compatible"))
        lines.append("[CommandListRegisterMod]")

        lines.append(self._note("Pass mod info variables to EFMI"))
        lines.append("$\\EFMIv1\\required_version = $required_efmi_version")
        lines.append("$\\EFMIv1\\object_guid = $object_guid")

        lines.append(self._note("Pass mod info resources to EFMI"))
        lines.append("Resource\\EFMIv1\\ModName = ref ResourceModName")
        lines.append("Resource\\EFMIv1\\ModAuthor = ref ResourceModAuthor")
        lines.append("Resource\\EFMIv1\\ModDesc = ref ResourceModDesc")
        lines.append("Resource\\EFMIv1\\ModLink = ref ResourceModLink")
        lines.append("Resource\\EFMIv1\\ModLogo = ref ResourceModLogo")

        lines.append(self._note("Register mod in EFMI"))
        lines.append("run = CommandList\\EFMIv1\\RegisterMod")

        lines.append(self._note("Read mod_id assigned to our mod by EFMI"))
        lines.append("$mod_id = $\\EFMIv1\\mod_id")

        lines.append(self._note("Enable our mod if EFMI assigned valid $mod_id"))
        lines.append("if $mod_id >= 0")
        lines.append("    $mod_enabled = 1")
        lines.append("endif")

        return lines

    def _generate_draw_commands(self) -> List[str]:
        """컴포넌트별 드로우 커맨드 생성"""
        lines = []

        for comp in self.components:
            if comp.index_count == 0:
                continue

            lines.append("")
            lines.append(self._note(f"Do custom draw calls for Component {comp.component_id}"))
            lines.append(f"[CommandList_Draw_Component{comp.component_id}]")

            lines.append(self._note("Trigger TextureOverride sections for PS slots"))
            lines.append("run = CommandList\\EFMIv1\\OverrideTextures")
            lines.append(self._note("Do by-slot resource overrides"))

            lines.append(f"ib = ref Resource_Component{comp.component_id}_IB")
            lines.append(f"vb0 = ref Resource_Component{comp.component_id}_VB0")
            lines.append(f"vb1 = ref Resource_Component{comp.component_id}_VB1")

            if comp.has_vb2:
                lines.append(self._note("Conditional VB2 (blends buffer) swap for LoDs handling"))
                if not comp.has_lod:
                    lines.append(f"vb2 = ref Resource_Component{comp.component_id}_VB2")
                else:
                    lines.append(f"if $lod_detected == 0")
                    lines.append(self._note("Use VB2 with weights for full model"))
                    lines.append(f"    vb2 = ref Resource_Component{comp.component_id}_VB2")
                    lines.append(f"else")
                    lines.append(self._note("Use VB2 with weights for LoD model"))
                    lines.append(f"    vb2 = ref Resource_Component{comp.component_id}_VB2_LOD")
                    lines.append(f"endif")

            lines.append(f"; Draw Component {comp.component_id}")
            lines.append(f"drawindexedinstanced = {comp.index_count}, INSTANCE_COUNT, {comp.index_offset}, 0, FIRST_INSTANCE")

        return lines

    def _generate_texture_overrides(self) -> List[str]:
        """TextureOverride (풀 모델) 섹션 생성"""
        lines = []

        for comp in self.components:
            lines.append("")
            lines.append(self._note(f"Override draw calls for Component {comp.component_id}"))
            lines.append(f"[TextureOverride_Component{comp.component_id}]")
            lines.append(f"hash = {comp.vb0_hash}")

            lines.append(self._note("Signal our mod that object is found on screen"))
            lines.append("$object_detected = 1")

            if comp.has_lod:
                lines.append(self._note("Signal our mod that object LoD is NOT found"))
                lines.append("$lod_detected = 0")

            lines.append("if $mod_enabled && DRAW_TYPE == 4")
            lines.append(self._note("Skip original draw call"))
            lines.append("    handling = skip")

            if comp.index_count > 0:
                lines.append(self._note("Do custom draw calls"))
                lines.append(f"    run = CommandList_Draw_Component{comp.component_id}")
            else:
                lines.append("    ; Draw skipped: No matching custom components found")

            lines.append("endif")

        return lines

    def _generate_lod_overrides(self) -> List[str]:
        """TextureOverride (LOD 모델) 섹션 생성"""
        lines = []

        for comp in self.components:
            if not comp.has_lod:
                continue

            lines.append("")
            lines.append(self._note(f"Override draw calls for LoD of Component {comp.component_id}"))
            lines.append(f"[TextureOverride_Component{comp.component_id}_LOD0]")
            lines.append(f"hash = {comp.lod_vb0_hash}")

            lines.append(self._note("Signal our mod that object is found on screen"))
            lines.append("$object_detected = 1")

            lines.append(self._note("Signal our mod that object LoD is found on screen"))
            lines.append("$lod_detected = 1")

            lines.append("if $mod_enabled && DRAW_TYPE == 4")
            lines.append(self._note("Skip original draw call"))
            lines.append("    handling = skip")

            if comp.index_count > 0:
                lines.append(self._note("Do custom draw calls"))
                lines.append(f"    run = CommandList_Draw_Component{comp.component_id}")
            else:
                lines.append("    ; Draw skipped: No matching custom components found")

            lines.append("endif")

        return lines

    def _generate_texture_resources(self) -> List[str]:
        """텍스처 리소스 섹션 생성"""
        lines = []

        if not self.textures:
            return lines

        lines.append("; Shading: Textures -------------------------")
        lines.append("")

        for i, texture in enumerate(self.textures):
            lines.append(f"[Resource_Texture{i}]")
            lines.append(f"filename = Textures/{texture.filename}")
            lines.append("")

            lines.append(f"[TextureOverride_Texture{i}]")
            lines.append(f"hash = {texture.hash}")
            lines.append("match_priority = 0")
            lines.append("if $object_detected")
            lines.append(f"    this = Resource_Texture{i}")
            lines.append("endif")
            lines.append("")

        return lines

    def _generate_buffer_resources(self) -> List[str]:
        """버퍼 리소스 섹션 생성"""
        lines = []

        lines.append("; Resources: Buffers -------------------------")
        lines.append("")

        for buffer in self.buffers:
            lines.append(f"[Resource_{buffer.name}]")
            lines.append("type = Buffer")

            if buffer.name.endswith('IB') and buffer.format_str:
                lines.append(f"format = {buffer.format_str}")

            lines.append(f"stride = {buffer.stride}")
            lines.append(f"filename = Meshes/{buffer.filename}")
            lines.append("")

        return lines

    def _generate_footer(self) -> List[str]:
        """푸터 생성"""
        lines = []

        lines.append("; Autogenerated -------------------------")
        lines.append("")
        lines.append(f"; This mod.ini was automatically generated by EFMI Export Tool")
        lines.append(f"; Requires EFMI v{self.required_efmi_version}+ to function")
        lines.append("")
        lines.append("; EFMI Package GitHub: https://github.com/SpectrumQT/EFMI-Package")
        lines.append("; XXMI Launcher GitHub: https://github.com/SpectrumQT/XXMI-Launcher")
        lines.append("; Arknights: Endfield Mods - GameBanana: https://gamebanana.com/games/21842")

        return lines

    def _add_checksum(self, content: str) -> str:
        """SHA256 체크섬 추가"""
        content = content.strip() + '\n'
        sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
        content += f'; SHA256 CHECKSUM: {sha256}' + '\n'
        return content

    def write(self, output_path: Path):
        """
        mod.ini 파일로 저장

        Args:
            output_path: 출력 파일 경로
        """
        content = self.generate()

        # 기존 파일이 있고 체크섬이 다르면 백업
        if output_path.is_file():
            if self._is_ini_edited(output_path):
                timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
                backup_path = output_path.with_name(f'{output_path.name} {timestamp}.BAK')
                print(f"Writing backup: {backup_path.name}")
                output_path.rename(backup_path)

        with open(output_path, 'w', encoding='utf-8') as f:
            print(f"Writing: {output_path.name}")
            f.write(content)

    @staticmethod
    def _is_ini_edited(ini_path: Path) -> bool:
        """mod.ini 수동 편집 여부 확인"""
        with open(ini_path, 'r', encoding='utf-8') as f:
            data = list(f)

        if len(data) < 2:
            return False

        checksum_line = data[-1].strip()
        checksum_prefix = '; SHA256 CHECKSUM: '

        if not checksum_line.startswith(checksum_prefix):
            return False

        stored_sha256 = checksum_line[len(checksum_prefix):]
        ini_data = data[:-1]
        calculated_sha256 = hashlib.sha256(''.join(ini_data).encode('utf-8')).hexdigest()

        return calculated_sha256 != stored_sha256
