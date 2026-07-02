"""
파일 처리 모듈
- 배경 제거된 이미지를 메모리 버퍼(bytes)로 변환
- 다건 결과물을 ZIP 파일로 일괄 압축
"""

import io
import zipfile
from PIL import Image

from utils import build_result_file_name


def convert_image_to_png_bytes(image: Image.Image) -> bytes:
    """PIL Image 객체를 PNG 형식의 바이트 데이터로 변환한다. (다운로드 버튼에 사용)"""
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    return image_buffer.getvalue()


def build_zip_file_from_results(processed_results: list) -> bytes:
    """
    처리된 결과 목록을 하나의 ZIP 파일(bytes)로 압축한다.

    동일한 이름의 원본 파일이 여러 번 업로드되어 결과 파일명이 겹치는 경우,
    파일이 서로 덮어써지지 않도록 번호를 붙여 구분한다.

    Args:
        processed_results: [{"original_file_name": str, "result_image": PIL.Image}, ...] 형태의 리스트

    Returns:
        ZIP 파일의 바이트 데이터
    """
    zip_buffer = io.BytesIO()
    used_file_names = set()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for result_item in processed_results:
            original_file_name = result_item["original_file_name"]
            result_image = result_item["result_image"]

            result_file_name = build_result_file_name(original_file_name)

            # 결과 파일명이 이미 사용 중이면 번호를 붙여 겹치지 않게 한다
            if result_file_name in used_file_names:
                base_name, extension = result_file_name.rsplit(".", 1)
                duplicate_count = 1
                candidate_name = f"{base_name}_{duplicate_count}.{extension}"
                while candidate_name in used_file_names:
                    duplicate_count += 1
                    candidate_name = f"{base_name}_{duplicate_count}.{extension}"
                result_file_name = candidate_name

            used_file_names.add(result_file_name)

            image_bytes = convert_image_to_png_bytes(result_image)
            zip_file.writestr(result_file_name, image_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
