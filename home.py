"""
이미지 도구 모음 - 홈 화면 내용
왼쪽 사이드바에서 원하는 도구를 선택해서 사용할 수 있다.
"""

import streamlit as st

st.set_page_config(page_title="이미지 도구 모음", layout="wide")

st.title("🧰 이미지 도구 모음")
st.write("왼쪽 사이드바에서 사용할 도구를 선택해주세요.")

st.divider()

tool_column1, tool_column2 = st.columns(2)

with tool_column1:
    st.subheader("🖼️ 이미지 배경 제거")
    st.write("여러 장의 이미지에서 배경을 자동으로 제거하고, 투명 배경 PNG로 다운로드합니다.")
    st.page_link("app_pages/1_background_removal.py", label="배경 제거 도구 열기", icon="➡️")

with tool_column2:
    st.subheader("📐 이미지 크기 조정")
    st.write("여러 장의 이미지를 원하는 픽셀 또는 비율로 한 번에 크기 조정합니다.")
    st.page_link("app_pages/2_image_resize.py", label="크기 조정 도구 열기", icon="➡️")
