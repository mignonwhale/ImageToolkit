"""
파일 처리 모듈
- 이미지를 메모리 버퍼(bytes)로 변환
- 다건 결과물을 ZIP 파일로 일괄 압축
- 배경 제거 결과와 크기 조정 결과 모두에서 공통으로 사용한다
"""

import io
import zipfile
from PIL import Image

from utils import build_result_file_name


def convert_image_to_png_bytes(image: Image.Image) -> bytes:
    """PIL Image 객체를 PNG 형식의 바이트 데이터로 변환한다. (배경 제거 결과처럼 투명도가 필요한 경우 사용)"""
    image_buffer = io.BytesIO()
    image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    return image_buffer.getvalue()


def convert_image_to_bytes(image: Image.Image, image_format: str) -> bytes:
    """
    PIL Image 객체를 지정된 포맷의 바이트 데이터로 변환한다. (크기 조정 결과처럼 원본 포맷을 유지해야 하는 경우 사용)

    Args:
        image: 변환할 PIL Image 객체
        image_format: 저장할 이미지 포맷 (예: "PNG", "JPEG", "BMP", "WEBP")

    Returns:
        지정된 포맷의 바이트 데이터
    """
    normalized_format = (image_format or "PNG").upper()
    if normalized_format == "JPG":
        normalized_format = "JPEG"

    save_target_image = image
    save_kwargs = {}
    if normalized_format == "JPEG":
        # JPEG은 투명도(알파 채널)를 지원하지 않으므로 RGB로 변환한다
        if save_target_image.mode in ("RGBA", "P", "LA"):
            save_target_image = save_target_image.convert("RGB")
        save_kwargs["quality"] = 95

    image_buffer = io.BytesIO()
    save_target_image.save(image_buffer, format=normalized_format, **save_kwargs)
    image_buffer.seek(0)
    return image_buffer.getvalue()


def deduplicate_file_name(candidate_file_name: str, used_file_names: set) -> str:
    """이미 사용 중인 파일명이면 번호를 붙여 겹치지 않는 이름을 반환한다."""
    if candidate_file_name not in used_file_names:
        return candidate_file_name

    base_name, extension = candidate_file_name.rsplit(".", 1)
    duplicate_count = 1
    new_candidate = f"{base_name}_{duplicate_count}.{extension}"
    while new_candidate in used_file_names:
        duplicate_count += 1
        new_candidate = f"{base_name}_{duplicate_count}.{extension}"
    return new_candidate


def build_zip_file_from_results(processed_results: list) -> bytes:
    """
    배경 제거 결과 목록을 하나의 ZIP 파일(bytes)로 압축한다. (파일명 규칙: build_result_file_name)

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
            result_file_name = build_result_file_name(result_item["original_file_name"])
            result_file_name = deduplicate_file_name(result_file_name, used_file_names)
            used_file_names.add(result_file_name)

            image_bytes = convert_image_to_png_bytes(result_item["result_image"])
            zip_file.writestr(result_file_name, image_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def build_zip_file_from_named_results(named_results: list) -> bytes:
    """
    이미 파일명이 정해진 결과 목록을 하나의 ZIP 파일(bytes)로 압축한다. (크기 조정 결과 등 범용으로 사용)

    동일한 파일명이 겹치는 경우, 파일이 서로 덮어써지지 않도록 번호를 붙여 구분한다.

    Args:
        named_results: [{"result_file_name": str, "result_image": PIL.Image, "image_format": str}, ...] 형태의 리스트

    Returns:
        ZIP 파일의 바이트 데이터
    """
    zip_buffer = io.BytesIO()
    used_file_names = set()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for result_item in named_results:
            result_file_name = deduplicate_file_name(result_item["result_file_name"], used_file_names)
            used_file_names.add(result_file_name)

            image_bytes = convert_image_to_bytes(
                result_item["result_image"], result_item.get("image_format", "PNG")
            )
            zip_file.writestr(result_file_name, image_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
