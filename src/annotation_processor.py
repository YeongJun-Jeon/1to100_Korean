import os
import json
from PIL import Image, ImageDraw
from typing import List, Dict, Tuple, Any, Optional

# --- Configuration Constants ---
SCALE_FACTOR = 400 / 72
DEFAULT_B4_WIDTH_PT = 729 

# --- Type Aliases ---
Component = Dict[str, Any]
LogicalUnit = List[Component]
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
            cropped_img = img.crop(main_bbox)

            if mask_bboxes:
                draw = ImageDraw.Draw(cropped_img)
                for mask_bbox_relative in mask_bboxes:
                    draw.rectangle(mask_bbox_relative, fill="white")

            cropped_img.save(output_path)
    except Exception as e:
        print(f"오류: 이미지 처리 중 실패했습니다: {image_path}, {e}")


def process_annotations_from_json(json_file_path: str, base_output_dir: str) -> List[LogicalUnit]:
    """
    JSON 어노테이션을 읽어 컴포넌트 이미지를 만들고, 2단 구성을 감지하여 논리적 단위로 그룹화합니다.
    """
    with open(json_file_path, 'r', encoding='utf-8') as f:
        all_data = json.load(f)

    all_logical_units: List[LogicalUnit] = []

    for data in all_data:
        image_path = data["image_path"]
        annotations = data["annotations"]
        label_counts = {}
        
        try:
            with Image.open(image_path) as img:
                original_img_width, _ = img.size
                center_x = original_img_width / 2
        except Exception as e:
            print(f"경고: 이미지 크기를 가져올 수 없습니다. 기본 중앙 x 좌표 사용. {e}")
            center_x = DEFAULT_B4_WIDTH_PT * SCALE_FACTOR / 2

        left_column_annotations = []
        right_column_annotations = []
        standalone_components = []

        for anno in annotations:
            label = anno['label']
            if label == 'figure':
                continue
            
            bbox_center_x = (anno['bbox'][0] + anno['bbox'][2]) / 2
            
            if label in ['header', 'passage', 'question_block']:
                if bbox_center_x < center_x:
                    left_column_annotations.append(anno)
                else:
                    right_column_annotations.append(anno)
            else:
                standalone_components.append(anno)
        
        left_column_annotations.sort(key=lambda x: x['bbox'][1])
        right_column_annotations.sort(key=lambda x: x['bbox'][1])

        def _crop_and_create_component(label: str, bbox: Bbox, text_content: str, mask_bboxes: Optional[List[Bbox]] = None) -> Component:
            label_counts[label] = label_counts.get(label, 0) + 1
            output_dir = os.path.join(base_output_dir, label)
            os.makedirs(output_dir, exist_ok=True)

            original_image_basename = os.path.splitext(os.path.basename(image_path))[0]
            output_filename = f"{original_image_basename}_{label}_{label_counts[label]-1}.png"
            output_filepath = os.path.join(output_dir, output_filename)

            ### ★★★ 수정-1: 자르기(crop) 전에 bbox 좌표를 스케일링합니다. ★★★
            scaled_crop_bbox = tuple(c * SCALE_FACTOR for c in bbox)

            crop_and_mask_image(image_path, output_filepath, scaled_crop_bbox, mask_bboxes)
            
            return {"label": label, "image_path": output_filepath, "text_content": text_content, "scaled_bbox": scaled_crop_bbox}

        def process_column_annotations(column_annos: List[Dict[str, Any]]) -> List[LogicalUnit]:
            
            def _convert_problem_set_to_unit(problem_set: Dict[str, Any]) -> Optional[LogicalUnit]:
                if not problem_set: return None
                unit: LogicalUnit = []
                if problem_set.get('header'): unit.append(problem_set['header'])
                if problem_set.get('passage'): unit.append(problem_set['passage'])
                unit.extend(problem_set.get('question_blocks', []))
                return unit if unit else None

            column_logical_units: List[LogicalUnit] = []
            current_problem_set: Optional[Dict[str, Any]] = None
            
            for anno in column_annos:
                label = anno['label']
                text_content = anno.get('text_content', '')

                if label == 'header':
                    if current_problem_set:
                        final_unit = _convert_problem_set_to_unit(current_problem_set)
                        if final_unit: column_logical_units.append(final_unit)
                    component_data = _crop_and_create_component(label, anno['bbox'], text_content)
                    current_problem_set = {'header': component_data, 'passage': None, 'question_blocks': []}
                
                elif label == 'passage':
                    if not current_problem_set:
                        print(f"경고: Passage가 header 없이 발견되었습니다. 새 문제 세트를 생성합니다: {image_path}")
                        current_problem_set = {'header': None, 'passage': None, 'question_blocks': []}
                    component_data = _crop_and_create_component(label, anno['bbox'], text_content)
                    current_problem_set['passage'] = component_data

                elif label == 'question_block':
                    if not current_problem_set:
                        print(f"경고: Question block이 header/passage 없이 발견되었습니다. 새 문제 세트를 생성합니다: {image_path}")
                        current_problem_set = {'header': None, 'passage': None, 'question_blocks': []}
                    
                    mask_bboxes_relative = []
                    if 'children' in anno:
                        for child in anno['children']:
                            if child['label'] == "question_number":
                                original_parent_bbox = anno['bbox']
                                original_child_bbox = child['bbox']
                                
                                ### ★★★ 수정-2: 마스킹 상대 좌표도 동일하게 스케일링합니다. ★★★
                                mask_bboxes_relative.append((
                                    (original_child_bbox[0] - original_parent_bbox[0]) * SCALE_FACTOR,
                                    (original_child_bbox[1] - original_parent_bbox[1]) * SCALE_FACTOR,
                                    (original_child_bbox[2] - original_parent_bbox[0]) * SCALE_FACTOR,
                                    (original_child_bbox[3] - original_parent_bbox[1]) * SCALE_FACTOR
                                ))
                    qb_component = _crop_and_create_component(label, anno['bbox'], text_content, mask_bboxes_relative)
                    current_problem_set['question_blocks'].append(qb_component)

            if current_problem_set:
                final_unit = _convert_problem_set_to_unit(current_problem_set)
                if final_unit: column_logical_units.append(final_unit)
            
            return column_logical_units

        left_logical_units = process_column_annotations(left_column_annotations)
        right_logical_units = process_column_annotations(right_column_annotations)

        page_all_logical_units = left_logical_units + right_logical_units

        for anno in standalone_components:
            standalone_unit = [_crop_and_create_component(anno['label'], anno['bbox'], anno.get('text_content', ''))]
            page_all_logical_units.append(standalone_unit)
        
        all_logical_units.extend(page_all_logical_units)

    return all_logical_units