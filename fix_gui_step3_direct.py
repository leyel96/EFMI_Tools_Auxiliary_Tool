# Step 3 최종 - 실제 파일의 바이트 내용으로 직접 수정

with open('mesh_extractor_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. _start_extracted_import 함수 수정
# 실제 파일에서 확인한 내용으로 정확히 매칭
old_start_lines = [
    '    def _start_extracted_import(self):',
    '        """추출물 변환 시작"""',
    '        source_dir = self.ext_import_source_dir.get()',
    '        output_dir = self.ext_import_output_dir.get()',
    '        do_individual = self.ext_import_export_individual.get()',
    '        do_combined = self.ext_import_export_combined.get()',
    '',
]

new_start_lines = [
    '    def _start_extracted_import(self):',
    '        """추출물 변환 시작"""',
    '        source_dir = self.ext_import_source_dir.get()',
    '        output_dir = self.ext_import_output_dir.get()',
    '        do_individual = self.ext_import_export_individual.get()',
    '        do_combined = self.ext_import_export_combined.get()',
    '        coord_system = self._get_coord_value(self.ext_import_coord_system.get())',
    '',
]

old_text = '\n'.join(old_start_lines)
new_text = '\n'.join(new_start_lines)

if old_text in content:
    content = content.replace(old_text, new_text, 1)
    print("1. _start_extracted_import - coord_system 변수 추가 완료")
else:
    print("1. _start_extracted_import 패턴 불일치")

# thread args 수정
old_thread = '''        thread = threading.Thread(
            target=self._run_extracted_import_thread, 
            args=(source_dir, output_dir, do_individual, do_combined),
            daemon=True
        )'''

new_thread = '''        thread = threading.Thread(
            target=self._run_extracted_import_thread, 
            args=(source_dir, output_dir, do_individual, do_combined, coord_system),
            daemon=True
        )'''

if old_thread in content:
    content = content.replace(old_thread, new_thread, 1)
    print("2. thread args 수정 완료")
else:
    print("2. thread args 패턴 불일치")

# importer 생성 수정
old_importer = '            importer = ExtractedObjectImporter()'
new_importer = '            importer = ExtractedObjectImporter(coordinate_system=coord_system)'

if old_importer in content:
    # _run_extracted_import_thread 함수 내의 것만 수정 (첫 번째 등장)
    idx = content.find(old_importer)
    if idx >= 0:
        content = content[:idx] + new_importer + content[idx + len(old_importer):]
        print("3. ExtractedObjectImporter 생성자 수정 완료")
else:
    print("3. importer 패턴 불일치")

# 함수 시그니처 수정
old_sig = 'def _run_extracted_import_thread(self, source_dir, output_dir, do_individual, do_combined):'
new_sig = 'def _run_extracted_import_thread(self, source_dir, output_dir, do_individual, do_combined, coord_system):'

if old_sig in content:
    content = content.replace(old_sig, new_sig, 1)
    print("4. 함수 시그니처 수정 완료")
else:
    print("4. 함수 시그니처 패턴 불일치")

# 로그 메시지 수정 - 개별 OBJ
old_log_ind = '                self._log(f"  개별 OBJ 내보내는 중... (저장위치: {output_dir})")'
new_log_ind = '                self._log(f"  개별 OBJ 내보내는 중... (좌표계: {coord_system}, 저장위치: {output_dir})")'

if old_log_ind in content:
    content = content.replace(old_log_ind, new_log_ind, 1)
    print("5. 개별 OBJ 로그 수정 완료")
else:
    print("5. 개별 OBJ 로그 패턴 불일치")

# 로그 메시지 수정 - 결합 OBJ
old_log_comb = '                self._log(f"  결합된 OBJ 내보내는 중: {combined_path}")'
new_log_comb = '                self._log(f"  결합된 OBJ 내보내는 중 (좌표계: {coord_system}): {combined_path}")'

if old_log_comb in content:
    content = content.replace(old_log_comb, new_log_comb, 1)
    print("6. 결합 OBJ 로그 수정 완료")
else:
    print("6. 결합 OBJ 로그 패턴 불일치")

with open('mesh_extractor_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n파일 저장 완료!")
