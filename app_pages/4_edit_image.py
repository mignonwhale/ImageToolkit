"""
이미지 편집(통합) 페이지
동작 흐름: 이미지 업로드 > "이미지 편집 시작" 버튼 클릭 >
          배경 제거 -> 여백(투명 마진) 제거 -> 긴 변 3000px로 리사이즈 -> 300dpi 적용 -> 결과 미리보기/다운로드

300dpi 적용은 픽셀 데이터를 새로 만들어내는 것이 아니라, 저장되는 PNG 파일에
"인쇄 시 1인치당 300픽셀" 이라는 메타데이터(pHYs 청크)를 기록하는 단계다.

세부 옵션 UI는 제공하지 않는다. 모델 선택 등 세밀한 조정이 필요하면
개별 도구 페이지(배경 제거/크기 조정/자르기)를 이용해야 한다.
"""

import io

import streamlit as st
from PIL import Image

from background_remover import remove_background_from_image
from image_cropper import compute_trim_bounding_box, crop_image_to_box
from image_resizer import calculate_dimensions_by_longest_side, resize_image
from file_handler import convert_image_to_png_bytes, build_zip_file_from_named_results
from utils import (
    is_supported_image_file,
    build_error_message,
    build_error_message_from_exception,
    build_progress_text,
    build_edited_file_name,
    encode_image_to_thumbnail_data_url,
)

# 긴 변 리사이즈 목표 픽셀
TARGET_LONGEST_SIDE = 3000

# 결과 PNG에 기록할 인쇄 해상도 메타데이터 (가로, 세로 dpi)
TARGET_DPI = (300, 300)

# 화면 기본 설정
st.set_page_config(page_title="이미지 편집 - 이미지 도구 모음", layout="wide")
st.title("🪄 이미지 편집")
st.caption(
    "여러 장의 이미지를 업로드하고 버튼 한 번으로 배경 제거 → 여백 제거 → "
    f"긴 변 {TARGET_LONGEST_SIDE}px 리사이즈 → {TARGET_DPI[0]}dpi 적용까지 한 번에 처리합니다."
)

# 세션 상태 초기화 (다른 페이지와 상태가 섞이지 않도록 "edit_" 접두사로 구분)
if "edit_processed_results" not in st.session_state:
    st.session_state.edit_processed_results = []

if "edit_last_uploaded_file_signature" not in st.session_state:
    st.session_state.edit_last_uploaded_file_signature = ()

# 실제 업로드된 파일을 보관하는 저장소 (서명 -> {name, size, bytes})
if "edit_uploaded_files_store" not in st.session_state:
    st.session_state.edit_uploaded_files_store = {}

# 업로더 위젯의 key에 사용되는 번호. 새 파일을 저장소로 옮긴 뒤 이 값을 올려서
# 업로더 위젯을 완전히 새로 만들어(=항상 빈 상태로) 파일명이 계속 남아있지 않도록 한다.
if "edit_uploader_reset_counter" not in st.session_state:
    st.session_state.edit_uploader_reset_counter = 0

# ------------------------------------------------------------------
# 1단계: 이미지 파일 업로드
# ------------------------------------------------------------------
header_column, count_column = st.columns([5, 1])
with header_column:
    st.header("1. 이미지 업로드")

with st.expander("이미지 선택", expanded=len(st.session_state.edit_uploaded_files_store) == 0):
    newly_selected_files = st.file_uploader(
        "편집할 이미지를 선택하세요 (여러 장 선택 가능, 파일을 이 영역으로 끌어다 놓아도 됩니다)",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=True,
        key=f"edit_file_uploader_{st.session_state.edit_uploader_reset_counter}",
    )

# 새로 선택된 파일을 저장소로 옮긴다 (이미 저장소에 있는 파일은 건너뛴다)
has_newly_added_file = False
for newly_selected_file in newly_selected_files or []:
    file_signature = (newly_selected_file.name, newly_selected_file.size)
    if file_signature not in st.session_state.edit_uploaded_files_store:
        st.session_state.edit_uploaded_files_store[file_signature] = {
            "name": newly_selected_file.name,
            "size": newly_selected_file.size,
            "bytes": newly_selected_file.getvalue(),
        }
        has_newly_added_file = True

if has_newly_added_file:
    # 업로더 위젯의 key를 바꿔 완전히 새(빈) 상태로 리셋한다
    st.session_state.edit_uploader_reset_counter += 1
    st.rerun()

# 이후 모든 로직은 저장소에 있는 파일을 기준으로 동작한다
active_files = list(st.session_state.edit_uploaded_files_store.values())

with count_column:
    st.markdown(
        f"<div style='text-align:right; padding-top:0.6rem; font-weight:600;'>총 {len(active_files)}개 업로드</div>",
        unsafe_allow_html=True,
    )

# 업로드된 파일 목록(이름+크기)으로 서명을 만들어, 이전 업로드와 달라졌는지 감지한다
current_uploaded_file_signature = tuple(sorted(st.session_state.edit_uploaded_files_store.keys()))

if current_uploaded_file_signature != st.session_state.edit_last_uploaded_file_signature:
    # 업로드 파일이 새로 추가/변경/삭제된 경우, 이전 편집 결과는 더 이상 유효하지 않으므로 초기화한다
    if st.session_state.edit_processed_results:
        st.session_state.edit_processed_results = []
        st.info("업로드된 파일이 변경되어 이전 편집 결과를 초기화했습니다.")
    st.session_state.edit_last_uploaded_file_signature = current_uploaded_file_signature

if active_files:
    st.subheader("업로드한 이미지 미리보기")
    preview_gallery_columns = st.columns(4)
    for preview_index, active_file in enumerate(active_files):
        gallery_column = preview_gallery_columns[preview_index % 4]
        file_signature = (active_file["name"], active_file["size"])

        with gallery_column:
            title_column, close_button_column = st.columns([5, 1])
            with title_column:
                st.caption(active_file["name"])
            with close_button_column:
                if st.button("✕", key=f"edit_remove_{preview_index}_{file_signature}", help="이 이미지를 목록에서 제거"):
                    del st.session_state.edit_uploaded_files_store[file_signature]
                    st.rerun()

            try:
                preview_image = Image.open(io.BytesIO(active_file["bytes"]))
                preview_width, preview_height = preview_image.size
                thumbnail_data_url = encode_image_to_thumbnail_data_url(preview_image, 300)
                # 일반 st.image 대신 순수 HTML <img>로 렌더링하여 불필요한 확대(전체화면) 기능을 없앤다
                st.markdown(
                    f"<img src='{thumbnail_data_url}' style='display:block;' />",
                    unsafe_allow_html=True,
                )
                st.caption(f"{preview_width}x{preview_height}px")
            except Exception:
                st.warning(f"'{active_file['name']}' 미리보기를 불러올 수 없습니다.")

# ------------------------------------------------------------------
# 2단계: 이미지 편집 처리 실행 (배경 제거 -> 여백 제거 -> 3000px 리사이즈)
# ------------------------------------------------------------------
st.header("2. 이미지 편집 처리")
st.caption(
    f"배경 제거 → 여백 제거 → 긴 변 {TARGET_LONGEST_SIDE}px 리사이즈 → "
    f"{TARGET_DPI[0]}dpi 적용이 기본값으로 자동 실행됩니다."
)

start_processing_button = st.button("이미지 편집 시작", type="primary", disabled=not active_files)

if start_processing_button and active_files:
    st.session_state.edit_processed_results = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    error_messages = []

    total_count = len(active_files)

    for index, active_file in enumerate(active_files, start=1):
        file_name = active_file["name"]
        status_text.info(build_progress_text(index, total_count, file_name))

        # 지원하지 않는 파일 형식 검사
        if not is_supported_image_file(file_name):
            error_messages.append(
                build_error_message(file_name, "지원하지 않는 파일 형식입니다.")
            )
            progress_bar.progress(index / total_count)
            continue

        try:
            original_image = Image.open(io.BytesIO(active_file["bytes"])).convert("RGBA")

            # 1) 배경 제거
            result_image = remove_background_from_image(original_image)

            # 2) 여백(투명 마진) 제거
            trim_box = compute_trim_bounding_box(result_image)
            if trim_box is not None and trim_box != (0, 0, result_image.width, result_image.height):
                result_image = crop_image_to_box(result_image, trim_box)

            # 3) 긴 변 기준 3000px 리사이즈
            final_width, final_height = calculate_dimensions_by_longest_side(
                result_image.width, result_image.height, TARGET_LONGEST_SIDE
            )
            result_image = resize_image(result_image, final_width, final_height)

            # 4) 300dpi 메타데이터 적용 (픽셀은 그대로, 저장 시 인쇄 해상도 정보만 기록)
            result_image.info["dpi"] = TARGET_DPI

            st.session_state.edit_processed_results.append(
                {
                    "original_file_name": file_name,
                    "original_image": original_image,
                    "result_image": result_image,
                    "result_size": (final_width, final_height),
                }
            )
        except Exception as processing_error:
            error_messages.append(
                build_error_message_from_exception(file_name, processing_error)
            )

        progress_bar.progress(index / total_count)

    status_text.empty()

    success_count = len(st.session_state.edit_processed_results)
    fail_count = len(error_messages)

    if success_count > 0:
        st.success(f"처리 완료! 성공 {success_count}건 / 실패 {fail_count}건")
    else:
        st.error("처리에 성공한 이미지가 없습니다.")

    if error_messages:
        with st.expander(f"오류 목록 보기 ({fail_count}건)"):
            for error_message in error_messages:
                st.write(f"⚠️ {error_message}")

# ------------------------------------------------------------------
# 3단계: 결과 미리보기
# ------------------------------------------------------------------
if st.session_state.edit_processed_results:
    st.header("3. 결과 미리보기")

    for preview_index, result_item in enumerate(st.session_state.edit_processed_results):
        result_w, result_h = result_item["result_size"]

        st.subheader(result_item["original_file_name"])
        st.caption(
            f"편집 결과 {result_w} x {result_h}px · {TARGET_DPI[0]}dpi "
            "(배경 제거 + 여백 제거 + 리사이즈 + dpi 적용)"
        )

        # 결과 이미지를 가운데 정렬하기 위해 좌우에 여백 컬럼을 둔다
        # width는 지정하지 않아, 확대(전체화면) 시 원본 해상도가 그대로 보이도록 한다
        left_margin_column, image_column, right_margin_column = st.columns([1, 2, 1])
        with image_column:
            st.image(result_item["result_image"])

        # 개별 파일 다운로드 버튼
        result_file_name = build_edited_file_name(result_item["original_file_name"])
        image_bytes = convert_image_to_png_bytes(result_item["result_image"], dpi=TARGET_DPI)
        st.download_button(
            label=f"'{result_file_name}' 다운로드",
            data=image_bytes,
            file_name=result_file_name,
            mime="image/png",
            key=f"edit_download_{preview_index}_{result_item['original_file_name']}",
            type="primary",
        )
        st.divider()

    # ------------------------------------------------------------------
    # 4단계: 전체 결과 ZIP 일괄 다운로드
    # ------------------------------------------------------------------
    st.header("4. 전체 결과 다운로드")
    try:
        named_results_for_zip = [
            {
                "result_file_name": build_edited_file_name(item["original_file_name"]),
                "result_image": item["result_image"],
                "image_format": "PNG",
                "dpi": TARGET_DPI,
            }
            for item in st.session_state.edit_processed_results
        ]
        zip_file_bytes = build_zip_file_from_named_results(named_results_for_zip)
        st.download_button(
            label=f"전체 결과 ZIP으로 다운로드 ({len(st.session_state.edit_processed_results)}건)",
            data=zip_file_bytes,
            file_name="이미지편집_결과_전체.zip",
            mime="application/zip",
            type="primary",
        )
    except Exception as zip_error:
        st.error(f"ZIP 파일을 만드는 중 오류가 발생했습니다: {zip_error}")
        st.caption("개별 다운로드 버튼으로 파일을 하나씩 받아주세요.")
