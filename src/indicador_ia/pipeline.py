"""Pipeline v1: download → load → extract → score → export."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cvm_download import download_cadastro, download_dfp
from .cvm_load import load_all, load_cadastro
from .extract import build_firm_table, load_mapping
from .scoring import compute_scores, load_pesos


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
DATA = ROOT / "data"
OUTPUT = ROOT / "output"


def run(year: int = 2024, force_download: bool = False) -> pd.DataFrame:
    DATA.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"ExAnte-AI (B3) — pipeline v0.1 | DFP {year}")
    print("=" * 60)

    year_dir = download_dfp(year, DATA, force=force_download)

    mapping = load_mapping(CONFIG / "mapeamento_contas.yaml")
    pesos = load_pesos(CONFIG / "pesos.yaml")
    setor_cvm_path = CONFIG / "setor_cvm.yaml"
    setor_cvm_regras = (
        (load_mapping(setor_cvm_path) or {}).get("regras") if setor_cvm_path.exists() else None
    )

    cadastro = None
    if pesos.get("usar_setor_cvm", True):
        cad_path = download_cadastro(DATA, force=force_download)
        cadastro = load_cadastro(cad_path)
        if cadastro is None or cadastro.empty:
            print("  AVISO: sem cadastro CVM — setor só por heurística de nome")
            cadastro = None

    print("\nCarregando demonstrações...")
    data = load_all(
        year_dir,
        year,
        usar_consolidado=bool(pesos.get("usar_consolidado", True)),
        fallback_individual=bool(pesos.get("fallback_individual", True)),
    )

    print("\nExtraindo linhas contábeis...")
    firms = build_firm_table(
        data,
        mapping,
        setor_keywords=pesos.get("setor_keywords"),
        cadastro=cadastro,
        setor_cvm_regras=setor_cvm_regras,
    )
    print(f"  Empresas com ao menos uma conta: {len(firms)}")
    if "setor_fonte" in firms.columns:
        vc = firms["setor_fonte"].value_counts()
        print("  Setor por fonte: " + ", ".join(f"{k}={v}" for k, v in vc.items()))

    raw_path = OUTPUT / f"variaveis_firmas_{year}.csv"
    firms.to_csv(raw_path, encoding="utf-8-sig")
    print(f"  Variáveis salvas: {raw_path}")

    print("\nCalculando scores...")
    scored = compute_scores(firms, pesos)

    out_path = OUTPUT / f"ranking_ia_exante_{year}.csv"
    cols = [
        "rank", "DENOM_CIA", "setor", "setor_fonte", "setor_cvm", "categoria_cvm", "mercado_cvm",
        "origem_dfp", "template", "pdd_fonte", "score_0_100", "score_bruto",
        "obj1_teto_rs", "obj1_teto_pct_receita", "obj1_0_100",
        "obj2_potencial_viavel_rs", "obj2_viavel_pct_receita", "obj2_desconto_financeiro_rs", "obj2_0_100",
        "obj3_potencial_final_rs", "obj3_viavel_pct_receita", "obj3_boost_readiness_rs", "obj3_0_100",
        "exposicao", "exposicao_score", "exposicao_0_100",
        "f_fin", "f_fin_0_100", "f_caixa", "g_alavancagem", "h_fco",
        "readiness", "readiness_bruto", "readiness_0_100", "mult_setor",
        "rho_captura", "fator_execucao", "obj2_desconto_captura_rs", "obj2_desconto_total_rs",
        "obj3_ajuste_execucao_rs", "pessoal_modo", "fator_pessoal_liquido",
        "receita", "sga", "vendas", "pessoal", "cpv", "pdd", "estoques",
        "sga_afetavel", "vendas_afetavel", "cpv_afetavel", "pessoal_afetavel",
        "caixa", "divida_liquida", "ebitda", "ativo_total", "fco", "fco_sobre_receita",
        "valor_sga_rs", "valor_vendas_rs", "valor_pessoal_rs",
        "valor_cpv_rs", "valor_pdd_rs", "valor_estoques_rs",
        "contrib_sga", "contrib_vendas", "contrib_pessoal", "contrib_cpv",
        "contrib_pdd", "contrib_estoques",
        "caixa_sobre_ativo", "dl_sobre_ebitda", "alerta_receita", "valido",
    ]
    cols = [c for c in cols if c in scored.columns]
    scored[cols].to_csv(out_path, encoding="utf-8-sig")
    print(f"  Ranking salvo: {out_path}")

    valid = scored[scored["valido"]]
    print("\n" + "=" * 60)
    print(f"Empresas válidas: {len(valid)} / {len(scored)}")
    print("TOP 10 — potencial final (R$)")
    print("=" * 60)
    show_cols = [
        c for c in [
            "rank", "DENOM_CIA", "obj3_potencial_final_rs",
            "obj1_teto_rs", "obj2_potencial_viavel_rs", "score_0_100",
        ] if c in valid.columns
    ]
    show = valid.head(10)[show_cols]
    pd.set_option("display.max_colwidth", 42)
    pd.set_option("display.width", 140)
    pd.set_option("display.float_format", lambda x: f"{x:,.0f}" if abs(x) >= 1000 else f"{x:.2f}")
    print(show.to_string(index=False))

    setor_path = OUTPUT / f"media_setorial_{year}.csv"
    setor_avg = (
        valid.groupby("setor")
        .agg(
            n=("score_0_100", "count"),
            potencial_medio_rs=("obj3_potencial_final_rs", "mean"),
            score_medio=("score_0_100", "mean"),
            exposicao_media=("exposicao", "mean"),
        )
        .sort_values("potencial_medio_rs", ascending=False)
    )
    setor_avg.to_csv(setor_path, encoding="utf-8-sig")
    print(f"\nMédias setoriais: {setor_path}")
    print(setor_avg.to_string())

    return scored
