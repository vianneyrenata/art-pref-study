#!/usr/bin/env python3
"""
Create ChromaDB embeddings for Pilot Study Dataset

Generates CLIP embeddings for the 400 pilot images and stores them in ChromaDB.
Based on create_sample_mini_db.py but adapted for pilot-400 dataset.
"""

import os
from pathlib import Path
import chromadb
from chromadb.config import Settings
import open_clip
import torch
from PIL import Image
import re

# Configuration
IMAGE_DIR = Path(__file__).parent  # This script's directory (pilot-400)
DB_PATH = Path(__file__).parent.parent / "pilot-400-db"  # ./data/pilot-400-db
COLLECTION_NAME = "pilot-400"

# Styles to process
STYLES = [
    "Post_Impressionism",
    "Realism",
    "Cubism",
    "Rococo"
]


def parse_filename(filename):
    """
    Parse WikiArt filename format: artist-name_title-of-artwork-year.jpg
    Returns: (artist, title, year)
    """
    stem = Path(filename).stem

    # Try to extract year (last 4 digits before extension)
    year_match = re.search(r'[-_](\d{4})$', stem)
    year = year_match.group(1) if year_match else "Unknown"

    # Remove year from stem if found
    if year_match:
        stem = stem[:year_match.start()]

    # Split by first underscore to separate artist and title
    if '_' in stem:
        parts = stem.split('_', 1)
        artist = parts[0].replace('-', ' ').strip()
        title = parts[1].replace('-', ' ').strip() if len(parts) > 1 else "Untitled"
    else:
        artist = "Unknown"
        title = stem.replace('-', ' ').strip()

    return artist, title, year


def main():
    print("=" * 70)
    print("Pilot Study ChromaDB Generator")
    print("=" * 70)
    print(f"\nImage directory: {IMAGE_DIR.resolve()}")
    print(f"Database path: {DB_PATH.resolve()}")
    print(f"Collection name: {COLLECTION_NAME}\n")

    # Load CLIP model
    print("Loading CLIP model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        'ViT-B-32',
        pretrained='openai',
        device=device
    )
    model.eval()
    print(f"✓ CLIP model loaded (device: {device})\n")

    # Create ChromaDB client
    print("Initializing ChromaDB...")
    DB_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(DB_PATH),
        settings=Settings(anonymized_telemetry=False)
    )

    # Delete collection if it exists (for clean regeneration)
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"  Deleted existing collection: {COLLECTION_NAME}")
    except:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Pilot study dataset - 400 images from 4 art styles"}
    )
    print(f"✓ Collection created: {COLLECTION_NAME}\n")

    # Process images by style
    all_ids = []
    all_embeddings = []
    all_metadatas = []

    total_processed = 0

    for style in STYLES:
        print(f"Processing: {style}")
        print("-" * 50)

        style_dir = IMAGE_DIR / style

        if not style_dir.exists():
            print(f"  ⚠️  Warning: Directory not found: {style_dir}")
            continue

        # Get all image files
        image_files = list(style_dir.glob("*.jpg")) + \
                     list(style_dir.glob("*.jpeg")) + \
                     list(style_dir.glob("*.png")) + \
                     list(style_dir.glob("*.JPG")) + \
                     list(style_dir.glob("*.JPEG")) + \
                     list(style_dir.glob("*.PNG"))

        if not image_files:
            print(f"  ⚠️  No images found in {style_dir}")
            continue

        print(f"  Found {len(image_files)} images")

        # Process each image
        for i, img_path in enumerate(image_files):
            try:
                # Load and preprocess image
                image = Image.open(img_path).convert('RGB')
                image_tensor = preprocess(image).unsqueeze(0).to(device)

                # Generate embedding
                with torch.no_grad():
                    embedding = model.encode_image(image_tensor)
                    embedding = embedding / embedding.norm(dim=-1, keepdim=True)  # Normalize
                    embedding = embedding.cpu().numpy().flatten().tolist()

                # Parse metadata from filename
                artist, title, year = parse_filename(img_path.name)

                # Create unique ID
                img_id = f"{style}_{img_path.stem}"

                # Store data
                all_ids.append(img_id)
                all_embeddings.append(embedding)
                all_metadatas.append({
                    "style": style,
                    "artist": artist,
                    "title": title,
                    "year": year,
                    "filename": img_path.name,
                    "relative_path": f"{style}/{img_path.name}"
                })

                total_processed += 1

                # Progress indicator
                if (i + 1) % 25 == 0 or (i + 1) == len(image_files):
                    print(f"    Processed {i + 1}/{len(image_files)} images...")

            except Exception as e:
                print(f"  ❌ Error processing {img_path.name}: {e}")
                continue

        print(f"  ✓ Completed {style}\n")

    # Add all embeddings to collection
    if all_ids:
        print("Adding embeddings to ChromaDB...")
        collection.add(
            ids=all_ids,
            embeddings=all_embeddings,
            metadatas=all_metadatas
        )
        print(f"✓ Added {len(all_ids)} embeddings to collection\n")

    print("=" * 70)
    print(f"✅ Done! Processed {total_processed} images")
    print("=" * 70)
    print(f"\nDatabase location: {DB_PATH}")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Total embeddings: {len(all_ids)}")
    print("\nYou can now use this database in your experiment platform!")
    print()


if __name__ == "__main__":
    main()
