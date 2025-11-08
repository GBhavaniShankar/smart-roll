"""Unified embeddings builder CLI.

Build an embeddings database for a chosen backend among lightweight options:
  - arcface  (InsightFace FaceAnalysis buffalo_l)
  - facenet  (facenet-pytorch InceptionResnetV1)
  - dlib     (face_recognition 128D)

Usage examples (PowerShell):
  python build_embeddings.py --backend arcface --faces-dir students --db arcface_students.pkl
  python build_embeddings.py --backend facenet --faces-dir students --db facenet_students.pkl
  python build_embeddings.py --backend dlib --faces-dir students --db dlib_students.pkl

The faces directory is assumed hierarchical by default: root/identity/*.jpg
You can pass --flat if all images are directly in the folder and names come from filenames.
"""
from __future__ import annotations

import os
import sys
import argparse
from typing import Optional

from models.embedders import (
    available_backends,
    create_backend,
)

LIGHT_BACKENDS = {"arcface", "facenet", "dlib"}


def parse_args():
    p = argparse.ArgumentParser(description="Build embeddings DB for a selected face backend")
    p.add_argument("--backend", required=True, choices=sorted(LIGHT_BACKENDS), help="Which backend to use")
    p.add_argument("--faces-dir", required=True, help="Directory of known faces")
    p.add_argument("--db", required=True, help="Output pickle path for embeddings DB")
    p.add_argument("--flat", action="store_true", help="Faces directory is flat (names from filenames)")
    p.add_argument("--max-per-id", type=int, default=None, help="Cap images stored per identity")
    p.add_argument("--min-face", type=int, default=40, help="Minimum face size to accept")
    return p.parse_args()


def main():
    args = parse_args()
    if args.backend not in available_backends():
        print(f"Backend '{args.backend}' not available. Installed: {', '.join(available_backends())}")
        return
    backend = create_backend(args.backend)
    print(f"[build] Using backend: {backend.name}")
    print(f"[build] Faces dir: {args.faces_dir}")
    print(f"[build] Output DB: {args.db}")
    try:
        backend.build_db(
            faces_dir=args.faces_dir,
            db_path=args.db,
            hierarchical=not args.flat,
            max_per_id=args.max_per_id,
            min_face=args.min_face,
        )
    except Exception as e:
        print(f"[error] build failed: {e}")
        return
    print("[done] Embeddings DB created")


if __name__ == "__main__":
    main()
