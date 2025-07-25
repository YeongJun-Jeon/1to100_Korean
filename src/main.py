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
from src.config import Config # Import the Config class

if __name__ == "__main__":
    print("스크립트 실행 시작")

    config = Config() # Instantiate the Config class

    # --- Step 0: PDF to PNG Conversion (using pdf_processor.py) ---
    print("\n[0/4] PDF를 PNG 이미지로 변환...")
    pdf_processor_path = os.path.join(config.PROJECT_ROOT, "src", "pdf_processor.py")

    # Temporarily modify pdf_processor.py to point to raw_0725
    with open(pdf_processor_path, 'r', encoding='utf-8') as f:
        pdf_processor_content = f.read()

    modified_pdf_processor_content = pdf_processor_content.replace(
        "input_dir = os.path.join(project_root, 'data', 'raw')",
        "input_dir = os.path.join(project_root, 'data', 'raw_0725')"
    )

    with open(pdf_processor_path, 'w', encoding='utf-8') as f:
        f.write(modified_pdf_processor_content)

    # Run pdf_processor.py as a module
    subprocess.run([sys.executable, '-m', 'src.pdf_processor'], check=True)

    # Revert pdf_processor.py back to original
    with open(pdf_processor_path, 'w', encoding='utf-8') as f:
        f.write(pdf_processor_content)
    print("PDF to PNG conversion complete.")

    # --- Step 1: YOLOv8 Inference and Annotation JSON Generation ---
    print("\n[1/4] YOLOv8 추론 및 어노테이션 JSON 생성...")
    model = YOLO(config.YOLO_MODEL_PATH) # Use path from config

    all_image_annotations = []
    image_files = glob.glob(os.path.join(config.IMAGE_DIR, '**', '*.png'), recursive=True) + \
                  glob.glob(os.path.join(config.IMAGE_DIR, '**', '*.jpg'), recursive=True) + \
                  glob.glob(os.path.join(config.IMAGE_DIR, '**', '*.jpeg'), recursive=True)

    if not image_files:
        print(f"No image files found in {config.IMAGE_DIR}. Please ensure images are present.")
    else:
        print(f"Found {len(image_files)} images for inference.")
        for image_path in image_files:
            results = model(image_path, conf=0.3)

            image_annotations = {
                "image_path": image_path,
                "annotations": []
            }

            for r in results:
                # Save detected images for debugging
                im_bgr = r.plot()  # plot a BGR numpy array of predictions
                im_rgb = Image.fromarray(im_bgr[..., ::-1])  # convert to RGB PIL image
                output_dir_detected = config.INFERENCE_RESULTS_DIR
                os.makedirs(output_dir_detected, exist_ok=True)
                output_filename_detected = os.path.basename(image_path).replace(".png", "_detected.png")
                output_filepath_detected = os.path.join(output_dir_detected, output_filename_detected)
                im_rgb.save(output_filepath_detected)

                for *xyxy, conf, cls in r.boxes.data:
                    x_min, y_min, x_max, y_max = map(float, xyxy)
                    label = config.CLASS_NAMES.get(int(cls), "unknown")
                    annotation = {
                        "label": label,
                        "bbox": [x_min, y_min, x_max, y_max],
                        "text_content": "" # OCR would fill this
                    }
                    image_annotations["annotations"].append(annotation)

            all_image_annotations.append(image_annotations)

        with open(config.SAMPLE_ANNOTATIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_image_annotations, f, ensure_ascii=False, indent=4)

        print(f"All annotations saved to {config.SAMPLE_ANNOTATIONS_PATH}")

    # --- Step 2: Process Annotations and Group Logical Units ---
    print("\n[2/4] 어노테이션 처리 및 논리적 단위 그룹화...")
    logical_units = process_annotations_from_json(
        config.SAMPLE_ANNOTATIONS_PATH,
        config.CROPPED_COMPONENTS_DIR,
        config # Pass the config object
    )
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
            "margin": config.top_margin_pt, # Using TOP_MARGIN_PT as general margin for now
            "spacing_between_components": config.gutter_margin_pt,
            "header_y_position": config.header_height_pt,
            "header_line_width": 0.5,
            "two_column_layout": True,
            "column_line_width": 0.5,
            "image_scale_factor": config.SCALE_FACTOR,
            "start_question_number": 1,
            "question_number_font_size": 12,
            "question_number_offset_x": 10,
            "question_number_offset_y": 12
        }
    )
    
    print("\n모든 작업이 완료되었습니다.")
