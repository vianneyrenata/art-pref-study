#!/usr/bin/env python3
"""
Generate Pilot Study Dataset (400 images)

Randomly selects 100 images from each of 4 art styles:
- Post_Impressionism
- Realism
- Cubism
- Rococo

Copies selected images to the pilot-400 folder structure.
"""

import os
import shutil
import random
from pathlib import Path

# Configuration
STYLES = [
    "Post_Impressionism",
    "Realism",
    "Cubism",
    "Rococo"
]

IMAGES_PER_STYLE = 100
SOURCE_DIR = Path("../../wikiart")  # Relative to this script location
TARGET_DIR = Path(__file__).parent  # This script's directory

# Seed for reproducibility (change this to get different random selections)
RANDOM_SEED = 42


def get_image_files(style_dir):
    """Get all image files from a style directory"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}
    image_files = []

    if not style_dir.exists():
        print(f"  ⚠️  Warning: Directory not found: {style_dir}")
        return image_files

    for file_path in style_dir.iterdir():
        if file_path.is_file() and file_path.suffix in image_extensions:
            image_files.append(file_path)

    return image_files


def main():
    print("=" * 60)
    print("Pilot Study Dataset Generator (400 images)")
    print("=" * 60)
    print(f"\nSource: {SOURCE_DIR.resolve()}")
    print(f"Target: {TARGET_DIR.resolve()}\n")

    # Set random seed for reproducibility
    random.seed(RANDOM_SEED)
    print(f"Using random seed: {RANDOM_SEED}\n")

    total_copied = 0

    for style in STYLES:
        print(f"Processing: {style}")
        print("-" * 40)

        # Get source and target directories
        source_style_dir = SOURCE_DIR / style
        target_style_dir = TARGET_DIR / style

        # Get all images from source
        all_images = get_image_files(source_style_dir)

        if not all_images:
            print(f"  ❌ No images found in {source_style_dir}")
            continue

        print(f"  Found {len(all_images)} images in source")

        # Check if we have enough images
        if len(all_images) < IMAGES_PER_STYLE:
            print(f"  ⚠️  Warning: Only {len(all_images)} images available, need {IMAGES_PER_STYLE}")
            print(f"  Will copy all {len(all_images)} images")
            selected_images = all_images
        else:
            # Randomly select images
            selected_images = random.sample(all_images, IMAGES_PER_STYLE)
            print(f"  Randomly selected {IMAGES_PER_STYLE} images")

        # Create target directory
        target_style_dir.mkdir(parents=True, exist_ok=True)

        # Copy selected images
        copied = 0
        for img_path in selected_images:
            target_path = target_style_dir / img_path.name
            shutil.copy2(img_path, target_path)
            copied += 1

        print(f"  ✓ Copied {copied} images to {target_style_dir.name}/")
        total_copied += copied
        print()

    print("=" * 60)
    print(f"✅ Done! Total images copied: {total_copied}")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Verify the images in each style folder")
    print("2. Run create_pilot_chromadb.py to generate embeddings")
    print()


if __name__ == "__main__":
    main()
