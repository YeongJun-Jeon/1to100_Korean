# -*- coding: utf-8 -*-
"""
Configuration file for the AI project.

This file centralizes settings like file paths, model hyperparameters,
and AWS configurations to make the project more modular and easier to manage.
"""

import os

# --- Project Root ---
# Defines the absolute path to the project root for consistent pathing.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# --- Data Paths ---
# Paths to various data directories.
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
LABELED_DATA_DIR = os.path.join(DATA_DIR, 'labeled') # For output.manifest
TRAINING_DATA_DIR = os.path.join(PROCESSED_DATA_DIR, 'training_data') # For final dataset
IMAGE_DIR = os.path.join(PROCESSED_DATA_DIR, 'images') # PNGs from PDFs

# --- AWS S3 Configuration ---
# S3 bucket and paths for data storage and model artifacts.
S3_BUCKET = '1to100-ai-data-jykim-250626' # Example bucket name
S3_RAW_IMAGES_PATH = 'raw-images/2_image_outputs/' # Raw images uploaded
S3_LABELED_DATA_PATH = 'sagemaker/ground-truth-labels/' # Labeled data from Ground Truth
S3_MODEL_OUTPUT_PATH = 'sagemaker/training-output/' # Trained model artifacts

# --- Model & Training Configuration ---
# Hyperparameters and settings for the LayoutLMv3 model.
MODEL_NAME = 'microsoft/layoutlmv3-base'

# Classes defined in SageMaker Ground Truth
CLASSES = ['header', 'passage', 'question_block', 'question_number', 'figure', 'footer']
ID2LABEL = {k: v for k, v in enumerate(CLASSES)}
LABEL2ID = {v: k for k, v in enumerate(CLASSES)}

# Training hyperparameters
MAX_LENGTH = 512
BATCH_SIZE = 8
LEARNING_RATE = 5e-5
NUM_EPOCHS = 5

# --- Post-processing ---
DPI = 300 # Resolution for image processing
