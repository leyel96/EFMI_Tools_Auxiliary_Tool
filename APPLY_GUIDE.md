# EFMI VB0/VB1/VB2 저장 문제 - 수정 코드 적용 가이드

## 📦 수정된 파일 목록

생성된 수정 파일:
1. ✅ **efmi_extractor_FIXED.py** - 핵심 수정 파일
2. ✅ **buffer_builder_FIXED.py** - VB1/VB2 빌드 지원
3. ✅ **exporter_FIXED.py** - VB1/VB2 처리 통합

---

## 🔧 적용 방법

### Step 1: 백업 생성

```bash
# 기존 파일 백업
cp efmi_extractor.py efmi_extractor.py.backup
cp buffer_builder.py buffer_builder.py.backup
cp exporter.py exporter.py.backup
```

### Step 2: 수정 파일 적용

```bash
# 수정된 파일로 교체
cp efmi_extractor_FIXED.py efmi_extractor.py
cp buffer_builder_FIXED.py buffer_builder.py
cp exporter_FIXED.py exporter.py
```

### Step 3: 테스트

```bash
# 실행
python3 efmi_extractor.py FrameAnalysis/ output/

# 결과 확인
ls -lh output/Component\ 0.*
```

---

## 📊 주요 수정 사항

### 1. EFMIComponent 클래스 수정

#### 이전:
```python
@dataclass
class EFMIComponent:
    vb_data: Optional[bytes] = None  # ❌ VB0만
```

#### 수정 후:
```python
@dataclass
class EFMIComponent:
    vb0_data: Optional[bytes] = None  # ✓ VB0
    vb1_data: Optional[bytes] = None  # ✓ VB1 추가
    vb2_data: Optional[bytes] = None  # ✓ VB2 추가
    vb0_info: Optional[object] = None
    vb1_info: Optional[object] = None
    vb2_info: Optional[object] = None
```

---

### 2. _extract_component() 메서드 수정

#### 이전:
```python
def _extract_component(self, comp_id, dc):
    vb0_buf = dc.buffers.get('VB0')  # ❌ VB0만
    # VB1, VB2 없음
```

#### 수정 후:
```python
def _extract_component(self, comp_id, dc):
    vb0_buf = dc.buffers.get('VB0')
    vb1_buf = dc.buffers.get('VB1')  # ✓ VB1 추가
    vb2_buf = dc.buffers.get('VB2')  # ✓ VB2 추가
    
    # 각각 읽기
    if vb1_buf:
        vb1_data = f.read(...)
    if vb2_buf:
        vb2_data = f.read(...)
```

---

### 3. _save_component_files() 메서드 수정

#### 이전:
```python
def _save_component_files(self, comp_id, component):
    vb_path = self.output_dir / f"Component {comp_id}.vb"
    # ❌ 1개 파일만
```

#### 수정 후:
```python
def _save_component_files(self, comp_id, component):
    # ✓ VB0 저장
    if component.vb0_data:
        vb0_path = self.output_dir / f"Component {comp_id}.vb0"
        f.write(component.vb0_data)
    
    # ✓ VB1 저장
    if component.vb1_data:
        vb1_path = self.output_dir / f"Component {comp_id}.vb1"
        f.write(component.vb1_data)
    
    # ✓ VB2 저장
    if component.vb2_data:
        vb2_path = self.output_dir / f"Component {comp_id}.vb2"
        f.write(component.vb2_data)
```

---

### 4. _generate_fmt_complete() 메서드 추가

#### 이전:
```python
def _generate_fmt(vb0_info, ib_info):
    # ❌ VB0 정보만 포함
```

#### 수정 후:
```python
def _generate_fmt_complete(vb0_info, vb1_info, vb2_info, ib_info):
    # ✓ VB0, VB1, VB2 모든 정보 포함
    # ✓ element 인덱싱 자동 계산
```

---

### 5. buffer_builder.py 수정

#### 이전:
```python
def build_buffers(self, mesh, ...):
    buffers['VB0'] = self._build_vb0(...)
    # VB1, VB2는 조건부로만
```

#### 수정 후:
```python
def build_buffers(self, mesh, ...):
    buffers['VB0'] = self._build_vb0(...)
    buffers['VB1'] = self._build_vb1(...)  # ✓ 항상 생성
    if self._has_skin_data(mesh.vertices):
        buffers['VB2'] = self._build_vb2(...)  # ✓ 스킨 정보 있으면
```

---

### 6. exporter.py 수정

#### 이전:
```python
for buffer_name, buffer in all_buffers.items():
    buf_path = self.meshes_path / f"{buffer_name}.buf"
    # ❌ VB0만 처리
```

#### 수정 후:
```python
for buffer_name, buffer in all_buffers.items():
    if 'VB0' in buffer_name or 'VB1' in buffer_name or 'VB2' in buffer_name:
        buf_path = self.meshes_path / f"{buffer_name}.buf"  # ✓ 모두 처리
```

---

## ✅ 검증 체크리스트

### 적용 후 확인

```bash
# 1. 파일 생성 확인
ls -lh output/Component\ 0.*

# 아래 파일들이 모두 있어야 함:
# ✓ Component 0.vb0   (~30 KB)
# ✓ Component 0.vb1   (~23 KB)  ← VB1 (UV 좌표)
# ✓ Component 0.vb2   (~23 KB)  ← VB2 (스킨 정보)
# ✓ Component 0.ib    (~11 KB)
# ✓ Component 0.fmt   (메타데이터)
```

### 로그 확인

```bash
# 실행 로그에서:
[Component 0] Reading VB0... OK (30272 bytes)
[Component 0] Reading VB1... OK (22704 bytes)   ✓ VB1 읽음
[Component 0] Reading VB2... OK (22704 bytes)   ✓ VB2 읽음
[Component 0] Reading IB... OK (11352 bytes)
[Component 0] Saved: vb0(30KB), vb1(23KB), vb2(23KB), ib(11KB), fmt  ✓ 모두 저장
```

---

## 📈 기대 효과

### 수정 전

```
output/
  Component 0.vb    (30KB, VB0만)
  Component 0.ib
  Component 0.fmt   (불완전한 메타데이터)

문제: UV 좌표, 스킨 정보 없음
```

### 수정 후

```
output/
  Component 0.vb0   (30KB, Position + Normal)   ✓
  Component 0.vb1   (23KB, TexCoord + Color)    ✓ UV 데이터 보존!
  Component 0.vb2   (23KB, BlendWeights + Indices) ✓ 스킨 정보 보존!
  Component 0.ib    (11KB)
  Component 0.fmt   (완전한 메타데이터)        ✓

결과: 모든 데이터 완벽히 저장
```

---

## 🚨 주의사항

### 1. 파일명 변경

```
이전: Component 0.vb   (1개)
수정 후: Component 0.vb0   (3개 중 1개)
        Component 0.vb1
        Component 0.vb2
```

**mod.ini 파일 업데이트 필요**:
```ini
# 이전
[Buffers]
Component0_IB = Component0_IB.buf
Component0_VB0 = Component0_VB0.buf

# 수정 후
[Buffers]
Component0_IB = Component0.ib
Component0_VB0 = Component0.vb0
Component0_VB1 = Component0.vb1      ← 추가
Component0_VB2 = Component0.vb2      ← 추가
```

### 2. FMT 파일 변경

```
이전 (불완전):
element[0]: POSITION (VB0)
element[1]: NORMAL (VB0)

수정 후 (완전):
element[0]: POSITION (VB0)
element[1]: NORMAL (VB0)
element[2]: TEXCOORD (VB1)    ← 추가
element[3]: COLOR (VB1)        ← 추가
element[4]: BLENDWEIGHTS (VB2) ← 추가
element[5]: BLENDINDICES (VB2) ← 추가
```

### 3. 호환성

**3DMigoto 버전 확인**:
- 최신 3DMigoto는 모두 지원
- 구형 버전: `InputSlot` 개념 부재 가능성
  - 해결: mod.ini에서 `InputSlot` 항목 제거

---

## 🐛 문제 발생 시

### VB1/VB2가 없다는 오류

```
[Component 0] Reading VB1... SKIP (File not found)
[Component 0] Reading VB2... SKIP (File not found)
```

**원인**: FrameAnalysis 덤프에 VB1, VB2 파일이 없음
**해결**: 정상 (VB0만으로도 기본 동작)

### FMT 파일 오류

```
element[2]: TEXCOORD (VB1) 는데 VB1이 없음
```

**원인**: VB1 파일이 없는데 FMT에 포함됨
**해결**: _generate_fmt_complete()에서 `if vb1_info:` 체크 확인

---

## 📞 롤백 방법

문제 발생 시:
```bash
# 백업 복원
cp efmi_extractor.py.backup efmi_extractor.py
cp buffer_builder.py.backup buffer_builder.py
cp exporter.py.backup exporter.py
```

---

## 🎯 최종 확인 체크리스트

- [ ] 3개 수정 파일 준비됨
- [ ] 기존 파일 백업됨
- [ ] 수정 파일 적용됨
- [ ] efmi_extractor.py 실행
- [ ] 로그에서 VB1, VB2 읽기 확인
- [ ] 파일 3개 (.vb0, .vb1, .vb2) 생성 확인
- [ ] FMT 파일 element 개수 확인 (6개 이상)
- [ ] 3DMigoto에서 모델 로드 확인

---

## ✨ 수정 완료!

**예상 소요 시간**: 5분
**복잡도**: 매우 낮음
**테스트 필요**: 필수

