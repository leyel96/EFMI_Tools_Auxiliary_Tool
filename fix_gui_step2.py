# Step 2: GUI에 좌표계 ComboBox 추가

with open('mesh_extractor_gui.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 좌표계 콤보박스 추가 (체크박스 다음에 삽입)
old_checkboxes = '''        ttk.Checkbutton(
            options_frame,
            text="개별 OBJ 파일로 저장 (Component_*.obj)",
            variable=self.ext_import_export_individual,
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Checkbutton(
            options_frame,
            text="하나의 OBJ 파일로 결합 (combined.obj)",
            variable=self.ext_import_export_combined,
        ).grid(row=1, column=0, sticky=tk.W, pady=2)

        # 실행 버튼'''

new_checkboxes = '''        ttk.Checkbutton(
            options_frame,
            text="개별 OBJ 파일로 저장 (Component_*.obj)",
            variable=self.ext_import_export_individual,
        ).grid(row=0, column=0, sticky=tk.W, pady=2)
        
        ttk.Checkbutton(
            options_frame,
            text="하나의 OBJ 파일로 결합 (combined.obj)",
            variable=self.ext_import_export_combined,
        ).grid(row=1, column=0, sticky=tk.W, pady=2)

        # 좌표계 선택
        coord_frame = ttk.LabelFrame(self.tab_ext_import, text="좌표계 설정", padding=10)
        coord_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(coord_frame, text="OBJ 내보내기 좌표계:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10), pady=2
        )
        ttk.Combobox(
            coord_frame,
            textvariable=self.ext_import_coord_system,
            values=["reference (Z-up)", "blender (Y-up)", "original (DirectX)"],
            state="readonly",
            width=35,
        ).grid(row=0, column=1, padx=(0, 10), pady=2)

        # 실행 버튼'''

content = content.replace(old_checkboxes, new_checkboxes)

with open('mesh_extractor_gui.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Step 2 complete: Added coordinate system ComboBox to GUI')
