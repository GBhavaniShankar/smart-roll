import argparse
import os
import pickle
from typing import Dict, List

import wandb
import numpy as np


def summarize_db(db_path: str):
    with open(db_path, "rb") as f:
        db: Dict[str, List[np.ndarray]] = pickle.load(f)
    id_count = len(db)
    emb_count = sum(len(v) for v in db.values())
    return id_count, emb_count


def main():
    parser = argparse.ArgumentParser(description="Publish embeddings DB to Weights & Biases as an artifact")
    parser.add_argument("--db", required=True, help="Path to arcface_embeddings.pkl")
    parser.add_argument("--name", default="arcface_embeddings", help="Artifact name")
    parser.add_argument("--type", default="embeddings-db", help="Artifact type")
    parser.add_argument("--entity", default=None, help="W&B entity/team (optional)")
    parser.add_argument("--project", default="class-attendance", help="W&B project name")
    parser.add_argument("--model", default="buffalo_l", help="Model pack name for metadata")

    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise FileNotFoundError(args.db)

    ids, embs = summarize_db(args.db)

    run = wandb.init(project=args.project, entity=args.entity, job_type="publish-embeddings")
    art = wandb.Artifact(args.name, type=args.type, metadata={
        "model_name": args.model,
        "identities": ids,
        "embeddings": embs,
    })
    art.add_file(args.db)
    wandb.log_artifact(art)
    run.finish()
    print(f"Published artifact '{args.name}' with {ids} identities and {embs} embeddings.")


if __name__ == "__main__":
    main()
