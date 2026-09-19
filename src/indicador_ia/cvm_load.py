"""Carrega CSVs da DFP CVM (DRE, BPA, BPP, DVA)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DOC_FILES = {
    "dre": "dfp_cia_aberta_DRE_con_{year}.csv",
    "bpa": "dfp_cia_aberta_BPA_con_{year}.csv",
    "bpp": "dfp_cia_aberta_BPP_con_{year}.csv",
    "dva": "dfp_cia_aberta_DVA_con_{year}.csv",
}


def _find_csv(year_dir: Path, pattern_name: str, year: int) -> Path:
    """Localiza CSV consolidado; tenta nome padrão e fallback por glob."""
    exact = year_dir / pattern_name.format(year=year)
    if exact.exists():
        return exact
    # alguns zips trazem tudo na raiz ou com maiúsculas diferentes
    key = pattern_name.split("_")[3].upper()  # DRE / BPA / ...
    candidates = list(year_dir.rglob(f"*_{key}_con_{year}.csv"))
    if not candidates:
        candidates = list(year_dir.rglob(f"*_{key}_con_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"CSV consolidado {key} não encontrado em {year_dir}")
    return candidates[0]


def load_statement(year_dir: Path, doc: str, year: int) -> pd.DataFrame:
    path = _find_csv(year_dir, DOC_FILES[doc], year)
    df = pd.read_csv(path, sep=";", encoding="latin-1", low_memory=False)
    # padroniza nomes
    df.columns = [c.strip().upper() for c in df.columns]
    if "VL_CONTA" in df.columns:
        df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
    return df


def filter_latest_exercise(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém o exercício mais recente por empresa (ORDEM_EXERC == 'ÚLTIMO').

    Importante: não usar contains('LTIMO') — 'PENÚLTIMO' também casa e mistura
    o ano anterior com o ano da DFP.
    """
    out = df.copy()
    if "ORDEM_EXERC" in out.columns:
        ordem = out["ORDEM_EXERC"].astype(str).str.upper().str.strip()
        # Exclui explicitamente PENÚLTIMO / PENULTIMO
        is_pen = ordem.str.contains(r"PEN", na=False)
        is_ult = ordem.str.contains(r"ÚLTIMO|ULTIMO|LAST", na=False) & ~is_pen
        if is_ult.any():
            out = out.loc[is_ult]
    if "ST_CONTA_FIXA" in out.columns:
        # preferimos contas fixas quando disponíveis, mas não descartamos não-fixas (PDD etc.)
        pass
    return out


def load_all(year_dir: Path, year: int) -> dict[str, pd.DataFrame]:
    data = {}
    for doc in DOC_FILES:
        try:
            df = load_statement(year_dir, doc, year)
            data[doc] = filter_latest_exercise(df)
            print(f"  {doc.upper()}: {len(data[doc]):,} linhas | {path_hint(year_dir, doc, year)}")
        except FileNotFoundError as e:
            print(f"  AVISO: {e}")
            data[doc] = pd.DataFrame()
    return data


def path_hint(year_dir: Path, doc: str, year: int) -> str:
    try:
        return _find_csv(year_dir, DOC_FILES[doc], year).name
    except FileNotFoundError:
        return "?"
