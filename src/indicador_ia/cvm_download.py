"""Download dos formulários DFP (dados abertos CVM)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import requests

CVM_DFP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"


def download_dfp(year: int, data_dir: Path, force: bool = False) -> Path:
    """Baixa e extrai o ZIP anual da DFP. Retorna a pasta do ano."""
    data_dir = Path(data_dir)
    year_dir = data_dir / f"dfp_{year}"
    marker = year_dir / "_OK"

    if marker.exists() and not force:
        return year_dir

    year_dir.mkdir(parents=True, exist_ok=True)
    url = CVM_DFP_URL.format(year=year)
    print(f"Baixando DFP {year}: {url}")

    resp = requests.get(url, timeout=180)
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(year_dir)

    marker.write_text("ok", encoding="utf-8")
    print(f"Extraído em: {year_dir}")
    return year_dir
