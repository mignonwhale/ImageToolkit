"""
공통 유틸리티 모듈
- 처리 진행 상황 표시
- 한글 오류 메시지 관리
- 날짜 형식 통일 (YYYY-MM-DD)
"""

from datetime import datetime


# 지원하는 이미지 확장자 목록
SUPPORTED_IMAGE_EXTENSIONS = ["jpg", "jpeg", "png", "bmp", "webp"]


def get_today_date_string() -> str:
    """오늘 날짜를 YYYY-MM-DD 형식 문자열로 반환한다."""
    return datetime.now().strftime("%Y-%m-%d")


def is_supported_image_file(file_name: str) -> bool:
    """업로드된 파일이 지원하는 이미지 확장자인지 확인한다."""
    file_extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    return file_extension in SUPPORTED_IMAGE_EXTENSIONS


def build_error_message(original_file_name: str, error_detail: str) -> str:
    """사용자에게 보여줄 한글 오류 메시지를 생성한다."""
    return f"'{original_file_name}' 처리 중 오류가 발생했습니다: {error_detail}"


def build_error_message_from_exception(original_file_name: str, error: Exception) -> str:
    """
    발생한 예외의 종류를 분석하여, 사용자가 원인을 짐작할 수 있는 구체적인 한글 오류 메시지를 생성한다.

    Args:
        original_file_name: 처리 중 오류가 발생한 원본 파일명
        error: 처리 중 발생한 예외 객체

    Returns:
        사용자에게 보여줄 한글 오류 메시지
    """
    error_type_name = type(error).__name__

    if "UnidentifiedImage" in error_type_name:
        error_detail = "이미지 파일이 손상되었거나 지원하지 않는 형식입니다."
    elif isinstance(error, MemoryError):
        error_detail = "이미지 용량이 너무 커서 처리할 메모리가 부족합니다. 더 작은 이미지로 다시 시도해주세요."
    elif isinstance(error, (ConnectionError, TimeoutError)):
        error_detail = "AI 모델을 다운로드하는 중 네트워크 오류가 발생했습니다. 인터넷 연결을 확인해주세요."
    elif isinstance(error, OSError):
        error_detail = "파일을 읽는 중 오류가 발생했습니다. 파일이 손상되지 않았는지 확인해주세요."
    else:
        error_detail = str(error)

    return build_error_message(original_file_name, error_detail)


def build_progress_text(current_index: int, total_count: int, current_file_name: str) -> str:
    """처리 진행 상황 텍스트를 생성한다. 예: '3 / 10 처리 중... (파일명.jpg)'"""
    return f"{current_index} / {total_count} 처리 중... ({current_file_name})"


def build_result_file_name(original_file_name: str) -> str:
    """결과 파일명을 규칙에 맞게 생성한다. 예: 원본파일명_removed_YYYY-MM-DD.png"""
    base_name = original_file_name.rsplit(".", 1)[0] if "." in original_file_name else original_file_name
    today_date_string = get_today_date_string()
    return f"{base_name}_removed_{today_date_string}.png"


def build_resized_file_name(original_file_name: str, target_width: int, target_height: int) -> str:
    """
    크기 조정 결과 파일명을 규칙에 맞게 생성한다.
    예: 원본파일명_resized_1024x768_YYYY-MM-DD.png
    """
    base_name = original_file_name.rsplit(".", 1)[0] if "." in original_file_name else original_file_name
    extension = original_file_name.rsplit(".", 1)[-1].lower() if "." in original_file_name else "png"
    today_date_string = get_today_date_string()
    return f"{base_name}_resized_{target_width}x{target_height}_{today_date_string}.{extension}"
