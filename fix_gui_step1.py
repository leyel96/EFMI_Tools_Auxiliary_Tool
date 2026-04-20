# GUI 수정 스크립트

with open('mesh_extractor_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. __init__에 ext_import_coord_system 추가
old_init = '''        self.ext_import_export_combined = tk.BooleanVar(value=False)

        # 창 아이콘 설정'''
new_init = '''        self.ext_import_export_combined = tk.BooleanVar(value=False)
        self.ext_import_coord_system = tk.StringVar(value="reference")

        # 창 아이콘 설정'''
content = content.replace(old_init, new_init)

with open('mesh_extractor_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Step 1 complete: Added ext_import_coord_system variable')
