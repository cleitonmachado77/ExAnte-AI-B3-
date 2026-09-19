"""Cálculo do Score Ex-Ante de exposição / potencial de benefício por IA."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def load_pesos(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _lookup_step(value: float, rules: list[dict], fallback: float = 1.0) -> float:
    """rules: lista ordenada com max_exclusive e valor."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return fallback
    for rule in rules:
        mx = rule.get("max_exclusive")
        if mx is None or value < float(mx):
            return float(rule["valor"])
    return float(rules[-1]["valor"])


def _is_fin(out: pd.DataFrame) -> pd.Series:
    if "template" in out.columns:
        return out["template"].astype(str) == "financeiro"
    return pd.Series(False, index=out.index)


def _validity(out: pd.DataFrame, pesos: dict[str, Any]) -> pd.Series:
    """Filtros de qualidade (quem entra no painel)."""
    min_receita = float(pesos.get("min_receita", 50_000_000.0))
    valido = (
        (out["receita"].fillna(0).abs() >= min_receita)
        & out["exposicao"].notna()
        & (out["exposicao"] > 0)
    )

    if pesos.get("excluir_recuperacao_judicial", True) and "DENOM_CIA" in out.columns:
        rj = out["DENOM_CIA"].astype(str).str.upper().str.contains("RECUPERA", na=False)
        valido &= ~rj

    req = pesos.get("exigir_ao_menos_uma_de", [])
    if req:
        present = [c for c in req if c in out.columns]
        if present:
            valido &= out[present].fillna(0).abs().sum(axis=1) > 0

    # Subsidiárias / SPEs: entram pela DFP individual (não têm controladas) e são
    # "Categoria B" na CVM (não podem ter ações em bolsa) — ex.: malhas da Rumo,
    # concessionárias de rodovia. Evita contar a controlada e a holding.
    cat = out["categoria_cvm"].astype(str).str.upper() if "categoria_cvm" in out.columns else pd.Series("", index=out.index)
    is_b = cat.str.contains(" B", na=False)
    if pesos.get("excluir_individual_categoria_b", True) and "origem_dfp" in out.columns:
        ind = out["origem_dfp"].astype(str) == "individual"
        valido &= ~(ind & is_b)
    if pesos.get("apenas_categoria_a", False):
        valido &= cat.str.contains(" A", na=False)

    if pesos.get("excluir_alerta_receita", False) and "alerta_receita" in out.columns:
        valido &= ~out["alerta_receita"].fillna(False).astype(bool)

    return valido


def compute_scores(df: pd.DataFrame, pesos: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    alpha = dict(pesos["alpha_base"])
    setor_mult = pesos.get("setor_mult", {})
    alpha_max = float(pesos.get("alpha_max", 0.60))
    is_fin = _is_fin(out)

    out["mult_setor"] = out["setor"].map(
        lambda s: float(setor_mult.get(s, setor_mult.get("outros", 1.0)))
    )

    # α da PDD fora do setor financeiro (Pesos_Alpha_Beta §3: 0,15 ou excluir).
    # Bancos/financeiras mantêm alpha_base['pdd'].
    alpha_pdd_nf = pesos.get("alpha_pdd_nao_financeiro")
    is_fin_setor = (out["setor"].astype(str) == "financeiro") | is_fin
    alpha_pdd_base = pd.Series(float(alpha.get("pdd", 0.0)), index=out.index)
    if alpha_pdd_nf is not None:
        alpha_pdd_base = alpha_pdd_base.where(is_fin_setor, float(alpha_pdd_nf))

    def a(name: str) -> pd.Series:
        if name == "pdd":
            base = alpha_pdd_base
        else:
            base = pd.Series(float(alpha.get(name, 0.0)), index=out.index)
        return (base * out["mult_setor"]).clip(upper=alpha_max)

    rol = out["receita"].replace(0, np.nan)
    cap = float(pesos.get("max_linha_sobre_receita", 3.0))

    # --- Pessoal (DVA 7.08.01) já está dentro de CPV + SG&A + Vendas ---------
    # pessoal_modo:
    #   liquido  → tira de CPV/SG&A/Vendas (pro rata) a parcela de pessoal e aplica
    #              α_pessoal só sobre Pessoal (sem dupla contagem)   [padrão]
    #   separado → soma tudo como linhas independentes (comportamento antigo)
    #   excluir  → ignora a linha Pessoal
    # No plano de contas financeiro "Despesas de Pessoal" já é linha própria
    # (fora de "Outras despesas administrativas") → nunca há netting.
    modo = str(pesos.get("pessoal_modo", "liquido")).lower()
    pessoal = out["pessoal"].fillna(0).abs() if "pessoal" in out.columns else pd.Series(0.0, index=out.index)
    linhas_custo = [c for c in ["cpv", "sga", "vendas"] if c in out.columns]
    custos = sum((out[c].fillna(0).abs() for c in linhas_custo), pd.Series(0.0, index=out.index))
    fator_liq = pd.Series(1.0, index=out.index)
    if modo == "liquido":
        share = (pessoal / custos.replace(0, np.nan)).fillna(0).clip(0, 1)
        fator_liq = (1.0 - share).where(~is_fin, 1.0)
    out["pessoal_modo"] = modo
    out["fator_pessoal_liquido"] = fator_liq
    for c in linhas_custo:
        out[f"{c}_afetavel"] = out[c].fillna(0).abs() * fator_liq
    if "pessoal" in out.columns:
        out["pessoal_afetavel"] = pessoal if modo != "excluir" else 0.0

    expo = pd.Series(0.0, index=out.index)
    teto_rs = pd.Series(0.0, index=out.index)

    def add_line(col: str, alpha_name: str):
        nonlocal expo, teto_rs
        src = f"{col}_afetavel" if f"{col}_afetavel" in out.columns else col
        if src not in out.columns:
            out[f"contrib_{alpha_name}"] = np.nan
            out[f"valor_{alpha_name}_rs"] = np.nan
            return
        # base afetável em R$ = min(|L|, cap * ROL) * α
        base_rs = out[src].fillna(0).abs().clip(upper=(cap * rol))
        alpha_s = a(alpha_name)
        valor_rs = base_rs * alpha_s
        ratio = (out[src].fillna(0).abs() / rol).clip(upper=cap)
        c = ratio * alpha_s
        out[f"contrib_{alpha_name}"] = c
        out[f"valor_{alpha_name}_rs"] = valor_rs
        expo = expo + c.fillna(0)
        teto_rs = teto_rs + valor_rs.fillna(0)

    add_line("sga", "sga")
    add_line("vendas", "vendas")
    add_line("pessoal", "pessoal")
    add_line("cpv", "cpv")
    add_line("pdd", "pdd")
    add_line("estoques", "estoques")

    out["exposicao"] = expo

    # OBJETIVO 1 — teto de eficiência em R$ (potencial bruto de ganho)
    out["obj1_teto_rs"] = teto_rs
    out["obj1_teto_pct_receita"] = (teto_rs / rol) * 100

    # Painel válido (necessário antes de winsorizar / percentis)
    out["valido"] = _validity(out, pesos)
    valid = out["valido"]

    # Winsorização da exposição para o score relativo: uma DFP atípica
    # (ex.: exposição 1,27 com painel mediano 0,19) não comprime todo o 0–100.
    # O teto em R$ (obj1) não é alterado.
    wpct = pesos.get("winsor_exposicao_pct", 0.99)
    out["exposicao_score"] = out["exposicao"]
    if wpct is not None and valid.sum() >= 20:
        lim = float(out.loc[valid, "exposicao"].quantile(float(wpct)))
        out["exposicao_score"] = out["exposicao"].clip(upper=lim)
        out["exposicao_winsor_limite"] = lim

    # F^fin = f * g * h
    caixa_ativo = out["caixa"].fillna(0) / out["ativo_total"].replace(0, np.nan)
    out["caixa_sobre_ativo"] = caixa_ativo
    dl_ebitda = out["divida_liquida"] / out["ebitda"].replace(0, np.nan)
    # sem dívida financeira mapeável → indicador não definido para bancos
    dl_ebitda = dl_ebitda.mask(is_fin)
    out["dl_sobre_ebitda"] = dl_ebitda
    fco = out["fco"] if "fco" in out.columns else pd.Series(np.nan, index=out.index)
    out["fco_sobre_receita"] = fco / rol

    g_fin = pesos.get("g_financeiro", 1.0)
    usar_fco = bool(pesos.get("usar_fco", True))
    h_rules = pesos.get("h_fco") or []
    f_vals, g_vals, h_vals = [], [], []
    for i, row in out.iterrows():
        f_vals.append(_lookup_step(row.get("caixa_sobre_ativo"), pesos["f_caixa"], 1.0))
        # Instituições financeiras: DL/EBITDA não é definido → g fixo
        if bool(is_fin.loc[i]) and g_fin is not None:
            g_vals.append(float(g_fin))
        else:
            ebitda = row.get("ebitda")
            if ebitda is None or (isinstance(ebitda, float) and (np.isnan(ebitda) or ebitda <= 0)):
                g_vals.append(float(pesos.get("g_ebitda_negativo", 0.25)))
            else:
                g_vals.append(_lookup_step(row.get("dl_sobre_ebitda"), pesos["g_alavancagem"], 0.40))
        # h: geração de caixa operacional (DFC 6.01 / ROL); sem DFC → 1,0.
        # Bancos: FCO oscila com a carteira de crédito/captação → não é sinal de folga.
        if usar_fco and h_rules and not bool(is_fin.loc[i]):
            h_vals.append(_lookup_step(row.get("fco_sobre_receita"), h_rules, 1.0))
        else:
            h_vals.append(1.0)

    out["f_caixa"] = f_vals
    out["g_alavancagem"] = g_vals
    out["h_fco"] = h_vals
    out["f_fin"] = out["f_caixa"] * out["g_alavancagem"] * out["h_fco"]

    # Taxa de captura: nem todo teto teórico se realiza (funil didático/metodológico)
    rho = float(pesos.get("rho_captura", 0.70))
    rho = min(max(rho, 0.0), 1.0)
    out["rho_captura"] = rho

    # OBJETIVO 2 — potencial viável (teto × F financeiro × ρ captura)
    out["obj2_potencial_viavel_rs"] = out["obj1_teto_rs"] * out["f_fin"] * rho
    out["obj2_viavel_pct_receita"] = (out["obj2_potencial_viavel_rs"] / rol) * 100
    out["obj2_desconto_financeiro_rs"] = out["obj1_teto_rs"] * (1.0 - out["f_fin"])
    out["obj2_desconto_captura_rs"] = out["obj1_teto_rs"] * out["f_fin"] * (1.0 - rho)
    out["obj2_desconto_total_rs"] = out["obj1_teto_rs"] - out["obj2_potencial_viavel_rs"]

    # Readiness R ∈ [0, 1]
    soft = out["software"].fillna(0) if "software" in out.columns else 0
    intang = out["intangivel"].fillna(0) if "intangivel" in out.columns else 0
    ativo = out["ativo_total"].replace(0, np.nan)
    r_bruto = (
        float(pesos.get("w_software", 0.5)) * (soft / ativo).fillna(0)
        + float(pesos.get("w_intangivel", 0.2)) * (intang / ativo).fillna(0)
    )
    out["readiness_bruto"] = r_bruto
    # readiness_modo:
    #   percentil → posição relativa no painel válido (0–1)            [padrão]
    #   escala    → r_bruto / quantil de referência (readiness_quantil_ref), clip 0–1
    #   bruto     → clip(r_bruto, 0, 1)  (razões Soft/Ativo ficam < 0,05 → Bloco C inerte)
    rmodo = str(pesos.get("readiness_modo", "percentil")).lower()
    out["readiness_modo"] = rmodo
    if rmodo == "percentil" and valid.sum() >= 5:
        r = pd.Series(np.nan, index=out.index)
        r.loc[valid] = r_bruto.loc[valid].rank(pct=True, method="average")
        # fora do painel: posição relativa à distribuição do painel
        ref = np.sort(r_bruto.loc[valid].to_numpy())
        r.loc[~valid] = np.searchsorted(ref, r_bruto.loc[~valid].to_numpy(), side="right") / len(ref)
        out["readiness"] = r.clip(0, 1)
    elif rmodo == "escala" and valid.sum() >= 5:
        q = float(pesos.get("readiness_quantil_ref", 0.90))
        ref = float(r_bruto.loc[valid].quantile(q))
        out["readiness"] = (r_bruto / ref).clip(0, 1) if ref > 0 else r_bruto.clip(0, 1)
    else:
        out["readiness"] = r_bruto.clip(0, 1)
    lam = float(pesos.get("lambda_ready", 0.10))

    # Execução: sem readiness não se realiza 100% do viável; R eleva até 1,0
    phi = float(pesos.get("phi_execucao_base", 0.85))
    phi = min(max(phi, 0.0), 1.0)
    # readiness efetiva levemente amplificada por λ (mantém papel do parâmetro)
    r_eff = (out["readiness"] * (1.0 + lam)).clip(0, 1)
    fator_exec = phi + (1.0 - phi) * r_eff
    out["phi_execucao_base"] = phi
    out["fator_execucao"] = fator_exec

    # OBJETIVO 3 — potencial final (viável × execução/readiness)
    out["obj3_potencial_final_rs"] = out["obj2_potencial_viavel_rs"] * fator_exec
    out["obj3_viavel_pct_receita"] = (out["obj3_potencial_final_rs"] / rol) * 100
    out["obj3_ajuste_execucao_rs"] = (
        out["obj3_potencial_final_rs"] - out["obj2_potencial_viavel_rs"]
    )
    # compatibilidade com colunas antigas da UI
    out["obj3_boost_readiness_rs"] = out["obj3_ajuste_execucao_rs"]

    # Score relativo (ranking) — usa a exposição winsorizada
    out["score_bruto"] = out["exposicao_score"] * out["f_fin"] * rho * fator_exec

    if pesos.get("normalizar_score_0_100", True):
        s = out.loc[valid, "score_bruto"]
        # normalizacao_score: minmax (padrão, documentado) | percentil
        nmodo = str(pesos.get("normalizacao_score", "minmax")).lower()
        if nmodo == "percentil" and len(s) > 1:
            out.loc[valid, "score_0_100"] = s.rank(pct=True, method="average") * 100
        elif len(s) > 1 and s.max() > s.min():
            out.loc[valid, "score_0_100"] = 100 * (s - s.min()) / (s.max() - s.min())
        else:
            out.loc[valid, "score_0_100"] = 50.0
        out.loc[~valid, "score_0_100"] = np.nan

        # Escalas 0–100 por objetivo (percentil no painel válido)
        for src, dst in [
            ("obj1_teto_rs", "obj1_0_100"),
            ("obj2_potencial_viavel_rs", "obj2_0_100"),
            ("obj3_potencial_final_rs", "obj3_0_100"),
            ("exposicao", "exposicao_0_100"),
        ]:
            out[dst] = np.nan
            if src in out.columns and valid.any():
                out.loc[valid, dst] = out.loc[valid, src].rank(pct=True, method="average") * 100
    else:
        out["score_0_100"] = out["score_bruto"]
        out["obj1_0_100"] = np.nan
        out["obj2_0_100"] = np.nan
        out["obj3_0_100"] = np.nan
        out["exposicao_0_100"] = np.nan

    # F financeiro já é 0–1 → escala 0–100 direta
    out["f_fin_0_100"] = out["f_fin"] * 100
    out["readiness_0_100"] = out["readiness"] * 100

    out = out.sort_values("score_0_100", ascending=False)
    out["rank"] = np.nan
    out.loc[out["valido"], "rank"] = range(1, int(out["valido"].sum()) + 1)

    return out
