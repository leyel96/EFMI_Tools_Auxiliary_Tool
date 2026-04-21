"""
FrameAnalysis 메쉬 추출 GUI (tkinter 기반)
Python 표준 라이브러리만 사용 (별도 설치 불필요)
중복 메쉬 제거 기능 포함
EFMI Export 기능 통합
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path


class MeshExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FrameAnalysis 메쉬 추출 도구")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)

        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar(value="./Extracted_Meshes")
        self.coord_system = tk.StringVar(value="reference")
        self.export_individual = tk.BooleanVar(value=True)
        self.export_combined = tk.BooleanVar(value=True)
        self.is_running = False
        self.current_meshes = {}  # 현재 로드된 메쉬 저장

        # EFMI Export 관련 변수
        self.efmi_source_folder = tk.StringVar()
        self.efmi_output_folder = tk.StringVar(value="./EFMI_Mod")
        self.efmi_mod_name = tk.StringVar(value="My EFMI Mod")
        self.efmi_mod_author = tk.StringVar(value="Unknown")
        self.efmi_mod_desc = tk.StringVar()
        self.efmi_mod_link = tk.StringVar()
        self.efmi_mirror_mesh = tk.BooleanVar(value=False)
        self.efmi_copy_textures = tk.BooleanVar(value=True)
        self.efmi_comment_ini = tk.BooleanVar(value=False)

        # EFMI 오브젝트 추출 관련 변수
        self.efmi_extract_dump_dir = tk.StringVar()
        self.efmi_extract_output_dir = tk.StringVar(value="./EFMI_Extracted")

        # LOD 추출 관련 변수
        self.lod_full_model_dir = tk.StringVar()
        self.lod_dump_dir = tk.StringVar()
        self.lod_similarity_threshold = tk.DoubleVar(value=50.0)
        self.lod_voxel_size = tk.DoubleVar(value=0.05)
        self.lod_sensitivity = tk.DoubleVar(value=0.5)

        # 추출물 변환 관련 변수
        self.ext_import_source_dir = tk.StringVar()
        self.ext_import_output_dir = tk.StringVar(value="./Extracted_OBJ")
        self.ext_import_export_individual = tk.BooleanVar(value=True)
        self.ext_import_export_combined = tk.BooleanVar(value=False)

        # 모드 익스포트 관련 변수
        self.mod_export_obj_path = tk.StringVar()
        self.mod_export_efmi_dir = tk.StringVar()
        self.mod_export_output_dir = tk.StringVar(value="./Exported_Mod")

        # 창 아이콘 설정
        self._set_window_icon()

        self._build_ui()

    def _set_window_icon(self):
        """윈도우 상단바/작업표시줄 아이콘 설정"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(script_dir, "image-Photoroom.png")

            if os.path.exists(logo_path):
                from PIL import Image, ImageTk

                img = Image.open(logo_path)
                img = img.resize((48, 48), Image.Resampling.LANCZOS)
                icon = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, icon)
        except Exception as e:
            print(f"아이콘 설정 실패: {e}")

    def _build_ui(self):
        """UI 구성 - 탭 기반"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 탭 컨트롤
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # 탭 1: OBJ 추출
        self.tab_obj = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_obj, text="OBJ 추출")
        self._build_obj_tab()

        # 탭 2: EFMI 오브젝트 추출 (NEW!)
        self.tab_efmi_extract = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_efmi_extract, text="EFMI 오브젝트 추출")
        self._build_efmi_extract_tab()

        # 탭 3: EFMI Export
        self.tab_efmi = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_efmi, text="EFMI Export")
        self._build_efmi_tab()

        # 탭 4: LOD 추출
        self.tab_lod = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_lod, text="LOD 추출")
        self._build_lod_tab()

        # 탭 5: 추출물 변환
        self.tab_ext_import = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_ext_import, text="추출물 변환 (Import)")
        self._build_extracted_import_tab()

        # 탭 6: 모드 익스포트 (Mod Export)
        self.tab_mod_export = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_mod_export, text="모드 익스포트 (Mod Export)")
        self._build_mod_export_tab()

        # 로그 (하단 공통)
        log_frame = ttk.LabelFrame(main_frame, text="로그", padding=10)
        log_frame.pack(fill=tk.X, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.X)

    def _build_obj_tab(self):
        """OBJ 추출 탭"""
        # 입력 설정
        input_frame = ttk.LabelFrame(self.tab_obj, text="입력 설정", padding=10)
        input_frame.pack(fill=tk.X, pady=5)

        ttk.Label(input_frame, text="추출할 FrameAnalysis 폴더:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Entry(input_frame, textvariable=self.input_dir, width=60).grid(
            row=0, column=1, padx=5, pady=2
        )
        ttk.Button(input_frame, text="찾아보기", command=self._browse_input).grid(
            row=0, column=2, pady=2
        )

        ttk.Label(input_frame, text="mesh 저장위치:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        ttk.Entry(input_frame, textvariable=self.output_dir, width=60).grid(
            row=1, column=1, padx=5, pady=2
        )
        ttk.Button(input_frame, text="찾아보기", command=self._browse_output).grid(
            row=1, column=2, pady=2
        )

        # 추출 옵션
        options_frame = ttk.LabelFrame(self.tab_obj, text="추출 옵션", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        ttk.Label(options_frame, text="좌표계:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        coord_combo = ttk.Combobox(
            options_frame, textvariable=self.coord_system, width=40, state="readonly"
        )
        coord_combo["values"] = [
            "Reference (Z-up, chen.obj 기준)",
            "Blender (Y-up)",
            "Original (DirectX 원본)",
        ]
        coord_combo.current(0)
        coord_combo.grid(row=0, column=1, padx=5, pady=2)
        coord_combo.bind("<<ComboboxSelected>>", self._on_coord_select)

        ttk.Checkbutton(
            options_frame,
            text="개별 OBJ 파일 내보내기",
            variable=self.export_individual,
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Checkbutton(
            options_frame,
            text="결합된 OBJ 파일 내보내기 (combined_mesh.obj)",
            variable=self.export_combined,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)

        # 메쉬 목록
        mesh_frame = ttk.LabelFrame(self.tab_obj, text="메쉬 목록", padding=10)
        mesh_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        mesh_btn_frame = ttk.Frame(mesh_frame)
        mesh_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(
            mesh_btn_frame, text="메쉬 목록 불러오기", command=self._load_mesh_list
        ).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            mesh_btn_frame, text="중복 메쉬 제거", command=self._remove_duplicates
        ).pack(side=tk.LEFT, padx=2)

        tree_frame = ttk.Frame(mesh_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("id", "verts", "faces", "vs_hash", "vb0_parent"),
            show="headings",
            height=8,
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("verts", text="버텍스")
        self.tree.heading("faces", text="삼각형")
        self.tree.heading("vs_hash", text="VS 해시")
        self.tree.heading("vb0_parent", text="VB0 Parent")
        self.tree.column("id", width=80)
        self.tree.column("verts", width=80)
        self.tree.column("faces", width=80)
        self.tree.column("vs_hash", width=120)
        self.tree.column("vb0_parent", width=120)

        scrollbar = ttk.Scrollbar(
            tree_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 실행 버튼
        btn_frame = ttk.Frame(self.tab_obj)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_extract = ttk.Button(
            btn_frame, text="OBJ 추출 시작", command=self._start_extraction
        )
        self.btn_extract.pack(side=tk.LEFT, padx=5)
        self.btn_cancel = ttk.Button(
            btn_frame, text="취소", command=self._cancel_extraction, state=tk.DISABLED
        )
        self.btn_cancel.pack(side=tk.LEFT, padx=5)

    def _build_efmi_extract_tab(self):
        """EFMI 오브젝트 추출 탭"""
        # 소스 설정
        source_frame = ttk.LabelFrame(self.tab_efmi_extract, text="소스 설정", padding=10)
        source_frame.pack(fill=tk.X, pady=5)

        ttk.Label(source_frame, text="FrameAnalysis 덤프 폴더:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Label(source_frame, text="(캐릭터 메뉴에서 촬영)", font=("", 8)).grid(
            row=0, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.efmi_extract_dump_dir, width=60).grid(
            row=1, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_efmi_extract_dump
        ).grid(row=1, column=2, pady=2)

        ttk.Label(source_frame, text="출력 폴더:").grid(
            row=2, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Label(source_frame, text="(Component .vb, .ib, .fmt, Metadata.json)", font=("", 8)).grid(
            row=2, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.efmi_extract_output_dir, width=60).grid(
            row=3, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_efmi_extract_output
        ).grid(row=3, column=2, pady=2)

        # 실행 버튼
        btn_frame = ttk.Frame(self.tab_efmi_extract)
        btn_frame.pack(fill=tk.X, pady=10)

        self.btn_efmi_extract = ttk.Button(
            btn_frame, text="EFMI 오브젝트 추출 시작", command=self._start_efmi_extract
        )
        self.btn_efmi_extract.pack(side=tk.LEFT, padx=5)

        # 설명
        help_frame = ttk.Frame(self.tab_efmi_extract)
        help_frame.pack(fill=tk.X, pady=5)

        help_text = (
            "EFMI 오브젝트 추출 방법:\n"
            "1. FrameAnalysis 덤프 폴더: 캐릭터 메뉴에서 Shift+F11로 촬영한 덤프\n"
            "2. 출력 폴더: Component .vb, .ib, .fmt 파일과 Metadata.json이 저장됨\n"
            "3. [EFMI 오브젝트 추출 시작] 클릭 -> LOD 매칭 준비 완료\n\n"
            "출력된 폴더는 LOD 추출 탭에서 바로 사용할 수 있습니다!"
        )
        ttk.Label(
            help_frame, text=help_text, justify=tk.LEFT, font=("", 9), foreground="gray"
        ).pack(anchor=tk.W)

    def _build_efmi_tab(self):
        """EFMI Export 탭"""
        # 소스 설정
        source_frame = ttk.LabelFrame(self.tab_efmi, text="소스 설정", padding=10)
        source_frame.pack(fill=tk.X, pady=5)

        ttk.Label(source_frame, text="FrameAnalysis 폴더:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Label(source_frame, text="(메쉬 추출 원본)", font=("", 8)).grid(
            row=0, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.input_dir, width=60).grid(
            row=1, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(source_frame, text="찾아보기", command=self._browse_input).grid(
            row=1, column=2, pady=2
        )

        ttk.Label(source_frame, text="Metadata.json 출력 폴더:").grid(
            row=2, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Entry(source_frame, textvariable=self.efmi_source_folder, width=60).grid(
            row=3, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_efmi_source
        ).grid(row=3, column=2, pady=2)

        # Metadata.json 생성 버튼
        meta_btn_frame = ttk.Frame(source_frame)
        meta_btn_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.btn_gen_metadata = ttk.Button(
            meta_btn_frame, text="Metadata.json 생성", command=self._generate_metadata
        )
        self.btn_gen_metadata.pack(side=tk.LEFT, padx=5)

        ttk.Label(
            meta_btn_frame,
            text="← 먼저 클릭하여 Metadata.json을 생성하세요",
            font=("", 8),
            foreground="gray",
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(source_frame, text="모드 출력 폴더:").grid(
            row=5, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Entry(source_frame, textvariable=self.efmi_output_folder, width=60).grid(
            row=6, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_efmi_output
        ).grid(row=6, column=2, pady=2)

        # 모드 정보
        info_frame = ttk.LabelFrame(self.tab_efmi, text="모드 정보", padding=10)
        info_frame.pack(fill=tk.X, pady=5)

        ttk.Label(info_frame, text="모드 이름:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Entry(info_frame, textvariable=self.efmi_mod_name, width=60).grid(
            row=0, column=1, padx=5, pady=2
        )

        ttk.Label(info_frame, text="작성자:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(info_frame, textvariable=self.efmi_mod_author, width=60).grid(
            row=1, column=1, padx=5, pady=2
        )

        ttk.Label(info_frame, text="설명:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(info_frame, textvariable=self.efmi_mod_desc, width=60).grid(
            row=2, column=1, padx=5, pady=2
        )

        ttk.Label(info_frame, text="링크:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(info_frame, textvariable=self.efmi_mod_link, width=60).grid(
            row=3, column=1, padx=5, pady=2
        )

        # 옵션
        options_frame = ttk.LabelFrame(self.tab_efmi, text="추출 옵션", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(
            options_frame,
            text="메쉬 좌우 반전 (Mirror Mesh)",
            variable=self.efmi_mirror_mesh,
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(
            options_frame, text="텍스처 복사", variable=self.efmi_copy_textures
        ).grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(
            options_frame, text="mod.ini 주석 포함", variable=self.efmi_comment_ini
        ).grid(row=2, column=0, sticky=tk.W, pady=2)

        # 설명
        help_label = ttk.Label(
            options_frame,
            text="FrameAnalysis 폴더에서 추출한 메쉬를 EFMI 형식으로 내보냅니다",
            font=("", 8),
            foreground="gray",
        )
        help_label.grid(row=3, column=0, sticky=tk.W, pady=(10, 2))

        # 실행 버튼
        btn_frame = ttk.Frame(self.tab_efmi)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_efmi_export = ttk.Button(
            btn_frame, text="EFMI 모드 내보내기", command=self._start_efmi_export
        )
        self.btn_efmi_export.pack(side=tk.LEFT, padx=5)

    def _build_extracted_import_tab(self):
        """추출물 변환 탭 (EFMI-Tools Import 기능 구현)"""
        # 소스 설정
        source_frame = ttk.LabelFrame(self.tab_ext_import, text="설정", padding=10)
        source_frame.pack(fill=tk.X, pady=5)

        ttk.Label(source_frame, text="추출물 폴더 (Source):").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Label(source_frame, text="(Metadata.json 및 .vb 파일들이 있는 곳)", font=("", 8)).grid(
            row=0, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.ext_import_source_dir, width=60).grid(
            row=1, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_ext_import_source
        ).grid(row=1, column=2, pady=2)

        ttk.Label(source_frame, text="출력 저장 폴더 (Output):").grid(
            row=2, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Entry(source_frame, textvariable=self.ext_import_output_dir, width=60).grid(
            row=3, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(source_frame, text="찾아보기", command=self._browse_ext_import_output).grid(
            row=3, column=2, pady=2
        )

        # 옵션
        options_frame = ttk.LabelFrame(self.tab_ext_import, text="내보내기 옵션", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        ttk.Checkbutton(
            options_frame,
            text="개별 OBJ 파일로 저장 (Component_*.obj)",
            variable=self.ext_import_export_individual,
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Checkbutton(
            options_frame,
            text="하나의 OBJ 파일로 결합 (combined.obj)",
            variable=self.ext_import_export_combined,
        ).grid(row=1, column=0, sticky=tk.W, pady=2)

        # 실행 버튼
        btn_frame = ttk.Frame(self.tab_ext_import)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_ext_import = ttk.Button(
            btn_frame, text="변환 시작", command=self._start_extracted_import
        )
        self.btn_ext_import.pack(side=tk.LEFT, padx=5)

        # 설명
        help_frame = ttk.Frame(self.tab_ext_import)
        help_frame.pack(fill=tk.X, pady=5)

        help_text = (
            "추출물 변환 (Extracted Object Import):\n"
            "1. EFMI 오브젝트 추출 탭에서 생성된 폴더를 선택합니다.\n"
            "2. 모든 컴포넌트(.vb, .ib)를 하나로 합쳐서 .obj 파일로 변환합니다.\n"
            "3. TBN(10-10-10-2) 데이터 디코딩 및 메타데이터의 회전값이 적용됩니다."
        )
        ttk.Label(
            help_frame, text=help_text, justify=tk.LEFT, font=("", 9), foreground="gray"
        ).pack(anchor=tk.W)

    def _build_mod_export_tab(self):
        """모드 익스포트 탭"""
        # 소스 설정
        source_frame = ttk.LabelFrame(self.tab_mod_export, text="설정", padding=10)
        source_frame.pack(fill=tk.X, pady=5)

        ttk.Label(source_frame, text="수정된 OBJ 파일/폴더:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.mod_export_obj_path, width=60).grid(
            row=1, column=0, columnspan=2, padx=5, pady=2
        )
        
        btn_frame_obj = ttk.Frame(source_frame)
        btn_frame_obj.grid(row=1, column=2, pady=2)
        
        ttk.Button(
            btn_frame_obj, text="파일", command=self._browse_mod_export_obj, width=6
        ).pack(side=tk.LEFT, padx=1)
        ttk.Button(
            btn_frame_obj, text="폴더", command=self._browse_mod_export_obj_dir, width=6
        ).pack(side=tk.LEFT, padx=1)

        ttk.Label(source_frame, text="원본 추출물 폴더 (efmi_output):").grid(
            row=2, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Label(source_frame, text="(Component .vb 및 Metadata.json)", font=("", 8)).grid(
            row=2, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.mod_export_efmi_dir, width=60).grid(
            row=3, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_mod_export_efmi
        ).grid(row=3, column=2, pady=2)

        ttk.Label(source_frame, text="출력 저장 폴더 (Mod Output):").grid(
            row=4, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Entry(source_frame, textvariable=self.mod_export_output_dir, width=60).grid(
            row=5, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(source_frame, text="찾아보기", command=self._browse_mod_export_output).grid(
            row=5, column=2, pady=2
        )

        # 실행 버튼
        btn_frame = ttk.Frame(self.tab_mod_export)
        btn_frame.pack(fill=tk.X, pady=10)

        self.btn_mod_export = ttk.Button(
            btn_frame, text="모드 익스포트 시작", command=self._start_mod_export
        )
        self.btn_mod_export.pack(side=tk.LEFT, padx=5)

        # 설명
        help_frame = ttk.Frame(self.tab_mod_export)
        help_frame.pack(fill=tk.X, pady=5)

        help_text = (
            "모드 익스포트 (Mod Export):\n"
            "1. 블렌더 등에서 수정된 OBJ 파일을 선택합니다. (정점 개수가 원본과 정확히 동일해야 함!)\n"
            "2. EFMI 오브젝트 추출 탭에서 생성한 추출물 폴더(Metadata.json, .vb)를 선택합니다.\n"
            "3. 지정된 출력 폴더에 3DMigoto용 모드 파일(.buf 및 mod.ini)이 생성됩니다.\n"
            "4. 이 과정에서 수정된 법선(Normal)과 UV가 인코딩되어 원본 버퍼에 결합됩니다."
        )
        ttk.Label(
            help_frame, text=help_text, justify=tk.LEFT, font=("", 9), foreground="gray"
        ).pack(anchor=tk.W)

    def _build_lod_tab(self):
        """LOD 추출 탭"""
        # 소스 설정
        source_frame = ttk.LabelFrame(self.tab_lod, text="소스 설정", padding=10)
        source_frame.pack(fill=tk.X, pady=5)

        ttk.Label(source_frame, text="원본 메쉬 폴더:").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Label(source_frame, text="(Metadata.json 포함)", font=("", 8)).grid(
            row=0, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.lod_full_model_dir, width=60).grid(
            row=1, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(
            source_frame, text="찾아보기", command=self._browse_lod_full_model
        ).grid(row=1, column=2, pady=2)

        ttk.Label(source_frame, text="LOD 덤프 폴더:").grid(
            row=2, column=0, sticky=tk.W, pady=(10, 2)
        )
        ttk.Label(source_frame, text="(오픈 월드 FrameAnalysis)", font=("", 8)).grid(
            row=2, column=1, sticky=tk.W, pady=2
        )
        ttk.Entry(source_frame, textvariable=self.lod_dump_dir, width=60).grid(
            row=3, column=0, columnspan=2, padx=5, pady=2
        )
        ttk.Button(source_frame, text="찾아보기", command=self._browse_lod_dump).grid(
            row=3, column=2, pady=2
        )

        # 매칭 설정
        settings_frame = ttk.LabelFrame(self.tab_lod, text="매칭 설정", padding=10)
        settings_frame.pack(fill=tk.X, pady=5)

        ttk.Label(settings_frame, text="유사도 임계값 (%):").grid(
            row=0, column=0, sticky=tk.W, pady=2
        )
        ttk.Spinbox(
            settings_frame,
            from_=20,
            to=100,
            textvariable=self.lod_similarity_threshold,
            width=10,
        ).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(
            settings_frame,
            text="(낮을수록 더 많은 LOD 매칭)",
            font=("", 8),
            foreground="gray",
        ).grid(row=0, column=2, sticky=tk.W, pady=2)

        ttk.Label(settings_frame, text="복셀 크기:").grid(
            row=1, column=0, sticky=tk.W, pady=2
        )
        ttk.Spinbox(
            settings_frame,
            from_=0.01,
            to=0.2,
            increment=0.01,
            textvariable=self.lod_voxel_size,
            width=10,
        ).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(
            settings_frame,
            text="(작을수록 정밀, 느림)",
            font=("", 8),
            foreground="gray",
        ).grid(row=1, column=2, sticky=tk.W, pady=2)

        ttk.Label(settings_frame, text="민감도:").grid(
            row=2, column=0, sticky=tk.W, pady=2
        )
        ttk.Spinbox(
            settings_frame,
            from_=0.1,
            to=2.0,
            increment=0.1,
            textvariable=self.lod_sensitivity,
            width=10,
        ).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(
            settings_frame, text="(클수록 관대한 매칭)", font=("", 8), foreground="gray"
        ).grid(row=2, column=2, sticky=tk.W, pady=2)

        # 실행 버튼
        btn_frame = ttk.Frame(self.tab_lod)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_extract_lod = ttk.Button(
            btn_frame, text="LOD 추출 시작", command=self._start_lod_extraction
        )
        self.btn_extract_lod.pack(side=tk.LEFT, padx=5)

        # 설명
        help_frame = ttk.Frame(self.tab_lod)
        help_frame.pack(fill=tk.X, pady=5)

        help_text = (
            "LOD 추출 방법:\n"
            "1. 원본 메쉬 폴더: Metadata.json이 있는 폴더 선택\n"
            "2. LOD 덤프 폴더: 게임에서 멀리 떨어진 상태로 찍은 FrameAnalysis 덤프\n"
            "3. [LOD 추출 시작] 클릭 → Metadata.json이 LOD 정보로 업데이트됨"
        )
        ttk.Label(
            help_frame, text=help_text, justify=tk.LEFT, font=("", 9), foreground="gray"
        ).pack(anchor=tk.W)

    def _on_coord_select(self, event):
        """좌표계 선택 시 실제 값 매핑"""
        mapping = {
            "Reference (Z-up, chen.obj 기준)": "reference",
            "Blender (Y-up)": "blender",
            "Original (DirectX 원본)": "original",
        }
        display = self.coord_system.get()
        self.coord_system.set(mapping.get(display, "reference"))

    def _browse_input(self):
        """입력 디렉토리 선택"""
        dir_path = filedialog.askdirectory(title="FrameAnalysis 디렉토리 선택")
        if dir_path:
            self.input_dir.set(dir_path)

    def _browse_output(self):
        """출력 디렉토리 선택"""
        dir_path = filedialog.askdirectory(title="출력 디렉토리 선택")
        if dir_path:
            self.output_dir.set(dir_path)

    def _browse_efmi_source(self):
        """EFMI 소스 폴더 선택"""
        dir_path = filedialog.askdirectory(
            title="오브젝트 소스 폴더 (Metadata.json 있는 곳)"
        )
        if dir_path:
            self.efmi_source_folder.set(dir_path)

    def _browse_efmi_output(self):
        """EFMI 출력 폴더 선택"""
        dir_path = filedialog.askdirectory(title="모드 출력 폴더")
        if dir_path:
            self.efmi_output_folder.set(dir_path)

    def _browse_lod_full_model(self):
        """원본 메쉬 폴더 선택"""
        dir_path = filedialog.askdirectory(title="원본 메쉬 폴더 (Metadata.json 포함)")
        if dir_path:
            self.lod_full_model_dir.set(dir_path)

    def _browse_lod_dump(self):
        """LOD 덤프 폴더 선택"""
        dir_path = filedialog.askdirectory(
            title="LOD 덤프 디렉토리 선택 (오픈 월드 FrameAnalysis)"
        )
        if dir_path:
            self.lod_dump_dir.set(dir_path)

    def _browse_ext_import_source(self):
        dir_path = filedialog.askdirectory(title="추출물 폴더 선택 (Metadata.json 포함)")
        if dir_path:
            self.ext_import_source_dir.set(dir_path)
            # 기본 출력 폴더 설정
            self.ext_import_output_dir.set(os.path.join(dir_path, "OBJ_Export"))

    def _browse_ext_import_output(self):
        dir_path = filedialog.askdirectory(title="출력 폴더 선택")
        if dir_path:
            self.ext_import_output_dir.set(dir_path)

    def _browse_efmi_extract_dump(self):
        """EFMI 추출 덤프 폴더 선택"""
        dir_path = filedialog.askdirectory(title="FrameAnalysis 덤프 폴더 선택")
        if dir_path:
            self.efmi_extract_dump_dir.set(dir_path)

    def _browse_efmi_extract_output(self):
        """EFMI 추출 출력 폴더 선택"""
        dir_path = filedialog.askdirectory(title="출력 폴더 선택")
        if dir_path:
            self.efmi_extract_output_dir.set(dir_path)

    def _browse_mod_export_obj(self):
        file_path = filedialog.askopenfilename(
            title="수정된 OBJ 파일 선택 (Combined.obj)",
            filetypes=[("OBJ Files", "*.obj"), ("All Files", "*.*")]
        )
        if file_path:
            self.mod_export_obj_path.set(file_path)
            
    def _browse_mod_export_obj_dir(self):
        dir_path = filedialog.askdirectory(title="수정된 OBJ 폴더 선택 (Component_*.obj)")
        if dir_path:
            self.mod_export_obj_path.set(dir_path)

    def _browse_mod_export_efmi(self):
        dir_path = filedialog.askdirectory(title="원본 추출물 폴더 (Metadata.json 포함)")
        if dir_path:
            self.mod_export_efmi_dir.set(dir_path)

    def _browse_mod_export_output(self):
        dir_path = filedialog.askdirectory(title="모드 출력 폴더 선택")
        if dir_path:
            self.mod_export_output_dir.set(dir_path)

    def _log(self, message):
        """로그 추가"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.root.update_idletasks()

    def _load_mesh_list(self):
        """메쉬 목록 로드"""
        input_dir = self.input_dir.get()
        if not input_dir or not os.path.exists(input_dir):
            messagebox.showwarning("경고", "유효한 입력 디렉토리를 선택하세요")
            return

        self._log("메쉬 목록 로딩 중...")

        try:
            from mesh_parser import parse_frame_analysis_directory

            self.current_meshes = parse_frame_analysis_directory(input_dir)

            for item in self.tree.get_children():
                self.tree.delete(item)

            for dc_id, mesh in sorted(self.current_meshes.items()):
                self.tree.insert(
                    "",
                    tk.END,
                    values=(
                        f"{dc_id:06d}",
                        len(mesh.vertices),
                        len(mesh.indices) // 3,
                        mesh.vertex_shader_hash[:12] if mesh.vertex_shader_hash else "",
                        mesh.vb0_parent_hash[:12] if mesh.vb0_parent_hash else "",
                    ),
                )

            self._log(f"{len(self.current_meshes)}개 메쉬 발견")

        except Exception as e:
            messagebox.showerror("오류", f"메쉬 로딩 실패:\n{str(e)}")
            self._log(f"오류: {str(e)}")

    def _remove_duplicates(self):
        """중복 메쉬 제거"""
        if not self.current_meshes:
            messagebox.showwarning("경고", "먼저 메쉬를 로드하세요")
            return

        self._log("중복 메쉬 검사 중...")

        try:
            from remove_duplicates import remove_duplicate_meshes

            original_count = len(self.current_meshes)
            cleaned_meshes, removed_ids = remove_duplicate_meshes(
                self.current_meshes, keep_first=True
            )

            if not removed_ids:
                self._log("중복된 메쉬가 없습니다.")
                messagebox.showinfo("완료", "중복된 메쉬가 없습니다.")
                return

            removed_count = len(removed_ids)
            self._log(
                f"중복 제거 완료: {original_count}개 → {len(cleaned_meshes)}개 메쉬 ({removed_count}개 제거)"
            )

            removed_list = ", ".join(f"DC {dc_id:06d}" for dc_id in removed_ids)
            self._log(f"제거된 메쉬: {removed_list}")

            self.current_meshes = cleaned_meshes

            for item in self.tree.get_children():
                self.tree.delete(item)

            for dc_id, mesh in sorted(self.current_meshes.items()):
                self.tree.insert(
                    "",
                    tk.END,
                    values=(
                        f"{dc_id:06d}",
                        len(mesh.vertices),
                        len(mesh.indices) // 3,
                        mesh.vertex_shader_hash[:12] if mesh.vertex_shader_hash else "",
                        mesh.vb0_parent_hash[:12] if mesh.vb0_parent_hash else "",
                    ),
                )

            messagebox.showinfo(
                "중복 제거 완료",
                f"중복 메쉬 제거 완료\n\n"
                f"제거 전: {original_count}개\n"
                f"제거 후: {len(cleaned_meshes)}개\n"
                f"제거됨: {removed_count}개",
            )

        except Exception as e:
            messagebox.showerror("오류", f"중복 제거 실패:\n{str(e)}")
            self._log(f"중복 제거 오류: {str(e)}")

    def _start_extraction(self):
        """추출 시작"""
        input_dir = self.input_dir.get()
        output_dir = self.output_dir.get()

        if not input_dir or not os.path.exists(input_dir):
            messagebox.showwarning("경고", "유효한 입력 디렉토리를 선택하세요")
            return

        if not output_dir:
            messagebox.showwarning("경고", "출력 디렉토리를 입력하세요")
            return

        if not self.export_individual.get() and not self.export_combined.get():
            messagebox.showwarning("경고", "최소 하나의 내보내기 옵션을 선택하세요")
            return

        self.btn_extract.configure(state=tk.DISABLED)
        self.btn_cancel.configure(state=tk.NORMAL)
        self.is_running = True

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self._log("추출 시작...")

        thread = threading.Thread(
            target=self._run_extraction, args=(input_dir, output_dir), daemon=True
        )
        thread.start()

    def _run_extraction(self, input_dir, output_dir):
        """실제 추출 실행 (백그라운드)"""
        try:
            from obj_exporter import (
                export_all_meshes_to_obj,
                export_meshes_combined_obj,
            )

            if not self.current_meshes:
                from mesh_parser import parse_frame_analysis_directory

                self._log("메쉬 파싱 중...")
                self.current_meshes = parse_frame_analysis_directory(input_dir)

            meshes = self.current_meshes
            self._log(f"{len(meshes)}개 메쉬 처리")

            if not meshes:
                self._log("추출할 메쉬가 없습니다.")
                self.root.after(
                    0, self._extraction_done, False, "추출할 메쉬가 없습니다."
                )
                return

            os.makedirs(output_dir, exist_ok=True)

            if self.export_individual.get():
                self._log("개별 OBJ 파일 내보내기...")
                files = export_all_meshes_to_obj(
                    meshes, output_dir, coord_system=self.coord_system.get()
                )
                self._log(f"{len(files)}개 파일 생성 완료")

            if self.export_combined.get():
                self._log("결합된 OBJ 파일 내보내기...")
                combined_path = os.path.join(output_dir, "combined_mesh.obj")
                export_meshes_combined_obj(
                    meshes, combined_path, coord_system=self.coord_system.get()
                )
                self._log(f"결합된 파일 생성: {combined_path}")

            self.root.after(
                0, self._extraction_done, True, f"추출 완료! ({len(meshes)}개 메쉬)"
            )

        except Exception as e:
            self.root.after(0, self._extraction_done, False, f"오류 발생: {str(e)}")

    def _extraction_done(self, success, message):
        """추출 완료 처리"""
        self.btn_extract.configure(state=tk.NORMAL)
        self.btn_cancel.configure(state=tk.DISABLED)
        self.is_running = False

        self._log(message)

        if success:
            self._log("Mesh_000013, Mesh_000014 오리진 설정 및 위치 이동 적용 중...")
            self._apply_origin_and_transform()
            messagebox.showinfo("완료", message)
        else:
            messagebox.showerror("오류", message)

    def _apply_origin_and_transform(self):
        """Mesh_000013, Mesh_000014에 오리진 설정 및 위치 이동 적용"""
        try:
            import subprocess

            script_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "apply_origin_and_move.py"
            )

            if os.path.exists(script_path):
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.stdout:
                    for line in result.stdout.strip().split("\n"):
                        self._log(f"  {line}")

                if result.returncode == 0:
                    self._log("오리진 설정 및 위치 이동 완료!")
                else:
                    self._log(f"경고: 변환 스크립트 실행 실패")
                    if result.stderr:
                        self._log(f"  오류: {result.stderr.strip()}")
            else:
                self._log(f"경고: apply_origin_and_move.py를 찾을 수 없습니다")

        except subprocess.TimeoutExpired:
            self._log("경고: 변환 스크립트 시간 초과")
        except Exception as e:
            self._log(f"경고: 변환 중 오류 발생 - {str(e)}")

    def _cancel_extraction(self):
        """추출 취소"""
        self.is_running = False
        self._log("추출 취소됨")
        self.btn_extract.configure(state=tk.NORMAL)
        self.btn_cancel.configure(state=tk.DISABLED)

    def _start_efmi_export(self):
        """EFMI Export 시작"""
        source_folder = self.efmi_source_folder.get()
        output_folder = self.efmi_output_folder.get()
        input_dir = self.input_dir.get()

        if not output_folder:
            messagebox.showwarning("경고", "출력 디렉토리를 입력하세요")
            return

        # Metadata.json 확인, 없으면 자동 생성
        metadata_path = Path(source_folder) / "Metadata.json"
        if not metadata_path.exists():
            if not input_dir or not os.path.exists(input_dir):
                messagebox.showerror(
                    "오류",
                    f"Metadata.json이 없고 FrameAnalysis 폴더도 설정되지 않았습니다.\n\n1. FrameAnalysis 폴더를 선택하세요\n2. Metadata.json 생성 버튼을 클릭하세요\n3. 다시 시도하세요",
                )
                return

            # 자동 생성 확인
            result = messagebox.askyesno(
                "Metadata.json 없음",
                f"Metadata.json이 없습니다.\n\nFrameAnalysis 폴더에서 자동 생성할까요?\n\n{input_dir}",
            )
            if result:
                self._log("Metadata.json 자동 생성 중...")
                try:
                    from metadata_generator import generate_metadata_from_directory

                    metadata_path = generate_metadata_from_directory(
                        input_dir, source_folder, object_name="ExtractedObject"
                    )
                    self._log(f"Metadata.json 자동 생성 완료: {metadata_path}")
                except Exception as e:
                    messagebox.showerror(
                        "오류", f"Metadata.json 자동 생성 실패:\n{str(e)}"
                    )
                    return
            else:
                return

        # 버튼 상태
        self.btn_efmi_export.configure(state=tk.DISABLED)
        self.is_running = True

        self._log("EFMI Export 시작...")

        thread = threading.Thread(
            target=self._run_efmi_export,
            args=(source_folder, output_folder),
            daemon=True,
        )
        thread.start()

    def _run_efmi_export(self, source_folder, output_folder):
        """EFMI Export 실행 (백그라운드)"""
        try:
            from pathlib import Path
            from efmi_export import ExportConfig, EFMIExporter

            # 현재 로드된 메쉬 사용
            if not self.current_meshes:
                input_dir = self.input_dir.get()
                if input_dir and os.path.exists(input_dir):
                    self._log("메쉬 파싱 중...")
                    from mesh_parser import parse_frame_analysis_directory

                    self.current_meshes = parse_frame_analysis_directory(input_dir)
                else:
                    self._log("경고: FrameAnalysis 폴더에서 메쉬를 먼저 로드하세요")
                    self.current_meshes = {}

            config = ExportConfig(
                object_source_folder=Path(source_folder),
                mod_output_folder=Path(output_folder),
                mod_name=self.efmi_mod_name.get(),
                mod_author=self.efmi_mod_author.get(),
                mod_desc=self.efmi_mod_desc.get(),
                mod_link=self.efmi_mod_link.get(),
                mirror_mesh=self.efmi_mirror_mesh.get(),
                copy_textures=self.efmi_copy_textures.get(),
                comment_ini=self.efmi_comment_ini.get(),
            )

            exporter = EFMIExporter(config)
            success = exporter.export(self.current_meshes)

            if success:
                self.root.after(
                    0,
                    self._efmi_export_done,
                    True,
                    f"EFMI Export 완료!\n출력: {output_folder}",
                )
            else:
                self.root.after(
                    0, self._efmi_export_done, False, "EFMI Export 실패 (로그 확인)"
                )

        except Exception as e:
            self.root.after(0, self._efmi_export_done, False, f"오류 발생: {str(e)}")

    def _efmi_export_done(self, success, message):
        """EFMI Export 완료 처리"""
        self.btn_efmi_export.configure(state=tk.NORMAL)
        self.is_running = False

        self._log(message)

        if success:
            messagebox.showinfo("완료", message)
        else:
            messagebox.showerror("오류", message)

    def _generate_metadata(self):
        """Metadata.json 생성"""
        input_dir = self.input_dir.get()
        output_dir = self.efmi_source_folder.get()

        if not input_dir or not os.path.exists(input_dir):
            messagebox.showwarning("경고", "FrameAnalysis 폴더를 먼저 선택하세요")
            return

        if not output_dir:
            messagebox.showwarning("경고", "Metadata.json 출력 폴더를 선택하세요")
            return

        self._log("Metadata.json 생성 중...")
        self.btn_gen_metadata.configure(state=tk.DISABLED)

        try:
            from metadata_generator import generate_metadata_from_directory

            metadata_path = generate_metadata_from_directory(
                input_dir, output_dir, object_name="ExtractedObject"
            )

            self._log(f"Metadata.json 생성 완료: {metadata_path}")
            messagebox.showinfo("완료", f"Metadata.json 생성 완료\n{metadata_path}")

        except Exception as e:
            self._log(f"Metadata.json 생성 실패: {str(e)}")
            messagebox.showerror("오류", f"Metadata.json 생성 실패:\n{str(e)}")
        finally:
            self.btn_gen_metadata.configure(state=tk.NORMAL)

    def _start_lod_extraction(self):
        """LOD 추출 시작"""
        full_model_dir = self.lod_full_model_dir.get()
        lod_dump_dir = self.lod_dump_dir.get()
        similarity_threshold = self.lod_similarity_threshold.get()
        voxel_size = self.lod_voxel_size.get()
        sensitivity = self.lod_sensitivity.get()

        if not full_model_dir or not os.path.exists(full_model_dir):
            messagebox.showwarning("경고", "원본 메쉬 폴더를 선택하세요")
            return

        if not lod_dump_dir or not os.path.exists(lod_dump_dir):
            messagebox.showwarning("경고", "LOD 덤프 폴더를 선택하세요")
            return

        metadata_path = Path(full_model_dir) / "Metadata.json"
        if not metadata_path.exists():
            messagebox.showerror(
                "오류", "Metadata.json이 없습니다.\n원본 메쉬 폴더를 확인하세요."
            )
            return

        self.btn_extract_lod.configure(state=tk.DISABLED)
        self.is_running = True

        self._log("LOD 추출 시작...")
        self._log(f"  원본: {full_model_dir}")
        self._log(f"  LOD 덤프: {lod_dump_dir}")
        self._log(f"  유사도 임계값: {similarity_threshold}%")

        thread = threading.Thread(
            target=self._run_lod_extraction,
            args=(
                full_model_dir,
                lod_dump_dir,
                similarity_threshold,
                voxel_size,
                sensitivity,
            ),
            daemon=True,
        )
        thread.start()

    def _run_lod_extraction(
        self,
        full_model_dir,
        lod_dump_dir,
        similarity_threshold,
        voxel_size,
        sensitivity,
    ):
        """LOD 추출 실행 (백그라운드) - stdout 캡처"""
        import io

        # stdout/stderr 캡처용
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_output = io.StringIO()

        try:
            sys.stdout = captured_output
            sys.stderr = captured_output

            from lod_extractor import extract_lods

            output_dir = full_model_dir

            results = extract_lods(
                full_model_dir=full_model_dir,
                lod_dump_dir=lod_dump_dir,
                output_dir=output_dir,
                similarity_threshold=similarity_threshold,
                voxel_size=voxel_size,
                sensitivity=sensitivity,
            )

            # 캡처된 출력 가져오기
            output_text = captured_output.getvalue()
            for line in output_text.split('\n'):
                if line.strip():
                    self.root.after(0, lambda l=line: self._log(l))

            matched_count = len(results)
            self.root.after(
                0,
                self._lod_extraction_done,
                True,
                f"LOD 추출 완료! ({matched_count}개 매칭됨)",
            )

        except Exception as e:
            import traceback
            
            # 오류 시에도 캡처된 출력 가져오기
            output_text = captured_output.getvalue()
            for line in output_text.split('\n'):
                if line.strip():
                    self.root.after(0, lambda l=line: self._log(l))

            self.root.after(
                0,
                self._lod_extraction_done,
                False,
                f"오류 발생: {str(e)}\n{traceback.format_exc()}",
            )
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    def _lod_extraction_done(self, success, message):
        """LOD 추출 완료 처리"""
        self.btn_extract_lod.configure(state=tk.NORMAL)
        self.is_running = False

        self._log(message)

        if success:
            messagebox.showinfo("완료", message)
        else:
            messagebox.showerror("오류", message)

    def _start_extracted_import(self):
        """추출물 변환 시작"""
        source_dir = self.ext_import_source_dir.get()
        output_dir = self.ext_import_output_dir.get()
        do_individual = self.ext_import_export_individual.get()
        do_combined = self.ext_import_export_combined.get()

        if not source_dir or not os.path.isdir(source_dir):
            messagebox.showerror("오류", "유효한 추출물 폴더를 선택해주세요.")
            return
        
        if not output_dir:
            messagebox.showerror("오류", "출력 폴더 경로를 지정해주세요.")
            return

        if not do_individual and not do_combined:
            messagebox.showwarning("경고", "최소 하나 이상의 내보내기 옵션을 선택하세요.")
            return

        self.is_running = True
        self.btn_ext_import.configure(state=tk.DISABLED)
        self._log("============================================================")
        self._log("추출물 변환 시작...")
        
        thread = threading.Thread(
            target=self._run_extracted_import_thread, 
            args=(source_dir, output_dir, do_individual, do_combined),
            daemon=True
        )
        thread.start()

    def _run_extracted_import_thread(self, source_dir, output_dir, do_individual, do_combined):
        """추출물 변환 실행 (백그라운드)"""
        try:
            from extracted_object_importer import ExtractedObjectImporter
            import time
            
            start_time = time.time()
            importer = ExtractedObjectImporter()
            
            self._log(f"  폴더 로드 중: {source_dir}")
            meshes = importer.import_from_folder(source_dir)
            
            if not meshes:
                self._log("  오류: 로드된 메쉬가 없습니다.")
                return

            self._log(f"  {len(meshes)}개 컴포넌트 로드 완료.")
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            if do_individual:
                self._log(f"  개별 OBJ 내보내는 중... (저장위치: {output_dir})")
                importer.export_individual(meshes, output_dir)
            
            if do_combined:
                combined_path = os.path.join(output_dir, "combined_mesh.obj")
                self._log(f"  결합된 OBJ 내보내는 중: {combined_path}")
                importer.export_combined(meshes, combined_path)
            
            elapsed = time.time() - start_time
            self._log("============================================================")
            self._log(f"변환 완료! (소요 시간: {elapsed:.1f}s)")
            self._log(f"결과 폴더: {output_dir}")
            self._log("============================================================")
            
            self.root.after(0, lambda: messagebox.showinfo("완료", f"성공적으로 {len(meshes)}개 컴포넌트를 변환했습니다."))
            
        except Exception as e:
            self._log(f"오류 발생: {e}")
            import traceback
            self._log(traceback.format_exc())
            self.root.after(0, lambda: messagebox.showerror("오류", f"변환 중 오류가 발생했습니다: {e}"))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.btn_ext_import.configure(state=tk.NORMAL))

    def _start_efmi_extract(self):
        """EFMI 추출 시작"""
        dump_dir = self.efmi_extract_dump_dir.get()
        output_dir = self.efmi_extract_output_dir.get()

        if not dump_dir or not os.path.exists(dump_dir):
            messagebox.showwarning("경고", "유효한 FrameAnalysis 덤프 폴더를 선택하세요")
            return

        if not output_dir:
            messagebox.showwarning("경고", "출력 폴더를 입력하세요")
            return

        self.btn_efmi_extract.configure(state=tk.DISABLED)
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self._log("EFMI 오브젝트 추출 시작...")

        thread = threading.Thread(
            target=self._run_efmi_extract, args=(dump_dir, output_dir), daemon=True
        )
        thread.start()

    def _run_efmi_extract(self, dump_dir, output_dir):
        """EFMI 추출 실행 (백그라운드) - stdout 캡처"""
        import io
        
        # stdout/stderr 캡용
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        captured_output = io.StringIO()
        
        try:
            sys.stdout = captured_output
            sys.stderr = captured_output
            
            from efmi_extractor import extract_efmi_objects

            self._log(f"Dump: {dump_dir}")
            self._log(f"Output: {output_dir}")
            self._log("")

            objects = extract_efmi_objects(
                dump_dir=dump_dir,
                output_dir=output_dir,
            )

            # 캡처된 출력 가져오기
            output_text = captured_output.getvalue()
            for line in output_text.split('\n'):
                if line.strip():
                    self.root.after(0, lambda l=line: self._log(l))

            total_components = sum(len(obj.components) for obj in objects) if objects else 0
            
            self.root.after(
                0,
                self._efmi_extract_done,
                True,
                f"추출 완료! {len(objects)}개 오브젝트, {total_components}개 컴포넌트",
            )

        except Exception as e:
            # 캡처된 출력 가져오기
            output_text = captured_output.getvalue()
            for line in output_text.split('\n'):
                if line.strip():
                    self.root.after(0, lambda l=line: self._log(l))
            
            self.root.after(0, self._efmi_extract_done, False, f"오류 발생: {str(e)}")
        finally:
            # stdout/stderr 복원
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            captured_output.close()

    def _efmi_extract_done(self, success, message):
        """EFMI 추출 완료 처리"""
        self.btn_efmi_extract.configure(state=tk.NORMAL)
        self._log(message)

        if success:
            self._log("")
            self._log("LOD 추출 탭에서 바로 사용할 수 있습니다!")
            messagebox.showinfo("완료", message)
        else:
            messagebox.showerror("오류", message)

    def _start_mod_export(self):
        obj_path = self.mod_export_obj_path.get()
        efmi_dir = self.mod_export_efmi_dir.get()
        output_dir = self.mod_export_output_dir.get()

        if not obj_path or not os.path.exists(obj_path):
            messagebox.showwarning("경고", "유효한 수정된 OBJ 파일 또는 폴더를 선택하세요")
            return
        if not efmi_dir or not os.path.exists(efmi_dir):
            messagebox.showwarning("경고", "유효한 원본 추출물 폴더(efmi_output)를 선택하세요")
            return
        if not output_dir:
            messagebox.showwarning("경고", "모드 출력 폴더를 선택하세요")
            return

        self.btn_mod_export.configure(state=tk.DISABLED)
        self.is_running = True
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self._log("모드 익스포트 시작...")

        thread = threading.Thread(
            target=self._run_mod_export, args=(obj_path, efmi_dir, output_dir), daemon=True
        )
        thread.start()

    def _run_mod_export(self, obj_path, efmi_dir, output_dir):
        try:
            from mod_exporter import export_mod
            
            export_mod(obj_path, efmi_dir, output_dir)

            self.root.after(0, self._log, "모드 익스포트 완료!")
            self.root.after(
                0, messagebox.showinfo, "완료", f"모드 익스포트 완료!\n출력 폴더: {output_dir}"
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.root.after(0, self._log, f"오류 발생: {str(e)}")
            self.root.after(0, messagebox.showerror, "오류", f"익스포트 실패:\n{str(e)}")
        finally:
            self.root.after(0, lambda: self.btn_mod_export.configure(state=tk.NORMAL))
            self.is_running = False



def main():
    root = tk.Tk()
    app = MeshExtractorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
