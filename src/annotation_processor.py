import os
import json
from typing import List, Dict, Tuple, Any, Optional

from .image_cropper import crop_and_mask_image, Bbox
from .config import SCALE_FACTOR

# --- Type Aliases ---
Component = Dict[str, Any]
LogicalUnit = List[Component]

def process_annotations_from_json(json_file_path: str, base_output_dir: str) -> List[LogicalUnit]:
    """
    여러 페이지에 걸친 JSON 어노테이션을 읽어 하나의 연속된 흐름으로 처리하고,
    페이지 경계를 넘어가는 문제 세트도 올바르게 그룹화합니다.
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        all_data = json.load(f)

    # --- 1. 모든 페이지의 어노테이션을 하나의 리스트로 통합 ---
    all_annotations_flat = []
    for page_index, page_data in enumerate(all_data):
        image_path = page_data["image_path"]
        for anno in page_data["annotations"]:
            anno['original_image_path'] = image_path
            anno['page_index'] = page_index
            all_annotations_flat.append(anno)

    # --- 2. 페이지 번호 -> y좌표 순으로 전체 어노테이션을 정렬 ---
    all_annotations_flat.sort(key=lambda x: (x['page_index'], x['bbox'][1]))

    label_counts = {}

    def _crop_and_create_component(anno_data: Dict[str, Any], mask_bboxes_relative: Optional[List[Bbox]] = None) -> Component:
        label = anno_data['label']
        bbox = anno_data['bbox']
        text_content = anno_data.get('text_content', '')
        image_path = anno_data['original_image_path']

        label_counts[label] = label_counts.get(label, 0) + 1
        output_dir = os.path.join(base_output_dir, label)
        os.makedirs(output_dir, exist_ok=True)

        original_image_basename = os.path.splitext(os.path.basename(image_path))[0]
        output_filename = f"{original_image_basename}_{label}_{label_counts[label]-1}.png"
        output_filepath = os.path.join(output_dir, output_filename)

        # crop에 사용될 좌표는 스케일링
        scaled_crop_bbox = tuple(c * SCALE_FACTOR for c in bbox)

        # crop_and_mask_image 함수는 이미 스케일링된 main_bbox와, 그에 대한 상대적인 mask_bboxes를 기대함
        crop_and_mask_image(image_path, output_filepath, scaled_crop_bbox, mask_bboxes_relative)

        return {"label": label, "image_path": output_filepath, "text_content": text_content}

    # --- 3. 통합되고 정렬된 단일 리스트를 순회하며 그룹핑 ---
    logical_units: List[LogicalUnit] = []
    current_unit: LogicalUnit = []

    for anno in all_annotations_flat:
        label = anno['label']
        if label == 'figure':
            continue

        is_standalone_component = label not in ['header', 'passage', 'question_block']

        if label == 'header' or is_standalone_component:
            if current_unit:
                logical_units.append(current_unit)
            current_unit = []

        if label == "question_block":
            mask_bboxes_relative = []
            if 'children' in anno:
                for child in anno['children']:
                    if child['label'] == "question_number":
                        parent_bbox = anno['bbox']
                        child_bbox = child['bbox']
                        # 마스크 좌표를 부모 bbox에 대한 상대 좌표로 변환 (스케일링은 crop_and_mask_image 내부에서 처리되지 않음)
                        # crop_and_mask_image에 전달하기 전에 스케일링이 필요함.
                        # 하지만, crop_and_mask_image는 이미 잘린 이미지에 그리므로, 상대좌표만 넘겨주면 됨.
                        # 중요한 점: crop_and_mask_image에 넘겨주는 mask_bboxes는 *잘릴 이미지* 기준의 상대좌표여야 함.
                        # 그리고 그 좌표값들은 스케일링이 되어있어야 함.
                        
                        # 1. 부모 대비 상대 좌표 계산
                        relative_mask_bbox_unscaled = (
                            child_bbox[0] - parent_bbox[0], child_bbox[1] - parent_bbox[1],
                            child_bbox[2] - parent_bbox[0], child_bbox[3] - parent_bbox[1]
                        )
                        # 2. 상대 좌표 스케일링
                        scaled_relative_mask_bbox = tuple(c * SCALE_FACTOR for c in relative_mask_bbox_unscaled)
                        mask_bboxes_relative.append(scaled_relative_mask_bbox)

            qb_component = _crop_and_create_component(anno, mask_bboxes_relative)
            current_unit.append(qb_component)

        elif label in ['header', 'passage']:
            component = _crop_and_create_component(anno)
            current_unit.append(component)

        else: # footer 등 독립적인 컴포넌트
            standalone_unit = [_crop_and_create_component(anno)]
            logical_units.append(standalone_unit)

    if current_unit:
        logical_units.append(current_unit)

    return logical_units
