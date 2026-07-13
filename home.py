"""
이미지 도구 모음 - 홈 화면 내용
왼쪽 사이드바에서 원하는 도구를 선택해서 사용할 수 있다.
"""

import streamlit as st

st.set_page_config(page_title="이미지 도구 모음", layout="wide")

st.title("🧰 이미지 도구 모음")
st.write("왼쪽 사이드바에서 사용할 도구를 선택해주세요.")

st.divider()

st.subheader("🪄 이미지 편집 (통합)")
st.write("업로드 후 버튼 한 번으로 배경 제거 → 여백 제거 → 긴 변 3000px 리사이즈 → 300dpi 적용까지 한 번에 처리합니다.")
st.page_link("app_pages/4_edit_image.py", label="이미지 편집 열기", icon="➡️")

st.divider()

tool_column1, tool_column2, tool_column3 = st.columns(3)

with tool_column1:
    st.subheader("🖼️ 이미지 배경 제거")
    st.write("여러 장의 이미지에서 배경을 자동으로 제거하고, 투명 배경 PNG로 다운로드합니다.")
    st.page_link("app_pages/1_background_removal.py", label="배경 제거 도구 열기", icon="➡️")

with tool_column2:
    st.subheader("📐 이미지 크기 조정")
    st.write("여러 장의 이미지를 원하는 픽셀 또는 비율로 한 번에 크기 조정합니다.")
    st.page_link("app_pages/2_image_resize.py", label="크기 조정 도구 열기", icon="➡️")

with tool_column3:
    st.subheader("✂️ 여백/영역 자르기")
    st.write("투명 배경은 요소 영역을 자동 제안하고, 일반 이미지는 직접 영역을 지정해 자릅니다.")
    st.page_link("app_pages/3_crop_image.py", label="자르기 도구 열기", icon="➡️")
