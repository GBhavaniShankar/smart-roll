import os
from typing import Optional

import wandb


def download_embeddings_artifact(
    artifact_path: str,
    filename: str = "arcface_embeddings.pkl",
    entity: Optional[str] = None,
    project: Optional[str] = None,
) -> str:
    """Download a W&B artifact containing the embeddings DB and return local file path.

    artifact_path examples:
      - "entity/project/arcface_embeddings:latest"
      - "arcface_embeddings:latest" (requires env WANDB_ENTITY/PROJECT or a logged-in context)
    """
    run = wandb.init(project=project, entity=entity, job_type="fetch-embeddings")
    art = wandb.use_artifact(artifact_path)
    local_dir = art.download()
    run.finish()

    path = os.path.join(local_dir, filename)
    if not os.path.exists(path):
        # if the artifact contains a different name, try to locate a .pkl file
        for root, _, files in os.walk(local_dir):
            for f in files:
                if f.lower().endswith(".pkl"):
                    return os.path.join(root, f)
        raise FileNotFoundError(f"Embeddings file '{filename}' not found in artifact {artifact_path}")
    return path
