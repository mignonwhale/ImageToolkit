"""
여백/영역 자르기 처리 모듈
- 투명 배경(알파 채널)이 실제로 존재하는 이미지: 요소를 감싸는 최소 영역을 자동 계산한다
- 투명 배경이 없는 이미지: 사용자가 지정한 좌표로 자른다
- 두 경우 모두, 실제로 자르기 전에 "이 영역을 자를 것"이라는 미리보기(점선 테두리)를 만들 수 있다
"""

from PIL import Image, ImageDraw


def has_meaningful_transparency(image: Image.Image) -> bool:
    """
    이미지에 알파 채널이 있고, 실제로 투명한(완전 불투명이 아닌) 픽셀이 하나라도 있는지 판별한다.

    알파 채널 자체는 있지만 전부 255(완전 불투명)인 PNG는 "배경이 있는 이미지"로 취급해야
    하므로, 단순히 모드(RGBA 등)만 보지 않고 실제 알파값 최솟값까지 확인한다.

    Args:
        image: 판별할 PIL Image 객체

    Returns:
        실제로 투명한 픽셀이 존재하면 True, 아니면 False
    """
    if image.mode not in ("RGBA", "LA", "PA"):
        return False

    alpha_channel = image.convert("RGBA").getchannel("A")
    min_alpha_value, _max_alpha_value = alpha_channel.getextrema()
    return min_alpha_value < 255


def compute_trim_bounding_box(image: Image.Image, alpha_threshold: int = 0) -> tuple | None:
    """
    알파값이 alpha_threshold를 초과하는 모든 픽셀을 포함하는 최소 사각형(bounding box)을 계산한다.

    요소의 일부라도 잘리는 것을 막기 위해, 기본값은 0으로 두어 아주 미세하게라도
    불투명한(alpha > 0) 픽셀까지 전부 포함시킨다.

    Args:
        image: 대상 PIL Image 객체 (내부적으로 RGBA로 변환하여 계산)
        alpha_threshold: 이 값을 초과하는 알파값을 가진 픽셀만 "요소"로 간주한다 (기본 0)

    Returns:
        (left, top, right, bottom) 형태의 튜플. 자를 대상이 전혀 없으면(완전 투명) None
    """
    rgba_image = image.convert("RGBA")
    alpha_channel = rgba_image.getchannel("A")

    if alpha_threshold > 0:
        # 임계값을 적용해야 하는 경우, 이진 마스크로 변환 후 bbox를 계산한다
        alpha_channel = alpha_channel.point(lambda value: 255 if value > alpha_threshold else 0)

    return alpha_channel.getbbox()


def crop_image_to_box(image: Image.Image, box: tuple) -> Image.Image:
    """
    지정된 좌표로 이미지를 자른다.

    Args:
        image: 자를 대상 PIL Image 객체
        box: (left, top, right, bottom) 형태의 좌표

    Returns:
        잘라낸 PIL Image 객체

    Raises:
        ValueError: 좌표가 이미지 범위를 벗어나거나, left>=right 혹은 top>=bottom인 경우
    """
    left, top, right, bottom = box
    image_width, image_height = image.size

    if left < 0 or top < 0 or right > image_width or bottom > image_height:
        raise ValueError("자르기 영역이 이미지 범위를 벗어났습니다.")
    if left >= right or top >= bottom:
        raise ValueError("자르기 영역이 올바르지 않습니다 (좌우 또는 상하 좌표를 확인해주세요).")

    return image.crop(box)


def build_crop_preview_overlay(image: Image.Image, box: tuple, outline_color=(255, 0, 0, 255)) -> Image.Image:
    """
    제안되었거나 사용자가 선택한 자르기 영역을 점선 테두리로 표시한 미리보기 이미지를 만든다.
    원본 이미지 픽셀 자체는 훼손하지 않고, 테두리만 그려진 새 이미지를 반환한다.

    Args:
        image: 원본 PIL Image 객체
        box: (left, top, right, bottom) 형태의 표시할 영역 좌표
        outline_color: 테두리 색상 (기본 빨간색)

    Returns:
        테두리가 그려진 미리보기용 PIL Image 객체 (RGBA)
    """
    preview_image = image.convert("RGBA").copy()
    draw_context = ImageDraw.Draw(preview_image)

    left, top, right, bottom = box
    dash_length = 10
    gap_length = 6

    # 점선 사각형을 4변 각각 그린다 (Pillow 기본 도형 함수는 점선을 지원하지 않으므로 직접 구현)
    def draw_dashed_horizontal_line(y_position, x_start, x_end):
        current_x = x_start
        while current_x < x_end:
            segment_end = min(current_x + dash_length, x_end)
            draw_context.line([(current_x, y_position), (segment_end, y_position)], fill=outline_color, width=3)
            current_x += dash_length + gap_length

    def draw_dashed_vertical_line(x_position, y_start, y_end):
        current_y = y_start
        while current_y < y_end:
            segment_end = min(current_y + dash_length, y_end)
            draw_context.line([(x_position, current_y), (x_position, segment_end)], fill=outline_color, width=3)
            current_y += dash_length + gap_length

    draw_dashed_horizontal_line(top, left, right)
    draw_dashed_horizontal_line(bottom, left, right)
    draw_dashed_vertical_line(left, top, bottom)
    draw_dashed_vertical_line(right, top, bottom)

    return preview_image
