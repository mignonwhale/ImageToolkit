"""
배경 제거 페이지
동작 흐름: 이미지파일 업로드 > 배경없앤 이미지 미리보기 > 결과파일 자동 다운로드
"""

import io

import streamlit as st
from PIL import Image

from background_remover import remove_background_from_image
from image_cropper import compute_trim_bounding_box, crop_image_to_box
from file_handler import convert_image_to_png_bytes, build_zip_file_from_results
from utils import (
    is_supported_image_file,
    build_error_message,
    build_error_message_from_exception,
    build_progress_text,
    build_result_file_name,
    compute_contained_display_width,
    encode_image_to_thumbnail_data_url,
)

# 모델별 알파매팅 필요 여부
# - birefnet 계열: 이미 정밀한 마스크를 만들기 때문에 알파매팅이 불필요 (오히려 경계를 해칠 수 있음)
# - u2net/isnet 계열: 마스크가 비교적 거칠어 알파매팅으로 경계를 다듬는 것이 도움이 됨
MODEL_ALPHA_MATTING_RECOMMENDATION = {
    "birefnet-general": False,
    "birefnet-general-lite": False,
    "isnet-general-use": True,
    "u2net": True,
    "u2netp": True,
}

MODEL_OPTIONS = list(MODEL_ALPHA_MATTING_RECOMMENDATION.keys())


def sync_alpha_matting_with_selected_model():
    """모델 선택이 바뀌면, 해당 모델에 알파매팅이 필요한지에 따라 옵션을 자동으로 켜거나 끈다."""
    selected_model = st.session_state.bg_selected_model_name
    st.session_state.bg_enable_alpha_matting = MODEL_ALPHA_MATTING_RECOMMENDATION.get(selected_model, True)


# 화면 기본 설정
st.set_page_config(page_title="배경 제거 - 이미지 도구 모음", layout="wide")
st.title("🖼️ 이미지 배경 제거")
st.caption("여러 장의 이미지를 업로드하면 배경을 자동으로 제거하고, 결과를 미리보기 후 다운로드할 수 있습니다.")

# 세션 상태 초기화 (재실행 시에도 처리 결과 유지)
# 다른 페이지(예: 크기 조정)와 상태가 섞이지 않도록 "bg_" 접두사로 구분한다
if "bg_processed_results" not in st.session_state:
    st.session_state.bg_processed_results = []

# 업로드된 파일이 바뀌었는지 감지하기 위한 서명(파일명+크기 조합) 초기값
if "bg_last_uploaded_file_signature" not in st.session_state:
    st.session_state.bg_last_uploaded_file_signature = ()

# 실제 업로드된 파일을 보관하는 저장소 (서명 -> {name, size, bytes})
# 파일 업로더 위젯 자체가 아니라 이 저장소를 기준으로 미리보기/처리를 진행하므로,
# 개별 파일을 삭제해도 업로더 쪽에 파일명이 남아있는 문제가 생기지 않는다.
if "bg_uploaded_files_store" not in st.session_state:
    st.session_state.bg_uploaded_files_store = {}

# 업로더 위젯의 key에 사용되는 번호. 새 파일을 저장소로 옮긴 뒤 이 값을 올려서
# 업로더 위젯을 완전히 새로 만들어(=항상 빈 상태로) 파일명이 계속 남아있지 않도록 한다.
if "bg_uploader_reset_counter" not in st.session_state:
    st.session_state.bg_uploader_reset_counter = 0

# 고급 옵션 초기값 설정 (최초 1회만) - 기본 모델(birefnet-general) 기준으로 알파매팅 초기값 결정
if "bg_selected_model_name" not in st.session_state:
    st.session_state.bg_selected_model_name = MODEL_OPTIONS[0]
if "bg_enable_alpha_matting" not in st.session_state:
    st.session_state.bg_enable_alpha_matting = MODEL_ALPHA_MATTING_RECOMMENDATION[MODEL_OPTIONS[0]]

# ------------------------------------------------------------------
# 1단계: 이미지 파일 업로드
# ------------------------------------------------------------------
header_column, count_column = st.columns([5, 1])
with header_column:
    st.header("1. 이미지 업로드")

with st.expander("이미지 선택", expanded=len(st.session_state.bg_uploaded_files_store) == 0):
    newly_selected_files = st.file_uploader(
        "배경을 제거할 이미지를 선택하세요 (여러 장 선택 가능, 파일을 이 영역으로 끌어다 놓아도 됩니다)",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=True,
        key=f"bg_file_uploader_{st.session_state.bg_uploader_reset_counter}",
    )

# 새로 선택된 파일을 저장소로 옮긴다 (이미 저장소에 있는 파일은 건너뛴다)
has_newly_added_file = False
for newly_selected_file in newly_selected_files or []:
    file_signature = (newly_selected_file.name, newly_selected_file.size)
    if file_signature not in st.session_state.bg_uploaded_files_store:
        st.session_state.bg_uploaded_files_store[file_signature] = {
            "name": newly_selected_file.name,
            "size": newly_selected_file.size,
            "bytes": newly_selected_file.getvalue(),
        }
        has_newly_added_file = True

if has_newly_added_file:
    # 업로더 위젯의 key를 바꿔 완전히 새(빈) 상태로 리셋한다
    st.session_state.bg_uploader_reset_counter += 1
    st.rerun()

# 이후 모든 로직은 저장소에 있는 파일을 기준으로 동작한다
active_files = list(st.session_state.bg_uploaded_files_store.values())

with count_column:
    st.markdown(
        f"<div style='text-align:right; padding-top:0.6rem; font-weight:600;'>총 {len(active_files)}개 업로드</div>",
        unsafe_allow_html=True,
    )

# 업로드된 파일 목록(이름+크기)으로 서명을 만들어, 이전 업로드와 달라졌는지 감지한다
current_uploaded_file_signature = tuple(sorted(st.session_state.bg_uploaded_files_store.keys()))

if current_uploaded_file_signature != st.session_state.bg_last_uploaded_file_signature:
    # 업로드 파일이 새로 추가/변경/삭제된 경우, 이전 배경 제거 결과는 더 이상 유효하지 않으므로 초기화한다
    if st.session_state.bg_processed_results:
        st.session_state.bg_processed_results = []
        st.info("업로드된 파일이 변경되어 이전 배경 제거 결과를 초기화했습니다.")
    st.session_state.bg_last_uploaded_file_signature = current_uploaded_file_signature

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
                if st.button("✕", key=f"bg_remove_{preview_index}_{file_signature}", help="이 이미지를 목록에서 제거"):
                    del st.session_state.bg_uploaded_files_store[file_signature]
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
# 고급 옵션: 모델 선택 및 경계선 정밀 보정(알파매팅)
# ------------------------------------------------------------------
with st.expander("⚙️ 고급 옵션 (경계선이 잘리거나 뭉개질 때 조절하세요)"):
    selected_model_name = st.selectbox(
        "배경 제거 모델",
        options=MODEL_OPTIONS,
        key="bg_selected_model_name",
        on_change=sync_alpha_matting_with_selected_model,
        help="birefnet-general: 사진처럼 배경이 복잡할 때 가장 정밀함 (기본값 권장, 처리 다소 느림)\n"
             "birefnet-general-lite: birefnet-general보다 가볍고 빠른 경량 버전\n"
             "isnet-general-use: 일반 사물/아이콘 경계 인식에 적합\n"
             "u2net: 범용 모델, 처리 속도 빠름\n"
             "u2netp: 경량 모델, 정확도는 낮지만 매우 빠름",
    )

    st.caption("""
    **모델 설명**
    - birefnet-general : 사진처럼 배경이 복잡할 때 가장 정밀 (기본값 권장, 처리 다소 느림)
    - birefnet-general-lite : 경량 버전
    - isnet-general-use : 일반 사물/아이콘 경계 인식에 적합
    - u2net : 범용
    - u2netp : 경량 모델, 정확도는 낮지만 매우 빠름
    """)

    alpha_matting_needed_for_model = MODEL_ALPHA_MATTING_RECOMMENDATION.get(selected_model_name, True)

    if not alpha_matting_needed_for_model:
        st.caption("ℹ️ 현재 모델은 알파매팅이 필요 없어 자동으로 꺼져 있습니다 (경계를 오히려 해칠 수 있음).")
    else:
        st.caption("ℹ️ 현재 모델은 알파매팅이 도움이 되어 자동으로 켜져 있습니다.")

    enable_alpha_matting = st.checkbox(
        "경계선 정밀 보정(알파매팅) 사용",
        key="bg_enable_alpha_matting",
        disabled=not alpha_matting_needed_for_model,
        help="u2net/isnet처럼 비교적 거친 마스크를 정교하게 다듬을 때 유용합니다. "
             "birefnet 계열 모델은 이미 정밀한 마스크를 만들기 때문에, 알파매팅을 함께 켜면 "
             "그릇처럼 어둡고 명암 대비가 낮은 사물의 경계가 오히려 통째로 지워질 수 있어 "
             "선택할 수 없도록 자동으로 막아두었습니다.",
    )

    alpha_matting_erode_size_value = st.slider(
        "경계 침식(erode) 크기",
        min_value=0,
        max_value=30,
        value=5,
        disabled=not enable_alpha_matting,
        help="값이 작을수록 얇은 테두리가 덜 잘려나가지만, 배경 잔여물이 남을 수 있습니다.",
    )

    enable_fill_interior_holes = st.checkbox(
        "사물 내부 구멍 채우기",
        value=True,
        help="달력의 흰 칸처럼 사물 안쪽의 밝은 영역이 배경으로 오인되어 지워질 때, "
             "테두리와 연결되지 않은 투명 영역을 원래 색상으로 복원합니다.",
    )

    hole_bridging_size_value = st.slider(
        "내부 구멍 - 좁은 틈 메우기 강도",
        min_value=0,
        max_value=10,
        value=3,
        disabled=not enable_fill_interior_holes,
        help="내부 구멍이 얇은 틈으로 바깥 배경과 이어져 복원되지 않을 때 값을 높여보세요. "
             "너무 높이면 사물 내부의 실제 뚫린 부분(예: 링 구멍)까지 채워질 수 있습니다.",
    )

    alpha_cleanup_threshold_value = st.slider(
        "경계 잔여 얼룩 정리 강도",
        min_value=0,
        max_value=60,
        value=8,
        help="경계 부근에 희미하게 남는 반투명 배경 흔적을 지웁니다. "
             "값이 클수록 더 확실히 지우지만, 그릇 테두리나 머리카락처럼 명암 대비가 낮은 사물 경계도 "
             "함께 잘릴 수 있습니다. 문제가 없다면 낮게, 얼룩이 남으면 조금씩만 올려보세요.",
    )

    enable_auto_trim_transparent_margin = st.checkbox(
        "투명 여백 자동 잘라내기",
        value=False,
        help="배경 제거 후 남는 투명 여백을 요소 영역만 남기고 자동으로 잘라냅니다. "
             "요소가 조금이라도 잘리지 않도록 안전하게 계산되며, 결과 미리보기에서 확인 후 다운로드할 수 있습니다. "
             "더 세밀하게 영역을 확인하거나 직접 조정하고 싶다면 '자르기' 도구를 별도로 이용해주세요.",
    )

# ------------------------------------------------------------------
# 2단계: 배경 제거 처리 실행
# ------------------------------------------------------------------
st.header("2. 배경 제거 처리")

start_processing_button = st.button("배경 제거 시작", type="primary", disabled=not active_files)

if start_processing_button and active_files:
    st.session_state.bg_processed_results = []

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
            result_image = remove_background_from_image(
                original_image,
                model_name=selected_model_name,
                use_alpha_matting=enable_alpha_matting,
                alpha_matting_erode_size=alpha_matting_erode_size_value,
                fill_interior_holes_enabled=enable_fill_interior_holes,
                hole_bridging_size=hole_bridging_size_value,
                alpha_cleanup_threshold=alpha_cleanup_threshold_value,
            )

            if enable_auto_trim_transparent_margin:
                trim_box = compute_trim_bounding_box(result_image)
                # 요소가 하나도 없거나(완전 투명), 이미 여백이 없는 경우는 그대로 둔다
                if trim_box is not None and trim_box != (0, 0, result_image.width, result_image.height):
                    result_image = crop_image_to_box(result_image, trim_box)

            st.session_state.bg_processed_results.append(
                {
                    "original_file_name": file_name,
                    "original_image": original_image,
                    "result_image": result_image,
                }
            )
        except Exception as processing_error:
            error_messages.append(
                build_error_message_from_exception(file_name, processing_error)
            )

        progress_bar.progress(index / total_count)

    status_text.empty()

    success_count = len(st.session_state.bg_processed_results)
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
# 3단계: 결과 미리보기 (Before / After 비교)
# ------------------------------------------------------------------
if st.session_state.bg_processed_results:
    st.header("3. 결과 미리보기")

    for preview_index, result_item in enumerate(st.session_state.bg_processed_results):
        st.subheader(result_item["original_file_name"])
        st.caption("배경 제거 결과")

        # 결과 이미지를 가운데 정렬하기 위해 좌우에 여백 컬럼을 둔다
        # width는 지정하지 않아, 확대(전체화면) 시 원본 해상도가 그대로 보이도록 한다
        left_margin_column, image_column, right_margin_column = st.columns([1, 2, 1])
        with image_column:
            st.image(result_item["result_image"])

        # 개별 파일 다운로드 버튼
        result_file_name = build_result_file_name(result_item["original_file_name"])
        image_bytes = convert_image_to_png_bytes(result_item["result_image"])
        st.download_button(
            label=f"'{result_file_name}' 다운로드",
            data=image_bytes,
            file_name=result_file_name,
            mime="image/png",
            key=f"bg_download_{preview_index}_{result_item['original_file_name']}",
            type="primary",
        )
        st.divider()

    # ------------------------------------------------------------------
    # 4단계: 전체 결과 ZIP 일괄 다운로드
    # ------------------------------------------------------------------
    st.header("4. 전체 결과 다운로드")
    try:
        zip_file_bytes = build_zip_file_from_results(st.session_state.bg_processed_results)
        st.download_button(
            label=f"전체 결과 ZIP으로 다운로드 ({len(st.session_state.bg_processed_results)}건)",
            data=zip_file_bytes,
            file_name="배경제거_결과_전체.zip",
            mime="application/zip",
            type="primary",
        )
    except Exception as zip_error:
        st.error(f"ZIP 파일을 만드는 중 오류가 발생했습니다: {zip_error}")
        st.caption("개별 다운로드 버튼으로 파일을 하나씩 받아주세요.")
