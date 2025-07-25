# -*- coding: utf-8 -*-
"""
Image Cropping Utilities

This module provides functions for cropping and processing image components
based on bounding box annotations.
"""

import os
from PIL import Image
from typing import Tuple

# Bbox is defined as a tuple of four floats (x_min, y_min, x_max, y_max)
Bbox = Tuple[float, float, float, float]

def crop_and_mask_image(image: Image.Image, bbox: Bbox) -> Image.Image:
    """
    Crops the given PIL Image to the specified bounding box.
    The 'mask' functionality is not yet implemented.

    Args:
        image (Image.Image): The source PIL image.
        bbox (Bbox): A tuple representing the bounding box (x_min, y_min, x_max, y_max).

    Returns:
        Image.Image: The cropped PIL image.
    """
    # The crop method takes a 4-tuple (left, upper, right, lower).
    # We assume the bbox format matches this.
    cropped_image = image.crop(bbox)
    return cropped_image
