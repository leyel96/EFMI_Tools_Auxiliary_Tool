# Step 3 재시도 - UTF-8 인코딩으로 수정 (깨진 한글 포함)

with open('mesh_extractor_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

print("파일 길이:", len(content))

# 실제 파일 내용을 확인하여 정확한 문자열 찾기
idx_start = content.find('def _start_extracted_import')
if idx_start >= 0:
    print("\n=== _start_extracted_import 함수 시작 ===")
    print(repr(content[idx_start:idx_start+1000]))

idx_run = content.find('def _run_extracted_import_thread')
if idx_run >= 0:
    print("\n=== _run_extracted_import_thread 함수 시작 ===")
    print(repr(content[idx_run:idx_run+1500]))
