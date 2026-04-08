"""
FrameAnalysis 메쉬 추출 GUI (tkinter 기반)
Python 표준 라이브러리만 사용 (별도 설치 불필요)
중복 메쉬 제거 기능 포함
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


class MeshExtractorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("FrameAnalysis 메쉬 추출 도구")
        self.root.geometry("800x650")
        self.root.minsize(700, 550)

        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar(value="./Extracted_Meshes")
        self.coord_system = tk.StringVar(value="reference")
        self.export_individual = tk.BooleanVar(value=True)
        self.export_combined = tk.BooleanVar(value=True)
        self.is_running = False
        self.current_meshes = {}  # 현재 로드된 메쉬 저장

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
                # 아이콘 크기 조정 (32x32 또는 48x48)
                img = img.resize((48, 48), Image.Resampling.LANCZOS)
                icon = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, icon)
        except Exception as e:
            print(f"아이콘 설정 실패: {e}")

    def _build_ui(self):
        """UI 구성"""
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 입력 설정
        input_frame = ttk.LabelFrame(main_frame, text="입력 설정", padding=10)
        input_frame.pack(fill=tk.X, pady=5)

        # 입력 디렉토리
        ttk.Label(input_frame, text="추출할 FrameAnalysis 폴더 안 :").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(input_frame, textvariable=self.input_dir, width=60).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(input_frame, text="찾아보기", command=self._browse_input).grid(row=0, column=2, pady=2)

        # 출력 디렉토리
        ttk.Label(input_frame, text="mesh 저장위치:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(input_frame, textvariable=self.output_dir, width=60).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(input_frame, text="찾아보기", command=self._browse_output).grid(row=1, column=2, pady=2)

        # 추출 옵션
        options_frame = ttk.LabelFrame(main_frame, text="추출 옵션", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        # 좌표계 선택
        ttk.Label(options_frame, text="좌표계:").grid(row=0, column=0, sticky=tk.W, pady=2)
        coord_combo = ttk.Combobox(options_frame, textvariable=self.coord_system, width=40, state="readonly")
        coord_combo["values"] = [
            "Reference (Z-up, chen.obj 기준)",
            "Blender (Y-up)",
            "Original (DirectX 원본)"
        ]
        coord_combo.current(0)
        coord_combo.grid(row=0, column=1, padx=5, pady=2)
        # 실제 값 매핑
        coord_combo.bind("<<ComboboxSelected>>", self._on_coord_select)

        # 내보내기 옵션
        ttk.Checkbutton(options_frame, text="개별 OBJ 파일 내보내기", variable=self.export_individual).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)
        ttk.Checkbutton(options_frame, text="결합된 OBJ 파일 내보내기 (combined_mesh.obj)", variable=self.export_combined).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=2)

        # 메쉬 목록
        mesh_frame = ttk.LabelFrame(main_frame, text="메쉬 목록", padding=10)
        mesh_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 버튼 프레임 (메쉬 목록 상단)
        mesh_btn_frame = ttk.Frame(mesh_frame)
        mesh_btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(mesh_btn_frame, text="메쉬 목록 불러오기", command=self._load_mesh_list).pack(side=tk.LEFT, padx=2)
        ttk.Button(mesh_btn_frame, text="중복 메쉬 제거", command=self._remove_duplicates).pack(side=tk.LEFT, padx=2)

        # 트리뷰
        tree_frame = ttk.Frame(mesh_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("id", "verts", "faces", "vs_hash", "vb0_parent"), show="headings", height=8)
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

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 실행 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_extract = ttk.Button(btn_frame, text="추출 시작", command=self._start_extraction, style="Accent.TButton")
        self.btn_extract.pack(side=tk.LEFT, padx=5)
        self.btn_cancel = ttk.Button(btn_frame, text="취소", command=self._cancel_extraction, state=tk.DISABLED)
        self.btn_cancel.pack(side=tk.LEFT, padx=5)

        # 로그
        log_frame = ttk.LabelFrame(main_frame, text="로그", padding=10)
        log_frame.pack(fill=tk.X, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, state=tk.DISABLED, wrap=tk.WORD)
        self.log_text.pack(fill=tk.X)

    def _on_coord_select(self, event):
        """좌표계 선택 시 실제 값 매핑"""
        mapping = {
            "Reference (Z-up, chen.obj 기준)": "reference",
            "Blender (Y-up)": "blender",
            "Original (DirectX 원본)": "original"
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

            # 트리 초기화
            for item in self.tree.get_children():
                self.tree.delete(item)

            for dc_id, mesh in sorted(self.current_meshes.items()):
                self.tree.insert("", tk.END, values=(
                    f"{dc_id:06d}",
                    len(mesh.vertices),
                    len(mesh.indices) // 3,
                    mesh.vertex_shader_hash[:12] if mesh.vertex_shader_hash else "",
                    mesh.vb0_parent_hash[:12] if mesh.vb0_parent_hash else ""
                ))

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
            
            # 중복 제거 실행
            original_count = len(self.current_meshes)
            cleaned_meshes, removed_ids = remove_duplicate_meshes(self.current_meshes, keep_first=True)
            
            if not removed_ids:
                self._log("중복된 메쉬가 없습니다.")
                messagebox.showinfo("완료", "중복된 메쉬가 없습니다.")
                return
            
            # 결과 확인
            removed_count = len(removed_ids)
            self._log(f"중복 제거 완료: {original_count}개 → {len(cleaned_meshes)}개 메쉬 ({removed_count}개 제거)")
            
            # 제거된 메쉬 ID 표시
            removed_list = ", ".join(f"DC {dc_id:06d}" for dc_id in removed_ids)
            self._log(f"제거된 메쉬: {removed_list}")
            
            # 현재 메쉬 업데이트
            self.current_meshes = cleaned_meshes
            
            # 트리 업데이트
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            for dc_id, mesh in sorted(self.current_meshes.items()):
                self.tree.insert("", tk.END, values=(
                    f"{dc_id:06d}",
                    len(mesh.vertices),
                    len(mesh.indices) // 3,
                    mesh.vertex_shader_hash[:12] if mesh.vertex_shader_hash else "",
                    mesh.vb0_parent_hash[:12] if mesh.vb0_parent_hash else ""
                ))
            
            # 결과 메시지
            messagebox.showinfo(
                "중복 제거 완료",
                f"중복 메쉬 제거 완료\n\n"
                f"제거 전: {original_count}개\n"
                f"제거 후: {len(cleaned_meshes)}개\n"
                f"제거됨: {removed_count}개"
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

        # 버튼 상태
        self.btn_extract.configure(state=tk.DISABLED)
        self.btn_cancel.configure(state=tk.NORMAL)
        self.is_running = True

        # 로그 초기화
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self._log("추출 시작...")

        # 백그라운드 스레드에서 실행
        thread = threading.Thread(target=self._run_extraction, args=(input_dir, output_dir), daemon=True)
        thread.start()

    def _run_extraction(self, input_dir, output_dir):
        """실제 추출 실행 (백그라운드)"""
        try:
            from obj_exporter import export_all_meshes_to_obj, export_meshes_combined_obj

            # 현재 로드된 메쉬 사용 (중복 제거가 적용되었을 수 있음)
            if not self.current_meshes:
                from mesh_parser import parse_frame_analysis_directory
                self._log("메쉬 파싱 중...")
                self.current_meshes = parse_frame_analysis_directory(input_dir)
            
            meshes = self.current_meshes
            self._log(f"{len(meshes)}개 메쉬 처리")

            if not meshes:
                self._log("추출할 메쉬가 없습니다.")
                self.root.after(0, self._extraction_done, False, "추출할 메쉬가 없습니다.")
                return

            os.makedirs(output_dir, exist_ok=True)

            # 개별 OBJ
            if self.export_individual.get():
                self._log("개별 OBJ 파일 내보내기...")
                files = export_all_meshes_to_obj(meshes, output_dir, coord_system=self.coord_system.get())
                self._log(f"{len(files)}개 파일 생성 완료")

            # 결합 OBJ
            if self.export_combined.get():
                self._log("결합된 OBJ 파일 내보내기...")
                combined_path = os.path.join(output_dir, "combined_mesh.obj")
                export_meshes_combined_obj(meshes, combined_path, coord_system=self.coord_system.get())
                self._log(f"결합된 파일 생성: {combined_path}")

            self.root.after(0, self._extraction_done, True, f"추출 완료! ({len(meshes)}개 메쉬)")

        except Exception as e:
            self.root.after(0, self._extraction_done, False, f"오류 발생: {str(e)}")

    def _extraction_done(self, success, message):
        """추출 완료 처리"""
        self.btn_extract.configure(state=tk.NORMAL)
        self.btn_cancel.configure(state=tk.DISABLED)
        self.is_running = False

        self._log(message)

        if success:
            # 추출 완료 후 Mesh_000013, Mesh_000014 오리진 설정 및 위치 이동 적용
            self._log("Mesh_000013, Mesh_000014 오리진 설정 및 위치 이동 적용 중...")
            self._apply_origin_and_transform()
            
            messagebox.showinfo("완료", message)
        else:
            messagebox.showerror("오류", message)

    def _apply_origin_and_transform(self):
        """Mesh_000013, Mesh_000014에 오리진 설정 및 위치 이동 적용"""
        try:
            import subprocess
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apply_origin_and_move.py")
            
            if os.path.exists(script_path):
                result = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                # stdout 로그 출력
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
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
        self._log("추취 취소됨")
        self.btn_extract.configure(state=tk.NORMAL)
        self.btn_cancel.configure(state=tk.DISABLED)


def main():
    root = tk.Tk()
    app = MeshExtractorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
