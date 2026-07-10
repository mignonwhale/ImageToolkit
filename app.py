"""
이미지 도구 모음 - 진입점(라우터)
st.navigation으로 각 도구 페이지를 등록하고, 사이드바 메뉴와 페이지 전환을 관리한다.

페이지 스크립트 파일명은 영문으로 통일한다 (한글 파일명은 다운로드/전송 과정에서
유니코드 정규화(NFC/NFD) 방식이 달라져 "파일을 찾을 수 없음" 오류를 유발할 수 있기 때문).
사이드바에 표시되는 메뉴 이름은 title 옵션으로 한글을 그대로 사용한다.
"""

import streamlit as st

home_page = st.Page("home.py", title="홈", icon="🧰", default=True)
background_removal_page = st.Page("app_pages/1_background_removal.py", title="배경 제거", icon="🖼️")
image_resize_page = st.Page("app_pages/2_image_resize.py", title="크기 조정", icon="📐")
crop_image_page = st.Page("app_pages/3_crop_image.py", title="자르기", icon="✂️")

selected_page = st.navigation([home_page, background_removal_page, image_resize_page, crop_image_page])
selected_page.run()
