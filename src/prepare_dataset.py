import os
import json
import shutil
import re
import sys
import urllib.parse

# Define paths
MANIFEST_FILE = "C:/Users/CUBOX/1to100/output.manifest"
TRAINING_DATA_ROOT = "C:/Users/CUBOX/1to100/data/processed/training_data"
IMAGES_DIR = os.path.join(TRAINING_DATA_ROOT, "images")
LABELS_DIR = os.path.join(TRAINING_DATA_ROOT, "labels")
SOURCE_IMAGES_DIR = "C:/Users/CUBOX/1to100/data/processed/images"

def convert_bbox_to_yolo(img_width, img_height, box_left, box_top, box_width, box_height):
    # Convert to normalized YOLO format (center_x, center_y, width, height)
    center_x = (box_left + box_width / 2) / img_width
    center_y = (box_top + box_height / 2) / img_height
    norm_width = box_width / img_width
    norm_height = box_height / img_height
    return center_x, center_y, norm_width, norm_height

def prepare_yolo_dataset():
    print("Starting YOLO dataset preparation...")

    # Create directories if they don't exist
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

    if not os.path.exists(MANIFEST_FILE):
        print(f"Error: Manifest file not found at {MANIFEST_FILE}")
        print("Please ensure `output.manifest` is in the project root directory.")
        return

    processed_count = 0
    with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())

                s3_ref = data['source-ref']
                image_filename_s3 = urllib.parse.unquote(os.path.basename(s3_ref))

                # Correct page number format: page_00 -> page_1, page_01 -> page_2, etc.
                # This regex handles both _page_XX.png and _page_X.png
                match = re.search(r'_page_(\d+)\.png$', image_filename_s3)
                if match:
                    page_num_str = match.group(1)
                    page_num_int = int(page_num_str)
                    corrected_page_num = page_num_int + 1
                    # Replace the original page number with the corrected one
                    # Ensure leading zeros are removed if the original was _page_0X
                    image_filename = image_filename_s3.replace(
                        f'_page_{page_num_str}.png',
                        f'_page_{corrected_page_num}.png'
                    )
                else:
                    image_filename = image_filename_s3 # No change if pattern not found

                # Encode and decode filename to handle potential encoding issues on Windows
                encoded_image_filename = image_filename.encode(sys.getfilesystemencoding()).decode('latin1')
                local_image_path = os.path.join(SOURCE_IMAGES_DIR, encoded_image_filename)

                # Check if the source image file exists before copying
                if not os.path.exists(local_image_path):
                    print(f"Warning: Source image not found: {local_image_path}. Skipping this entry.")
                    continue

                # Determine which annotation key to use
                annotations_key = 'suneung-korean-layout-detection-v2'
                if 'suneung-korean-layout-detection-v2-chain' in data:
                    annotations_key = 'suneung-korean-layout-detection-v2-chain'

                annotations = data[annotations_key]['annotations']

                # Prepare label file
                label_filename = os.path.splitext(image_filename)[0] + ".txt"
                label_filepath = os.path.join(LABELS_DIR, label_filename)

                with open(label_filepath, 'w', encoding='utf-8') as label_f:
                    # Get image dimensions from manifest (from the chosen annotation key)
                    img_size_info = data[annotations_key]['image_size'][0]
                    img_width = img_size_info['width']
                    img_height = img_size_info['height']

                    for ann in annotations:
                        class_id = ann['class_id']
                        box_top = ann['top']
                        box_left = ann['left']
                        box_width = ann['width']
                        box_height = ann['height']

                        center_x, center_y, norm_width, norm_height = convert_bbox_to_yolo(
                            img_width, img_height, box_left, box_top, box_width, box_height
                        )
                        label_f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {norm_width:.6f} {norm_height:.6f}\n")
                processed_count += 1

            except Exception as e:
                print(f"Error processing line: {line.strip()}. Error: {e}")
                continue

    print(f"Successfully processed {processed_count} images and generated YOLO format labels.")
    print(f"Images are in: {IMAGES_DIR}")
    print(f"Labels are in: {LABELS_DIR}")

if __name__ == '__main__':
    prepare_yolo_dataset()
