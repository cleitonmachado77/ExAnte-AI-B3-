"""Textos de zoom: como cada resultado do ExAnte-AI foi obtido."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent

# Linhas que entram no teto (rótulo UI → colunas do ranking)
LINHAS_TETO: dict[str, dict[str, str]] = {
    "SG&A": {
        "bruto": "sga",
        "afetavel": "sga_afetavel",
        "valor": "valor_sga_rs",
        "contrib": "contrib_sga",
        "alpha": "sga",
        "nome": "Despesas gerais e administrativas (SG&A)",
        "origem": "DRE — despesas administrativas / gerais",
    },
    "Vendas": {
        "bruto": "vendas",
        "afetavel": "vendas_afetavel",
        "valor": "valor_vendas_rs",
        "contrib": "contrib_vendas",
        "alpha": "vendas",
        "nome": "Despesas com vendas",
        "origem": "DRE — despesas com vendas",
    },
    "Pessoal": {
        "bruto": "pessoal",
        "afetavel": "pessoal_afetavel",
        "valor": "valor_pessoal_rs",
        "contrib": "contrib_pessoal",
        "alpha": "pessoal",
        "nome": "Pessoal (DVA)",
        "origem": "DVA 7.08.01 — remunerações, encargos e benefícios",
    },
    "CPV": {
        "bruto": "cpv",
        "afetavel": "cpv_afetavel",
        "valor": "valor_cpv_rs",
        "contrib": "contrib_cpv",
        "alpha": "cpv",
        "nome": "Custo dos produtos / serviços vendidos (CPV)",
        "origem": "DRE — custo dos produtos ou serviços vendidos",
    },
    "PDD": {
        "bruto": "pdd",
        "afetavel": "pdd",
        "valor": "valor_pdd_rs",
        "contrib": "contrib_pdd",
        "alpha": "pdd",
        "nome": "Provisão para devedores duvidosos (PDD)",
        "origem": "DRE ou DVA (fallback) — PDD / perdas com créditos",
    },
    "Estoques": {
        "bruto": "estoques",
        "afetavel": "estoques",
        "valor": "valor_estoques_rs",
        "contrib": "contrib_estoques",
        "alpha": "estoques",
        "nome": "Estoques",
        "origem": "Balanço — estoques",
    },
}


def _fmt_num(v, casas: int = 1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_money(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    x = float(v)
    sinal = "-" if x < 0 else ""
    x = abs(x)
    if x >= 1_000_000_000:
        return f"{sinal}R$ {x/1_000_000_000:,.2f} bi".replace(",", "X").replace(".", ",").replace("X", ".")
    if x >= 1_000_000:
        return f"{sinal}R$ {x/1_000_000:,.1f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if x >= 1_000:
        return f"{sinal}R$ {x/1_000:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {x:,.0f}".replace(",", ".")


def _fmt_pct(v, casas: int = 1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{float(v):.{casas}f}%".replace(".", ",")


def _safe(row: pd.Series, col: str, default: float | None = None) -> float | None:
    if col not in row.index:
        return default
    v = row[col]
    if pd.isna(v):
        return default
    return float(v)


def _missing(row: pd.Series, col: str) -> bool:
    if col not in row.index:
        return True
    return bool(pd.isna(row[col]))


def load_pesos() -> dict[str, Any]:
    path = ROOT / "config" / "pesos.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _alpha_efetivo(row: pd.Series, alpha_key: str, pesos: dict[str, Any]) -> float:
    """α efetivo ≈ α_base × mult_setor (limitado a alpha_max), com override PDD NF."""
    alpha = dict(pesos.get("alpha_base") or {})
    mult = _safe(row, "mult_setor", 1.0) or 1.0
    alpha_max = float(pesos.get("alpha_max", 0.60))
    base = float(alpha.get(alpha_key, 0.0))
    template = str(row.get("template", "")) if "template" in row.index else ""
    setor = str(row.get("setor", "")) if "setor" in row.index else ""
    is_fin = template == "financeiro" or setor == "financeiro"
    if alpha_key == "pdd" and not is_fin:
        nf = pesos.get("alpha_pdd_nao_financeiro")
        if nf is not None:
            base = float(nf)
    return min(base * mult, alpha_max)


def motivo_zero_linha(row: pd.Series, rotulo: str, meta: dict[str, str]) -> str:
    """Explica por que o potencial da linha é R$ 0 / 0% do teto."""
    template = str(row.get("template", "")) if "template" in row.index else ""
    bruto_col = meta["bruto"]
    modo = str(row.get("pessoal_modo", "")) if "pessoal_modo" in row.index else ""

    if template == "financeiro" and bruto_col in {"cpv", "vendas", "estoques"}:
        return (
            "Esta empresa usa **plano de contas de instituição financeira**. "
            f"A linha **{meta['nome']}** **não se aplica** nesse template "
            "(é anulada no mapeamento) — por isso o potencial é **R$ 0** e **0% do teto**."
        )

    if bruto_col == "pessoal" and modo == "excluir":
        return (
            "O parâmetro `pessoal_modo` está em **excluir**: a linha Pessoal é "
            "ignorada de propósito no teto → potencial **R$ 0**."
        )

    if _missing(row, bruto_col):
        return (
            f"A conta **{meta['nome']}** **não foi encontrada** na DFP desta companhia "
            f"({meta['origem']}). Sem valor contábil mapeado, a contribuição é **R$ 0**."
        )

    bruto = _safe(row, bruto_col, 0.0) or 0.0
    if abs(bruto) < 1e-9:
        return (
            f"A conta **{meta['nome']}** existe no mapeamento, mas o valor na DFP é "
            f"**R$ 0**. Sem base contábil, o potencial da linha é **0% do teto**."
        )

    afetavel_col = meta.get("afetavel", bruto_col)
    afetavel = _safe(row, afetavel_col, 0.0) or 0.0
    if abs(afetavel) < 1e-9 and abs(bruto) > 1e-9:
        return (
            f"Há valor bruto de **{_fmt_money(bruto)}** em {meta['nome']}, mas a "
            f"base **afetável** ficou **R$ 0** (ex.: netting de pessoal zerou a parcela "
            f"desta linha). Só a base afetável entra no teto."
        )

    return (
        f"O cálculo resultou em potencial nulo para **{meta['nome']}** "
        f"(base afetável × α ≈ 0)."
    )


def explicar_linha_teto(row: pd.Series, rotulo: str, pesos: dict[str, Any] | None = None) -> str:
    """Zoom de uma linha do quadro 'De onde vem o teto'."""
    pesos = pesos or load_pesos()
    meta = LINHAS_TETO[rotulo]
    receita = _safe(row, "receita")
    teto = _safe(row, "obj1_teto_rs", 0.0) or 0.0
    valor = _safe(row, meta["valor"], 0.0) or 0.0
    bruto = _safe(row, meta["bruto"])
    afetavel_col = meta.get("afetavel", meta["bruto"])
    afetavel = _safe(row, afetavel_col)
    alpha_eff = _alpha_efetivo(row, meta["alpha"], pesos)
    cap = float(pesos.get("max_linha_sobre_receita", 3.0))
    pct_teto = (100.0 * valor / teto) if teto else None
    mult = _safe(row, "mult_setor", 1.0)

    linhas = [
        f"### {rotulo} — {meta['nome']}",
        "",
        f"**Origem contábil:** {meta['origem']}",
        "",
        "#### Como o potencial desta linha é obtido",
        "",
        "```",
        f"base_afetável = |linha|  (após netting de pessoal, se aplicável)",
        f"base_capada   = min(base_afetável, {cap:g} × receita)",
        f"potencial R$  = base_capada × α_efetivo",
        f"α_efetivo     = min(α_base × mult_setor, α_max)",
        "```",
        "",
        "#### Números desta empresa",
        "",
        f"| Etapa | Valor |",
        f"|---|---|",
        f"| Receita (ROL) | {_fmt_money(receita)} |",
        f"| Valor bruto da linha | {_fmt_money(bruto) if bruto is not None else '— (não mapeado)'} |",
        f"| Base afetável | {_fmt_money(afetavel) if afetavel is not None else '—'} |",
        f"| Multiplicador setorial | {_fmt_num(mult, 2)} |",
        f"| α efetivo ({meta['alpha']}) | {_fmt_num(100 * alpha_eff, 1)}% |",
        f"| **Potencial desta linha** | **{_fmt_money(valor)}** |",
        f"| % do teto total | {_fmt_pct(pct_teto) if pct_teto is not None else '—'} |",
        f"| Teto total (soma das linhas) | {_fmt_money(teto)} |",
    ]

    if abs(valor) < 1e-6:
        linhas.extend(["", "#### Por que está em 0,0%?", "", motivo_zero_linha(row, rotulo, meta)])
    else:
        if receita and bruto is not None and abs(bruto) > 0:
            linhas.append(
                f"\nA linha representa **{_fmt_pct(100 * abs(bruto) / receita)}** da receita; "
                f"após α, contribui com **{_fmt_money(valor)}** para o teto."
            )

    if rotulo in {"SG&A", "Vendas", "CPV"}:
        fpl = _safe(row, "fator_pessoal_liquido")
        modo = str(row.get("pessoal_modo", "")) if "pessoal_modo" in row.index else ""
        if modo == "liquido" and fpl is not None and fpl < 0.999:
            linhas.extend(
                [
                    "",
                    "#### Netting de pessoal",
                    "",
                    f"Modo **líquido**: fator {_fmt_num(fpl, 3)} — a parcela de pessoal "
                    f"já embutida em CPV/SG&A/Vendas foi retirada destas linhas para evitar "
                    f"dupla contagem (entra só em Pessoal).",
                ]
            )

    return "\n".join(linhas)


def explicar_teto(row: pd.Series, pesos: dict[str, Any] | None = None) -> str:
    pesos = pesos or load_pesos()
    teto = _safe(row, "obj1_teto_rs", 0.0) or 0.0
    pct = _safe(row, "obj1_teto_pct_receita")
    partes = []
    for rotulo, meta in LINHAS_TETO.items():
        v = _safe(row, meta["valor"], 0.0) or 0.0
        if abs(v) > 1e-6:
            p = (100 * v / teto) if teto else 0.0
            partes.append(f"- **{rotulo}**: {_fmt_money(v)} ({_fmt_pct(p)} do teto)")
        else:
            partes.append(f"- **{rotulo}**: {_fmt_money(0)} — sem contribuição (veja zoom da linha)")

    return "\n".join(
        [
            "### Teto de eficiência — como foi obtido",
            "",
            "Ganho **máximo teórico** com IA sobre a estrutura de custos "
            "(ainda **sem** desconto financeiro F, taxa ρ nem readiness).",
            "",
            "```",
            "Teto = Σ_k  min(|linha_k afetável|, cap × receita) × α_k,setor",
            "```",
            "",
            f"**Resultado:** {_fmt_money(teto)}"
            + (f" (**{_fmt_pct(pct)}** da receita)" if pct is not None else ""),
            "",
            "#### Composição por linha",
            "",
            *partes,
            "",
            "Clique em cada linha do quadro ao lado para o detalhe (incluindo por que "
            "alguma linha pode estar em **0,0%**).",
        ]
    )


def explicar_viavel(row: pd.Series) -> str:
    teto = _safe(row, "obj1_teto_rs", 0.0) or 0.0
    viavel = _safe(row, "obj2_potencial_viavel_rs", 0.0) or 0.0
    f = _safe(row, "f_fin", 1.0) or 1.0
    f_c = _safe(row, "f_caixa", 1.0)
    g = _safe(row, "g_alavancagem", 1.0)
    h = _safe(row, "h_fco", 1.0)
    rho = _safe(row, "rho_captura", 0.70) or 0.70
    pct = _safe(row, "obj2_viavel_pct_receita")
    d_fin = _safe(row, "obj2_desconto_financeiro_rs")
    d_cap = _safe(row, "obj2_desconto_captura_rs")
    d_tot = _safe(row, "obj2_desconto_total_rs")
    template = str(row.get("template", "")) if "template" in row.index else ""

    return "\n".join(
        [
            "### Potencial viável — como foi obtido",
            "",
            "Parcela do teto que a empresa consegue **sustentar financeiramente**, "
            "já aplicando a taxa de captura ρ.",
            "",
            "```",
            "F = f(Caixa/Ativo) × g(DL/EBITDA) × h(FCO/Receita)",
            "Viável = Teto × F × ρ",
            "```",
            "",
            f"| Peça | Valor | Papel |",
            f"|---|---|---|",
            f"| Teto | {_fmt_money(teto)} | Ponto de partida |",
            f"| f (caixa) | {_fmt_num(f_c, 2)} | Liquidez |",
            f"| g (alavancagem) | {_fmt_num(g, 2)} | Dívida vs EBITDA"
            + (" *(fixo em financeiras)*" if template == "financeiro" else "")
            + " |",
            f"| h (FCO) | {_fmt_num(h, 2)} | Geração de caixa operacional |",
            f"| **F = f×g×h** | **{_fmt_num(f, 3)}** ({_fmt_num(100 * f, 0)}/100) | Capacidade financeira |",
            f"| ρ (captura) | {_fmt_pct(100 * rho, 0)} | Nem todo teto se realiza |",
            f"| **Viável** | **{_fmt_money(viavel)}** | "
            + (f"{_fmt_pct(pct)} da receita" if pct is not None else "—")
            + " |",
            "",
            f"Desconto vs teto: **{_fmt_money(d_tot)}** "
            f"(financeiro {_fmt_money(d_fin)} + captura {_fmt_money(d_cap)}).",
            "",
            _explicar_f_detalhe(row),
        ]
    )


def _explicar_f_detalhe(row: pd.Series) -> str:
    template = str(row.get("template", "")) if "template" in row.index else ""
    caixa_at = _safe(row, "caixa_sobre_ativo")
    dl_eb = _safe(row, "dl_sobre_ebitda")
    fco_r = _safe(row, "fco_sobre_receita")
    f_c = _safe(row, "f_caixa", 1.0)
    g = _safe(row, "g_alavancagem", 1.0)
    h = _safe(row, "h_fco", 1.0)
    ebitda = _safe(row, "ebitda")

    blocos = ["#### Detalhe de F", ""]
    if caixa_at is not None:
        blocos.append(
            f"- **Caixa/Ativo = {_fmt_pct(100 * caixa_at)}** → f = {_fmt_num(f_c, 2)} "
            f"(regras: &lt;3% → 0,75; &lt;8% → 0,90; senão 1,0)."
        )
    else:
        blocos.append(f"- Caixa/Ativo indisponível → f = {_fmt_num(f_c, 2)} (fallback).")

    if template == "financeiro":
        blocos.append(
            f"- **Financeira:** DL/EBITDA não se aplica → g fixo = {_fmt_num(g, 2)}."
        )
    elif ebitda is not None and ebitda <= 0:
        blocos.append(
            f"- EBITDA ≤ 0 → g = {_fmt_num(g, 2)} (penalidade de EBITDA negativo)."
        )
    elif dl_eb is not None:
        blocos.append(
            f"- **DL/EBITDA = {_fmt_num(dl_eb, 2)}** → g = {_fmt_num(g, 2)} "
            f"(regras: &lt;2 → 1,0; &lt;3,5 → 0,7; senão 0,4)."
        )
    else:
        blocos.append(f"- DL/EBITDA indisponível → g = {_fmt_num(g, 2)}.")

    if template == "financeiro" or fco_r is None:
        blocos.append(
            f"- FCO ausente ou financeira → h = {_fmt_num(h, 2)} (neutro)."
        )
    else:
        blocos.append(
            f"- **FCO/Receita = {_fmt_pct(100 * fco_r)}** → h = {_fmt_num(h, 2)} "
            f"(FCO negativo → 0,85; senão 1,0)."
        )
    return "\n".join(blocos)


def explicar_final(row: pd.Series) -> str:
    viavel = _safe(row, "obj2_potencial_viavel_rs", 0.0) or 0.0
    final = _safe(row, "obj3_potencial_final_rs", 0.0) or 0.0
    fator = _safe(row, "fator_execucao", 0.85) or 0.85
    r = _safe(row, "readiness")
    r100 = _safe(row, "readiness_0_100")
    r_bruto = _safe(row, "readiness_bruto")
    pct = _safe(row, "obj3_viavel_pct_receita")
    ajuste = _safe(row, "obj3_ajuste_execucao_rs")
    if ajuste is None:
        ajuste = _safe(row, "obj3_boost_readiness_rs")
    score = _safe(row, "score_0_100")

    return "\n".join(
        [
            "### Potencial final — como foi obtido",
            "",
            "Parcela do viável realizada após o **fator de execução** "
            "(readiness tecnológica / organizacional).",
            "",
            "```",
            "R_eff = clip(readiness × (1+λ), 0, 1)",
            "fator_execução = φ + (1−φ) × R_eff",
            "Final = Viável × fator_execução",
            "```",
            "",
            f"| Peça | Valor |",
            f"|---|---|",
            f"| Viável | {_fmt_money(viavel)} |",
            f"| Readiness bruto | {_fmt_num(r_bruto, 4) if r_bruto is not None else '—'} |",
            (
                f"| Readiness (0–1) | {_fmt_num(r, 3)} ({_fmt_num(r100, 1)}/100) |"
                if r is not None and r100 is not None
                else f"| Readiness (0–1) | {_fmt_num(r, 3) if r is not None else '—'} |"
            ),
            f"| Fator de execução | {_fmt_num(fator, 3)} |",
            f"| **Potencial final** | **{_fmt_money(final)}**"
            + (f" ({_fmt_pct(pct)} da receita)" if pct is not None else "")
            + " |",
            f"| Ajuste vs viável | {_fmt_money(ajuste)} |",
            f"| Índice 0–100 (ranking) | {_fmt_num(score, 1)} |",
            "",
            "O índice 0–100 é o **score relativo** no painel (min–max do score bruto), "
            "não um percentual da receita. **0** = menor score entre as válidas; "
            "**100** = maior — não significa potencial econômico zero.",
        ]
    )


def explicar_score(row: pd.Series, n_painel: int | None = None) -> str:
    score = _safe(row, "score_0_100")
    bruto = _safe(row, "score_bruto")
    expo = _safe(row, "exposicao_score")
    f = _safe(row, "f_fin")
    rho = _safe(row, "rho_captura")
    fator = _safe(row, "fator_execucao")
    rank = row.get("rank") if "rank" in row.index else None
    rank_txt = f"**{int(rank)}º**" if pd.notna(rank) else "—"
    painel_txt = f" de **{n_painel}**" if n_painel else ""

    zero_nota = ""
    if score is not None and abs(score) < 1e-9:
        zero_nota = (
            "\n\n> **Atenção:** índice **0** significa que esta empresa tem o "
            "**menor score bruto** do painel válido neste ano (normalização min–max). "
            "Não quer dizer que o potencial em R$ seja zero."
        )

    return "\n".join(
        [
            "### Índice 0–100 — como foi obtido",
            "",
            "```",
            "score_bruto = exposição_winsorizada × F × ρ × fator_execução",
            "score_0_100 = 100 × (score_bruto − min) / (max − min)   no painel válido",
            "```",
            "",
            f"| Peça | Valor |",
            f"|---|---|",
            f"| Exposição (winsorizada) | {_fmt_num(expo, 4) if expo is not None else '—'} |",
            f"| F | {_fmt_num(f, 3) if f is not None else '—'} |",
            f"| ρ | {_fmt_num(rho, 2) if rho is not None else '—'} |",
            f"| Fator execução | {_fmt_num(fator, 3) if fator is not None else '—'} |",
            f"| Score bruto | {_fmt_num(bruto, 6) if bruto is not None else '—'} |",
            f"| **Índice 0–100** | **{_fmt_num(score, 1)}** |",
            f"| Posição | {rank_txt}{painel_txt} |",
            zero_nota,
        ]
    )


def explicar_metrica(row: pd.Series, chave: str) -> str:
    """Zoom de métricas auxiliares (Caixa/Ativo, DL/EBITDA, FCO, mult_setor)."""
    template = str(row.get("template", "")) if "template" in row.index else ""

    if chave == "caixa_ativo":
        v = _safe(row, "caixa_sobre_ativo")
        f = _safe(row, "f_caixa")
        return "\n".join(
            [
                "### Caixa / Ativo",
                "",
                "```",
                "Caixa / Ativo total",
                "```",
                "",
                f"**Valor:** {_fmt_pct(100 * v) if v is not None else '—'}",
                f"→ alimenta **f** = {_fmt_num(f, 2)} no fator financeiro F.",
                "",
                "Regras: &lt; 3% → f=0,75; &lt; 8% → f=0,90; caso contrário f=1,0.",
            ]
        )

    if chave == "dl_ebitda":
        v = _safe(row, "dl_sobre_ebitda")
        g = _safe(row, "g_alavancagem")
        ebitda = _safe(row, "ebitda")
        if template == "financeiro":
            motivo = (
                "Instituição financeira: a métrica DL/EBITDA **não é usada** "
                f"(g fixo = {_fmt_num(g, 2)})."
            )
        elif ebitda is not None and ebitda <= 0:
            motivo = f"EBITDA ≤ 0 → g = {_fmt_num(g, 2)} (penalidade)."
        elif v is None:
            motivo = "DL/EBITDA indisponível (dívida ou EBITDA não mapeados)."
        else:
            motivo = (
                f"**DL/EBITDA = {_fmt_num(v, 2)}** → g = {_fmt_num(g, 2)}. "
                "Regras: &lt;2 → 1,0; &lt;3,5 → 0,7; senão 0,4."
            )
        return "\n".join(
            [
                "### Dívida líquida / EBITDA",
                "",
                "```",
                "DL = Dívida − Caixa",
                "g = função degrau de (DL / EBITDA)",
                "```",
                "",
                motivo,
            ]
        )

    if chave == "fco_receita":
        v = _safe(row, "fco_sobre_receita")
        h = _safe(row, "h_fco")
        if template == "financeiro" or v is None:
            motivo = (
                f"Sem DFC aplicável ou empresa financeira → h = {_fmt_num(h, 2)} (neutro)."
            )
        else:
            motivo = (
                f"**FCO/Receita = {_fmt_pct(100 * v)}** → h = {_fmt_num(h, 2)}. "
                "FCO negativo reduz h para 0,85."
            )
        return "\n".join(
            [
                "### FCO / Receita",
                "",
                "Fluxo de caixa operacional (DFC 6.01) em razão da receita. "
                "Alimenta o fator **h** dentro de F.",
                "",
                motivo,
            ]
        )

    if chave == "mult_setor":
        mult = _safe(row, "mult_setor", 1.0)
        setor = str(row.get("setor", "—")) if "setor" in row.index else "—"
        return "\n".join(
            [
                "### Multiplicador setorial",
                "",
                f"Setor classificado: **{setor}** → mult = **{_fmt_num(mult, 2)}**.",
                "",
                "Escala o α de cada linha: `α_efetivo = min(α_base × mult, α_max)`. "
                "Setores com maior exposição ocupacional a IA têm mult &gt; 1.",
            ]
        )

    return "Sem explicação cadastrada para esta métrica."


def explicar_comparativo_linha(
    rotulo: str,
    row_empresa: pd.Series,
    peers: pd.DataFrame,
    df: pd.DataFrame,
) -> str:
    """Zoom de uma linha do quadro Comparativo."""
    if rotulo.startswith("Empresa"):
        final = _safe(row_empresa, "obj3_potencial_final_rs")
        score = _safe(row_empresa, "score_0_100")
        pct = _safe(row_empresa, "obj3_viavel_pct_receita")
        return "\n".join(
            [
                "### Comparativo — esta empresa",
                "",
                f"- Potencial final: **{_fmt_money(final)}**",
                f"- Índice 0–100: **{_fmt_num(score, 1)}**",
                f"- % da receita: **{_fmt_pct(pct)}**",
                "",
                "São os mesmos números do funil (Obj3) e do ranking, "
                "exibidos aqui para contraste com médias.",
            ]
        )

    if "setor" in rotulo.lower() or rotulo.startswith("Média setor"):
        n = len(peers)
        return "\n".join(
            [
                "### Comparativo — média do setor",
                "",
                f"Média aritmética das **{n}** empresas válidas do mesmo setor "
                f"(**{row_empresa.get('setor', '—')}**).",
                "",
                f"- Potencial final médio: **{_fmt_money(peers['obj3_potencial_final_rs'].mean())}**",
                f"- Índice médio: **{_fmt_num(peers['score_0_100'].mean(), 1)}**",
                f"- % receita médio: **{_fmt_pct(peers['obj3_viavel_pct_receita'].mean())}**",
            ]
        )

    return "\n".join(
        [
            "### Comparativo — média do painel",
            "",
            f"Média aritmética das **{len(df)}** empresas válidas do ano.",
            "",
            f"- Potencial final médio: **{_fmt_money(df['obj3_potencial_final_rs'].mean())}**",
            f"- Índice médio: **{_fmt_num(df['score_0_100'].mean(), 1)}**",
            f"- % receita médio: **{_fmt_pct(df['obj3_viavel_pct_receita'].mean())}**",
        ]
    )


def explicar_linha_bruta(row: pd.Series, label: str, col: str) -> str:
    val = _safe(row, col)
    receita = _safe(row, "receita")
    if _missing(row, col):
        return (
            f"### {label}\n\nConta **não mapeada** nesta DFP "
            f"(coluna `{col}` ausente ou vazia). "
            "No cálculo, valores ausentes em linhas de custo tendem a contribuir **0** "
            "para o teto."
        )
    pct = ""
    if receita and abs(receita) > 0 and col not in {"receita", "ativo_total", "caixa", "divida_liquida", "ebitda", "fco"}:
        pct = f"\n\nEquivale a **{_fmt_pct(100 * abs(val) / receita)}** da receita."
    return (
        f"### {label}\n\n"
        f"**Valor na DFP:** {_fmt_money(val)}{pct}\n\n"
        f"Campo interno: `{col}`. Este é o input contábil bruto antes de α, F e ρ."
    )


def explicar_empresa_resumo(row: pd.Series, n_painel: int | None = None) -> str:
    """Resumo completo para zoom a partir do ranking / pares."""
    nome = str(row.get("DENOM_CIA", "Empresa"))
    partes = [
        f"## {nome}",
        "",
        explicar_teto(row),
        "",
        "---",
        "",
        explicar_viavel(row),
        "",
        "---",
        "",
        explicar_final(row),
        "",
        "---",
        "",
        explicar_score(row, n_painel=n_painel),
    ]
    return "\n".join(partes)
