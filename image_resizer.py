"""
이미지 크기 조정 처리 모듈
- 픽셀 지정 또는 비율(퍼센트) 지정으로 이미지 크기를 계산하고 변경한다
- Pillow의 LANCZOS 리샘플링 필터를 사용해 확대/축소 시 화질 저하를 최소화한다
"""

from PIL import Image

# 지원하는 사전 정의 비율 목록 (가로:세로)
PREDEFINED_ASPECT_RATIOS = {
    "1:1 (정사각형)": (1, 1),
    "4:3": (4, 3),
    "3:2": (3, 2),
    "16:9": (16, 9),
    "9:16 (세로)": (9, 16),
}


def calculate_dimensions_by_pixels(
    original_width: int,
    original_height: int,
    target_width: int,
    target_height: int,
    keep_aspect_ratio: bool,
) -> tuple:
    """
    픽셀 값을 기준으로 최종 가로/세로 크기를 계산한다.

    Args:
        original_width: 원본 이미지 가로 픽셀
        original_height: 원본 이미지 세로 픽셀
        target_width: 사용자가 입력한 목표 가로 픽셀
        target_height: 사용자가 입력한 목표 세로 픽셀
        keep_aspect_ratio: True이면 가로 값을 기준으로 세로를 원본 비율에 맞춰 자동 계산한다

    Returns:
        (계산된 가로 픽셀, 계산된 세로 픽셀) 튜플

    Raises:
        ValueError: 픽셀 값이 1보다 작은 경우
    """
    if target_width < 1 or (not keep_aspect_ratio and target_height < 1):
        raise ValueError("가로/세로 픽셀 값은 1 이상이어야 합니다.")

    if keep_aspect_ratio:
        aspect_ratio = original_height / original_width
        calculated_height = max(1, round(target_width * aspect_ratio))
        return target_width, calculated_height

    return target_width, target_height


def calculate_dimensions_by_percentage(
    original_width: int,
    original_height: int,
    scale_percentage: float,
) -> tuple:
    """
    비율(%) 기준으로 최종 가로/세로 크기를 계산한다.

    Args:
        original_width: 원본 이미지 가로 픽셀
        original_height: 원본 이미지 세로 픽셀
        scale_percentage: 원본 대비 조정할 비율(%). 예: 50이면 원본의 절반 크기

    Returns:
        (계산된 가로 픽셀, 계산된 세로 픽셀) 튜플

    Raises:
        ValueError: 비율 값이 0 이하인 경우
    """
    if scale_percentage <= 0:
        raise ValueError("비율은 0보다 커야 합니다.")

    scale_factor = scale_percentage / 100
    calculated_width = max(1, round(original_width * scale_factor))
    calculated_height = max(1, round(original_height * scale_factor))
    return calculated_width, calculated_height


def calculate_dimensions_by_aspect_ratio(
    original_width: int,
    original_height: int,
    ratio_width: int,
    ratio_height: int,
) -> tuple:
    """
    지정된 가로:세로 비율에 맞춰, 원본 가로 픽셀을 기준으로 크기를 계산한다.

    Args:
        original_width: 원본 이미지 가로 픽셀
        original_height: 원본 이미지 세로 픽셀
        ratio_width: 목표 비율의 가로 값 (예: 16:9의 16)
        ratio_height: 목표 비율의 세로 값 (예: 16:9의 9)

    Returns:
        (계산된 가로 픽셀, 계산된 세로 픽셀) 튜플
    """
    calculated_height = max(1, round(original_width * (ratio_height / ratio_width)))
    return original_width, calculated_height


def resize_image(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    이미지를 지정된 크기로 조정한다. Pillow의 LANCZOS 필터를 사용해 화질 저하를 최소화한다.

    Args:
        image: 크기를 조정할 PIL Image 객체
        target_width: 목표 가로 픽셀 (1 이상)
        target_height: 목표 세로 픽셀 (1 이상)

    Returns:
        크기가 조정된 PIL Image 객체

    Raises:
        ValueError: 목표 픽셀 값이 1보다 작은 경우
    """
    if target_width < 1 or target_height < 1:
        raise ValueError("가로/세로 픽셀 값은 1 이상이어야 합니다.")

    return image.resize((target_width, target_height), Image.LANCZOS)
