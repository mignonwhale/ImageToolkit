## 이미지 배경 삭제 개발 계획

### Phase 1. 환경 설정
- 가상환경 생성 및 확인 (venv, Python 경로 확인 — 이전 프로젝트에서 겪은 `ModuleNotFoundError` 재발 방지)
- 필요 라이브러리 설치: `streamlit`, `rembg`, `onnxruntime`, `Pillow`
- 프로젝트 폴더 구조 설계

```
image-background-remover/
├── app.py                    # Streamlit 메인 화면
├── background_remover.py     # 배경 제거 처리 모듈 (rembg 호출)
├── file_handler.py           # 업로드/결과 파일 저장, ZIP 압축
├── utils.py                  # 진행 상황 표시, 로그, 오류 메시지
└── output/                   # 결과 파일 저장 폴더
```

### Phase 2. 파일 업로드 기능
- `st.file_uploader`로 다건 이미지 업로드 (jpg, png, jpeg 등 지원)
- 업로드된 파일명(한글 포함) 그대로 유지
- 업로드 개수 및 파일 목록을 화면에 표시

### Phase 3. 배경 제거 처리 엔진
- `background_remover.py`에서 rembg의 u2net 모델로 배경 제거 실행
- 다건 처리 시 진행 상황(예: "3/10 처리 중...")을 화면에 실시간 표시
- 처리 실패 시 한글 오류 메시지 출력 (예: "이미지 처리 중 오류가 발생했습니다: 지원하지 않는 파일 형식입니다")

### Phase 4. 미리보기 기능
- 원본 이미지와 배경 제거된 이미지를 좌우(Before/After) 비교로 표시
- 다건 처리 시 갤러리 형태로 썸네일 나열
- 개별 이미지 확대 보기 지원

### Phase 5. 결과 파일 다운로드
- 개별 이미지 다운로드 버튼 (`st.download_button`)
- 다건 처리 시 전체 결과를 ZIP으로 일괄 다운로드
- 결과 파일명 규칙: `원본파일명_배경제거_YYYY-MM-DD.png` (날짜 형식 규칙 적용)

### Phase 6. 오류 처리 및 마무리
- 지원하지 않는 파일 형식, 손상된 이미지 등에 대한 한글 예외 처리
- 처리 완료 후 요약 로그 표시 (성공/실패 건수)
- 전체 기능 통합 테스트

---

**코딩 규칙 적용:**
- 모든 주석 한글, 변수/함수명 영문(의미 전달 명확하게)
- 오류 발생 시 한글 메시지 출력, 처리 진행 상황 화면 표시
- 날짜는 `YYYY-MM-DD`, 파일명 한글 허용




# 이미지 크기 조절 개발계획

# 여백/영역 자르기 개발계획
## 개발 계획: 여백/영역 자르기 기능

### 새 파일 구성
```
vibe-20260701-ImageToolkit/
├── image_cropper.py              # 신규 - 자동 감지, 크롭 좌표 계산 로직
├── app_pages/
│   └── 3_crop_image.py           # 신규 - 통합 자르기 페이지 (자동/수동 모드)
├── app_pages/1_background_removal.py   # 옵션 추가
├── utils.py                       # 결과 파일명 규칙 등 확장
├── build_exe.bat                  # --add-data 경로 추가
```

---

### Phase 1. 핵심 처리 로직 (`image_cropper.py`)
- `has_meaningful_transparency(image)`: 이미지에 알파 채널이 있고, 실제로 투명한(알파 < 255) 픽셀이 하나라도 있는지 판별 → 자동/수동 모드 분기 기준
- `compute_trim_bounding_box(image, alpha_threshold=0)`: 알파값이 0을 초과하는 모든 픽셀을 포함하는 최소 사각형 계산 (요소 일부 손실 방지가 핵심 요구사항이므로 임계값 0 고정)
- `crop_image_to_box(image, box)`: 계산된 좌표로 실제 크롭 수행
- `build_crop_preview_overlay(image, box)`: 제안/선택 영역을 점선 테두리로 표시한 미리보기 이미지 생성 (자동 모드의 "제안 영역"과 수동 모드의 "슬라이더로 선택한 영역" 둘 다 재사용)
- 예외 상황 처리: 완전 투명 이미지(자를 것이 없음), 알파 채널은 있지만 전부 불투명(수동 모드로 전환), 잘못된 슬라이더 범위(좌우/상하가 뒤바뀐 경우) 등

### Phase 2. 단위 테스트
- 합성 RGBA 이미지(투명 여백 + 중앙 사물)로 bounding box가 사물 경계와 정확히 일치하는지 검증
- 요소 가장자리에 알파값 1짜리 픽셀을 일부러 넣어, 해당 픽셀까지 포함되어 잘리지 않는지 검증 (핵심 요구사항)
- 완전 투명/완전 불투명 이미지에 대한 예외 처리 검증
- 오버레이 미리보기 함수가 원본 픽셀을 훼손하지 않고 테두리만 그리는지 검증

### Phase 3. 통합 페이지 UI (`app_pages/3_crop_image.py`)
- 1단계: 이미지 업로드 (기존 도구들과 동일한 패턴 - 저장소 방식 업로더, 300px 미리보기 갤러리, ✕ 삭제, 확대 기능 없음)
- 2단계: 이미지별 자동 모드 판별 결과 표시 ("투명 배경 감지됨 → 자동 제안" / "배경 있음 → 직접 선택 필요")
- 3단계-A (자동 모드): 제안된 크롭 영역을 점선으로 표시 + "이 영역대로 자르기" 승인 버튼
- 3단계-B (수동 모드): 상/하/좌/우 슬라이더 4개 + 실시간 오버레이 미리보기 + "이 영역으로 자르기" 버튼
- 다건 처리 시 이미지마다 개별적으로 승인/조정 (한 이미지씩 순차 확인, 또는 아코디언으로 모두 펼쳐서 각각 확인 — 세부 UX는 구현 시 결정)
- 4단계: 최종 결과 미리보기 (확대 기능 유지, width 제한 없음 - 기존 결과 화면 규칙과 동일)
- 5단계: 개별 다운로드 + ZIP 일괄 다운로드

### Phase 4. 배경 제거 페이지에 옵션 추가
- 고급 옵션에 "투명 여백 자동 잘라내기" 체크박스 추가
- 배경 제거 처리 직후, 결과 이미지에 자동으로 bounding box 계산 → 제안 영역 표시 → 승인 시 크롭까지 이어서 진행
- 배경 제거와 자르기가 한 화면 흐름 안에서 자연스럽게 이어지도록 구성

### Phase 5. 공통 유틸 확장
- `utils.py`에 크롭 결과 파일명 규칙 추가 (예: `원본파일명_cropped_YYYY-MM-DD.png`)
- `file_handler.py`의 기존 ZIP/중복파일명 처리 로직 재사용

### Phase 6. exe 빌드 스크립트 반영
- `build_exe.bat`의 `--add-data`에 `image_cropper.py`, `3_crop_image.py` 추가
- 새 의존성 없음 확인 (슬라이더 방식이므로 `requirements.txt` 변경 불필요)

### Phase 7. 오류 처리 및 통합 테스트
- 자동/수동 모드 판별이 다양한 이미지(완전 투명, 부분 투명, 불투명 PNG, JPG)에서 정확히 동작하는지 확인
- 다건 업로드 시 자동/수동 모드가 이미지별로 섞여 있어도 각각 올바르게 처리되는지 확인
- 배경 제거 → 자동 자르기 연계 흐름 통합 테스트
- Streamlit AppTest로 슬라이더 조작, 승인 버튼 클릭, 최종 결과까지 시뮬레이션 검증


# 이미지 편집(통합) 개발계획
## 개발 계획: 이미지 편집(통합) 기능

### Context
배경 제거 / 크기 조정 / 자르기가 각각 독립된 페이지로 분리되어 있어, "배경 제거 → 여백 제거 → 3000x3000 리사이즈"를 하려면 세 페이지를 오가며 다운로드/재업로드를 반복해야 한다. 이 3단계를 한 번의 클릭으로 이어서 처리하는 새 통합 페이지 "이미지 편집"을 추가해, 상품 이미지 등을 준비할 때 반복 작업 없이 한 번에 결과물을 받을 수 있게 한다.

**확정된 파이프라인:**
1. 이미지 업로드 (여러 장)
2. "이미지 편집" 버튼 클릭
3. 배경 제거 (`remove_background_from_image`, 기본 옵션 그대로 — 모델 `birefnet-general`, 알파매팅 off, 내부 구멍 채우기 on)
4. 여백 제거 (배경 제거 결과의 투명 여백을 요소 경계까지 자동 트리밍 — `1_background_removal.py`의 "투명 여백 자동 잘라내기" 옵션과 동일한 로직을 항상 실행)
5. 긴 변 기준 3000px로 리사이즈 (비율 유지, 캔버스 확장/패딩 없음 — 긴 변이 이미 3000px보다 크면 축소도 포함해 정확히 3000px로 맞춘다)
6. 결과 미리보기 + 개별/ZIP 다운로드

별도의 새 페이지로 추가한다 (기존 배경 제거 페이지 확장이 아님). 3000x3000 정사각 캔버스로 패딩하는 방식은 채택하지 않았다 — 배경 제거로 이미 투명 배경이므로 별도 패딩 로직 없이도 결과물은 자연스럽게 투명 배경을 유지한다. 옵션 UI(모델 선택, 알파매팅 슬라이더 등)는 넣지 않고, 전 과정을 기본값으로 자동 실행한다 — 세부 조정이 필요하면 기존 개별 도구 페이지를 이용한다.

### 새 파일 구성
```
vibe-20260701-ImageToolkit/
├── app_pages/
│   └── 4_edit_image.py           # 신규 - 배경제거+여백제거+3000px 리사이즈 통합 페이지
├── image_resizer.py               # 긴 변 기준 리사이즈 계산 함수 추가
├── utils.py                       # 편집 결과 파일명 규칙 추가
├── app.py                         # 새 페이지 등록
├── home.py                        # 새 도구 카드 추가
```

### Phase 1. 리사이즈 헬퍼 함수 (`image_resizer.py`)
- `calculate_dimensions_by_longest_side(original_width, original_height, target_longest_side)`: 긴 변이 `target_longest_side`가 되도록 비율을 유지하며 크기를 계산 (확대/축소 모두 포함). 기존 `calculate_dimensions_by_pixels` 등과 동일한 docstring/예외 스타일(`target_longest_side < 1`이면 `ValueError`).
- 실제 리사이즈 실행은 기존 `resize_image(image, width, height)`를 그대로 재사용.

### Phase 2. 공통 유틸 확장 (`utils.py`)
- `build_edited_file_name(original_file_name)` 추가: `원본파일명_edited_YYYY-MM-DD.png` 규칙 (배경 제거 결과와 동일한 이유로 확장자는 항상 PNG 고정).

### Phase 3. 통합 페이지 UI (`app_pages/4_edit_image.py`)
- 세션 상태 접두사 `edit_` (`edit_uploaded_files_store`, `edit_uploader_reset_counter`, `edit_last_uploaded_file_signature`, `edit_processed_results`)
- 업로드 UI, 썸네일 미리보기 갤러리, ✕ 삭제: 기존 세 페이지와 동일한 코드 패턴 재사용
- "이미지 편집 시작" 버튼 클릭 시 파일별로 순차 처리 (progress bar + `build_progress_text` 재사용):
  1. `Image.open(...).convert("RGBA")`
  2. `remove_background_from_image(image)` — 기본 인자만 사용
  3. `compute_trim_bounding_box(result)` → box가 있고 전체 캔버스와 다르면 `crop_image_to_box`로 트리밍 (`1_background_removal.py`의 기존 트리밍 조건문 재사용)
  4. `calculate_dimensions_by_longest_side(w, h, 3000)` → `resize_image`
  5. 실패 시 `build_error_message_from_exception`으로 한글 오류 메시지 수집
- 결과 미리보기: "원본 {name} → 편집 결과 {W}x{H}px" 캡션 + 가운데 정렬 이미지, 개별 다운로드 버튼(`convert_image_to_png_bytes` + `build_edited_file_name`)
- 전체 ZIP 다운로드: `build_zip_file_from_named_results` 재사용 (파일명은 `build_edited_file_name`, `image_format="PNG"` 고정)

### Phase 4. 페이지 등록 (`app.py`, `home.py`)
- `app.py`: `edit_image_page = st.Page("app_pages/4_edit_image.py", title="이미지 편집", icon="🪄")` 를 `st.navigation([...])`에 등록, `home_page` 바로 다음(개별 도구들보다 앞)에 배치
- `home.py`: "🪄 이미지 편집" 카드 추가 (기존 `st.columns(3)` 레이아웃을 4열 또는 2x2로 조정)

### Phase 5. exe 빌드 스크립트
- `build_exe.bat`는 `app_pages` 폴더 전체를 `--add-data "app_pages;app_pages"`로 이미 통째로 포함하고 있고, `image_resizer.py`/`utils.py`도 이미 개별 `--add-data` 대상이므로 **수정 불필요** (새 top-level 모듈을 추가하지 않는 한)

### Phase 6. 오류 처리 및 통합 테스트
- `streamlit run app.py`로 새 "이미지 편집" 메뉴 진입 확인
- 배경 있는 JPG, 이미 투명 배경인 PNG 각각 업로드 후 배경제거 → 트리밍 → 3000px 리사이즈까지 오류 없이 이어지는지 확인
- 결과가 긴 변 3000px·비율 유지·투명 배경(RGBA)인지 확인 (원본이 3000px보다 큰 경우 축소도 정상 동작하는지 포함)
- 개별 다운로드(`_edited_YYYY-MM-DD.png`)와 ZIP 일괄 다운로드 정상 동작 확인
- 지원하지 않는 파일 형식/손상된 이미지 업로드 시 한글 오류 메시지 표시 및 나머지 파일 처리 계속 여부 확인
- `home.py`의 새 카드 링크 정상 이동 확인


# 이미지 편집(통합) - 300dpi 업그레이드 개발계획
## 개발 계획: 결과 이미지 300dpi 메타데이터 적용

### Context
"이미지 편집(통합)" 페이지에 이어서, 결과물을 300dpi로 만드는 단계를 하나 더 추가한다.

DPI는 픽셀 데이터를 늘리는 것이 아니라 "인쇄 시 1인치에 몇 픽셀인지"를 나타내는 메타데이터다. 픽셀 수 자체는 이미 직전 단계(긴 변 3000px 리사이즈)에서 정해지므로, 이번 기능은 새로 픽셀을 만들어내거나 화질을 보정하는 것이 아니라 저장되는 PNG 파일에 `300dpi` 메타데이터(pHYs 청크)를 기록하는 작업이다. 마침 긴 변 3000px에 300dpi를 지정하면 인쇄 시 10인치 크기로 계산되는데, 이는 다수의 인쇄/커머스 플랫폼이 요구하는 "3000x3000px · 300dpi" 스펙과 맞아떨어진다. (만약 픽셀 자체를 늘려 화질까지 개선하는 것을 의도하신 거라면 별도로 알려달라 — 그 경우 업스케일링 방식을 다시 논의해야 한다.)

기존 배경 제거/크기 조정/자르기 개별 페이지에는 이 옵션을 넣지 않는다 — "이미지 편집(통합)" 페이지의 결과물에만 적용되는 마무리 단계다.

### 수정 파일
```
vibe-20260701-ImageToolkit/
├── file_handler.py                # convert_image_to_png_bytes / convert_image_to_bytes에 선택적 dpi 파라미터 추가
├── app_pages/4_edit_image.py      # 리사이즈 다음 단계로 300dpi 적용을 파이프라인에 추가
```

### Phase 1. `file_handler.py`에 DPI 저장 지원 추가
- `convert_image_to_png_bytes(image, dpi=None)`: `dpi`가 주어지면 `image.save(buffer, format="PNG", dpi=dpi)`로 저장. `dpi=None`(기본값)이면 기존과 완전히 동일하게 동작해 배경 제거 페이지 등 기존 호출부는 영향받지 않는다.
- `convert_image_to_bytes(image, image_format, dpi=None)`: 동일하게 `dpi` 파라미터를 추가하고 `save_kwargs`에 포함시켜 저장.
- `build_zip_file_from_named_results`: 각 결과 아이템 dict가 선택적으로 `"dpi"` 키를 가질 수 있도록 하여, 있으면 `convert_image_to_bytes` 호출 시 함께 전달 (없으면 기존과 동일하게 dpi 미지정).

### Phase 2. `app_pages/4_edit_image.py` 파이프라인에 DPI 단계 추가
- 상수 `TARGET_DPI = (300, 300)` 추가
- 파이프라인 갱신: 업로드 → 배경 제거 → 여백 제거 → 긴 변 3000px 리사이즈 → **300dpi 적용(신규)** → 결과 저장
- 개별 다운로드는 `convert_image_to_png_bytes(result_image, dpi=TARGET_DPI)`로, ZIP 다운로드는 named_results 아이템에 `"dpi": TARGET_DPI`를 포함시켜 양쪽 모두 300dpi로 저장되도록 반영
- 화면 안내 문구 갱신: "배경 제거 → 여백 제거 → 긴 변 3000px 리사이즈 → 300dpi 적용까지 한 번에 처리합니다."
- 결과 미리보기 캡션에도 dpi 적용 여부 표시 (예: "편집 결과 3000 x 2256px · 300dpi")

### Phase 3. 검증
- 다운로드된 PNG 파일을 Pillow로 다시 열어 `Image.open(path).info["dpi"]`가 `(300, 300)`인지 확인
- ZIP 다운로드 안의 파일도 개별 다운로드와 동일하게 300dpi로 저장되는지 확인
- 기존 배경 제거/크기 조정/자르기 페이지의 다운로드 결과는 dpi를 넘기지 않으므로 기존 동작(DPI 미지정)이 그대로 유지되는지 확인해 회귀가 없는지 검증
- Streamlit AppTest로 처리 결과 이미지의 `info["dpi"]`가 `(300, 300)`인지 검증
