"""Carrega CSVs da DFP CVM (DRE, BPA, BPP, DVA, DFC) e o cadastro de companhias."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DOC_FILES = {
    "dre": "dfp_cia_aberta_DRE_{scope}_{year}.csv",
    "bpa": "dfp_cia_aberta_BPA_{scope}_{year}.csv",
    "bpp": "dfp_cia_aberta_BPP_{scope}_{year}.csv",
    "dva": "dfp_cia_aberta_DVA_{scope}_{year}.csv",
    # DFC: cada companhia publica pelo método indireto (MI, maioria) OU direto (MD)
    "dfc_mi": "dfp_cia_aberta_DFC_MI_{scope}_{year}.csv",
    "dfc_md": "dfp_cia_aberta_DFC_MD_{scope}_{year}.csv",
}

# chaves finais entregues ao extrator
STATEMENTS = ["dre", "bpa", "bpp", "dva", "dfc"]


def _find_csv(year_dir: Path, pattern_name: str, year: int, scope: str = "con") -> Path:
    """Localiza CSV (con/ind); tenta nome padrão e fallback por glob."""
    year_dir = Path(year_dir)
    exact = year_dir / pattern_name.format(year=year, scope=scope)
    if exact.exists():
        return exact
    # alguns zips trazem tudo na raiz ou com maiúsculas diferentes
    parts = pattern_name.split("_")
    key = "_".join(parts[3:-2]).upper()  # DRE / BPA / DFC_MI ...
    candidates = list(year_dir.rglob(f"*_{key}_{scope}_{year}.csv"))
    if not candidates:
        candidates = list(year_dir.rglob(f"*_{key}_{scope}_*.csv"))
    if not candidates:
        raise FileNotFoundError(f"CSV {scope} {key} não encontrado em {year_dir}")
    return candidates[0]


def load_statement(year_dir: Path, doc: str, year: int, scope: str = "con") -> pd.DataFrame:
    path = _find_csv(year_dir, DOC_FILES[doc], year, scope)
    df = pd.read_csv(path, sep=";", encoding="latin-1", low_memory=False)
    # padroniza nomes
    df.columns = [c.strip().upper() for c in df.columns]
    if "VL_CONTA" in df.columns:
        df["VL_CONTA"] = pd.to_numeric(df["VL_CONTA"], errors="coerce")
    return df


def filter_latest_exercise(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém o exercício mais recente por empresa (ORDEM_EXERC == 'ÚLTIMO')
    e, se houver reapresentações, apenas a maior VERSAO.

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
    key = "CD_CVM" if "CD_CVM" in out.columns else "CNPJ_CIA"
    if "VERSAO" in out.columns and key in out.columns:
        ver = pd.to_numeric(out["VERSAO"], errors="coerce")
        latest = ver.groupby(out[key]).transform("max")
        out = out.loc[ver == latest]
    return out


def _company_ids(df: pd.DataFrame) -> set:
    key = "CD_CVM" if "CD_CVM" in df.columns else "CNPJ_CIA"
    return set(df[key].unique()) if not df.empty else set()


def _load_scope(year_dir: Path, year: int, scope: str) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for doc in DOC_FILES:
        try:
            frames[doc] = filter_latest_exercise(load_statement(year_dir, doc, year, scope))
        except FileNotFoundError as e:
            if not doc.startswith("dfc"):
                print(f"  AVISO: {e}")
            frames[doc] = pd.DataFrame()
    # DFC única: MI + MD (uma companhia usa um OU outro)
    dfc = [frames.pop("dfc_mi"), frames.pop("dfc_md")]
    dfc = [d for d in dfc if not d.empty]
    frames["dfc"] = pd.concat(dfc, ignore_index=True) if dfc else pd.DataFrame()
    return frames


def load_all(
    year_dir: Path,
    year: int,
    usar_consolidado: bool = True,
    fallback_individual: bool = True,
) -> dict[str, pd.DataFrame]:
    """Carrega DRE, BPA, BPP, DVA e DFC.

    ``usar_consolidado=True``: base consolidada; companhias SEM consolidado
    (não têm controladas — ~1/3 do universo) entram pela individual quando
    ``fallback_individual=True``. O conjunto de empresas "consolidadas" é
    definido pela DRE e aplicado às demais demonstrações para consistência.
    ``usar_consolidado=False``: só individuais.

    Retorna também ``data["origem"]``: DataFrame CD_CVM → "consolidado"/"individual".
    """
    primary = "con" if usar_consolidado else "ind"
    frames = _load_scope(year_dir, year, primary)
    primary_ids = _company_ids(frames.get("dre", pd.DataFrame()))
    origem = {cd: ("consolidado" if usar_consolidado else "individual") for cd in primary_ids}

    if usar_consolidado and fallback_individual:
        ind = _load_scope(year_dir, year, "ind")
        n_extra = 0
        for doc in STATEMENTS:
            df_ind = ind.get(doc, pd.DataFrame())
            if df_ind.empty:
                continue
            key = "CD_CVM" if "CD_CVM" in df_ind.columns else "CNPJ_CIA"
            extra = df_ind[~df_ind[key].isin(primary_ids)]
            if doc == "dre":
                n_extra = extra[key].nunique()
                origem.update({cd: "individual" for cd in extra[key].unique()})
            frames[doc] = pd.concat([frames[doc], extra], ignore_index=True)
        if n_extra:
            print(f"  Fallback individual: +{n_extra} empresas sem consolidado")

    data: dict[str, pd.DataFrame] = {}
    for doc in STATEMENTS:
        data[doc] = frames.get(doc, pd.DataFrame())
        if not data[doc].empty:
            hint = "DFC_MI+MD" if doc == "dfc" else path_hint(year_dir, doc, year, primary)
            print(f"  {doc.upper()}: {len(data[doc]):,} linhas | {hint}")
    data["origem"] = pd.DataFrame(
        {"CD_CVM": list(origem.keys()), "origem_dfp": list(origem.values())}
    ).set_index("CD_CVM")
    return data


def path_hint(year_dir: Path, doc: str, year: int, scope: str = "con") -> str:
    try:
        return _find_csv(year_dir, DOC_FILES[doc], year, scope).name
    except FileNotFoundError:
        return "?"


# --------------------------------------------------------------------------
# Cadastro de companhias abertas (setor oficial, categoria, mercado)
# --------------------------------------------------------------------------

def load_cadastro(path: Path | None) -> pd.DataFrame:
    """CD_CVM → SETOR_ATIV, CATEG_REG, TP_MERC, SIT (uma linha por companhia).

    O cadastro tem várias linhas por CD_CVM (um por mercado/histórico); fica
    a linha ATIVO, preferindo TP_MERC = BOLSA e Categoria A.
    """
    cols = ["CD_CVM", "SETOR_ATIV", "CATEG_REG", "TP_MERC", "SIT"]
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=cols[1:]).rename_axis("CD_CVM")
    cad = pd.read_csv(path, sep=";", encoding="latin-1", low_memory=False)
    cad.columns = [c.strip().upper() for c in cad.columns]
    for c in cols:
        if c not in cad.columns:
            cad[c] = None
    cad = cad[cols].copy()
    cad["CD_CVM"] = pd.to_numeric(cad["CD_CVM"], errors="coerce")
    cad = cad.dropna(subset=["CD_CVM"])
    cad["CD_CVM"] = cad["CD_CVM"].astype(int)
    sit = cad["SIT"].astype(str).str.upper()
    cad["_p_sit"] = (sit == "ATIVO").astype(int)
    cad["_p_bolsa"] = (cad["TP_MERC"].astype(str).str.upper() == "BOLSA").astype(int)
    cad["_p_cat"] = (cad["CATEG_REG"].astype(str).str.upper().str.contains(" A")).astype(int)
    cad = (
        cad.sort_values(["_p_sit", "_p_bolsa", "_p_cat"], ascending=False)
        .drop_duplicates("CD_CVM", keep="first")
        .drop(columns=["_p_sit", "_p_bolsa", "_p_cat"])
        .set_index("CD_CVM")
    )
    return cad
