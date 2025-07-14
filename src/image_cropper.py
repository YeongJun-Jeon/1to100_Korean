import os
import glob
from PIL import Image

# Define paths
TRAINING_DATA_ROOT = "C:/Users/CUBOX/1to100/data/processed/training_data"
IMAGES_DIR = os.path.join(TRAINING_DATA_ROOT, "images")
LABELS_DIR = os.path.join(TRAINING_DATA_ROOT, "labels")
CROPPED_IMAGES_ROOT = "C:/Users/CUBOX/1to100/data/processed/cropped_images"

# Class names (must match yolo_data.yaml)
CLASS_NAMES = {
    0: 'header',
    1: 'passage',
    2: 'question_block',
    3: 'question_number',
    4: 'figure',
    5: 'footer'
}

def convert_yolo_to_pixels(img_width, img_height, center_x, center_y, norm_width, norm_height):
    # Convert normalized YOLO format to pixel coordinates (x_min, y_min, x_max, y_max)
    x_min = int((center_x - norm_width / 2) * img_width)
    y_min = int((center_y - norm_height / 2) * img_height)
    x_max = int((center_x + norm_width / 2) * img_width)
    y_max = int((center_y + norm_height / 2) * img_height)
    return x_min, y_min, x_max, y_max

def crop_images_from_yolo_labels():
    print("Starting image cropping from YOLO labels...")

    # Create class-specific subdirectories in CROPPED_IMAGES_ROOT
    for class_name in CLASS_NAMES.values():
        os.makedirs(os.path.join(CROPPED_IMAGES_ROOT, class_name), exist_ok=True)

    image_files = glob.glob(os.path.join(IMAGES_DIR, '**', '*.png'), recursive=True) # Assuming all are PNGs

    if not image_files:
        print(f"No images found in {IMAGES_DIR}. Please ensure images are present.")
        return

    processed_count = 0
    for image_path in image_files:
        try:
            base_name = os.path.basename(image_path)
            image_name_without_ext = os.path.splitext(base_name)[0]
            label_path = os.path.join(LABELS_DIR, image_name_without_ext + ".txt")

            if not os.path.exists(label_path):
                print(f"Warning: Label file not found for {base_name}. Skipping.")
                continue

            with Image.open(image_path) as img:
                img_width, img_height = img.size

                with open(label_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f):
                        parts = line.strip().split()
                        if len(parts) != 5:
                            print(f"Warning: Invalid line in label file {label_path} (line {line_num + 1}). Skipping.")
                            continue

                        class_id = int(parts[0])
                        center_x, center_y, norm_width, norm_height = map(float, parts[1:])

                        x_min, y_min, x_max, y_max = convert_yolo_to_pixels(
                            img_width, img_height, center_x, center_y, norm_width, norm_height
                        )

                        # Ensure coordinates are within image bounds
                        x_min = max(0, x_min)
                        y_min = max(0, y_min)
                        x_max = min(img_width, x_max)
                        y_max = min(img_height, y_max)

                        cropped_image = img.crop((x_min, y_min, x_max, y_max))

                        class_name = CLASS_NAMES.get(class_id, f"unknown_class_{class_id}")
                        output_dir = os.path.join(CROPPED_IMAGES_ROOT, class_name)
                        os.makedirs(output_dir, exist_ok=True) # Ensure class directory exists

                        output_image_path = os.path.join(output_dir, f"{image_name_without_ext}_obj_{line_num}.png")
                        cropped_image.save(output_image_path)

            processed_count += 1

        except Exception as e:
            print(f"Error processing image {image_path}. Error: {e}")
            continue

    print(f"\nSuccessfully cropped objects from {processed_count} images.")
    print(f"Cropped images are in: {CROPPED_IMAGES_ROOT}")

if __name__ == '__main__':
    crop_images_from_yolo_labels()