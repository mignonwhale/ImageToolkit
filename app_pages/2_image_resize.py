"""
이미지 크기 조정 페이지
동작 흐름: 이미지 업로드 > 픽셀 또는 비율 입력 > 크기가 변경된 파일 다운로드
"""

import io

import streamlit as st
from PIL import Image

from image_resizer import (
    PREDEFINED_ASPECT_RATIOS,
    calculate_dimensions_by_pixels,
    calculate_dimensions_by_percentage,
    calculate_dimensions_by_aspect_ratio,
    resize_image,
)
from file_handler import convert_image_to_bytes, build_zip_file_from_named_results
from utils import (
    is_supported_image_file,
    build_error_message,
    build_error_message_from_exception,
    build_progress_text,
    build_resized_file_name,
    encode_image_to_thumbnail_data_url,
)

# 화면 기본 설정
st.set_page_config(page_title="크기 조정 - 이미지 도구 모음", layout="wide")
st.title("📐 이미지 크기 조정")
st.caption("여러 장의 이미지를 업로드하면 원하는 픽셀 또는 비율로 크기를 조정하고, 결과를 미리보기 후 다운로드할 수 있습니다.")

# 세션 상태 초기화
# 배경 제거 페이지와 상태가 섞이지 않도록 "resize_" 접두사로 구분한다
if "resize_processed_results" not in st.session_state:
    st.session_state.resize_processed_results = []

if "resize_last_uploaded_file_signature" not in st.session_state:
    st.session_state.resize_last_uploaded_file_signature = ()

# 실제 업로드된 파일을 보관하는 저장소 (서명 -> {name, size, bytes})
if "resize_uploaded_files_store" not in st.session_state:
    st.session_state.resize_uploaded_files_store = {}

# 업로더 위젯의 key에 사용되는 번호. 새 파일을 저장소로 옮긴 뒤 이 값을 올려서
# 업로더 위젯을 완전히 새로 만들어(=항상 빈 상태로) 파일명이 계속 남아있지 않도록 한다.
if "resize_uploader_reset_counter" not in st.session_state:
    st.session_state.resize_uploader_reset_counter = 0

# ------------------------------------------------------------------
# 1단계: 이미지 파일 업로드
# ------------------------------------------------------------------
header_column, count_column = st.columns([5, 1])
with header_column:
    st.header("1. 이미지 업로드")

with st.expander("이미지 선택", expanded=len(st.session_state.resize_uploaded_files_store) == 0):
    newly_selected_files = st.file_uploader(
        "크기를 조정할 이미지를 선택하세요 (여러 장 선택 가능, 파일을 이 영역으로 끌어다 놓아도 됩니다)",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=True,
        key=f"resize_file_uploader_{st.session_state.resize_uploader_reset_counter}",
    )

# 새로 선택된 파일을 저장소로 옮긴다 (이미 저장소에 있는 파일은 건너뛴다)
has_newly_added_file = False
for newly_selected_file in newly_selected_files or []:
    file_signature = (newly_selected_file.name, newly_selected_file.size)
    if file_signature not in st.session_state.resize_uploaded_files_store:
        st.session_state.resize_uploaded_files_store[file_signature] = {
            "name": newly_selected_file.name,
            "size": newly_selected_file.size,
            "bytes": newly_selected_file.getvalue(),
        }
        has_newly_added_file = True

if has_newly_added_file:
    # 업로더 위젯의 key를 바꿔 완전히 새(빈) 상태로 리셋한다
    st.session_state.resize_uploader_reset_counter += 1
    st.rerun()

# 이후 모든 로직은 저장소에 있는 파일을 기준으로 동작한다
active_files = list(st.session_state.resize_uploaded_files_store.values())

with count_column:
    st.markdown(
        f"<div style='text-align:right; padding-top:0.6rem; font-weight:600;'>총 {len(active_files)}개 업로드</div>",
        unsafe_allow_html=True,
    )

current_uploaded_file_signature = tuple(sorted(st.session_state.resize_uploaded_files_store.keys()))

if current_uploaded_file_signature != st.session_state.resize_last_uploaded_file_signature:
    if st.session_state.resize_processed_results:
        st.session_state.resize_processed_results = []
        st.info("업로드된 파일이 변경되어 이전 크기 조정 결과를 초기화했습니다.")
    st.session_state.resize_last_uploaded_file_signature = current_uploaded_file_signature

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
                if st.button("✕", key=f"resize_remove_{preview_index}_{file_signature}", help="이 이미지를 목록에서 제거"):
                    del st.session_state.resize_uploaded_files_store[file_signature]
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
# 2단계: 크기 조정 옵션
# ------------------------------------------------------------------
st.header("2. 크기 조정 옵션")

resize_mode = st.radio(
    "크기 지정 방식",
    options=["픽셀로 지정", "비율(%)로 지정", "사전 정의 비율로 지정"],
    horizontal=True,
)

# 픽셀 드랍다운에서 선택할 수 있는 사전 정의 크기 목록
PIXEL_SIZE_PRESET_OPTIONS = ["320", "480", "640", "800", "1024", "1280", "1600", "1920", "2560", "3840"]
CUSTOM_PIXEL_OPTION_LABEL = "직접 입력"
PIXEL_SIZE_OPTIONS = PIXEL_SIZE_PRESET_OPTIONS + [CUSTOM_PIXEL_OPTION_LABEL]

target_width_input = None
target_height_input = None
keep_aspect_ratio = True
scale_percentage_input = None
selected_predefined_ratio = None

if resize_mode == "픽셀로 지정":
    keep_aspect_ratio = st.checkbox("가로세로 비율 고정 (가로 값 기준으로 세로 자동 계산)", value=True)

    pixel_input_column1, pixel_input_column2 = st.columns(2)

    with pixel_input_column1:
        selected_width_option = st.selectbox(
            "가로 (px)", options=PIXEL_SIZE_OPTIONS, index=PIXEL_SIZE_PRESET_OPTIONS.index("1024"),
        )
        if selected_width_option == CUSTOM_PIXEL_OPTION_LABEL:
            target_width_input = st.number_input("가로 직접 입력 (px)", min_value=1, value=1024, step=1)
        else:
            target_width_input = int(selected_width_option)

    with pixel_input_column2:
        if keep_aspect_ratio:
            st.caption("비율 고정이 켜져 있어, 세로 값은 가로 값에 맞춰 자동으로 계산됩니다.")
        else:
            selected_height_option = st.selectbox(
                "세로 (px)", options=PIXEL_SIZE_OPTIONS, index=PIXEL_SIZE_PRESET_OPTIONS.index("800"),
            )
            if selected_height_option == CUSTOM_PIXEL_OPTION_LABEL:
                target_height_input = st.number_input("세로 직접 입력 (px)", min_value=1, value=800, step=1)
            else:
                target_height_input = int(selected_height_option)

elif resize_mode == "비율(%)로 지정":
    scale_percentage_input = st.slider(
        "원본 대비 비율 (%)", min_value=1, max_value=300, value=50,
        help="100%는 원본과 동일한 크기입니다. 100% 미만은 축소, 초과는 확대됩니다.",
    )

else:  # 사전 정의 비율로 지정
    selected_predefined_ratio = st.selectbox(
        "비율 선택",
        options=list(PREDEFINED_ASPECT_RATIOS.keys()),
        help="원본 가로 픽셀을 기준으로, 선택한 비율에 맞춰 세로 픽셀이 계산됩니다.",
    )

# ------------------------------------------------------------------
# 3단계: 크기 조정 처리 실행
# ------------------------------------------------------------------
st.header("3. 크기 조정 처리")

start_processing_button = st.button("크기 조정 시작", type="primary", disabled=not active_files)

if start_processing_button and active_files:
    st.session_state.resize_processed_results = []

    progress_bar = st.progress(0)
    status_text = st.empty()
    error_messages = []

    total_count = len(active_files)

    for index, active_file in enumerate(active_files, start=1):
        file_name = active_file["name"]
        status_text.info(build_progress_text(index, total_count, file_name))

        if not is_supported_image_file(file_name):
            error_messages.append(
                build_error_message(file_name, "지원하지 않는 파일 형식입니다.")
            )
            progress_bar.progress(index / total_count)
            continue

        try:
            original_image = Image.open(io.BytesIO(active_file["bytes"]))
            original_image_format = (original_image.format or "PNG").upper()
            original_width, original_height = original_image.size

            # 선택한 방식에 따라 최종 크기를 계산한다
            if resize_mode == "픽셀로 지정":
                final_width, final_height = calculate_dimensions_by_pixels(
                    original_width, original_height,
                    int(target_width_input), int(target_height_input or 0),
                    keep_aspect_ratio,
                )
            elif resize_mode == "비율(%)로 지정":
                final_width, final_height = calculate_dimensions_by_percentage(
                    original_width, original_height, scale_percentage_input
                )
            else:
                ratio_width, ratio_height = PREDEFINED_ASPECT_RATIOS[selected_predefined_ratio]
                final_width, final_height = calculate_dimensions_by_aspect_ratio(
                    original_width, original_height, ratio_width, ratio_height
                )

            result_image = resize_image(original_image, final_width, final_height)

            st.session_state.resize_processed_results.append(
                {
                    "original_file_name": file_name,
                    "original_image": original_image,
                    "original_size": (original_width, original_height),
                    "result_image": result_image,
                    "result_size": (final_width, final_height),
                    "image_format": original_image_format,
                }
            )
        except Exception as processing_error:
            error_messages.append(
                build_error_message_from_exception(file_name, processing_error)
            )

        progress_bar.progress(index / total_count)

    status_text.empty()

    success_count = len(st.session_state.resize_processed_results)
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
# 4단계: 결과 미리보기 (Before / After 비교)
# ------------------------------------------------------------------
if st.session_state.resize_processed_results:
    st.header("4. 결과 미리보기")

    for preview_index, result_item in enumerate(st.session_state.resize_processed_results):
        original_w, original_h = result_item["original_size"]
        result_w, result_h = result_item["result_size"]

        st.subheader(result_item["original_file_name"])
        st.caption(f"원본 {original_w} x {original_h}px → 조정 결과 {result_w} x {result_h}px")

        # 결과 이미지를 가운데 정렬하기 위해 좌우에 여백 컬럼을 둔다
        # width는 지정하지 않아, 확대(전체화면) 시 원본 해상도가 그대로 보이도록 한다
        left_margin_column, image_column, right_margin_column = st.columns([1, 2, 1])
        with image_column:
            st.image(result_item["result_image"])

        result_file_name = build_resized_file_name(
            result_item["original_file_name"], result_w, result_h
        )
        image_bytes = convert_image_to_bytes(result_item["result_image"], result_item["image_format"])
        st.download_button(
            label=f"'{result_file_name}' 다운로드",
            data=image_bytes,
            file_name=result_file_name,
            mime=f"image/{result_item['image_format'].lower()}",
            key=f"resize_download_{preview_index}_{result_item['original_file_name']}",
            type="primary",
        )
        st.divider()

    # ------------------------------------------------------------------
    # 5단계: 전체 결과 ZIP 일괄 다운로드
    # ------------------------------------------------------------------
    st.header("5. 전체 결과 다운로드")
    try:
        named_results_for_zip = [
            {
                "result_file_name": build_resized_file_name(
                    item["original_file_name"], item["result_size"][0], item["result_size"][1]
                ),
                "result_image": item["result_image"],
                "image_format": item["image_format"],
            }
            for item in st.session_state.resize_processed_results
        ]
        zip_file_bytes = build_zip_file_from_named_results(named_results_for_zip)
        st.download_button(
            label=f"전체 결과 ZIP으로 다운로드 ({len(st.session_state.resize_processed_results)}건)",
            data=zip_file_bytes,
            file_name="크기조정_결과_전체.zip",
            mime="application/zip",
            type="primary",
        )
    except Exception as zip_error:
        st.error(f"ZIP 파일을 만드는 중 오류가 발생했습니다: {zip_error}")
        st.caption("개별 다운로드 버튼으로 파일을 하나씩 받아주세요.")
