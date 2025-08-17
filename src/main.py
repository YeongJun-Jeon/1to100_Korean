import os
import json
import glob
import subprocess
import sys
from PIL import Image
from typing import Dict, Any, List
from ultralytics import YOLO

from src.annotation_processor import process_annotations_from_json
from src.layout_organizer import shuffle_logical_units
from src.pdf_recombiner import recombine_pdf
from src.config import Config

if __name__ == "__main__":
    print("스크립트 실행 시작")

    config = Config()

    # --- Step 0: PDF to PNG Conversion (using pdf_processor.py) ---
    print("\n[0/4] PDF를 PNG 이미지로 변환...")
    pdf_processor_path = os.path.join(config.PROJECT_ROOT, "src", "pdf_processor.py")

    # (옵션) 입력 경로 스왑: 필요 시만 사용
    with open(pdf_processor_path, 'r', encoding='utf-8') as f:
        pdf_processor_content = f.read()

    modified_pdf_processor_content = pdf_processor_content.replace(
        "input_dir = os.path.join(project_root, 'data', 'raw')",
        "input_dir = os.path.join(project_root, 'data', 'raw_0725')"
    )

    with open(pdf_processor_path, 'w', encoding='utf-8') as f:
        f.write(modified_pdf_processor_content)

    subprocess.run([sys.executable, '-m', 'src.pdf_processor'], check=True)

    # revert
    with open(pdf_processor_path, 'w', encoding='utf-8') as f:
        f.write(pdf_processor_content)
    print("PDF to PNG conversion complete.")

    # --- Step 1: YOLOv8 Inference and Annotation JSON Generation ---
    print("\n[1/4] YOLOv8 추론 및 어노테이션 JSON 생성...")
    model = YOLO(config.YOLO_MODEL_PATH)

    all_image_annotations = []
    image_files = glob.glob(os.path.join(config.IMAGE_DIR, '**', '*.png'), recursive=True) + \
                  glob.glob(os.path.join(config.IMAGE_DIR, '**', '*.jpg'), recursive=True) + \
                  glob.glob(os.path.join(config.IMAGE_DIR, '**', '*.jpeg'), recursive=True)

    if not image_files:
        print(f"No image files found in {config.IMAGE_DIR}. Please ensure images are present.")
    else:
        print(f"Found {len(image_files)} images for inference.")
        for image_path in sorted(image_files):
            results = model(image_path, conf=0.3)

            image_annotations: Dict[str, Any] = {
                "image_path": image_path,
                "annotations": []
            }

            for r in results:
                # Save detected images for debugging
                im_bgr = r.plot()
                im_rgb = Image.fromarray(im_bgr[..., ::-1])
                output_dir_detected = config.INFERENCE_RESULTS_DIR
                os.makedirs(output_dir_detected, exist_ok=True)
                output_filename_detected = os.path.basename(image_path).rsplit('.',1)[0] + "_detected.png"
                output_filepath_detected = os.path.join(output_dir_detected, output_filename_detected)
                im_rgb.save(output_filepath_detected)

                for *xyxy, conf, cls in r.boxes.data:
                    x_min, y_min, x_max, y_max = map(float, xyxy)
                    label = config.CLASS_NAMES.get(int(cls), "unknown")
                    annotation = {
                        "label": label,
                        "bbox": [x_min, y_min, x_max, y_max],
                        "confidence": float(conf),
                        "text_content": ""
                    }
                    image_annotations["annotations"].append(annotation)

            all_image_annotations.append(image_annotations)

        with open(config.SAMPLE_ANNOTATIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_image_annotations, f, ensure_ascii=False, indent=2)

        print(f"All annotations saved to {config.SAMPLE_ANNOTATIONS_PATH}")

    # --- Step 2: Process Annotations and Group Logical Units ---
    print("\n[2/4] 어노테이션 처리 및 논리적 단위 그룹화...")
    logical_units = process_annotations_from_json(
        config.SAMPLE_ANNOTATIONS_PATH,
        config.CROPPED_COMPONENTS_DIR,
        config
    )
    # Where to find debug
    # Prefer config.PROCESSED_DATA_DIR/debug if exists else sibling of CROPPED_COMPONENTS_DIR
    pdf_dir = os.path.dirname(config.RECOMBINED_PDF_OUTPUT_PATH)
    debug_dir = os.path.join(pdf_dir, "debug")
    print(f"디버그 리포트/시각화 폴더: {os.path.abspath(debug_dir)}")
    print(f" - annotation_debug_report.json")
    print(f" - logical_units.json")
    print(f" - page_XXX_filtered.png ...")
    print(f"크롭 이미지 폴더: {os.path.abspath(config.CROPPED_COMPONENTS_DIR)}")
    print(f"-> {len(logical_units)}개의 논리적 단위를 생성했습니다.")

    # --- Step 3: Shuffle Logical Units ---
    print("\n[3/4] 논리적 단위 셔플하기...")
    shuffled_units = shuffle_logical_units(logical_units)
    print(f"-> {len(shuffled_units)}개의 유닛을 셔플했습니다.")

    # --- Step 4: Recombine PDF ---
    print("\n[4/4] PDF 파일로 재조합하기...")
    recombine_pdf(
        config.RECOMBINED_PDF_OUTPUT_PATH,
        shuffled_units,
        {
            "page_size": (config.DEFAULT_PAGE_WIDTH_PT, config.DEFAULT_PAGE_HEIGHT_PT),
            "margin": config.top_margin_pt,
            "spacing_between_components": config.gutter_margin_pt,
            "header_y_position": config.header_height_pt,
            "header_line_width": 0.5,
            "two_column_layout": True,
            "column_line_width": 0.5,
            "image_scale_factor": 1.0,  # 크롭은 픽셀 기반, 재조합에서 폭 맞춰 스케일
            "start_question_number": 1,
            "question_number_font_size": 12,
            "question_number_offset_x": 10,
            "question_number_offset_y": 12
        }
    )

    pdf_path = os.path.abspath(config.RECOMBINED_PDF_OUTPUT_PATH)
    placement_json = os.path.splitext(pdf_path)[0] + "_placement.json"
    print("\n모든 작업이 완료되었습니다.")
    print(f"- 최종 PDF: {pdf_path}")
    print(f"- 배치 맵 JSON: {placement_json}")
