# Step 4: Add _get_coord_value helper method

with open('mesh_extractor_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# _browse_input 함수 앞에 _get_coord_value 메서드 추가
old_browse = '''    def _browse_input(self):
        """입력 디렉토리 선택"""'''

new_methods = '''    def _get_coord_value(self, display_value):
        """좌표계 표시값을 실제 값으로 변환"""
        if "blender" in display_value.lower():
            return "blender"
        elif "original" in display_value.lower() or "directx" in display_value.lower():
            return "original"
        else:
            return "reference"

    def _browse_input(self):
        """입력 디렉토리 선택"""'''

content = content.replace(old_browse, new_methods)

with open('mesh_extractor_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Step 4 complete: Added _get_coord_value helper method')
