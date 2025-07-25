import os
import json
from typing import List, Dict, Tuple, Any, Optional
from PIL import Image, ImageDraw

from .image_cropper import crop_and_mask_image, Bbox
from .config import Config # Import Config class

# --- Type Aliases ---
Component = Dict[str, Any]
LogicalUnit = List[Component]

def process_annotations_from_json(json_file_path: str, base_output_dir: str, config: Config) -> List[LogicalUnit]:
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

    # --- 2. 페이지 번호 -> 컬럼 -> y좌표 순으로 전체 어노테이션을 정렬 ---
    # 컬럼 식별자: 페이지 너비의 절반을 기준으로 왼쪽(0) 또는 오른쪽(1)
    page_half_width = config.DEFAULT_PAGE_WIDTH_PT / 2 # Use config for page width

    all_annotations_flat.sort(key=lambda x: (
        x['page_index'],
        0 if x['bbox'][0] < page_half_width else 1, # Column identifier (0 for left, 1 for right)
        x['bbox'][1] # Y-coordinate
    ))

    label_counts = {}

    def _crop_and_create_component(anno_data: Dict[str, Any], config: Config, mask_bboxes_relative: Optional[List[Bbox]] = None) -> Component:
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

        # Create debug directory
        debug_output_dir = os.path.join(base_output_dir, "..", "debug_crops")
        os.makedirs(debug_output_dir, exist_ok=True)

        # Load the original image
        original_image = Image.open(image_path)

        # crop에 사용될 좌표는 스케일링 및 반올림하여 정수 변환
        scaled_crop_bbox = tuple(round(c * config.SCALE_FACTOR) for c in bbox)

        print(f"Debug: Label={label}, Original Bbox={bbox}, Scaled Bbox={scaled_crop_bbox}")

        # Crop the image
        cropped_image = crop_and_mask_image(original_image, scaled_crop_bbox)

        # Save pre-mask image for debugging
        debug_pre_mask_filepath = os.path.join(debug_output_dir, f"{original_image_basename}_{label}_{label_counts[label]-1}_pre_mask.png")
        cropped_image.save(debug_pre_mask_filepath)
        print(f"Debug: Pre-mask image saved to {debug_pre_mask_filepath}")

        # Apply masks if provided (for question_number in question_block)
        if mask_bboxes_relative and label == "question_block":
            print(f"Debug: Applying mask for {label}, Mask Bboxes={mask_bboxes_relative}")
            draw = ImageDraw.Draw(cropped_image)
            for mask_bbox in mask_bboxes_relative:
                # mask_bbox is relative to the cropped_image, and already scaled
                draw.rectangle(mask_bbox, fill="white")

            # Save post-mask image for debugging
            debug_post_mask_filepath = os.path.join(debug_output_dir, f"{original_image_basename}_{label}_{label_counts[label]-1}_post_mask.png")
            cropped_image.save(debug_post_mask_filepath)
            print(f"Debug: Post-mask image saved to {debug_post_mask_filepath}")

        # Save the final cropped image
        cropped_image.save(output_filepath)

        return {"label": label, "image_path": output_filepath, "text_content": text_content}

    # --- 3. 통합되고 정렬된 단일 리스트를 순회하며 그룹핑 ---
    logical_units: List[LogicalUnit] = []
    current_unit: LogicalUnit = []

    for anno in all_annotations_flat:
        label = anno['label']
        if label == 'figure':
            continue

        # Determine if a new logical unit should start
        start_new_unit = False

        if label == "header":
            start_new_unit = True
        elif label == "passage":
            # If current_unit is empty or the last component was a question_block, start new unit
            if not current_unit or (current_unit and current_unit[-1]['label'] == "question_block"):
                start_new_unit = True
        elif label == "question_block":
            # If current_unit is empty, or the last component was not a passage or question_block
            if not current_unit or (current_unit and current_unit[-1]['label'] not in ["passage", "question_block"]):
                start_new_unit = True

        if start_new_unit and current_unit:
            logical_units.append(current_unit)
            current_unit = []

        # Create the component with cropped image and add to current unit
        # For question_block, pass children for masking
        if label == "question_block":
            mask_bboxes_relative = []
            if 'children' in anno:
                for child in anno['children']:
                    if child['label'] == "question_number":
                        parent_bbox = anno['bbox']
                        child_bbox = child['bbox']
                        relative_mask_bbox_unscaled = (
                            child_bbox[0] - parent_bbox[0], child_bbox[1] - parent_bbox[1],
                            child_bbox[2] - parent_bbox[0], child_bbox[3] - parent_bbox[1]
                        )
                        scaled_relative_mask_bbox = tuple(round(c * config.SCALE_FACTOR) for c in relative_mask_bbox_unscaled)
                        mask_bboxes_relative.append(scaled_relative_mask_bbox)
            qb_component = _crop_and_create_component(anno, config, mask_bboxes_relative)
            current_unit.append(qb_component)
        else:
            component = _crop_and_create_component(anno, config)
            current_unit.append(component)

    if current_unit:
        logical_units.append(current_unit)

    return logical_units
