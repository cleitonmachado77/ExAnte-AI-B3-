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


def compute_scores(df: pd.DataFrame, pesos: dict[str, Any]) -> pd.DataFrame:
    out = df.copy()
    alpha = pesos["alpha_base"]
    setor_mult = pesos.get("setor_mult", {})
    alpha_max = float(pesos.get("alpha_max", 0.60))
    min_receita = float(pesos.get("min_receita", 50_000_000.0))

    out["mult_setor"] = out["setor"].map(
        lambda s: float(setor_mult.get(s, setor_mult.get("outros", 1.0)))
    )

    def a(name: str) -> pd.Series:
        base = float(alpha.get(name, 0.0))
        return (base * out["mult_setor"]).clip(upper=alpha_max)

    rol = out["receita"].replace(0, np.nan)
    cap = float(pesos.get("max_linha_sobre_receita", 3.0))

    expo = pd.Series(0.0, index=out.index)
    teto_rs = pd.Series(0.0, index=out.index)

    def add_line(col: str, alpha_name: str):
        nonlocal expo, teto_rs
        if col not in out.columns:
            out[f"contrib_{alpha_name}"] = np.nan
            out[f"valor_{alpha_name}_rs"] = np.nan
            return
        # base afetável em R$ = min(|L|, cap * ROL) * α
        base_rs = out[col].fillna(0).abs().clip(upper=(cap * rol))
        alpha_s = a(alpha_name)
        valor_rs = base_rs * alpha_s
        ratio = (out[col].fillna(0).abs() / rol).clip(upper=cap)
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

    # F^fin = f * g
    caixa_ativo = out["caixa"].fillna(0) / out["ativo_total"].replace(0, np.nan)
    out["caixa_sobre_ativo"] = caixa_ativo
    dl_ebitda = out["divida_liquida"] / out["ebitda"].replace(0, np.nan)
    out["dl_sobre_ebitda"] = dl_ebitda

    f_vals, g_vals = [], []
    for _, row in out.iterrows():
        f_vals.append(_lookup_step(row.get("caixa_sobre_ativo"), pesos["f_caixa"], 1.0))
        ebitda = row.get("ebitda")
        if ebitda is None or (isinstance(ebitda, float) and (np.isnan(ebitda) or ebitda <= 0)):
            g_vals.append(float(pesos.get("g_ebitda_negativo", 0.25)))
        else:
            g_vals.append(
                _lookup_step(row.get("dl_sobre_ebitda"), pesos["g_alavancagem"], 0.40)
            )

    out["f_caixa"] = f_vals
    out["g_alavancagem"] = g_vals
    out["f_fin"] = out["f_caixa"] * out["g_alavancagem"]

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
    r = (
        float(pesos.get("w_software", 0.5)) * (soft / ativo).fillna(0)
        + float(pesos.get("w_intangivel", 0.2)) * (intang / ativo).fillna(0)
    )
    out["readiness"] = r.clip(0, 1)
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

    # Score relativo (ranking)
    out["score_bruto"] = out["exposicao"] * out["f_fin"] * rho * fator_exec

    # Filtro de qualidade
    out["valido"] = (
        out["receita"].fillna(0).abs() >= min_receita
    ) & out["exposicao"].notna() & (out["exposicao"] > 0)

    if pesos.get("excluir_recuperacao_judicial", True) and "DENOM_CIA" in out.columns:
        rj = out["DENOM_CIA"].astype(str).str.upper().str.contains("RECUPERA", na=False)
        out.loc[rj, "valido"] = False

    req = pesos.get("exigir_ao_menos_uma_de", [])
    if req:
        present = [c for c in req if c in out.columns]
        if present:
            mask_cost = out[present].fillna(0).abs().sum(axis=1) > 0
            out.loc[~mask_cost, "valido"] = False

    if pesos.get("normalizar_score_0_100", True):
        valid = out["valido"]
        s = out.loc[valid, "score_bruto"]
        if len(s) > 1 and s.max() > s.min():
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
