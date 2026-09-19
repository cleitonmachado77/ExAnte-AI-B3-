"""Extração de linhas contábeis → variáveis do índice."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_mapping(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _match_rows(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    if df.empty:
        return df
    masks = []
    cds = cfg.get("cd_conta") or []
    if cds and "CD_CONTA" in df.columns:
        cd = df["CD_CONTA"].astype(str)
        for code in cds:
            masks.append(cd == str(code))
    patterns = cfg.get("ds_patterns") or []
    if patterns and "DS_CONTA" in df.columns:
        ds = df["DS_CONTA"].astype(str)
        for pat in patterns:
            # evita warning de grupos de captura
            safe = re.sub(r"(?<!\\)\((?!\?)", "(?:", pat)
            masks.append(ds.str.contains(safe, regex=True, na=False))
    if not masks:
        return df.iloc[0:0]
    m = masks[0]
    for extra in masks[1:]:
        m = m | extra
    return df.loc[m].copy()


def _pick_value(rows: pd.DataFrame, prefer_fixed: bool = True, prefer_deep: bool = False) -> float | None:
    if rows.empty:
        return None
    r = rows.copy()
    # preferir descrição de receita líquida quando houver
    if "DS_CONTA" in r.columns:
        liq = r[r["DS_CONTA"].astype(str).str.contains(r"(?i)operacional l[ií]quida|receita l[ií]quida", na=False)]
        if not liq.empty:
            r = liq
    if prefer_fixed and "ST_CONTA_FIXA" in r.columns:
        fixed = r[r["ST_CONTA_FIXA"].astype(str).str.upper().isin(["S", "SIM", "TRUE", "1"])]
        if not fixed.empty:
            r = fixed
    if "CD_CONTA" in r.columns:
        r = r.assign(_depth=r["CD_CONTA"].astype(str).str.count(r"\."))
        # receita líquida costuma ser mais profunda (3.01.01); demais contas: agregada
        ascending = not prefer_deep
        if prefer_deep or r["DS_CONTA"].astype(str).str.contains(r"(?i)l[ií]quida", na=False).any():
            r = r.sort_values(["_depth", "CD_CONTA"], ascending=[False, True])
        else:
            r = r.sort_values(["_depth", "CD_CONTA"], ascending=[True, True])
    r = r.drop_duplicates(subset=["CD_CONTA"], keep="first")
    val = r["VL_CONTA"].iloc[0]
    if pd.isna(val):
        return None
    return float(val)


def _scale_factor(escala: str) -> float:
    e = (escala or "").strip().upper()
    if e in {"MIL", "MILHAR", "THOUSAND", "1.000"}:
        return 1000.0
    return 1.0  # UNIDADE / REAL


def _company_key(df: pd.DataFrame) -> str:
    if "CD_CVM" in df.columns:
        return "CD_CVM"
    return "CNPJ_CIA"


def extract_from_statement(
    df: pd.DataFrame,
    var_name: str,
    cfg: dict[str, Any],
    abs_value: bool = False,
) -> pd.Series:
    """Retorna Series indexada por empresa com o valor da variável (já em R$)."""
    if df.empty:
        return pd.Series(dtype=float, name=var_name)
    key = _company_key(df)
    rows = _match_rows(df, cfg)
    if rows.empty:
        return pd.Series(dtype=float, name=var_name)

    sum_vars = {"pdd", "divida", "software", "depreciacao", "pessoal_dva"}
    out = {}
    for empresa, g in rows.groupby(key):
        if var_name in sum_vars or var_name == "divida":
            g2 = g.drop_duplicates(subset=["CD_CONTA"], keep="first")
            # escala por linha
            if "ESCALA_MOEDA" in g2.columns:
                scales = g2["ESCALA_MOEDA"].map(_scale_factor)
                v = (g2["VL_CONTA"] * scales).sum(min_count=1)
            else:
                v = g2["VL_CONTA"].sum(min_count=1)
        else:
            prefer_deep = var_name == "receita"
            v = _pick_value(g, prefer_deep=prefer_deep)
            if v is not None and "ESCALA_MOEDA" in g.columns:
                # escala da linha escolhida
                if prefer_deep and "DS_CONTA" in g.columns:
                    g_pref = g[g["DS_CONTA"].astype(str).str.contains(r"(?i)l[ií]quida", na=False)]
                    base = g_pref if not g_pref.empty else g
                else:
                    base = g
                esc = str(base["ESCALA_MOEDA"].iloc[0])
                v = v * _scale_factor(esc)
        if v is not None and not pd.isna(v):
            out[empresa] = abs(float(v)) if abs_value else float(v)
    return pd.Series(out, name=var_name, dtype=float)


DEFAULT_SETOR_KEYWORDS: dict[str, list[str]] = {
    "financeiro": ["BANCO", "BANK", "SEGUR", "FINANC", "CREDITO", "CRÉDITO", "CAPITALIZ", "PREV"],
    "tecnologia": ["SOFTWARE", "TECH", "DIGITAL", "TI ", " DATA", "CLOUD", "SAP", "TOTVS"],
    "varejo": ["LOJAS", "VAREJ", "MAGAZINE", "AREZZO", "RENNER", "AMERICANAS", "VIA ", "CASAS BAHIA", "MERCADO"],
    "saude_educacao": ["SAUDE", "SAÚDE", "HOSP", "FARMA", "EDUC", "UNIVERS", "ODONT", "DIAGNOST"],
    "utilities": ["ENERGIA", "ELETR", "SANEAMENTO", "TELECOM", "TIM ", "VIVO", "OI ", "CEMIG", "COPEL", "SABESP"],
    "construcao": ["CONSTR", "INCORPOR", "MRV", "CYRELA", "TECNISA", "DIRECIONAL"],
    "commodities": [
        "PETRO", "VALE", "MINER", "SIDER", "ACO ", "AÇO", "AGRO", "SUCOS", "PAPEL",
        "CELULOSE", "OIL", "GAS", "GÁS", "CSN", "GERDAU", "SUZANO", "KLABIN",
    ],
    "industria": ["INDUST", "METAL", "MAQUIN", "EMBRAER", "WEG", "RANDON", "TUPY"],
}


def classify_sector(
    nome: str,
    setor_keywords: dict[str, list[str]] | None = None,
) -> str:
    """Classificação heurística por nome/razão social (priors editáveis em pesos.yaml)."""
    n = (nome or "").upper()
    rules = setor_keywords or DEFAULT_SETOR_KEYWORDS
    for setor, kws in rules.items():
        if setor == "outros":
            continue
        if any(str(k).upper() in n for k in (kws or [])):
            return str(setor)
    return "outros"


def build_firm_table(
    data: dict[str, pd.DataFrame],
    mapping: dict[str, Any],
    setor_keywords: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Monta tabela firm-level com variáveis do índice."""
    dre = data.get("dre", pd.DataFrame())
    bpa = data.get("bpa", pd.DataFrame())
    bpp = data.get("bpp", pd.DataFrame())
    dva = data.get("dva", pd.DataFrame())

    series_list = []

    def add(df, name, abs_value=False):
        cfg = mapping.get(name)
        if not cfg:
            return
        s = extract_from_statement(df, name, cfg, abs_value=abs_value)
        series_list.append(s)

    add(dre, "receita", abs_value=True)
    add(dre, "cpv", abs_value=True)
    add(dre, "vendas", abs_value=True)
    add(dre, "sga", abs_value=True)
    add(dre, "ebit")
    add(dre, "pdd", abs_value=True)

    add(bpa, "caixa", abs_value=True)
    add(bpa, "estoques", abs_value=True)
    add(bpa, "ativo_total", abs_value=True)
    add(bpa, "intangivel", abs_value=True)
    add(bpa, "software", abs_value=True)

    add(bpp, "divida", abs_value=True)

    add(dva, "pessoal_dva", abs_value=True)
    add(dva, "depreciacao", abs_value=True)

    if not series_list:
        return pd.DataFrame()

    table = pd.concat(series_list, axis=1)
    table.index.name = "CD_CVM"

    # metadados (nome)
    meta_src = dre if not dre.empty else bpa
    if not meta_src.empty:
        key = "CD_CVM" if "CD_CVM" in meta_src.columns else "CNPJ_CIA"
        meta = (
            meta_src[[key, "DENOM_CIA"]]
            .drop_duplicates(key)
            .set_index(key)
        )
        table = table.join(meta, how="left")
    else:
        table["DENOM_CIA"] = None

    table["setor"] = table["DENOM_CIA"].map(
        lambda x: classify_sector(
            str(x) if pd.notna(x) else "",
            setor_keywords=setor_keywords,
        )
    )
    table = table.rename(columns={"pessoal_dva": "pessoal"})

    # EBITDA proxy
    ebit = table["ebit"] if "ebit" in table.columns else 0
    dep = table["depreciacao"] if "depreciacao" in table.columns else 0
    table["ebitda"] = ebit.fillna(0) + dep.fillna(0)
    # se ebit negativo e sem dep, mantém ebitda baixo

    # Dívida líquida
    caixa = table["caixa"] if "caixa" in table.columns else 0
    divida = table["divida"] if "divida" in table.columns else 0
    table["divida_liquida"] = divida.fillna(0) - caixa.fillna(0)

    return table
