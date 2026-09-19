"""Extração de linhas contábeis → variáveis do índice."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

# Variáveis cujo valor é a SOMA das linhas casadas (após remover duplicatas e
# descendentes). As demais escolhem UMA linha (a mais agregada).
DEFAULT_SUM_VARS = {"pdd", "pdd_dva", "divida", "software", "depreciacao", "pessoal_dva"}

# Chave da seção de overrides para instituições financeiras no YAML de mapeamento.
FIN_TEMPLATE_KEY = "financeiro"

# Variáveis que a ficha espera; usadas para garantir colunas mesmo sem match.
EXPECTED_VARS = [
    "receita", "cpv", "vendas", "sga", "ebit", "pdd",
    "caixa", "estoques", "ativo_total", "intangivel", "software",
    "divida", "pessoal_dva", "depreciacao", "fco",
]


def load_mapping(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def mapping_for_template(mapping: dict[str, Any], template: str) -> dict[str, Any]:
    """Mapeamento efetivo: base + overrides do template (``financeiro``).

    No YAML, ``financeiro: {var: cfg | null}``; ``null`` remove a variável
    (não aplicável a bancos/seguradoras — ex.: CPV, estoques, dívida).
    """
    base = {
        k: v for k, v in mapping.items()
        if k != FIN_TEMPLATE_KEY and isinstance(v, dict)
    }
    if template == FIN_TEMPLATE_KEY:
        for k, v in (mapping.get(FIN_TEMPLATE_KEY) or {}).items():
            if v is None:
                base.pop(k, None)
            elif isinstance(v, dict):
                base[k] = v
    return base


def _safe_pattern(pat: str) -> str:
    """Converte grupos de captura em não-capturantes (evita warning do pandas)."""
    return re.sub(r"(?<!\\)\((?!\?)", "(?:", pat)


def _match_rows(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Linhas que casam por código OU por padrão de descrição.

    Retorna cópia com coluna ``_via`` ∈ {"code", "pattern"} — código tem
    prioridade na seleção (ver ``_select_rows``).
    """
    if df.empty:
        return df.iloc[0:0].assign(_via=pd.Series(dtype=str))
    code_mask = pd.Series(False, index=df.index)
    cds = [str(c) for c in (cfg.get("cd_conta") or [])]
    if cds and "CD_CONTA" in df.columns:
        code_mask = df["CD_CONTA"].astype(str).isin(cds)
    pat_mask = pd.Series(False, index=df.index)
    patterns = cfg.get("ds_patterns") or []
    if patterns and "DS_CONTA" in df.columns:
        ds = df["DS_CONTA"].astype(str)
        for pat in patterns:
            pat_mask = pat_mask | ds.str.contains(_safe_pattern(str(pat)), regex=True, na=False)
    out = df.loc[code_mask | pat_mask].copy()
    out["_via"] = "pattern"
    out.loc[code_mask.loc[out.index], "_via"] = "code"
    return out


def _select_rows(g: pd.DataFrame) -> pd.DataFrame:
    """Dentro de uma empresa: se houver casamento por código, usa SÓ ele.

    Evita que padrões de texto tragam sublinhas (3.01.01, 2.01.04.02 …) ou
    contas de outro grupo (ex.: "Debêntures convertidas em ações" no PL).
    """
    if "_via" in g.columns:
        by_code = g[g["_via"] == "code"]
        if not by_code.empty:
            return by_code
    return g


def _drop_descendants(g: pd.DataFrame) -> pd.DataFrame:
    """Remove linhas cujo CD_CONTA é filho de outro CD_CONTA já presente.

    Ex.: 2.01.04 + 2.01.04.01 + 2.01.04.02 → mantém só 2.01.04 (a soma dos
    filhos já está no pai). Sem isso a dívida saía ~2× o valor real.
    """
    if "CD_CONTA" not in g.columns or g.empty:
        return g
    codes = sorted(set(g["CD_CONTA"].astype(str)))
    keep = []
    for c in codes:
        if not any(c.startswith(p + ".") for p in codes if p != c):
            keep.append(c)
    return g[g["CD_CONTA"].astype(str).isin(keep)]


def _scale_factor(escala: str) -> float:
    e = (escala or "").strip().upper()
    if e in {"MIL", "MILHAR", "THOUSAND", "1.000"}:
        return 1000.0
    return 1.0  # UNIDADE / REAL


def _value_rs(g: pd.DataFrame) -> pd.Series:
    """VL_CONTA em R$ (aplica ESCALA_MOEDA linha a linha)."""
    v = pd.to_numeric(g["VL_CONTA"], errors="coerce")
    if "ESCALA_MOEDA" in g.columns:
        v = v * g["ESCALA_MOEDA"].map(_scale_factor)
    return v


def _pick_value(g: pd.DataFrame) -> float | None:
    """Escolhe UMA linha: conta fixa (S) > menor profundidade > menor código.

    Regra simples e auditável: a conta padrão CVM (ex.: 3.01, 1.02.04) é
    sempre a mais agregada entre as casadas. Não há mais preferência por
    "receita líquida" em sublinhas — era isso que trocava 3.01 por 3.01.01
    (HAPVIDA: R$ 31,6 bi → R$ 0,7 bi).
    """
    if g.empty:
        return None
    r = g.copy()
    if "ST_CONTA_FIXA" in r.columns:
        fixed = r[r["ST_CONTA_FIXA"].astype(str).str.upper().isin(["S", "SIM", "TRUE", "1"])]
        if not fixed.empty:
            r = fixed
    r = r.assign(_depth=r["CD_CONTA"].astype(str).str.count(r"\."))
    r = r.sort_values(["_depth", "CD_CONTA"], ascending=[True, True])
    val = _value_rs(r).iloc[0]
    if pd.isna(val):
        return None
    return float(val)


def _sum_value(g: pd.DataFrame) -> float | None:
    g2 = g.drop_duplicates(subset=["CD_CONTA"], keep="first")
    g2 = _drop_descendants(g2)
    v = _value_rs(g2).sum(min_count=1)
    if pd.isna(v):
        return None
    return float(v)


def _company_key(df: pd.DataFrame) -> str:
    if "CD_CVM" in df.columns:
        return "CD_CVM"
    return "CNPJ_CIA"


def extract_from_statement(
    df: pd.DataFrame,
    var_name: str,
    cfg: dict[str, Any],
    abs_value: bool = False,
    sum_vars: set[str] | None = None,
) -> pd.Series:
    """Retorna Series indexada por empresa com o valor da variável (já em R$)."""
    if df.empty:
        return pd.Series(dtype=float, name=var_name)
    key = _company_key(df)
    rows = _match_rows(df, cfg)
    if rows.empty:
        return pd.Series(dtype=float, name=var_name)

    sum_vars = DEFAULT_SUM_VARS if sum_vars is None else sum_vars
    aggregate = bool(cfg.get("agregar", var_name in sum_vars))

    out: dict[Any, float] = {}
    for empresa, g in rows.groupby(key):
        g = _select_rows(g)
        v = _sum_value(g) if aggregate else _pick_value(g)
        if v is not None and not pd.isna(v):
            out[empresa] = abs(float(v)) if abs_value else float(v)
    return pd.Series(out, name=var_name, dtype=float)


def detect_financial_companies(dre: pd.DataFrame) -> set:
    """Empresas com plano de contas de instituição financeira (CVM).

    Critério: conta 3.01 descrita como "Receitas da/de Intermediação Financeira".
    Nesse template 3.02 é despesa de captação (não CPV), 3.04.01 é PDD ou
    receita de serviços (não "despesas com vendas") etc.
    """
    if dre.empty or "CD_CONTA" not in dre.columns:
        return set()
    key = _company_key(dre)
    m = (dre["CD_CONTA"].astype(str) == "3.01") & dre["DS_CONTA"].astype(str).str.contains(
        "intermedia", case=False, na=False
    )
    return set(dre.loc[m, key].unique())


# --------------------------------------------------------------------------
# Setor (heurística por nome — v1)
# --------------------------------------------------------------------------

DEFAULT_SETOR_KEYWORDS: dict[str, list[str]] = {
    "financeiro": [
        "BANCO", "BCO", "BANK", "SEGUR", "RESSEGUR", "FINANC", "CREDITO", "CAPITALIZ",
        "PREVID", "ITAU", "BRADESCO", "SANTANDER", "PACTUAL", "BANESTES", "BANRISUL",
        "NU HOLDINGS", "INTER & CO", "B3 S.A", "CIELO", "STONE",
    ],
    "tecnologia": [
        "SOFTWARE", "TECNOLOG", "TECH", "DIGITAL", "CLOUD", "TOTVS", "SINQIA",
        "INFORMATICA", "SISTEMAS", "LOCAWEB", "POSITIVO", "INTELBRAS", "SEMANTIX",
    ],
    "varejo": [
        "LOJAS", "VAREJ", "MAGAZINE", "AREZZO", "RENNER", "AMERICANAS", "VIA",
        "CASAS BAHIA", "MERCADO", "GRAZZIOTIN", "GUARARAPES", "RIACHUELO", "VIVARA",
        "PET CENTER", "PETZ", "ATACAD", "CARREFOUR", "ASSAI",
    ],
    "saude_educacao": [
        "SAUDE", "SAÚDE", "HOSP", "FARMA", "EDUC", "UNIVERS", "ODONT", "DIAGNOST",
        "HAPVIDA", "REDE D'OR", "FLEURY", "DASA", "ONCOCLINICAS", "YDUQS", "COGNA",
        "ANIMA", "CRUZEIRO DO SUL", "SER EDUCACIONAL", "MATER DEI", "QUALICORP",
    ],
    "utilities": [
        "ENERGIA", "ENERG", "ELETR", "SANEAMENTO", "SANEP", "TELECOM", "TIM", "VIVO",
        "TELEFONICA", "OI", "CEMIG", "COPEL", "SABESP", "TRANSMISS", "GERACAO",
        "GERAÇÃO", "DISTRIBUIDORA DE ENERGIA", "CPFL", "ENGIE", "EQUATORIAL", "NEOENERGIA",
        "ELETROBRAS", "TAESA", "ALUPAR", "LIGHT", "CLARO", "ALGAR", "COPASA", "CEG",
        "COMGAS", "COMGÁS",
    ],
    "construcao": [
        "CONSTR", "INCORPOR", "MRV", "CYRELA", "TECNISA", "DIRECIONAL", "EZTEC",
        "EVEN", "TENDA", "HELBOR", "TRISUL", "MOURA DUBEUX", "PLANO & PLANO", "LAVVI",
        "MITRE", "CURY", "GAFISA", "JHSF", "MELNICK", "RNI", "REALTY",
    ],
    "commodities": [
        "PETRO", "VALE", "MINER", "SIDER", "ACO", "AÇO", "AGRO", "SUCOS", "PAPEL",
        "CELULOSE", "OIL", "GAS", "GÁS", "CSN", "GERDAU", "SUZANO", "KLABIN", "USIMINAS",
        "BRASKEM", "ULTRAPAR", "COSAN", "RAIZEN", "RAÍZEN", "SLC", "BRASILAGRO",
        "MARFRIG", "MINERVA", "JBS", "BRF", "AMBIPAR", "3R", "PRIO", "ENAUTA", "VIBRA",
        "SAO MARTINHO", "SÃO MARTINHO", "JALLES", "IRANI", "DEXCO", "CBA",
    ],
    "industria": [
        "INDUST", "METAL", "MAQUIN", "EMBRAER", "WEG", "RANDON", "TUPY", "IOCHPE",
        "MARCOPOLO", "FRAS-LE", "KEPLER", "SCHULZ", "ROMI", "TAURUS", "METISA",
        "MAHLE", "WHIRLPOOL", "UNIPAR", "TEXTIL", "TÊXTIL", "CONFEC", "CALCADO",
        "CALÇADO", "ALPARGATAS", "VULCABRAS", "GRENDENE", "PETTENATI", "CEDRO",
    ],
}


def _norm(s: str) -> str:
    """Maiúsculas + sem acentos (comparação estável entre YAML e DENOM_CIA)."""
    t = unicodedata.normalize("NFKD", str(s or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.upper()


def _kw_regex(kw: str) -> re.Pattern:
    """Palavra-chave casa no INÍCIO de palavra; tokens curtos (≤3) exigem palavra inteira.

    Antes: ``"TI" in nome`` casava PARTICIPAÇÕES/INVESTIMENTOS → 117 empresas
    viravam "tecnologia". Com fronteira de palavra, ``TI`` só casa a sigla isolada
    e prefixos como ``SEGUR`` continuam pegando SEGURADORA.
    """
    k = _norm(kw).strip()
    esc = re.escape(k)
    if len(k.replace(" ", "")) <= 3:
        return re.compile(rf"(?<![A-Z0-9]){esc}(?![A-Z0-9])")
    return re.compile(rf"(?<![A-Z0-9]){esc}")


def classify_sector(
    nome: str,
    setor_keywords: dict[str, list[str]] | None = None,
) -> str:
    """Classificação heurística por nome/razão social (priors editáveis em pesos.yaml)."""
    n = _norm(nome)
    rules = setor_keywords or DEFAULT_SETOR_KEYWORDS
    for setor, kws in rules.items():
        if setor == "outros":
            continue
        for k in kws or []:
            if str(k).strip() and _kw_regex(str(k)).search(n):
                return str(setor)
    return "outros"


_HOLDING_PREFIX = re.compile(r"^EMP\.?\s*ADM\.?\s*PART(?:ICIPACOES)?\.?\s*-?\s*")


def classify_sector_cvm(setor_ativ: str, regras: list[dict[str, Any]] | None) -> str | None:
    """SETOR_ATIV oficial (cadastro CVM) → grupo do índice via config/setor_cvm.yaml.

    Remove o prefixo de holding ("Emp. Adm. Part. - X" → "X"). Retorna None quando
    não há regra (ex.: "Serviços Transporte e Logística", "Sem Setor Principal").
    """
    if not regras or setor_ativ is None or (isinstance(setor_ativ, float) and pd.isna(setor_ativ)):
        return None
    s = _HOLDING_PREFIX.sub("", _norm(setor_ativ)).strip()
    if not s:
        return None
    for r in regras:
        c = _norm(r.get("contem", ""))
        if c and c in s:
            return str(r.get("setor", "outros"))
    return None


# --------------------------------------------------------------------------
# Tabela firm-level
# --------------------------------------------------------------------------

def _extract_all(
    data: dict[str, pd.DataFrame],
    mapping: dict[str, Any],
) -> pd.DataFrame:
    dre = data.get("dre", pd.DataFrame())
    bpa = data.get("bpa", pd.DataFrame())
    bpp = data.get("bpp", pd.DataFrame())
    dva = data.get("dva", pd.DataFrame())
    dfc = data.get("dfc", pd.DataFrame())

    series_list: list[pd.Series] = []

    def add(df: pd.DataFrame, name: str, abs_value: bool = False) -> None:
        cfg = mapping.get(name)
        if not cfg:
            return
        series_list.append(extract_from_statement(df, name, cfg, abs_value=abs_value))

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
    add(dva, "pdd_dva", abs_value=True)
    add(dva, "receita_dva", abs_value=True)

    add(dfc, "fco")  # sinal importa (FCO negativo penaliza em h)

    series_list = [s for s in series_list if not s.empty]
    if not series_list:
        return pd.DataFrame()
    return pd.concat(series_list, axis=1)


def _col(table: pd.DataFrame, name: str) -> pd.Series:
    """Coluna como Series numérica (0.0 se ausente) — evita ``0.fillna`` em int."""
    if name in table.columns:
        return pd.to_numeric(table[name], errors="coerce")
    return pd.Series(0.0, index=table.index, dtype=float)


def build_firm_table(
    data: dict[str, pd.DataFrame],
    mapping: dict[str, Any],
    setor_keywords: dict[str, list[str]] | None = None,
    cadastro: pd.DataFrame | None = None,
    setor_cvm_regras: list[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Monta tabela firm-level com variáveis do índice.

    Empresas com plano de contas financeiro (bancos, seguradoras) são extraídas
    com o mapeamento ``financeiro`` do YAML e marcadas em ``template``.

    Setor: (1) SETOR_ATIV do cadastro CVM via ``setor_cvm_regras``; (2) heurística
    por nome; (3) plano de contas financeiro força ``financeiro``. A origem fica em
    ``setor_fonte``. Do cadastro vêm ainda ``categoria_cvm`` e ``mercado_cvm``.
    """
    statements = {k: v for k, v in data.items() if k != "origem"}
    dre = statements.get("dre", pd.DataFrame())
    bpa = statements.get("bpa", pd.DataFrame())

    fin_ids = detect_financial_companies(dre)

    def subset(ids: set, include: bool) -> dict[str, pd.DataFrame]:
        out = {}
        for k, df in statements.items():
            if df.empty:
                out[k] = df
                continue
            key = _company_key(df)
            m = df[key].isin(ids)
            out[k] = df[m] if include else df[~m]
        return out

    parts = []
    padrao = _extract_all(subset(fin_ids, False), mapping_for_template(mapping, "padrao"))
    if not padrao.empty:
        padrao["template"] = "padrao"
        parts.append(padrao)
    if fin_ids:
        fin = _extract_all(subset(fin_ids, True), mapping_for_template(mapping, FIN_TEMPLATE_KEY))
        if not fin.empty:
            fin["template"] = FIN_TEMPLATE_KEY
            parts.append(fin)
    if not parts:
        return pd.DataFrame()

    table = pd.concat(parts, axis=0)
    table.index.name = "CD_CVM"
    for c in EXPECTED_VARS + ["pdd_dva"]:
        if c not in table.columns:
            table[c] = float("nan")

    # PDD: DRE (texto) tem cobertura baixa (~12%); a DVA traz a linha fixa
    # 7.01.04 "Provisão/Reversão de Créditos de Liquidação Duvidosa" para
    # praticamente todas as companhias → usada como fallback.
    table["pdd_fonte"] = "dre"
    use_dva = table["pdd"].isna() & table["pdd_dva"].notna()
    table.loc[use_dva, "pdd"] = table.loc[use_dva, "pdd_dva"]
    table.loc[use_dva, "pdd_fonte"] = "dva"
    table.loc[table["pdd"].isna(), "pdd_fonte"] = "-"
    table = table.drop(columns=["pdd_dva"])

    # Consistência DRE × DVA: receita da DRE muito abaixo das receitas da DVA
    # (7.01) indica DFP com problema de preenchimento (ex.: QUALITY SOFTWARE
    # 2025: DRE R$ 65 mi vs DVA R$ 300 mi). Só alerta — não altera validade.
    # Bancos ficam de fora: na DVA a receita é bruta (juros), na DRE é o
    # resultado de intermediação — a diferença é estrutural, não erro.
    rec_dva = _col(table, "receita_dva")
    rec = _col(table, "receita")
    table["alerta_receita"] = (
        (rec_dva > 0) & (rec > 0) & (rec < 0.5 * rec_dva)
        & (table["template"] != FIN_TEMPLATE_KEY)
    )
    if "receita_dva" in table.columns:
        table = table.drop(columns=["receita_dva"])

    # metadados (nome)
    meta_src = dre if not dre.empty else bpa
    if not meta_src.empty:
        key = _company_key(meta_src)
        meta = (
            meta_src[[key, "DENOM_CIA"]]
            .drop_duplicates(key)
            .set_index(key)
        )
        table = table.join(meta, how="left")
    else:
        table["DENOM_CIA"] = None

    # --- cadastro CVM: setor oficial, categoria de registro, mercado ---
    table["setor_cvm"] = None
    table["categoria_cvm"] = None
    table["mercado_cvm"] = None
    if cadastro is not None and not cadastro.empty:
        cad = cadastro.copy()
        cad.index = pd.to_numeric(cad.index, errors="coerce")
        idx = pd.to_numeric(pd.Series(table.index, index=table.index), errors="coerce")
        table["setor_cvm"] = idx.map(cad["SETOR_ATIV"]) if "SETOR_ATIV" in cad else None
        table["categoria_cvm"] = idx.map(cad["CATEG_REG"]) if "CATEG_REG" in cad else None
        table["mercado_cvm"] = idx.map(cad["TP_MERC"]) if "TP_MERC" in cad else None

    # --- origem da DFP (consolidado / individual) ---
    origem = data.get("origem")
    if origem is not None and not origem.empty and "origem_dfp" in origem.columns:
        table["origem_dfp"] = pd.Series(table.index, index=table.index).map(origem["origem_dfp"])
    else:
        table["origem_dfp"] = "consolidado"
    table["origem_dfp"] = table["origem_dfp"].fillna("consolidado")

    # --- setor: cadastro CVM → nome → template financeiro ---
    setor_nome = table["DENOM_CIA"].map(
        lambda x: classify_sector(
            str(x) if pd.notna(x) else "",
            setor_keywords=setor_keywords,
        )
    )
    setor_cad = table["setor_cvm"].map(lambda s: classify_sector_cvm(s, setor_cvm_regras))
    table["setor"] = setor_cad.where(setor_cad.notna(), setor_nome)
    table["setor_fonte"] = pd.Series("nome", index=table.index).where(setor_cad.isna(), "cvm")
    table.loc[setor_cad.isna() & (setor_nome == "outros"), "setor_fonte"] = "padrao"
    # plano de contas financeiro é evidência mais forte que nome ou cadastro
    is_fin = table["template"] == FIN_TEMPLATE_KEY
    table.loc[is_fin & (table["setor"] != "financeiro"), "setor_fonte"] = "template"
    table.loc[is_fin, "setor"] = "financeiro"

    table = table.rename(columns={"pessoal_dva": "pessoal"})

    # EBITDA proxy = EBIT (3.05) + depreciação/amortização (DVA 7.04.01)
    table["ebitda"] = _col(table, "ebit").fillna(0) + _col(table, "depreciacao").fillna(0)

    # Dívida líquida = empréstimos/financiamentos/debêntures − caixa
    table["divida_liquida"] = _col(table, "divida").fillna(0) - _col(table, "caixa").fillna(0)

    return table
