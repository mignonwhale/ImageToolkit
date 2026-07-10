"""
여백/영역 자르기 페이지
동작 흐름: 이미지 업로드 > (자동/수동 모드 판별) > 자를 영역 확인 및 승인 > 결과 다운로드

- 실제 투명 배경이 있는 이미지(예: 배경 제거 결과물): 요소를 감싸는 최소 영역을 자동 계산해 제안하고,
  사용자가 승인해야 실제로 잘린다.
- 투명 배경이 없는 이미지(일반 사진 등): 사용자가 슬라이더로 직접 자를 영역을 지정한다.
"""

import io

import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper

from image_cropper import (
    has_meaningful_transparency,
    compute_trim_bounding_box,
    crop_image_to_box,
    build_crop_preview_overlay,
)
from file_handler import convert_image_to_bytes, build_zip_file_from_named_results
from utils import (
    is_supported_image_file,
    build_error_message_from_exception,
    build_cropped_file_name,
    encode_image_to_thumbnail_data_url,
)

# 화면 기본 설정
st.set_page_config(page_title="자르기 - 이미지 도구 모음", layout="wide")
st.title("✂️ 여백/영역 자르기")
st.caption(
    "투명 배경 이미지는 요소를 감싸는 영역을 자동으로 제안하고, "
    "배경이 있는 이미지는 직접 자를 영역을 지정할 수 있습니다."
)

# ------------------------------------------------------------------
# 세션 상태 초기화 ("crop_" 접두사로 다른 페이지와 구분)
# ------------------------------------------------------------------
if "crop_uploaded_files_store" not in st.session_state:
    st.session_state.crop_uploaded_files_store = {}
if "crop_uploader_reset_counter" not in st.session_state:
    st.session_state.crop_uploader_reset_counter = 0
if "crop_selection_state" not in st.session_state:
    # 파일 서명(이름,크기) -> {"box": (l,t,r,b), "mode": "auto"|"manual", "applied": bool}
    st.session_state.crop_selection_state = {}
if "crop_processed_results" not in st.session_state:
    st.session_state.crop_processed_results = []

# ------------------------------------------------------------------
# 1단계: 이미지 파일 업로드
# ------------------------------------------------------------------
header_column, count_column = st.columns([5, 1])
with header_column:
    st.header("1. 이미지 업로드")

with st.expander("이미지 선택", expanded=len(st.session_state.crop_uploaded_files_store) == 0):
    newly_selected_files = st.file_uploader(
        "자를 이미지를 선택하세요 (여러 장 선택 가능, 파일을 이 영역으로 끌어다 놓아도 됩니다)",
        type=["jpg", "jpeg", "png", "bmp", "webp"],
        accept_multiple_files=True,
        key=f"crop_file_uploader_{st.session_state.crop_uploader_reset_counter}",
    )

has_newly_added_file = False
for newly_selected_file in newly_selected_files or []:
    file_signature = (newly_selected_file.name, newly_selected_file.size)
    if file_signature not in st.session_state.crop_uploaded_files_store:
        st.session_state.crop_uploaded_files_store[file_signature] = {
            "name": newly_selected_file.name,
            "size": newly_selected_file.size,
            "bytes": newly_selected_file.getvalue(),
        }
        has_newly_added_file = True

if has_newly_added_file:
    st.session_state.crop_uploader_reset_counter += 1
    st.rerun()

active_files = list(st.session_state.crop_uploaded_files_store.values())

with count_column:
    st.markdown(
        f"<div style='text-align:right; padding-top:0.6rem; font-weight:600;'>총 {len(active_files)}개 업로드</div>",
        unsafe_allow_html=True,
    )

# 저장소에 없는(삭제된) 파일의 선택 상태/결과는 함께 정리한다
active_signatures = {(f["name"], f["size"]) for f in active_files}
st.session_state.crop_selection_state = {
    sig: state for sig, state in st.session_state.crop_selection_state.items() if sig in active_signatures
}
st.session_state.crop_processed_results = [
    item for item in st.session_state.crop_processed_results
    if item["original_size_bytes"] in active_signatures
]

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
                if st.button("✕", key=f"crop_remove_{preview_index}_{file_signature}", help="이 이미지를 목록에서 제거"):
                    del st.session_state.crop_uploaded_files_store[file_signature]
                    st.session_state.crop_selection_state.pop(file_signature, None)
                    st.rerun()

            try:
                preview_image = Image.open(io.BytesIO(active_file["bytes"]))
                preview_width, preview_height = preview_image.size
                thumbnail_data_url = encode_image_to_thumbnail_data_url(preview_image, 300)
                st.markdown(
                    f"<img src='{thumbnail_data_url}' style='display:block;' />",
                    unsafe_allow_html=True,
                )
                st.caption(f"{preview_width}x{preview_height}px")
            except Exception:
                st.warning(f"'{active_file['name']}' 미리보기를 불러올 수 없습니다.")

# ------------------------------------------------------------------
# 2단계: 자를 영역 확인 및 승인
# ------------------------------------------------------------------
if active_files:
    st.header("2. 자를 영역 확인")

    for active_file in active_files:
        file_signature = (active_file["name"], active_file["size"])
        file_name = active_file["name"]

        if not is_supported_image_file(file_name):
            st.error(f"'{file_name}': 지원하지 않는 파일 형식입니다.")
            continue

        try:
            original_image = Image.open(io.BytesIO(active_file["bytes"]))
        except Exception as open_error:
            st.error(build_error_message_from_exception(file_name, open_error))
            continue

        original_width, original_height = original_image.size
        image_format = (original_image.format or "PNG").upper()

        selection_state = st.session_state.crop_selection_state.get(file_signature)

        # 이미 적용 완료된 이미지는 여기서 다시 조정할 수 있게 안내만 표시한다
        already_applied = selection_state is not None and selection_state.get("applied", False)

        with st.expander(f"{'✅ ' if already_applied else ''}{file_name}", expanded=not already_applied):
            if already_applied:
                st.success("이미 적용되었습니다. 아래 '결과 미리보기'에서 확인하거나, 다시 조정할 수 있습니다.")
                if st.button("다시 조정하기", key=f"crop_readjust_{file_signature}"):
                    selection_state["applied"] = False
                    st.session_state.crop_processed_results = [
                        item for item in st.session_state.crop_processed_results
                        if not (item["original_file_name"] == file_name
                                and item["original_size_bytes"] == file_signature)
                    ]
                    st.rerun()

            else:
                is_auto_mode = has_meaningful_transparency(original_image)

                if is_auto_mode:
                    auto_bbox = compute_trim_bounding_box(original_image)
                    if auto_bbox is None:
                        st.info("이미지 전체가 투명해서 자를 요소가 없습니다.")
                        continue

                    st.caption("🟢 투명 배경이 감지되어 요소 영역을 자동으로 제안했습니다.")

                    if selection_state is None or selection_state.get("mode") != "auto":
                        selection_state = {"box": auto_bbox, "mode": "auto", "applied": False}
                        st.session_state.crop_selection_state[file_signature] = selection_state

                    current_box = selection_state["box"]
                    preview_image = build_crop_preview_overlay(original_image, current_box)
                    st.image(preview_image)
                    st.caption(
                        f"제안 영역: 가로 {current_box[2]-current_box[0]}px x "
                        f"세로 {current_box[3]-current_box[1]}px "
                        f"(원본 {original_width}x{original_height}px)"
                    )

                    if st.button("이 영역대로 자르기", key=f"crop_apply_auto_{file_signature}", type="primary"):
                        try:
                            cropped_image = crop_image_to_box(original_image, current_box)
                            st.session_state.crop_processed_results.append(
                                {
                                    "original_file_name": file_name,
                                    "original_size_bytes": file_signature,
                                    "original_size": (original_width, original_height),
                                    "result_image": cropped_image,
                                    "result_size": cropped_image.size,
                                    "image_format": image_format,
                                }
                            )
                            selection_state["applied"] = True
                            st.rerun()
                        except Exception as crop_error:
                            st.error(build_error_message_from_exception(file_name, crop_error))

                else:
                    st.caption("🔵 투명 배경이 없어 이미지 위에서 직접 자를 영역을 선택해주세요.")

                    if selection_state is None or selection_state.get("mode") != "manual":
                        selection_state = {
                            "box": (0, 0, original_width, original_height),
                            "mode": "manual",
                            "applied": False,
                            # st_cropper의 초기 좌표. 위젯 생성 시 한 번만 사용하고, 이후로는
                            # 절대 갱신하지 않는다. 매 rerun마다 직전 드래그 결과를 다시 넘기면
                            # st_cropper 프론트엔드가 그 좌표로 박스 위치를 강제로 되돌려버려서
                            # (컴포넌트 내부적으로 props가 바뀔 때마다 위치를 재설정함)
                            # 드래그 중 박스가 엉뚱한 곳으로 튀는 문제가 발생한다.
                            "cropper_default_coords": (0, original_width, 0, original_height),
                        }
                        st.session_state.crop_selection_state[file_signature] = selection_state

                    cropper_box = st_cropper(
                        original_image,
                        realtime_update=True,
                        box_color="#0000FF",
                        return_type="box",
                        default_coords=selection_state["cropper_default_coords"],
                        key=f"crop_cropper_{file_signature}",
                    )

                    left_val = cropper_box["left"]
                    top_val = cropper_box["top"]
                    right_val = left_val + cropper_box["width"]
                    bottom_val = top_val + cropper_box["height"]

                    # 좌우/상하가 뒤바뀌지 않도록 보정한다
                    if right_val <= left_val:
                        right_val = left_val + 1
                    if bottom_val <= top_val:
                        bottom_val = top_val + 1

                    current_box = (left_val, top_val, right_val, bottom_val)
                    selection_state["box"] = current_box

                    st.caption(
                        f"선택 영역: 가로 {right_val-left_val}px x 세로 {bottom_val-top_val}px "
                        f"(원본 {original_width}x{original_height}px)"
                    )

                    if st.button("이 영역으로 자르기", key=f"crop_apply_manual_{file_signature}", type="primary"):
                        try:
                            cropped_image = crop_image_to_box(original_image, current_box)
                            st.session_state.crop_processed_results.append(
                                {
                                    "original_file_name": file_name,
                                    "original_size_bytes": file_signature,
                                    "original_size": (original_width, original_height),
                                    "result_image": cropped_image,
                                    "result_size": cropped_image.size,
                                    "image_format": image_format,
                                }
                            )
                            selection_state["applied"] = True
                            st.rerun()
                        except Exception as crop_error:
                            st.error(build_error_message_from_exception(file_name, crop_error))

# ------------------------------------------------------------------
# 3단계: 결과 미리보기
# ------------------------------------------------------------------
if st.session_state.crop_processed_results:
    st.header("3. 결과 미리보기")

    for preview_index, result_item in enumerate(st.session_state.crop_processed_results):
        original_w, original_h = result_item["original_size"]
        result_w, result_h = result_item["result_size"]

        st.subheader(result_item["original_file_name"])
        st.caption(f"원본 {original_w} x {original_h}px → 자르기 결과 {result_w} x {result_h}px")

        # 결과 이미지를 가운데 정렬 (width는 지정하지 않아 확대 시 원본 해상도 유지)
        left_margin_column, image_column, right_margin_column = st.columns([1, 2, 1])
        with image_column:
            st.image(result_item["result_image"])

        result_file_name = build_cropped_file_name(result_item["original_file_name"])
        image_bytes = convert_image_to_bytes(result_item["result_image"], result_item["image_format"])
        st.download_button(
            label=f"'{result_file_name}' 다운로드",
            data=image_bytes,
            file_name=result_file_name,
            mime=f"image/{result_item['image_format'].lower()}",
            key=f"crop_download_{preview_index}_{result_item['original_file_name']}",
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
                "result_file_name": build_cropped_file_name(item["original_file_name"]),
                "result_image": item["result_image"],
                "image_format": item["image_format"],
            }
            for item in st.session_state.crop_processed_results
        ]
        zip_file_bytes = build_zip_file_from_named_results(named_results_for_zip)
        st.download_button(
            label=f"전체 결과 ZIP으로 다운로드 ({len(st.session_state.crop_processed_results)}건)",
            data=zip_file_bytes,
            file_name="자르기_결과_전체.zip",
            mime="application/zip",
            type="primary",
        )
    except Exception as zip_error:
        st.error(f"ZIP 파일을 만드는 중 오류가 발생했습니다: {zip_error}")
        st.caption("개별 다운로드 버튼으로 파일을 하나씩 받아주세요.")
