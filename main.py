#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CLI — ExAnte-AI (B3)

Uso:
  python main.py
  python main.py --year 2023
  python main.py --year 2024 --force-download
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# garante import do pacote local
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from indicador_ia.pipeline import run  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="ExAnte-AI (B3) — pipeline CVM/DFP")
    parser.add_argument("--year", type=int, default=2024, help="Ano da DFP (ex.: 2024)")
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Baixa novamente o ZIP da CVM mesmo se já existir",
    )
    args = parser.parse_args()
    run(year=args.year, force_download=args.force_download)


if __name__ == "__main__":
    main()
