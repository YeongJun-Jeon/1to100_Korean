from PIL import Image, ImageDraw
from typing import List, Tuple, Optional

Bbox = Tuple[float, float, float, float]

def crop_and_mask_image(
    image_path: str,
    output_path: str,
    main_bbox: Bbox,
    mask_bboxes: Optional[List[Bbox]] = None
):
    """
    이미지에서 지정된 영역(main_bbox)을 잘라내고,
    선택적으로 특정 영역(mask_bboxes)들을 흰색으로 채워 저장합니다.
    """
    try:
        with Image.open(image_path) as img:
            # 자르기 연산은 스케일링된 좌표로 수행
            cropped_img = img.crop(main_bbox)

            if mask_bboxes:
                draw = ImageDraw.Draw(cropped_img)
                # 마스킹 좌표는 main_bbox 기준으로 변환된 상대 좌표여야 함
                for mask_bbox_relative in mask_bboxes:
                    # 상대 좌표를 사용하여 마스킹
                    draw.rectangle(mask_bbox_relative, fill="white")

            cropped_img.save(output_path)
    except Exception as e:
        print(f"오류: 이미지 처리 중 실패했습니다: {image_path}, {e}")
