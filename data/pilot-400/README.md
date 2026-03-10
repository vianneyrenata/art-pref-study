# Pilot Study Dataset (400 images)

## Dataset Composition

This dataset contains **400 randomly selected images** from 4 art styles:

1. **Post_Impressionism** - 100 images
2. **Realism** - 100 images
3. **Cubism** - 100 images
4. **Rococo** - 100 images

**Total**: 4 × 100 = 400 images

## Source

Images are randomly selected from the full WikiArt dataset located at:
`../../wikiart/`

These are the same 4 styles used in the simulation scripts (art-sim-*.py files).

## Purpose

This dataset is intended for:
- Pilot studies with yourself/small group
- Testing the experiment platform with more images than demo (20) but less than full study
- Generating preliminary data before full participant recruitment

## Generation

To regenerate this dataset (if needed), run:
```bash
python3 generate_pilot_dataset.py
```

This will randomly select 100 images from each style and copy them here.

## Associated ChromaDB

After generating images, create the ChromaDB embeddings at:
`../../chromadb/pilot-400-db/`

Using the script: `create_pilot_chromadb.py`
