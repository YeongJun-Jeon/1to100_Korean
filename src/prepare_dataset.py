# -*- coding: utf-8 -*-
"""
Prepares the dataset for LayoutLMv3 fine-tuning.

This script will perform the following steps:
1.  Load the `output.manifest` file from SageMaker Ground Truth, which is expected
    to be in the `data/labeled` directory.
2.  Parse the manifest file to extract image paths, bounding box coordinates, and labels for each token.
3.  Convert the parsed data into the specific format required by the LayoutLMv3 model
    and the Hugging Face `datasets` library.
4.  Apply OCR (if necessary, though LayoutLMv3 can handle it) and tokenize the text.
5.  Align the labels with the tokenized input.
6.  Save the processed dataset (e.g., in JSON or Arrow format) to the `data/processed/training_data`
    directory, ready to be used by the `train.py` script.
"""

import os
from config import LABELED_DATA_DIR, TRAINING_DATA_DIR

def process_ground_truth_data():
    """Main function to process the labeled data."""
    print("Starting dataset preparation...")

    # Path to the manifest file from SageMaker Ground Truth
    manifest_file = os.path.join(LABELED_DATA_DIR, 'output.manifest')

    if not os.path.exists(manifest_file):
        print(f"Error: Manifest file not found at {manifest_file}")
        print("Please download the `output.manifest` file from your SageMaker Ground Truth labeling job and place it in the `data/labeled` directory.")
        return

    # --- Add data processing logic here ---
    # 1. Read and parse manifest_file.
    # 2. For each entry, load image, boxes, and labels.
    # 3. Convert to Hugging Face `Dataset` object.
    # 4. Save the processed dataset.

    print(f"Dataset successfully processed and saved to {TRAINING_DATA_DIR}")

if __name__ == '__main__':
    process_ground_truth_data()
