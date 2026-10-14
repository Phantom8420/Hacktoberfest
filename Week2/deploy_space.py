"""Publish the hosted demo to a free Hugging Face Docker Space.

    pip install huggingface_hub
    hf auth login                      # once, with a write token from huggingface.co/settings/tokens
    python deploy_space.py [user/space-name]

Hugging Face builds the Dockerfile itself; the first build takes about ten minutes.
"""
import sys
from pathlib import Path

from huggingface_hub import HfApi

HERE = Path(__file__).parent
CARD = """---
title: Déjà
emoji: 🎞️
colorFrom: gray
colorTo: red
sdk: docker
app_port: 7860
short_description: A memory of your screen you can talk to (demo)
---

Hosted demo of [Déjà](https://github.com/Phantom8420/Hacktoberfest/tree/main/Week2) on a day of sample screens.
Ask it what was on screen, by typing or by voice. The real app runs on your own Windows PC and keeps everything there.
"""


def main():
    api = HfApi()
    repo = sys.argv[1] if len(sys.argv) > 1 else f"{api.whoami()['name']}/deja"
    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
    (HERE / ".space-README.md").write_text(CARD, "utf8")
    try:
        api.upload_file(path_or_fileobj=HERE / ".space-README.md", path_in_repo="README.md",
                        repo_id=repo, repo_type="space")
        api.upload_folder(folder_path=HERE, repo_id=repo, repo_type="space",
                          allow_patterns=["Dockerfile", "start.sh", "requirements-space.txt", "deja/**"],
                          ignore_patterns=["**/__pycache__/**"])
    finally:
        (HERE / ".space-README.md").unlink()
    print(f"https://huggingface.co/spaces/{repo}")


if __name__ == "__main__":
    main()
