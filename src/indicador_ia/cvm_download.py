"""Download dos formulários DFP e do cadastro de companhias (dados abertos CVM)."""

from __future__ import annotations

import io
import time
import zipfile
from pathlib import Path

import requests

CVM_DFP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"
CVM_CAD_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
CAD_FILENAME = "cad_cia_aberta.csv"
CAD_MAX_AGE_DAYS = 30


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


def download_cadastro(data_dir: Path, force: bool = False) -> Path | None:
    """Baixa o cadastro de companhias abertas (SETOR_ATIV, CATEG_REG, TP_MERC).

    Reaproveita o arquivo local se tiver menos de ``CAD_MAX_AGE_DAYS``.
    Sem internet: devolve o arquivo local se existir, senão ``None``
    (o pipeline cai na heurística por nome).
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / CAD_FILENAME

    if path.exists() and not force:
        age_days = (time.time() - path.stat().st_mtime) / 86400
        if age_days < CAD_MAX_AGE_DAYS:
            return path

    try:
        print(f"Baixando cadastro CVM: {CVM_CAD_URL}")
        resp = requests.get(CVM_CAD_URL, timeout=120)
        resp.raise_for_status()
        path.write_bytes(resp.content)
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"  AVISO: cadastro CVM indisponível ({exc}).")
        return path if path.exists() else None
