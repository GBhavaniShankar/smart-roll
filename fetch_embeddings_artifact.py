import argparse
from utils.wandb_artifacts import download_embeddings_artifact


def main():
    parser = argparse.ArgumentParser(description="Download embeddings DB from W&B artifact")
    parser.add_argument("artifact", help="Artifact path, e.g., 'entity/project/arcface_embeddings:latest'")
    parser.add_argument("--filename", default="arcface_embeddings.pkl", help="Expected filename inside artifact")
    parser.add_argument("--entity", default=None, help="W&B entity/team (optional)")
    parser.add_argument("--project", default=None, help="W&B project (optional)")
    args = parser.parse_args()

    path = download_embeddings_artifact(
        artifact_path=args.artifact,
        filename=args.filename,
        entity=args.entity,
        project=args.project,
    )
    print(path)


if __name__ == "__main__":
    main()
