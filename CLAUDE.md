# CLAUDE.md

이 파일은 이 저장소에서 작업하는 Claude Code(claude.ai/code)에게 제공하는 가이드입니다.

## 프로젝트 개요

이미지 도구 모음 (Image Toolkit) — Streamlit 앱을 Windows 단일 `.exe`로 패키징한 프로그램으로, 세 가지 이미지 도구를 제공한다: 배경 제거(`rembg`/BiRefNet 사용), 크기 조정, 여백/영역 자르기. 별도 백엔드/서버 없이 모든 처리가 사용자 로컬 세션 안에서 메모리 기반으로 이루어진다.

## 명령어

```bash
# 개발 중 실행 (프로젝트 루트에서, venv 활성화 상태)
streamlit run app.py

# 의존성 설치
pip install -r requirements.txt

# 배포용 exe 빌드 (Windows 전용, venv가 이미 생성된 상태에서 프로젝트 루트에서 실행)
build_exe.bat
```

이 저장소에는 테스트 스위트나 린터 설정이 없다.

`build_exe.bat`는 단순히 PyInstaller만 호출하는 것이 아니라, 빌드 전에 `streamlit_cropper` 패치(아래 참고)도 다시 적용한다. 의존성을 새로 설치/재설치한 뒤 개발 모드에서 자르기 페이지를 실행해야 한다면 `python patch_streamlit_cropper.py`를 한 번 실행해야 한다. 그렇지 않으면 자르기 박스가 이미지 미리보기 밖으로 드래그될 수 있다.

## 아키텍처

**진입점이 두 개 있으니 혼동하지 말 것:**
- `run_app.py`는 exe 런처다 (`ImageToolkit.spec`/PyInstaller가 사용). `sys._MEIPASS`를 통해 번들 경로를 해석하고, 스플래시 화면을 띄우고, `--noconsole` 빌드를 위해 stdout/stderr를 안전하게 채워둔 뒤에야 Streamlit CLI로 `app.py`를 실행한다.
- `app.py`는 `streamlit run`으로 개발할 때 실제로 사용하는 Streamlit 진입점이다. `st.Page`/`st.navigation`으로 `home.py`와 각 `app_pages/*.py`를 등록하는 얇은 라우터 역할만 한다.

**페이지 스크립트 파일명은 의도적으로 영문이다** (`app_pages/1_background_removal.py` 등) — 한글 파일명은 다운로드/전송 과정에서 유니코드 정규화(NFC/NFD) 방식 차이로 오류가 발생하기 때문. 사이드바에 보이는 한글 메뉴명은 파일명이 아니라 `app.py`의 `title=` 인자로 지정한다.

**레이어 분리** — 각 도구는 동일한 구조를 따른다:
- Streamlit 의존성이 없는 순수 로직 모듈: `background_remover.py`, `image_resizer.py`, `image_cropper.py`. PIL `Image` 객체를 입출력으로 받고, 잘못된 입력에는 `ValueError` 등 예외를 던진다. 새로운 이미지 처리 로직은 이 계층에 추가한다.
- `app_pages/`의 페이지 모듈은 Streamlit UI와 세션 상태를 전담하며 로직 모듈을 호출한다.
- 도구 간 공유되는 헬퍼: `file_handler.py`(bytes/ZIP 변환), `utils.py`(한글 오류 메시지, 파일명 규칙, 썸네일 인코딩).

**세션 상태 규칙**: 각 페이지는 `st.session_state` 키에 접두사(`bg_`, `resize_`, `crop_`)를 붙여 세 도구의 상태가 서로 섞이지 않도록 한다. 세 페이지 모두 동일한 업로드 패턴을 쓴다 — `st.file_uploader` 위젯에서 직접 읽지 않고, `(name, size)`를 키로 하는 `*_uploaded_files_store` 딕셔너리에 파일을 저장한다. 그리고 업로더 위젯의 `key`를 매번 올려서(`*_uploader_reset_counter`) 위젯을 완전히 새로 만드는데, 이 덕분에 개별 파일 삭제(✕ 버튼) 후에도 업로더 쪽에 파일명이 남아있지 않는다.

**배경 제거 파이프라인** (`background_remover.py`): `remove_background_from_image`는 모델 이름별로 캐싱된 세션(`get_background_removal_session`, 모델 전환 시 디스크에서 재로딩하지 않도록 캐싱)으로 `rembg.remove()`를 호출한 뒤, 선택적으로 두 가지 후처리를 거친다 — `fill_interior_holes`(사물 내부에 완전히 둘러싸인 알파 구멍을 복원, 예: 흰색 달력 칸이 배경으로 오인된 경우)와 `clean_up_faint_residue`(경계에 남는 낮은 알파값의 잔여물을 확실히 제거). 어떤 모델을 쓰느냐에 따라 알파매팅을 켜야 할지가 달라진다 — `app_pages/1_background_removal.py`의 `MODEL_ALPHA_MATTING_RECOMMENDATION` 참고.

**자르기 자동/수동 모드 분기** (`image_cropper.py` + `app_pages/3_crop_image.py`): `has_meaningful_transparency`가 이미지별 모드를 결정한다. 실제로 불투명하지 않은 알파값이 있으면(예: 배경 제거 결과물) `compute_trim_bounding_box`로 자를 영역을 자동 계산하고 사용자 승인만 받으면 된다. 그렇지 않으면 `streamlit_cropper`의 `st_cropper`를 이용한 수동 선택으로 넘어간다. 해당 페이지의 `cropper_default_coords` 처리를 눈여겨볼 것 — 선택 상태가 처음 생성될 때 한 번만 설정하고 이후 rerun에서는 절대 갱신하지 않는데, 직전 드래그 좌표를 `st_cropper`에 다시 넘기면 프론트엔드가 박스 위치를 되돌려버려서 사용자의 드래그와 충돌하기 때문이다.

**PyInstaller 패키징**: `ImageToolkit.spec`은 빌드 산출물이다 (`*.spec`으로 gitignore 처리됨) — `build_exe.bat`는 매번 이 파일을 삭제하고 `pyinstaller` CLI 호출로 새로 생성하며, 직접 수정하는 파일이 아니다. 새로운 최상위 모듈이나 `app_pages/*.py` 파일을 추가하면 `build_exe.bat`의 `--add-data` 목록에도 추가해야 exe에 번들된다.

## 컨벤션

- 주석과 사용자에게 보이는 모든 문자열(오류, 라벨, 도움말)은 한글로, 식별자(함수/변수명)는 의미가 드러나는 영문으로 작성한다.
- 날짜 형식은 `YYYY-MM-DD` (`utils.get_today_date_string`).
- 결과 파일명은 `{원본파일명}_{suffix}_{YYYY-MM-DD}.{ext}` 규칙을 따른다 — `utils.py`의 `build_result_file_name` / `build_resized_file_name` / `build_cropped_file_name` 참고. 여러 결과를 하나의 ZIP에 담을 때는 동일 원본 파일명이 서로 덮어쓰지 않도록 `file_handler.py`의 `deduplicate_file_name`을 재사용한다.
- 지원하는 이미지 확장자는 `utils.SUPPORTED_IMAGE_EXTENSIONS`에 모아두었다 — 포맷을 추가할 때는 각 페이지의 `st.file_uploader(type=...)` 목록도 함께 갱신해야 한다.

## 언어 규칙

- **CLAUDE.md 파일은 한글로 작성한다.** (사용자 요청)
