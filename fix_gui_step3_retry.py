# Step 3 재시도 - _start_extracted_import and _run_extracted_import_thread 수정

with open('mesh_extractor_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. _start_extracted_import 함수 수정
old_start = '''    def _start_extracted_import(self):
        """추출물 변환 시작"""
        source_dir = self.ext_import_source_dir.get()
        output_dir = self.ext_import_output_dir.get()
        do_individual = self.ext_import_export_individual.get()
        do_combined = self.ext_import_export_combined.get()

        if not source_dir or not os.path.isdir(source_dir):
            messagebox.showerror("오류", "유효한 추출물 폴더를 선택하세요.")
            return
        
        if not output_dir:
            messagebox.showerror("오류", "출력 폴더를 입력해주세요.")
            return

        if not do_individual and not do_combined:
            messagebox.showwarning("경고", "최소 하나의 내보내기 옵션을 선택하세요")
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
        thread.start()'''

new_start = '''    def _start_extracted_import(self):
        """추출물 변환 시작"""
        source_dir = self.ext_import_source_dir.get()
        output_dir = self.ext_import_output_dir.get()
        do_individual = self.ext_import_export_individual.get()
        do_combined = self.ext_import_export_combined.get()
        coord_system = self._get_coord_value(self.ext_import_coord_system.get())

        if not source_dir or not os.path.isdir(source_dir):
            messagebox.showerror("오류", "유효한 추출물 폴더를 선택하세요.")
            return
        
        if not output_dir:
            messagebox.showerror("오류", "출력 폴더를 입력해주세요.")
            return

        if not do_individual and not do_combined:
            messagebox.showwarning("경고", "최소 하나의 내보내기 옵션을 선택하세요")
            return

        self.is_running = True
        self.btn_ext_import.configure(state=tk.DISABLED)
        self._log("============================================================")
        self._log(f"추출물 변환 시작... (좌표계: {coord_system})")
        
        thread = threading.Thread(
            target=self._run_extracted_import_thread, 
            args=(source_dir, output_dir, do_individual, do_combined, coord_system),
            daemon=True
        )
        thread.start()'''

if old_start in content:
    content = content.replace(old_start, new_start)
    print("1. _start_extracted_import 수정 완료")
else:
    print("1. _start_extracted_import 패턴을 찾을 수 없음 - 파일 내용 확인 필요")

# 2. _run_extracted_import_thread 함수 수정
old_run = '''    def _run_extracted_import_thread(self, source_dir, output_dir, do_individual, do_combined):
        """추출물 변환 실행 (백그라운드)"""
        try:
            from extracted_object_importer import ExtractedObjectImporter
            import time
            
            start_time = time.time()
            importer = ExtractedObjectImporter()
            
            self._log(f"  폴더 로드 중: {source_dir}")
            meshes = importer.import_from_folder(source_dir)
            
            if not meshes:
                self._log("  오류: 로드된 메시가 없습니다.")
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
                importer.export_combined(meshes, combined_path)'''

new_run = '''    def _run_extracted_import_thread(self, source_dir, output_dir, do_individual, do_combined, coord_system):
        """추출물 변환 실행 (백그라운드)"""
        try:
            from extracted_object_importer import ExtractedObjectImporter
            import time
            
            start_time = time.time()
            importer = ExtractedObjectImporter(coordinate_system=coord_system)
            
            self._log(f"  폴더 로드 중: {source_dir}")
            meshes = importer.import_from_folder(source_dir)
            
            if not meshes:
                self._log("  오류: 로드된 메시가 없습니다.")
                return

            self._log(f"  {len(meshes)}개 컴포넌트 로드 완료.")
            
            if not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            if do_individual:
                self._log(f"  개별 OBJ 내보내는 중... (좌표계: {coord_system}, 저장위치: {output_dir})")
                importer.export_individual(meshes, output_dir)
            
            if do_combined:
                combined_path = os.path.join(output_dir, "combined_mesh.obj")
                self._log(f"  결합된 OBJ 내보내는 중 (좌표계: {coord_system}): {combined_path}")
                importer.export_combined(meshes, combined_path)'''

if old_run in content:
    content = content.replace(old_run, new_run)
    print("2. _run_extracted_import_thread 수정 완료")
else:
    print("2. _run_extracted_import_thread 패턴을 찾을 수 없음 - 파일 내용 확인 필요")

with open('mesh_extractor_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n파일 저장 완료!")
