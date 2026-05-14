from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline import build_dataset_bundle
from .site import write_site


def build(output_dir: Path) -> None:
    bundle = build_dataset_bundle()
    write_site(output_dir, bundle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static AEMO forecast site.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build the static site.")
    build_parser.add_argument("--output-dir", default="site", help="Directory to write the generated site into.")

    args = parser.parse_args()
    if args.command == "build":
        build(Path(args.output_dir))


if __name__ == "__main__":
    main()

