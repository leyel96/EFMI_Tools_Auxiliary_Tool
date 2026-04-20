# EFMI Object Extraction UV Conversion Issue Analysis

## 1. Problem Description
Currently, the **EFMI Object Extraction** process (`efmi_extractor.py`) preserves the original UV coordinates from the game dump files without any modification. However, the user requires that during extraction, the UV values should be processed in the same way as the **OBJ Export** process (i.e., flipping the V-coordinate).

## 2. Current Behavior vs. Expected Behavior

### A. OBJ Export (`obj_exporter.py`)
*   **Behavior**: Flips the V-coordinate of the UV texture coordinates.
*   **Code Logic**: In functions like `transform_vertex_reference` and `transform_vertex_blender`, it explicitly calculates:
    ```python
    new_texcoord = (tx, 1.0 - ty)
    ```
*   **Reason**: To align with standard 3D viewer coordinate systems (like Blender or Reference OBJ), where the UV origin might differ from the game engine's DirectX origin.

### B. EFMI Object Extraction (`efmi_extractor.py`)
*   **Current Behavior**: Preserves raw data as-is.
    *   It reads binary vertex buffer data (`.vb`) directly from the dump and writes it to the output folder without parsing or modifying the UV components within that buffer.
    *   Code snippet in `_save_component_files`:
        ```python
        with open(vb_path, 'wb') as f:
            f.write(component.vb_data) # Raw binary copy
        ```
*   **Expected Behavior**: Should apply the same V-coordinate flip (`1.0 - v`) to the UV data before saving it to the `.vb` file or metadata.

## 3. Root Cause Analysis
The discrepancy arises because `efmi_extractor.py` treats the vertex buffer as a raw binary blob for efficiency during the extraction phase, whereas `obj_exporter.py` parses the mesh into Python objects (`MeshData`, `Vertex`) where individual attributes like UVs can be easily manipulated before writing to text files.

## 4. Proposed Solution
To fix this in `efmi_extractor.py`:
1.  **Parse UV Data**: Instead of just copying raw bytes, parse the vertex buffer data to locate the TEXCOORD semantic (UV coordinates).
2.  **Apply Transformation**: Iterate through the extracted UVs and apply the transformation: `v_new = 1.0 - v_old`.
3.  **Re-encode/Write**: Write the modified data back to the output files, ensuring the binary structure remains valid for downstream tools (like EFMI Export).

## 5. Files Involved
*   `efmi_extractor.py`: Needs modification in `_extract_component` or a new helper function to handle UV transformation during extraction.
*   `obj_exporter.py`: Reference for the correct transformation logic (`1.0 - v`).