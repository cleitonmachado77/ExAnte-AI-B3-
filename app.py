"""
Interface web do ExAnte-AI (B3).
Execute: streamlit run app.py
"""

from __future__ import annotations

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from config_ui import pagina_config
from explicacoes import (
    explicar_comparativo_linha,
    explicar_empresa_resumo,
    explicar_final,
    explicar_linha_bruta,
    explicar_linha_teto,
    explicar_metrica,
    explicar_score,
    explicar_teto,
    explicar_viavel,
    load_pesos,
)

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
PRODUCT_NAME = "ExAnte-AI (B3)"


def _zoom_popover(label: str, markdown: str, *, key: str | None = None) -> None:
    """Botão-popup com a explicação de como o resultado foi obtido."""
    with st.popover(label, help="Clique para ver como este resultado foi obtido"):
        st.markdown(markdown)

st.set_page_config(
    page_title=f"{PRODUCT_NAME}",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Remove chrome de desenvolvimento do Streamlit
st.markdown(
    """
    <style>
      [data-testid="stSidebar"],
      [data-testid="stSidebarCollapsedControl"],
      [data-testid="collapsedControl"] {
        display: none !important;
      }
      .stAppDeployButton,
      [data-testid="stStatusWidget"],
      [data-testid="stToolbar"],
      .stAppToolbar {
        display: none !important;
      }
      header[data-testid="stHeader"] {
        background: transparent !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def fmt_num(v, casas: int = 1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_money(v) -> str:
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


def fmt_pct(v, casas: int = 1) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{float(v):.{casas}f}%".replace(".", ",")


def safe(row, col, default=0.0):
    if col not in row.index:
        return default
    v = row[col]
    if pd.isna(v):
        return default
    return float(v)


def has_objetivos(df: pd.DataFrame) -> bool:
    need = [
        "obj1_teto_rs", "obj1_0_100",
        "obj2_potencial_viavel_rs", "obj2_0_100",
        "obj3_potencial_final_rs",
        "rho_captura", "fator_execucao",
    ]
    return all(c in df.columns for c in need)


@st.cache_data
def list_years() -> list[int]:
    years = []
    for p in OUTPUT.glob("ranking_ia_exante_*.csv"):
        try:
            years.append(int(p.stem.split("_")[-1]))
        except ValueError:
            pass
    return sorted(years, reverse=True)


@st.cache_data
def load_ranking(year: int, _mtime: float) -> pd.DataFrame:
    path = OUTPUT / f"ranking_ia_exante_{year}.csv"
    df = pd.read_csv(path)
    # normaliza coluna valido (bool ou string)
    if "valido" in df.columns:
        v = df["valido"]
        if v.dtype == object:
            df = df[v.astype(str).str.lower().isin(["true", "1", "sim"])].copy()
        else:
            df = df[v == True].copy()  # noqa: E712
    if "rank" in df.columns:
        df = df.sort_values("rank")
    return df.reset_index(drop=True)


@st.cache_data
def load_setor(year: int, _mtime: float = 0.0) -> pd.DataFrame | None:
    path = OUTPUT / f"media_setorial_{year}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path)


def _card_objetivo(
    nome: str,
    pergunta: str,
    rs: float,
    pct: float,
    pct_label: str,
    ajuste: str,
) -> str:
    return f"""
<div style="
  border:1px solid rgba(128,128,128,0.35);
  border-radius:12px;
  padding:1rem 1.1rem;
  height:100%;
  box-sizing:border-box;
">
  <div style="font-weight:700;font-size:1.35rem;margin-bottom:0.45rem;">{nome}</div>
  <div style="opacity:0.78;font-size:0.84rem;line-height:1.35;min-height:2.7rem;margin-bottom:0.85rem;">
    {pergunta}
  </div>
  <div style="font-size:1.85rem;line-height:1.15;margin-bottom:0.55rem;font-weight:700;">
    {fmt_money(rs)}
  </div>
  <div style="font-size:1.25rem;margin-bottom:0.75rem;">
    <span style="font-weight:700;">{fmt_pct(pct)}</span>
    <span style="opacity:0.7;font-size:1rem;"> da receita</span>
    <span style="opacity:0.55;font-size:0.9rem;"> · {pct_label}</span>
  </div>
  <div style="
    opacity:0.8;font-size:0.8rem;line-height:1.4;
    border-top:1px solid rgba(128,128,128,0.28);
    padding-top:0.55rem;
  ">{ajuste}</div>
</div>
"""


def _formula(
    passo: str,
    nome: str,
    latex: str,
    faz: str,
    serve: str,
    produz: str,
) -> None:
    """Cartão padrão da aba Sobre: fórmula, o que ela calcula e por que existe."""
    with st.container(border=True):
        st.markdown(f"**{passo} · {nome}**")
        st.latex(latex)
        st.markdown(f"**Faz:** {faz}")
        st.markdown(f"**Serve para:** {serve}")
        st.caption(f"Produz: {produz}")


def pagina_empresa(df: pd.DataFrame, year: int) -> None:
    st.subheader("Análise personalizada da empresa")
    st.caption(
        "Funil Teto → Viável → Final em R$ e % da receita."
    )

    if not has_objetivos(df):
        st.error(
            f"Os dados de {year} estão desatualizados (faltam campos do funil ρ/φ). "
            f"No terminal, rode: `python main.py --year {year}` e atualize esta página."
        )
        st.cache_data.clear()
        return

    nomes = df["DENOM_CIA"].astype(str).tolist()
    sel_col, _ = st.columns([1.2, 2.8])
    with sel_col:
        escolhida = st.selectbox(
            "Empresa",
            nomes,
            index=0,
            key="empresa_selecionada",
        )
    row = df[df["DENOM_CIA"] == escolhida].iloc[0]
    setor = str(row.get("setor", "outros"))
    peers = df[df["setor"] == setor]
    pesos = load_pesos()
    n_painel = len(df)

    rank_val = row.get("rank")
    if pd.notna(rank_val) and n_painel > 0:
        rank_i = int(rank_val)
        st.markdown(
            """
<style>
/* Popovers de zoom: azul pequeno; ranking ao lado do nome um pouco maior */
div[data-testid="stPopover"] button {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  min-height: 0 !important;
  height: auto !important;
  justify-content: flex-start !important;
}
div[data-testid="stPopover"] button p {
  color: #2563eb !important;
  font-weight: 500 !important;
  font-size: 0.8rem !important;
  line-height: 1.25 !important;
  margin: 0 !important;
}
div[data-testid="stPopover"] button svg {
  display: none !important;
}
div[data-testid="stHorizontalBlock"]:has(h3):has(div[data-testid="stPopover"]) {
  align-items: baseline !important;
  flex-wrap: wrap !important;
  gap: 0.85rem !important;
}
div[data-testid="stHorizontalBlock"]:has(h3):has(div[data-testid="stPopover"]) > div[data-testid="column"] {
  width: auto !important;
  flex: 0 1 auto !important;
  min-width: fit-content !important;
}
div[data-testid="stHorizontalBlock"]:has(h3):has(div[data-testid="stPopover"]) h3 {
  margin: 0 !important;
  padding: 0 !important;
}
div[data-testid="stHorizontalBlock"]:has(h3):has(div[data-testid="stPopover"]) div[data-testid="stPopover"] button p {
  font-size: 1.05rem !important;
  font-weight: 600 !important;
}
</style>
            """,
            unsafe_allow_html=True,
        )
        nome_col, rank_col = st.columns([1, 1])
        with nome_col:
            st.markdown(f"### {escolhida}")
        with rank_col:
            score_i = safe(row, "score_0_100")
            final_i = safe(row, "obj3_potencial_final_rs")
            pct_rec = safe(row, "obj3_viavel_pct_receita")
            peers_sorted = peers.sort_values("score_0_100", ascending=False).reset_index(drop=True)
            if escolhida in peers_sorted["DENOM_CIA"].astype(str).values:
                pos_setor = int(peers_sorted.index[peers_sorted["DENOM_CIA"] == escolhida][0]) + 1
            else:
                pos_setor = None
            n_setor = len(peers)
            if rank_i == 1:
                faixa = "no topo do painel"
            elif rank_i <= max(1, int(round(n_painel * 0.10))):
                faixa = "entre as 10% melhores"
            elif rank_i <= max(1, int(round(n_painel * 0.25))):
                faixa = "no primeiro quartil"
            elif rank_i <= max(1, int(round(n_painel * 0.50))):
                faixa = "na metade superior"
            else:
                faixa = "na metade inferior"
            setor_txt = (
                f"No setor **{setor}**, ocupa a **{pos_setor}ª** posição "
                f"entre {n_setor} empresas."
                if pos_setor is not None and n_setor > 0
                else f"Setor classificado: **{setor}**."
            )
            with st.popover(f"{rank_i}º de {n_painel}"):
                st.markdown(
                    f"""
**{escolhida}** — **{rank_i}º de {n_painel}**

No índice ExAnte-AI (B3) da DFP **{year}**, esta companhia ocupa a
**{rank_i}ª posição** entre as **{n_painel}** válidas — {faixa} —, com score
**{fmt_num(score_i, 1)}/100** e potencial final estimado de
**{fmt_money(final_i)}** (**{fmt_num(pct_rec, 2)}%** da receita).
A ordenação usa o score 0–100 (1º = melhor).

{setor_txt}
"""
                )
    else:
        st.markdown(f"### {escolhida}")
    template = str(row.get("template", "padrao")) if "template" in row.index else "padrao"
    fonte_map = {"cvm": "cadastro CVM", "nome": "heurística por nome", "template": "plano de contas", "padrao": "sem regra → outros"}
    setor_fonte = str(row.get("setor_fonte", "")) if "setor_fonte" in row.index else ""
    setor_cvm = row.get("setor_cvm") if "setor_cvm" in row.index else None
    extras = []
    if setor_fonte in fonte_map:
        extras.append(f"fonte do setor: {fonte_map[setor_fonte]}")
    if isinstance(setor_cvm, str) and setor_cvm.strip() and setor_cvm.lower() != "nan":
        extras.append(f"SETOR_ATIV CVM: {setor_cvm}")
    for k, lbl in [("categoria_cvm", ""), ("mercado_cvm", ""), ("origem_dfp", "DFP")]:
        v = row.get(k) if k in row.index else None
        if isinstance(v, str) and v.strip() and v.lower() != "nan":
            extras.append(f"{lbl + ' ' if lbl else ''}{v}")
    st.markdown(
        f"Setor: **{setor}** · DFP **{year}** · "
        f"CD_CVM: `{row.get('CD_CVM', '—')}` · Receita: **{fmt_money(row.get('receita'))}**"
        + (" · Plano de contas: **instituição financeira**" if template == "financeiro" else "")
    )
    if extras:
        st.caption(" · ".join(extras))
    if "alerta_receita" in row.index and str(row.get("alerta_receita")).lower() in {"true", "1"}:
        st.warning(
            "Receita da DRE muito abaixo das receitas da DVA (7.01) — a DFP desta companhia "
            "pode estar inconsistente; os percentuais sobre a receita devem ser lidos com cautela."
        )

    # -------- 3 OBJETIVOS (bloco principal) --------
    teto_rs = safe(row, "obj1_teto_rs")
    viavel_rs = safe(row, "obj2_potencial_viavel_rs")
    final_rs = safe(row, "obj3_potencial_final_rs")
    f_fin = safe(row, "f_fin", 1.0)
    readiness = safe(row, "readiness_0_100")
    desconto_fin = safe(row, "obj2_desconto_financeiro_rs")
    desconto_cap = safe(row, "obj2_desconto_captura_rs")
    desconto_tot = safe(row, "obj2_desconto_total_rs")
    ajuste_exec = safe(row, "obj3_ajuste_execucao_rs")
    if ajuste_exec == 0.0 and "obj3_boost_readiness_rs" in row.index:
        ajuste_exec = safe(row, "obj3_boost_readiness_rs")
    rho = safe(row, "rho_captura", 0.70)
    if rho <= 0:
        rho = 0.70
    fator_exec = safe(row, "fator_execucao", 0.85)
    if fator_exec <= 0:
        fator_exec = 0.85

    objetivos = [
        {
            "nome": "Teto de eficiência",
            "pergunta": "Ganho máximo teórico com IA sobre a estrutura de custos.",
            "rs": teto_rs,
            "pct": safe(row, "obj1_teto_pct_receita"),
            "pct_label": "ganho máximo estimado",
            "ajuste": "Ponto de partida do funil (ainda sem F, ρ nem execução).",
            "explicacao": explicar_teto(row, pesos),
            "zoom_label": "Como o teto foi obtido?",
        },
        {
            "nome": "Potencial viável",
            "pergunta": "Parcela do teto capturável dado caixa/dívida e a taxa de captura ρ.",
            "rs": viavel_rs,
            "pct": safe(row, "obj2_viavel_pct_receita"),
            "pct_label": "ganho viável estimado",
            "ajuste": (
                f"F = {fmt_num(100 * f_fin, 0)}/100 "
                f"(f {fmt_num(safe(row, 'f_caixa', 1.0), 2)} · g {fmt_num(safe(row, 'g_alavancagem', 1.0), 2)} · "
                f"h {fmt_num(safe(row, 'h_fco', 1.0), 2)}) · ρ = {fmt_num(100 * rho, 0)}% · "
                f"desconto total vs teto: {fmt_money(desconto_tot)} "
                f"(financeiro {fmt_money(desconto_fin)} + captura {fmt_money(desconto_cap)})"
            ),
            "explicacao": explicar_viavel(row),
            "zoom_label": "Como o viável foi obtido?",
        },
        {
            "nome": "Potencial final",
            "pergunta": "Parcela do viável realizada após o fator de execução/readiness.",
            "rs": final_rs,
            "pct": safe(row, "obj3_viavel_pct_receita"),
            "pct_label": "ganho final estimado",
            "ajuste": (
                f"Readiness = {fmt_num(readiness, 1)}/100 · "
                f"fator execução = {fmt_num(fator_exec, 2)} · "
                f"ajuste vs viável: {fmt_money(ajuste_exec)} · "
                f"score: {fmt_num(safe(row, 'score_0_100'), 1)}/100"
            ),
            "explicacao": explicar_final(row),
            "zoom_label": "Como o final foi obtido?",
        },
    ]

    cols = st.columns(3)
    for col, o in zip(cols, objetivos):
        with col:
            card_kwargs = {k: v for k, v in o.items() if k not in {"explicacao", "zoom_label"}}
            st.markdown(_card_objetivo(**card_kwargs), unsafe_allow_html=True)
            _zoom_popover(o["zoom_label"], o["explicacao"])

    with st.popover("Como o índice 0–100 foi obtido?"):
        st.markdown(explicar_score(row, n_painel=n_painel))

    # Funil visual dos 3 objetivos
    st.markdown("#### Funil de valor (R$)")
    st.caption("Clique em cada etapa abaixo do gráfico para o zoom do cálculo.")

    funil_df = pd.DataFrame(
        {
            "Etapa": [
                "1. Teto de eficiência",
                "2. Potencial viável",
                "3. Potencial final",
            ],
            "Valor_R$": [
                safe(row, "obj1_teto_rs"),
                safe(row, "obj2_potencial_viavel_rs"),
                safe(row, "obj3_potencial_final_rs"),
            ],
        }
    )
    funil_df["Etapa"] = pd.Categorical(
        funil_df["Etapa"],
        categories=[
            "1. Teto de eficiência",
            "2. Potencial viável",
            "3. Potencial final",
        ],
        ordered=True,
    )
    funil_chart = (
        alt.Chart(funil_df)
        .mark_bar(size=18, cornerRadiusEnd=3)
        .encode(
            x=alt.X(
                "Valor_R$:Q",
                title="R$",
                axis=alt.Axis(format="~s"),
            ),
            y=alt.Y(
                "Etapa:N",
                sort=[
                    "1. Teto de eficiência",
                    "2. Potencial viável",
                    "3. Potencial final",
                ],
                title=None,
            ),
            color=alt.Color(
                "Etapa:N",
                legend=None,
                scale=alt.Scale(
                    domain=[
                        "1. Teto de eficiência",
                        "2. Potencial viável",
                        "3. Potencial final",
                    ],
                    range=["#1f3a5f", "#3d6b9a", "#6fa8dc"],
                ),
            ),
            tooltip=[
                alt.Tooltip("Etapa:N", title="Etapa"),
                alt.Tooltip("Valor_R$:Q", title="R$", format=",.0f"),
            ],
        )
        .properties(height=160)
    )
    st.altair_chart(funil_chart, use_container_width=True)
    f1, f2, f3 = st.columns(3)
    with f1:
        _zoom_popover("Zoom: Teto", explicar_teto(row, pesos))
    with f2:
        _zoom_popover("Zoom: Viável", explicar_viavel(row))
    with f3:
        _zoom_popover("Zoom: Final", explicar_final(row))

    # De onde vem o valor
    st.markdown("#### De onde vem o teto (R$ por linha contábil)")
    st.caption(
        "Clique em uma **linha** da tabela para abrir o zoom — inclusive quando o valor for **0,0%**."
    )
    origem = pd.Series(
        {
            "SG&A": safe(row, "valor_sga_rs"),
            "Vendas": safe(row, "valor_vendas_rs"),
            "Pessoal": safe(row, "valor_pessoal_rs"),
            "CPV": safe(row, "valor_cpv_rs"),
            "PDD": safe(row, "valor_pdd_rs"),
            "Estoques": safe(row, "valor_estoques_rs"),
        },
        name="R$ potencial",
    )
    c_a, c_b = st.columns([1.2, 1])
    with c_a:
        st.bar_chart(origem)
    with c_b:
        detalhe = pd.DataFrame(
            {
                "Linha": list(origem.index),
                "Potencial R$": [fmt_money(v) for v in origem.values],
                "% do teto": [
                    fmt_pct(100 * v / safe(row, "obj1_teto_rs"))
                    if safe(row, "obj1_teto_rs")
                    else "—"
                    for v in origem.values
                ],
            }
        )
        evento_teto = st.dataframe(
            detalhe,
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"zoom_teto_{escolhida}",
        )
        sel_teto = evento_teto.selection.rows if evento_teto and evento_teto.selection else []
        if sel_teto:
            rotulo = str(detalhe.iloc[sel_teto[0]]["Linha"])
            with st.container(border=True):
                st.markdown(explicar_linha_teto(row, rotulo, pesos))
        st.caption("Atalhos de zoom por linha:")
        zcols = st.columns(3)
        for i, rotulo in enumerate(origem.index):
            with zcols[i % 3]:
                _zoom_popover(
                    f"Zoom: {rotulo}",
                    explicar_linha_teto(row, rotulo, pesos),
                )
    fpl = row.get("fator_pessoal_liquido") if "fator_pessoal_liquido" in row.index else None
    if fpl is not None and pd.notna(fpl) and float(fpl) < 0.999:
        st.caption(
            f"Pessoal (DVA) = {fmt_pct(100 * (1 - float(fpl)))} de CPV + SG&A + vendas. Essa parcela foi "
            f"retirada dessas três linhas (fator {fmt_num(float(fpl), 2)}) e entra só na linha Pessoal — "
            "sem dupla contagem."
        )

    # Comparativo
    st.markdown("#### Comparativo")
    st.caption("Clique em uma linha para ver de onde vêm os números.")
    peers_sorted = peers.sort_values("score_0_100", ascending=False).reset_index(drop=True)
    pos_setor = int(peers_sorted.index[peers_sorted["DENOM_CIA"] == escolhida][0]) + 1
    comp = pd.DataFrame(
        {
            "Referência": ["Empresa", f"Média setor ({setor})", "Média painel"],
            "Potencial final (R$)": [
                fmt_money(row.get("obj3_potencial_final_rs")),
                fmt_money(peers["obj3_potencial_final_rs"].mean())
                if "obj3_potencial_final_rs" in peers.columns
                else "—",
                fmt_money(df["obj3_potencial_final_rs"].mean())
                if "obj3_potencial_final_rs" in df.columns
                else "—",
            ],
            "Índice 0–100": [
                fmt_num(row.get("score_0_100"), 1),
                fmt_num(peers["score_0_100"].mean(), 1),
                fmt_num(df["score_0_100"].mean(), 1),
            ],
            "% da receita": [
                fmt_pct(row.get("obj3_viavel_pct_receita")),
                fmt_pct(peers["obj3_viavel_pct_receita"].mean())
                if "obj3_viavel_pct_receita" in peers.columns
                else "—",
                fmt_pct(df["obj3_viavel_pct_receita"].mean())
                if "obj3_viavel_pct_receita" in df.columns
                else "—",
            ],
        }
    )
    evento_comp = st.dataframe(
        comp,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"zoom_comp_{escolhida}",
    )
    sel_comp = evento_comp.selection.rows if evento_comp and evento_comp.selection else []
    if sel_comp:
        ref = str(comp.iloc[sel_comp[0]]["Referência"])
        st.markdown(explicar_comparativo_linha(ref, row, peers, df))
    st.caption(f"Posição no setor: #{pos_setor} / {len(peers)}")

    # Linhas brutas
    with st.expander("Ver linhas contábeis brutas usadas no cálculo", expanded=True):
        st.caption("Clique em uma linha para o zoom do valor contábil.")
        receita = safe(row, "receita")
        linhas = [
            ("Receita (ROL)", "receita", False),
            ("SG&A", "sga", True),
            ("Despesas com vendas", "vendas", True),
            ("Pessoal (DVA)", "pessoal", True),
            ("CPV", "cpv", True),
            ("PDD", "pdd", True),
            ("Estoques", "estoques", True),
            ("Caixa", "caixa", False),
            ("Dívida líquida", "divida_liquida", False),
            ("EBITDA (proxy)", "ebitda", False),
            ("FCO (DFC 6.01)", "fco", False),
            ("Ativo total", "ativo_total", False),
        ]
        rows_tab = []
        for label, col, as_pct in linhas:
            val = row[col] if col in row.index else float("nan")
            if pd.isna(val):
                rows_tab.append({"Linha": label, "Valor": "—", "% da receita": "—", "_col": col})
            else:
                pct = f"{100 * abs(float(val)) / receita:.1f}%" if as_pct and receita else "—"
                rows_tab.append(
                    {"Linha": label, "Valor": fmt_money(val), "% da receita": pct, "_col": col}
                )
        tab_brutas = pd.DataFrame(rows_tab)
        evento_brutas = st.dataframe(
            tab_brutas[["Linha", "Valor", "% da receita"]],
            hide_index=True,
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"zoom_brutas_{escolhida}",
        )
        sel_brutas = (
            evento_brutas.selection.rows if evento_brutas and evento_brutas.selection else []
        )
        if sel_brutas:
            rsel = tab_brutas.iloc[sel_brutas[0]]
            st.markdown(explicar_linha_bruta(row, str(rsel["Linha"]), str(rsel["_col"])))

        v1, v2, v3, v4 = st.columns(4)
        with v1:
            st.metric("Caixa / Ativo", fmt_pct(100 * safe(row, "caixa_sobre_ativo")))
            _zoom_popover("Como?", explicar_metrica(row, "caixa_ativo"))
        with v2:
            dl = row["dl_sobre_ebitda"] if "dl_sobre_ebitda" in row.index else float("nan")
            st.metric("DL / EBITDA", fmt_num(dl, 2) if pd.notna(dl) else "—")
            _zoom_popover("Como?", explicar_metrica(row, "dl_ebitda"))
        with v3:
            fr = row["fco_sobre_receita"] if "fco_sobre_receita" in row.index else float("nan")
            st.metric("FCO / Receita", fmt_pct(100 * float(fr)) if pd.notna(fr) else "—")
            _zoom_popover("Como?", explicar_metrica(row, "fco_receita"))
        with v4:
            st.metric("Multiplicador setorial", fmt_num(row.get("mult_setor", 1), 2))
            _zoom_popover("Como?", explicar_metrica(row, "mult_setor"))

    st.markdown(f"#### Pares do setor ({setor})")
    st.caption("Clique em uma empresa para o zoom completo do funil dela.")
    peer_cols = [
        c
        for c in [
            "rank", "DENOM_CIA", "obj3_potencial_final_rs",
            "obj1_teto_rs", "score_0_100", "f_fin",
        ]
        if c in peers.columns
    ]
    peers_raw = peers.nsmallest(min(10, len(peers)), "rank")[peer_cols].copy()
    peers_show = peers_raw.copy()
    if "obj3_potencial_final_rs" in peers_show.columns:
        peers_show["obj3_potencial_final_rs"] = peers_show["obj3_potencial_final_rs"].map(fmt_money)
    if "obj1_teto_rs" in peers_show.columns:
        peers_show["obj1_teto_rs"] = peers_show["obj1_teto_rs"].map(fmt_money)
    peers_show = peers_show.rename(
        columns={
            "rank": "Rank",
            "DENOM_CIA": "Empresa",
            "obj3_potencial_final_rs": "Potencial final",
            "obj1_teto_rs": "Teto",
            "score_0_100": "Score",
            "f_fin": "F",
        }
    )
    evento_peers = st.dataframe(
        peers_show,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"zoom_peers_{escolhida}",
    )
    sel_peers = evento_peers.selection.rows if evento_peers and evento_peers.selection else []
    if sel_peers:
        nome_peer = str(peers_raw.iloc[sel_peers[0]]["DENOM_CIA"])
        peer_row = df[df["DENOM_CIA"] == nome_peer].iloc[0]
        with st.expander(f"Zoom: {nome_peer}", expanded=True):
            st.markdown(explicar_empresa_resumo(peer_row, n_painel=n_painel))

    ficha = pd.DataFrame([row])
    st.download_button(
        "Baixar ficha da empresa (CSV)",
        data=ficha.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"ficha_{escolhida[:40].replace(' ', '_')}_{year}.csv",
        mime="text/csv",
    )


def pagina_ranking(df: pd.DataFrame, year: int) -> None:
    st.subheader("Ranking")
    f1, f2, f3 = st.columns([1.2, 1.6, 1])
    with f1:
        setores = ["Todos"] + sorted(df["setor"].dropna().unique().tolist())
        setor = st.selectbox("Setor", setores, key="filtro_setor_rank")
    with f2:
        busca = st.text_input("Buscar empresa", placeholder="Ex.: TOTVS...")
    with f3:
        n_max = max(10, min(300, len(df)))
        top_n = st.slider("Top N", 10, n_max, min(50, n_max))

    view = df.copy()
    if setor != "Todos":
        view = view[view["setor"] == setor]
    if busca.strip():
        q = busca.strip().upper()
        view = view[view["DENOM_CIA"].astype(str).str.upper().str.contains(q, na=False)]
    view = view.head(top_n)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Empresas no ranking", f"{len(df):,}")
    c2.metric("Exibidas agora", f"{len(view):,}")
    c3.metric("Score médio", f"{df['score_0_100'].mean():.1f}")
    c4.metric("Ano", str(year))
    st.caption(
        "Clique em uma **empresa** da tabela para abrir o zoom completo "
        "(teto, viável, final, índice e motivo de zeros)."
    )
    show_cols = [
        c
        for c in [
            "rank",
            "DENOM_CIA",
            "setor",
            "obj3_potencial_final_rs",
            "score_0_100",
            "obj1_teto_rs",
            "obj1_0_100",
            "obj2_potencial_viavel_rs",
            "obj2_0_100",
            "obj3_0_100",
            "f_fin_0_100",
            "receita",
        ]
        if c in view.columns
    ]
    display = view[show_cols].copy()
    for col in ["obj3_potencial_final_rs", "obj1_teto_rs", "obj2_potencial_viavel_rs", "receita"]:
        if col in display.columns:
            display[col] = display[col].map(fmt_money)
    for col in ["score_0_100", "obj1_0_100", "obj2_0_100", "obj3_0_100", "f_fin_0_100"]:
        if col in display.columns:
            display[col] = display[col].map(lambda v: fmt_num(v, 1))
    display = display.rename(
        columns={
            "rank": "Rank",
            "DENOM_CIA": "Empresa",
            "setor": "Setor",
            "obj3_potencial_final_rs": "Potencial final (R$)",
            "score_0_100": "Índice 0–100",
            "obj1_teto_rs": "Teto (R$)",
            "obj1_0_100": "Teto 0–100",
            "obj2_potencial_viavel_rs": "Viável (R$)",
            "obj2_0_100": "Viável 0–100",
            "obj3_0_100": "Final 0–100",
            "f_fin_0_100": "F 0–100",
            "receita": "Receita",
        }
    )
    evento_rank = st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        key="zoom_ranking",
    )
    sel_rank = evento_rank.selection.rows if evento_rank and evento_rank.selection else []
    if sel_rank:
        nome_sel = str(view.iloc[sel_rank[0]]["DENOM_CIA"])
        row_sel = df[df["DENOM_CIA"] == nome_sel].iloc[0]
        with st.expander(f"Zoom: {nome_sel}", expanded=True):
            tabs = st.tabs(["Resumo do funil", "Teto", "Viável", "Final", "Índice 0–100"])
            with tabs[0]:
                st.markdown(explicar_empresa_resumo(row_sel, n_painel=len(df)))
            with tabs[1]:
                st.markdown(explicar_teto(row_sel))
                st.markdown("#### Linhas do teto")
                for rotulo in ["SG&A", "Vendas", "Pessoal", "CPV", "PDD", "Estoques"]:
                    with st.popover(rotulo):
                        st.markdown(explicar_linha_teto(row_sel, rotulo))
            with tabs[2]:
                st.markdown(explicar_viavel(row_sel))
            with tabs[3]:
                st.markdown(explicar_final(row_sel))
            with tabs[4]:
                st.markdown(explicar_score(row_sel, n_painel=len(df)))
            if st.button(
                f"Abrir ficha completa de {nome_sel[:40]}",
                key=f"ir_ficha_{sel_rank[0]}",
            ):
                st.session_state["empresa_selecionada"] = nome_sel
                st.session_state["nav_principal"] = "Empresa"
                st.rerun()

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Top 20 por potencial final (R$)")
        top20 = df.nlargest(20, "obj3_potencial_final_rs") if "obj3_potencial_final_rs" in df.columns else df.nsmallest(20, "rank")
        chart_col = "obj3_potencial_final_rs" if "obj3_potencial_final_rs" in top20.columns else "score_0_100"
        st.bar_chart(top20.set_index("DENOM_CIA")[chart_col], horizontal=True)
    with col_b:
        st.subheader("Média setorial do potencial (R$)")
        if "obj3_potencial_final_rs" in df.columns:
            st.bar_chart(
                df.groupby("setor")["obj3_potencial_final_rs"].mean().sort_values(ascending=True)
            )
        else:
            setor_df = load_setor(year)
            if setor_df is not None and "score_medio" in setor_df.columns:
                if "setor" in setor_df.columns:
                    chart = setor_df.set_index("setor")["score_medio"].sort_values(ascending=True)
                else:
                    chart = setor_df["score_medio"].sort_values(ascending=True)
                st.bar_chart(chart)
            else:
                st.bar_chart(df.groupby("setor")["score_0_100"].mean().sort_values(ascending=True))

    st.download_button(
        "Baixar CSV filtrado",
        data=view.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"ranking_filtrado_{year}.csv",
        mime="text/csv",
    )


def pagina_sobre() -> None:
    st.subheader("Sobre o ExAnte-AI (B3)")
    st.caption("Documentação e Metodologia ExAnte-AI (B3) · versão 0.1")

    st.markdown(
        """
### 1. Resumo

O **ExAnte-AI (B3)** estima o potencial de ganho de eficiência associado à adoção de
inteligência artificial a partir da estrutura de custos e da condição financeira das
companhias com demonstrações na CVM (universo de empresas abertas / B3). Trata-se de
uma abordagem **Ex-Ante**: o índice não mensura discurso corporativo sobre IA, tampouco
investimentos já realizados em tecnologia; traduz, em valor (R$ e % da receita), a
exposição econômica a ganhos de eficiência implícita nas contas patrimoniais e de
resultado. A estimativa percorre um **funil em três etapas** — teto teórico, potencial
viável e potencial final — e produz, ainda, um **score 0–100** para ranking relativo
entre empresas no mesmo exercício.

| Objetivo | O que responde | Número no painel |
|---|---|---|
| **1. Teto de eficiência** | Ganho máximo teórico (custos afetáveis × α) | `obj1_teto_rs` |
| **2. Potencial viável** | Teto após capacidade financeira (F) e taxa de captura (ρ) | `obj2_potencial_viavel_rs` |
| **3. Potencial final** | Viável após fator de execução (φ + readiness) | `obj3_potencial_final_rs` |

Ordem do funil (sempre nesta sequência):

`Teto → Viável (= Teto × F × ρ) → Final (= Viável × fator de execução)`

O resultado principal na ficha da empresa é o **potencial final** (R$ e % da receita);
o score 0–100 destina-se à comparação relativa no mesmo ano.
"""
    )

    st.markdown("### 2. Fluxo do sistema (o que o código faz)")
    st.markdown(
        """
| Etapa | Módulo | Ação |
|---|---|---|
| 1. Download | `cvm_download.py` | Baixa o ZIP anual da DFP no portal de dados abertos da CVM |
| 2. Carga | `cvm_load.py` | Lê DRE, BPA, BPP e DVA consolidados; companhias sem consolidado entram pela individual |
| 3. Extração | `extract.py` | Mapeia contas (`CD_CONTA` / `DS_CONTA`) → variáveis em **R$** (converte ESCALA MIL→×1000); plano de contas de bancos tratado à parte |
| 4. Score | `scoring.py` | Funil: teto → F → ρ → viável → readiness/φ → final → score 0–100 |
| 5. Saída | `pipeline.py` + `app.py` | Gera CSVs em `output/` e esta interface |

**Como rodar o cálculo:**
```bash
python main.py --year 2025
```

**Como abrir a interface:**
```bash
streamlit run app.py
```
"""
    )

    st.markdown("### 3. Fórmulas — o que cada uma faz e em qual objetivo entra")
    st.markdown(
        "Nenhuma fórmula existe isolada: cada uma produz uma peça de **um dos três "
        "objetivos** do indicador. A cadeia completa, do custo contábil ao número final, é:"
    )
    st.latex(
        r"\underbrace{\sum_k \min\!\big(|\tilde L_{i,k}|,\, 3\,ROL_i\big)\,\alpha_{k,s}}"
        r"_{\textbf{1. Teto}}"
        r"\;\times\;\underbrace{F^{fin}_i \times \rho}_{\textbf{2. Viável}}"
        r"\;\times\;\underbrace{\big(\phi + (1-\phi)R^{eff}_i\big)}_{\textbf{3. Final}}"
    )
    st.markdown(
        """
| Objetivo | Pergunta que responde | Fórmulas que o constroem | Resultado |
|---|---|---|---|
| **1. Teto de eficiência** <br>*Bloco A · seção 3.1* | Quanto da estrutura de custos é teoricamente atacável por IA? | **A1** α efetivo · **A2** pessoal líquido · **A3** valor por linha · **A4** soma · *(**A5** exposição, só para o ranking)* | `obj1_teto_rs` |
| **2. Potencial viável** <br>*Bloco B · seção 3.2* | Quanto desse teto a empresa tem condição financeira de bancar? | **B1** F = f·g·h · **B2** ρ · **B3** viável · *(**B4** decomposição do desconto)* | `obj2_potencial_viavel_rs` |
| **3. Potencial final** <br>*Bloco C · seção 3.3* | Quanto ela consegue de fato executar? | **C1** r bruto · **C2** R percentil · **C3** R_eff · **C4** fator de execução · **C5** final | `obj3_potencial_final_rs` |
| *Camada de ranking* <br>*seção 3.4* | Quem está melhor posicionado no painel do ano? | **S1** winsorização · **S2** score bruto · **S3** min–max e rank · **S4** índices auxiliares | `score_0_100` · `rank` |
"""
    )
    st.info(
        "**Regra de leitura do funil:** F, ρ e o fator de execução são todos ≤ 1, "
        "portanto **Teto ≥ Viável ≥ Final** sempre. Nenhuma etapa posterior pode aumentar "
        "a anterior — o Bloco C (readiness) não cria potencial, apenas define quanto do "
        "viável se realiza."
    )

    # ---------------------------------------------------------------- Obj. 1
    st.markdown("#### 3.1 Objetivo 1 — Teto de eficiência · Bloco A (passos A1 a A5)")
    st.caption(
        "Pergunta: qual o ganho máximo teórico sobre a estrutura de custos, antes de "
        "qualquer restrição financeira ou de execução? Quatro fórmulas em sequência "
        "transformam contas da DFP em reais de potencial."
    )

    _formula(
        "A1",
        "α efetivo — quanto de cada linha é afetável",
        r"\alpha_{k,s} = \min\left(\alpha^{base}_k \times \frac{E_s}{\bar E},\; \alpha_{max}=0{,}60\right)",
        "parte do $\\alpha^{base}$ da linha $k$ (SG&A 0,30 · vendas 0,32 · pessoal 0,35 · "
        "CPV 0,10 · PDD 0,40 · estoques 0,18) e escala pelo prior setorial $E_s/\\bar E$, "
        "que vai de 0,75 em commodities a 1,25 em financeiro.",
        "definir **que fração** de cada conta entra no teto. É o parâmetro de maior "
        "impacto do modelo: mudar α muda o valor e a ordem do ranking.",
        "`mult_setor` e o α aplicado em cada linha do passo 1.3.",
    )
    st.markdown(
        "**Exceção — PDD.** Fora do setor financeiro a provisão para créditos é pequena e "
        "pouco automatizável, então o $\\alpha^{base}$ cai de 0,40 para **0,15** "
        "(`alpha_pdd_nao_financeiro`). **Sobre o $\\alpha_{max}$:** com a calibração atual o "
        "maior α possível é 0,40 × 1,25 = 0,50, então o limite de 0,60 é um **trilho de "
        "segurança** — protege edições feitas na aba Config e encosta no limite no teste de "
        "robustez R1 (+20% em todos os α)."
    )

    _formula(
        "A2",
        "Pessoal líquido — remover a dupla contagem da folha",
        r"\tilde L_{i,k} = L_{i,k}\times\left(1 - \frac{Pessoal_i}{CPV_i + SGA_i + Vendas_i}\right)"
        r"\quad k \in \{CPV, SGA, Vendas\}",
        "retira *pro rata* de CPV, SG&A e vendas a parcela que corresponde à folha "
        "(DVA 7.08.01), deixando nessas linhas só o custo não-salarial.",
        "impedir que a mesma despesa entre duas vezes no teto: a folha já está dentro "
        "das três linhas e ainda recebe seu próprio $\\alpha_{pessoal}$. Sem esse ajuste "
        "o teto era superestimado em cerca de 25%.",
        "`fator_pessoal_liquido`, `sga_afetavel`, `vendas_afetavel`, `cpv_afetavel`.",
    )
    st.markdown(
        "Em bancos “Despesas de Pessoal” já é linha separada no plano de contas e nada é "
        "subtraído. Os modos `separado` (versão antiga, com dupla contagem) e `excluir` "
        "seguem disponíveis em `pessoal_modo`."
    )

    _formula(
        "A3",
        "Valor potencial de cada linha — a conta vira R$",
        r"valor_{i,k} = \min\big(|\tilde L_{i,k}|,\; 3\cdot ROL_i\big)\times \alpha_{k,s}",
        "multiplica a base afetável de cada linha pelo seu α, truncando o valor absoluto "
        "em 3× a receita operacional líquida.",
        "é o ponto em que a linha contábil se converte em dinheiro. O corte de 3× o $ROL$ "
        "impede que uma DFP com escala ou preenchimento distorcido domine o painel.",
        "`valor_sga_rs`, `valor_vendas_rs`, `valor_pessoal_rs`, `valor_cpv_rs`, "
        "`valor_pdd_rs`, `valor_estoques_rs` — é a decomposição “De onde vem o teto” da ficha.",
    )

    _formula(
        "A4",
        "Teto de eficiência — o Objetivo 1",
        r"Teto_i = \sum_k valor_{i,k}"
        r"\qquad k \in \{SGA,\, Vendas,\, Pessoal,\, CPV,\, PDD,\, Estoques\}",
        "soma as seis linhas afetáveis.",
        "**é o Objetivo 1**: o espaço econômico bruto da empresa, o ponto de partida do "
        "funil. Ainda não considera caixa, dívida nem capacidade de execução.",
        "`obj1_teto_rs` e `obj1_teto_pct_receita`.",
    )

    _formula(
        "A5",
        "Exposição — o mesmo teto em razão da receita",
        r"Expo_i = \sum_k \min\left(\frac{|\tilde L_{i,k}|}{ROL_i},\, 3\right)\alpha_{k,s}"
        r"\;=\; \frac{Teto_i}{ROL_i}",
        "repete a soma do teto, mas normalizada pela receita.",
        "**não entra no valor em R$ de nenhum objetivo**. É a entrada da camada de "
        "ranking (3.4), que precisa comparar empresas de portes muito diferentes sem que "
        "as maiores dominem só por tamanho.",
        "`exposicao`.",
    )

    # ---------------------------------------------------------------- Obj. 2
    st.markdown("#### 3.2 Objetivo 2 — Potencial viável · Bloco B (passos B1 a B4)")
    st.caption(
        "Pergunta: desse teto, quanto a empresa tem condição financeira de bancar? "
        "Duas restrições entram aqui — a situação de balanço (F) e uma taxa de captura (ρ)."
    )

    _formula(
        "B1",
        "F financeiro — capacidade de bancar a adoção",
        r"F^{fin}_i = f\!\left(\frac{Caixa_i}{Ativo_i}\right)\times"
        r" g\!\left(\frac{DL_i}{EBITDA_i}\right)\times h\!\left(\frac{FCO_i}{ROL_i}\right)",
        "combina três notas em degrau — liquidez ($f$), alavancagem ($g$) e geração de "
        "caixa operacional ($h$) — num único multiplicador entre 0,19 e 1,00.",
        "reconhecer que ter oportunidade não é ter dinheiro: empresa sem caixa, muito "
        "endividada ou queimando caixa não consegue investir em IA. $F = 1$ significa "
        "nenhum desconto financeiro.",
        "`f_caixa`, `g_alavancagem`, `h_fco`, `f_fin` e `f_fin_0_100`.",
    )

    st.markdown("**Faixas das três funções de $F$**")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**$f$ — liquidez**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Caixa / Ativo": ["< 3%", "3% ≤ x < 8%", "≥ 8%"],
                    "f": ["0,75", "0,90", "1,00"],
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    with c2:
        st.markdown("**$g$ — alavancagem**")
        st.dataframe(
            pd.DataFrame(
                {
                    "DL / EBITDA": ["< 2,0×", "2,0× ≤ x < 3,5×", "≥ 3,5×", "EBITDA ≤ 0", "Inst. financeira"],
                    "g": ["1,00", "0,70", "0,40", "0,25", "1,00 (fixo)"],
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    with c3:
        st.markdown("**$h$ — geração de caixa**")
        st.dataframe(
            pd.DataFrame(
                {
                    "FCO / ROL": ["< 0 (queima caixa)", "≥ 0", "Sem DFC / inst. financeira"],
                    "h": ["0,85", "1,00", "1,00"],
                }
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.caption(
        "Para bancos e seguradoras (plano de contas com “Receitas da Intermediação Financeira”) "
        "DL/EBITDA não é definido — a captação é por depósitos e não há EBITDA — e o FCO oscila "
        "com a carteira de crédito. Usa-se g fixo (`g_financeiro`), h = 1 e apenas f(Caixa/Ativo) diferencia."
    )

    _formula(
        "B2",
        "ρ — taxa de captura",
        r"\rho = 0{,}70 \quad \text{(constante para todas as empresas)}",
        "aplica um redutor único sobre o teto já ajustado por F.",
        "reconhecer que nem todo ganho teórico se materializa, mesmo numa empresa com "
        "caixa e endividamento confortáveis. É **parâmetro de nível, não de ordenação** — "
        "ver a proposição em 3.2.1.",
        "`rho_captura` e as colunas de cenário `obj2_viavel_rs_rho_*` / `obj3_final_rs_rho_*`.",
    )

    _formula(
        "B3",
        "Potencial viável — o Objetivo 2",
        r"Viavel_i = Teto_i \times F^{fin}_i \times \rho",
        "comprime o teto pelas duas restrições da etapa.",
        "**é o Objetivo 2**: a parcela do ganho máximo que é financeiramente alcançável. "
        "É o segundo número do funil na ficha da empresa.",
        "`obj2_potencial_viavel_rs` e `obj2_viavel_pct_receita`.",
    )

    _formula(
        "B4",
        "Decomposição do desconto (auxiliar)",
        r"desc^{fin}_i = Teto_i(1-F^{fin}_i)"
        r"\qquad desc^{capt}_i = Teto_i\,F^{fin}_i(1-\rho)",
        "separa quanto do teto se perdeu por restrição financeira e quanto por taxa de captura.",
        "explicar o funil na interface. **Não alimenta o Objetivo 3** — é apenas leitura.",
        "`obj2_desconto_financeiro_rs`, `obj2_desconto_captura_rs`, `obj2_desconto_total_rs`.",
    )

    st.markdown("#### 3.2.1 Invariância do ranking a ρ")
    st.markdown(
        "**Proposição.** O `score_0_100` e o `rank` (definidos adiante em 3.4) são "
        "invariantes a $\\rho$. "
        "Como $\\rho$ é constante e idêntica para todas as empresas, ela é um fator "
        "multiplicativo comum no score bruto, e a normalização min–max "
        "$100(S-\\min)/(\\max-\\min)$ cancela qualquer constante positiva. "
        "Logo $\\rho$ desloca apenas o **nível em R$** dos objetivos 2 e 3."
    )
    st.markdown(
        "Isso é uma **propriedade desejável, não uma falha**: a ordenação do índice não "
        "depende do parâmetro mais arbitrário do modelo. Vale registrar que $\\rho$ também "
        "**não pode** ser diferenciada por setor ou por linha sem virar redundância — "
        "$\\rho_s$ seria absorvida por $E_s/\\bar E$ e $\\rho_k$ por $\\alpha^{base}_k$, já "
        "que ambos multiplicam os mesmos termos. Diferenciá-la exigiria ancorá-la em uma "
        "variável ainda fora da cadeia (porte da firma, por exemplo)."
    )
    st.markdown(
        "O pipeline materializa a sensibilidade em `rho_cenarios` (`pesos.yaml`), gerando "
        "colunas por cenário no ranking e o arquivo `output/sensibilidade_rho_AAAA.csv`:"
    )
    st.dataframe(
        pd.DataFrame(
            {
                "Cenário": ["Conservador", "Base", "Otimista"],
                "ρ": ["0,50", "0,70", "0,90"],
                "Potencial final do painel vs. base": ["0,71×", "1,00×", "1,29×"],
                "Mediana do % da receita (2025)": ["4,27%", "5,98%", "7,69%"],
                "Spearman do rank vs. base": ["1,000", "1,000", "1,000"],
                "Empresas que trocam de posição": ["0", "0", "0"],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    # ---------------------------------------------------------------- Obj. 3
    st.markdown("#### 3.3 Objetivo 3 — Potencial final · Bloco C (passos C1 a C5)")
    st.caption(
        "Pergunta: do que é financeiramente viável, quanto a empresa consegue executar? "
        "Aqui entra o Bloco C (readiness digital), em quatro passos. Este é o resultado "
        "principal da ficha."
    )

    _formula(
        "C1",
        "Readiness bruto — base digital no balanço",
        r"r_i = w_{soft}\cdot\frac{Soft_i}{Ativo_i} + w_{intang}\cdot\frac{Intang_i}{Ativo_i}",
        "combina software e intangível sobre o ativo total, com pesos 0,50 e 0,20.",
        "aproximar a **capacidade de absorção** (Cohen & Levinthal): ter oportunidade e "
        "dinheiro não basta se a empresa não tem base tecnológica instalada.",
        "`readiness_bruto`.",
    )

    _formula(
        "C2",
        "Readiness normalizada — posição relativa no painel",
        r"R_i = \mathrm{percentil}_{painel}(r_i) \in [0,1]",
        "converte $r_i$ na posição relativa da empresa entre as válidas do ano.",
        "tornar o Bloco C operante. As razões $Soft/Ativo$ e $Intang/Ativo$ ficam abaixo "
        "de 0,05 em quase todas as companhias, então um `clip(r, 0, 1)` direto deixaria "
        "o bloco inerte. Alternativas: `escala` ($r/q_{90}$) e `bruto`.",
        "`readiness` e `readiness_0_100`.",
    )

    _formula(
        "C3",
        "Readiness efetiva — curvatura por λ",
        r"R^{eff}_i = R_i^{\,1/(1+\lambda)} \qquad \lambda = 0{,}10",
        "curva $R_i$ para cima com expoente $1/(1+\\lambda)$, ou seja $R^{0,909}$.",
        "dar peso um pouco maior à readiness sem distorcer a escala. A transformação é "
        "estritamente crescente e mapeia [0, 1] em [0, 1], então **não precisa de clip e "
        "não satura**. Com $\\lambda = 0$ tem-se $R^{eff} = R$.",
        "`readiness_efetiva`.",
    )
    st.markdown(
        "**Por que não é mais $\\mathrm{clip}(R\\cdot(1+\\lambda))$.** A forma anterior "
        "empatava em $R^{eff} = 1$ toda empresa acima do percentil $1/(1+\\lambda)$: eram "
        "43 companhias em 2024 e 40 em 2025 com fator de execução idêntico, justamente no "
        "topo do Bloco C — o grupo que o bloco existe para diferenciar. Com a curvatura, o "
        "empate no topo caiu para **1 empresa** (a 1ª colocada em readiness, por construção) "
        "e o fator de execução passou a assumir 415 valores distintos entre as 434 válidas "
        "de 2025."
    )

    _formula(
        "C4",
        "Fator de execução",
        r"exec_i = \phi + (1-\phi)\,R^{eff}_i \qquad \phi = 0{,}85",
        "traduz a readiness num multiplicador que varia de 0,85 a 1,00.",
        "graduar quanto do viável se realiza: com readiness nula preserva 85% do viável; "
        "com readiness máxima chega a 100%. O piso $\\phi$ garante que mesmo uma empresa "
        "sem base digital capture a maior parte do potencial.",
        "`fator_execucao` e `phi_execucao_base`.",
    )

    _formula(
        "C5",
        "Potencial final — o Objetivo 3",
        r"Final_i = Viavel_i \times \big(\phi + (1-\phi)\, R^{eff}_i\big)",
        "aplica o fator de execução sobre o potencial viável.",
        "**é o Objetivo 3 e o resultado principal do indicador**: o número em R$ e em % "
        "da receita que a ficha da empresa destaca.",
        "`obj3_potencial_final_rs`, `obj3_viavel_pct_receita` e `obj3_ajuste_execucao_rs`.",
    )
    st.caption(
        "Ordem no código: teto → F → viável (ρ) → R → final (φ). Os empates que ainda "
        "restam no fator de execução vêm de companhias com `readiness_bruto` exatamente "
        "igual — cerca de 5% do painel, sem software nem intangível identificáveis, que "
        "compartilham o mesmo percentil médio. O peso de P&D (`w_ped`) está reservado na "
        "calibração e ainda não entra no cálculo da v0.1."
    )

    # ------------------------------------------------------------- Ranking
    st.markdown("#### 3.4 Camada de ranking — não é um objetivo, ordena o painel (passos S1 a S4)")
    st.caption(
        "As fórmulas acima produzem valores em R$, comparáveis entre anos. Esta camada "
        "existe para outra pergunta: **quem está melhor posicionado dentro do painel deste "
        "ano**. Ela reaproveita o funil, mas partindo da exposição (1.5) em vez do teto em R$."
    )

    _formula(
        "S1",
        "Winsorização da exposição",
        r"Expo^{score}_i = \min\big(Expo_i,\; q_{99}\big)",
        "trunca a exposição no percentil 99 do painel válido.",
        "impedir que uma DFP atípica ocupe sozinha o topo e comprima a escala 0–100 de "
        "todas as demais. **O teto em R$ não é alterado** — o corte vale só para o score.",
        "`exposicao_score` e `exposicao_winsor_limite`.",
    )

    _formula(
        "S2",
        "Score bruto — o funil em razão da receita",
        r"Score_i = \min(Expo_i,\, q_{99}) \times F^{fin}_i \times \rho"
        r" \times \big(\phi + (1-\phi)\, R^{eff}_i\big)",
        "repete exatamente os fatores dos objetivos 2 e 3, mas sobre a exposição "
        "winsorizada em vez do teto em reais.",
        "permitir **comparação relativa** entre empresas de portes diferentes. Não "
        "substitui o potencial final em R$, que continua sendo o resultado do indicador.",
        "`score_bruto`.",
    )

    _formula(
        "S3",
        "Normalização 0–100 e rank",
        r"Score^{0\text{-}100}_i = 100 \times"
        r" \frac{Score_i - \min(Score)}{\max(Score) - \min(Score)}",
        "aplica min–max **somente entre as válidas do mesmo ano** e ordena em seguida: o "
        "pior score do painel vira 0 e o melhor vira 100.",
        "produzir a escala de leitura do ranking. Por ser relativa ao painel, **score de "
        "2024 não se compara com score de 2025** sem reprocessar. Há a opção "
        "`normalizacao_score: percentil` na aba Config.",
        "`score_0_100` e `rank` (1º = maior score).",
    )

    _formula(
        "S4",
        "Índices auxiliares 0–100",
        r"obj_n^{0\text{-}100} = \mathrm{percentil}_{painel}\big(obj_n^{R\$}\big)\times 100",
        "converte cada objetivo em R$ para percentil dentro do painel válido.",
        "leitura auxiliar na tabela de ranking. São **percentis**, não min–max como o "
        "score principal; a ficha da empresa destaca R$ e % da receita.",
        "`obj1_0_100`, `obj2_0_100`, `obj3_0_100`, `exposicao_0_100`, `f_fin_0_100`.",
    )

    # -------------------------------------------------------- Parâmetros
    st.markdown("#### 3.5 Parâmetros do cenário-base")
    st.markdown(
        """
| Símbolo | Passo | Papel | Base |
|---|---|---|---|
| **α_base** | A1 | Fração afetável de cada linha contábil | 0,10 a 0,40 |
| **E_s / Ē** | A1 | Prior setorial que escala o α | 0,75 a 1,25 |
| **α_max** | A1 | Trilho de segurança do α efetivo | 0,60 |
| **cap L/ROL** | A3 | Trava de cada linha em múltiplos da receita | 3,0× |
| **ρ** | B2 | Taxa de captura — parâmetro de **nível**, não de ordenação | 0,70 |
| **w_soft / w_intang** | C1 | Pesos do readiness | 0,50 / 0,20 |
| **λ** | C3 | Curvatura de R: R_eff = R^(1/(1+λ)) | 0,10 |
| **φ** | C4 | Piso de execução sem readiness | 0,85 |
| **winsor** | S1 | Percentil de corte da exposição no score | 0,99 |
"""
    )
    st.caption(
        "Todos editáveis na aba **Config**, que grava em `config/pesos.yaml` e permite "
        "recalcular o ranking do ano sem sair da interface."
    )

    st.markdown("### 4. Linhas contábeis (Blocos A, B e C)")

    st.markdown("#### Bloco A — Exposição / teto de oportunidade (núcleo)")
    st.dataframe(
        pd.DataFrame(
            {
                "Variável": ["SG&A", "Vendas", "Pessoal", "CPV", "PDD", "Estoques"],
                "Fonte CVM": ["DRE", "DRE", "DVA", "DRE", "DRE (texto) → DVA 7.01.04", "BPA"],
                "Código / busca típica": [
                    "3.04.02 · gerais e administrativas",
                    "3.04.01 · despesas com vendas",
                    "DVA 7.08.01 · Pessoal",
                    "3.02 · custo dos bens/serviços",
                    "provisão / PeLD / crédito (texto); fallback DVA 7.01.04",
                    "1.01.04 · Estoques",
                ],
                "α base": ["0,30", "0,32", "0,35", "0,10", "0,40 fin. / 0,15 demais", "0,18"],
                "Por quê entra": [
                    "Colarinho branco / GenAI / RPA (parcela não-salarial)",
                    "Atendimento, churn, precificação (parcela não-salarial)",
                    "Folha total — recebe seu próprio α (retirada das outras linhas)",
                    "Manutenção preditiva / eficiência (parcela não-salarial; α baixo)",
                    "ML de crédito/fraude (forte em financeiro; residual fora dele)",
                    "Forecast de demanda → PME ↓",
                ],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Bloco B — Viabilidade financeira")
    st.dataframe(
        pd.DataFrame(
            {
                "Variável": ["Caixa", "Dívida", "EBITDA (proxy)", "FCO", "Ativo total", "Receita"],
                "Fonte": [
                    "BPA 1.01.01",
                    "BPP 2.01.04 + 2.02.01 (sem contar subcontas)",
                    "DRE 3.05 + DVA 7.04.01",
                    "DFC 6.01 (método indireto ou direto)",
                    "BPA 1",
                    "DRE 3.01",
                ],
                "Uso": [
                    "f(Caixa/Ativo)",
                    "DL = Dívida − Caixa",
                    "g(DL/EBITDA)",
                    "h(FCO/ROL) — penaliza queima de caixa",
                    "Denominadores e readiness",
                    "Normalização L/ROL",
                ],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Bloco C — Readiness (secundário)")
    st.dataframe(
        pd.DataFrame(
            {
                "Variável": ["Software", "Intangível"],
                "Fonte": ["BPA / notas (padrão de texto)", "BPA 1.02.04"],
                "Papel": [
                    "Proxy de base digital instalada",
                    "Intensidade tecnológica (peso menor; mais ruidoso)",
                ],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("### 5. Multiplicadores setoriais (priors v1)")
    st.dataframe(
        pd.DataFrame(
            {
                "Setor": [
                    "financeiro",
                    "tecnologia",
                    "varejo",
                    "saude_educacao",
                    "industria",
                    "outros",
                    "utilities",
                    "construcao",
                    "commodities",
                ],
                "E_s / Ē": ["1,25", "1,20", "1,10", "1,05", "1,00", "1,00", "0,90", "0,85", "0,75"],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )
    st.markdown(
        """
**Como o setor é atribuído** (coluna `setor_fonte`):

1. **`cvm`** — campo oficial `SETOR_ATIV` do cadastro de companhias abertas da CVM
   (`cad_cia_aberta.csv`), mapeado para os grupos acima em `config/setor_cvm.yaml`
   (ex.: “Bancos” → financeiro; “Comunicação e Informática” → tecnologia; “Emp. Adm. Part. – Energia Elétrica” → utilities).
2. **`nome`** — quando o setor CVM não tem regra (ex.: “Serviços Transporte e Logística”, “Sem Setor Principal”),
   vale a heurística por palavras-chave no nome (`setor_keywords`).
3. **`padrao`** — sem batida em nenhum dos dois → `outros` (multiplicador 1,0).
4. **`template`** — plano de contas de instituição financeira sempre força `financeiro`.
"""
    )

    st.markdown("### 6. Filtros de qualidade (quem entra no ranking)")
    st.markdown(
        """
- Receita mínima ≥ **R$ 50 milhões** (`min_receita`, já em R$ — a extração converte a escala MIL da DFP)  
- Exclui empresas com “**RECUPERA**” no nome (recuperação judicial)  
- Exige ao menos uma entre: **SG&A, vendas ou pessoal**  
- Cada razão $L/ROL$ é limitada a **3,0**  
- Usa demonstrações **consolidadas**; companhias sem consolidado entram pela **individual** (`origem_dfp`)  
- **Subsidiárias / SPEs ficam fora**: quem entra pela individual **e** é *Categoria B* no cadastro CVM
  (não pode ter ações em bolsa — malhas ferroviárias, distribuidoras de holdings listadas, concessionárias)
  é excluído para não contar controlada e holding (`excluir_individual_categoria_b`).
  Opcionalmente `apenas_categoria_a` restringe às emissoras de ações.  
- Coluna `alerta_receita`: receita da DRE < 50% das receitas da DVA (7.01) → DFP possivelmente inconsistente
  (só sinaliza; bancos não entram no alerta porque a diferença é estrutural; `excluir_alerta_receita` torna filtro)  
"""
    )

    st.markdown("### 7. Base teórica (resumo)")
    st.markdown(
        """
O indicador **traduz** a literatura de exposição à IA (ocupações/tarefas) para **proxy contábil firm-level**,
porque no Brasil não há breakdown ocupacional público comparável para toda a B3.

**Âncoras principais:**
- Felten, Raj & Seamans (2021) — AIOE / exposição ocupacional e industrial  
- Eloundou et al. (2023) — exposição a LLMs por tarefas  
- Brynjolfsson, Li & Raymond (2023) — GenAI e produtividade em atendimento  
- Cohen & Levinthal (1990) — absorptive capacity (Bloco C)  
- Fazzari / Kaplan-Zingales — restrições financeiras (Bloco B)  

Documentação detalhada: abra os PDFs no final desta página
(`Base_Teorica.pdf`, `Consenso_Linhas_Contabeis.pdf`, `Pesos_Alpha_Beta.pdf`).
"""
    )

    st.markdown("### 8. O que a interface mostra")
    st.markdown(
        """
| Aba | Conteúdo |
|---|---|
| **Empresa** | Ficha personalizada: score, ranks, narrativa, decomposição, linhas, peers |
| **Ranking** | Tabela filtrável, top 20, médias setoriais, download CSV |
| **Config** | Edição de pesos α, setores, viabilidade, readiness, filtros e mapeamento CVM |
| **Sobre** | Esta documentação metodológica |

Arquivos gerados em `output/`:
- `ranking_ia_exante_AAAA.csv`  
- `variaveis_firmas_AAAA.csv`  
- `media_setorial_AAAA.csv`  
"""
    )

    st.markdown("### 9. Limitações da v0.1 (transparência)")

    limitacoes = [
        (
            "1. Sem parse fino de notas explicativas (β)",
            """
O teto usa **α sobre a linha agregada** (SG&A, CPV, etc.).

As **notas explicativas** da DFP ainda **não** são lidas item a item. Por isso os pesos **β**
(sublinhas / buckets como atendimento, jurídico, aluguel) **não entram** no cálculo atual.

**Efeito:** o modelo pode superestimar o potencial em linhas com muita fatia “não automatizável”
(ex.: aluguel dentro do SG&A) e subestimar onde a nota revelaria buckets muito expostos à IA.
""",
        ),
        (
            "2. EBITDA é proxy",
            """
Não há um campo único e uniforme de EBITDA em todas as DFPs da CVM.

O sistema usa um **proxy**: resultado antes do financeiro (conta típica 3.05) **+** depreciação/amortização
quando disponível na DVA.

**Efeito:** o fator **g(DL/EBITDA)** — e portanto o **F** financeiro — pode ficar impreciso em empresas
com composição atípica de DRE/DVA ou sem depreciação bem identificada.
""",
        ),
        (
            "3. Setor vem do cadastro CVM, com grupos amplos",
            """
A classificação setorial usa o campo oficial **`SETOR_ATIV`** do cadastro de companhias abertas da CVM
(mapeado em `config/setor_cvm.yaml`); a heurística por **nome** (`setor_keywords`) só cobre quem não
tem regra. Companhias com plano de contas de instituição financeira são sempre **financeiro**.

**Efeito:** os 8 grupos do índice são mais amplos que o setor CVM — “Serviços Transporte e Logística”,
“Hospedagem e Turismo” e holdings “Sem Setor Principal” caem em **outros** (multiplicador 1,0), e a
escolha de para onde vai cada setor CVM (ex.: Alimentos → indústria, Siderurgia → commodities) é uma
decisão metodológica editável. O cadastro é baixado uma vez por mês; offline, vale a heurística.
""",
        ),
        (
            "4. PDD depende de texto da conta",
            """
Provisão para créditos / PeLD / PDD **não** tem um `CD_CONTA` estável na DRE de todas as companhias.

A extração busca por **padrões de texto** em `DS_CONTA` da DRE e, quando não encontra, usa a linha
fixa da DVA **7.01.04 — Provisão/Reversão de Créditos de Liquidação Duvidosa** (coluna `pdd_fonte`).

**Efeito:** a cobertura passa a ser quase universal, mas a linha da DVA é o **movimento líquido**
(constituição − reversão) do exercício e pode ser zero ou pequena em empresas sem carteira de crédito.
""",
        ),
        (
            "5. Pesos α são priors calibrados",
            """
Os α (0,10–0,40 por linha) vêm de **priors teóricos** (literatura de exposição a tarefas + julgamento
metodológico), não de uma estimação econométrica firm-level na B3.

**Efeito:** a ordem relativa do ranking pode mudar se os α mudarem. Por isso o protocolo de
**robustez R1–R6** (e a aba Config) existe: testar se top/bottom se mantêm sob cenários alternativos.
""",
        ),
        (
            "6. Score 0–100 é relativo ao painel do ano",
            """
O `score_0_100` é uma normalização **min–max entre empresas válidas do mesmo ano**, calculada sobre
a exposição **winsorizada** no percentil 99 (o outlier ainda fica em 100, mas não comprime os demais).

**Efeito:**
- score 100 = melhor do **painel daquele ano**, não “100% de potencial absoluto”
- **não** se compara score 2024 com score 2025 sem reprocessar / alinhar painéis
- o potencial em **R$** e o **% da receita** são as métricas comparáveis em nível de empresa;
  o 0–100 serve sobretudo ao **ranking relativo**
""",
        ),
        (
            "7. Readiness é posição relativa, não nível absoluto",
            """
Software e intangível sobre o ativo ficam abaixo de 5% na quase totalidade das companhias, e software
capitalizado só é identificável em ~10% delas. Por isso **R** é o **percentil** da razão composta no painel.

**Efeito:** R = 0,9 significa “entre as 10% mais intensivas em ativos digitais do painel”, não “90% pronta
para IA”. Intangível inclui **goodwill** de aquisições, o que favorece empresas que cresceram por M&A.
""",
        ),
        (
            "8. Pessoal líquido é aproximação pro rata",
            """
A folha (DVA 7.08.01) é retirada de CPV, SG&A e vendas **na mesma proporção**, porque a DFP não informa
quanto de pessoal está em cada linha.

**Efeito:** em empresas com folha concentrada no CPV (indústria) ou no SG&A (serviços) a divisão entre
linhas fica imprecisa, embora o **total** afetável seja correto (sem dupla contagem).
""",
        ),
    ]
    for titulo, texto in limitacoes:
        with st.expander(titulo, expanded=False):
            st.markdown(texto)


    st.markdown("### 10. Próximos passos naturais")

    proximos = [
        (
            "1. Taxonomia de sublinhas (β) via notas",
            """
Hoje o **α** pesa a **linha agregada** (ex.: SG&A inteiro, CPV inteiro).

O **β** entra nas **notas explicativas**, quebrando cada linha-mãe em buckets, por exemplo:
- atendimento / SAC
- jurídico e back-office
- aluguel e contratos (pouco afetáveis por IA)
- manutenção preditiva / operação

Assim, aplica-se um peso diferente a cada sublinha e o teto de eficiência fica mais fino:
separa o que é realmente automatizável do que não é.
""",
        ),
        (
            "2. Painel multi-ano",
            """
Hoje o ranking e o score 0–100 são **relativos a um único ano**.

A ideia é comparar várias DFPs (2023, 2024, 2025…) na mesma tela:
- evolução do potencial em R$
- entrada e saída do top do ranking
- séries temporais por empresa e por setor

Isso evita misturar escalas absolutas entre anos sem reprocessar o painel completo.
""",
        ),
        (
            "3. Setores mais finos (B3 / CNAE)",
            """
O setor já vem do cadastro **CVM** (`SETOR_ATIV`), mas é agregado em 8 grupos.

Próximos refinamentos:
- grupos próprios para **transporte/logística** e **serviços**, hoje em “outros”
- classificação setorial da **B3** (setor/subsetor/segmento) ou **CNAE** para separar, por exemplo,
  siderurgia de autopeças dentro de “Metalurgia e Siderurgia”
- calibrar $E_s/\\bar E$ com o AIIE de Felten por setor fino
""",
        ),
        (
            "4. Testes de robustez R1–R6",
            """
Protocolo da dissertação para mostrar que o ranking **não depende de um único conjunto de α**.

| Código | O que testa |
|---|---|
| **R1** | α ±20% (sobe e desce todos os pesos) |
| **R2** | pesos iguais (α = 0,25 para todas as linhas) |
| **R3** | só núcleo cognitivo (pessoal + SG&A + vendas) |
| **R4** | sem readiness (φ = 1 — com φ = 1 o fator de execução vale 1 para todos; λ = 0 sozinho **não** desliga o Bloco C nesta versão) |
| **R5** | sem multiplicador setorial |
| **R6** | só alavancagem (ignora o fator de caixa) |

Se o top/bottom quartil e a ordem relativa se mantêm sob esses cenários,
o indicador ganha credibilidade acadêmica — padrão de índices compostos.
""",
        ),
        (
            "5. Validação setorial vs. AIIE (Felten)",
            """
Confrontar a **média setorial do ExAnte-AI (B3)** com o **AIIE**
(*AI Industry Exposure*) de Felten, Raj & Seamans (2021) —
exposição ocupacional agregada por indústria.

A pergunta de validação:
se setores “cognitivos” no AIIE também saem altos no seu índice,
a tradução contábil da exposição à IA para a B3 fica **validada externamente**
pela literatura de referência.
""",
        ),
    ]
    for titulo, texto in proximos:
        with st.expander(titulo, expanded=False):
            st.markdown(texto)

    st.markdown("---")
    st.markdown("### Documentação (PDFs)")

    docs = [
        (
            "Base teórica",
            "Fundamentos acadêmicos e âncoras da abordagem Ex-Ante.",
            ROOT / "Base_Teorica.pdf",
        ),
        (
            "Consenso de linhas contábeis",
            "Quais contas entram no índice e por quê.",
            ROOT / "Consenso_Linhas_Contabeis.pdf",
        ),
        (
            "Pesos α / β",
            "Calibração dos pesos, fatores financeiros e readiness.",
            ROOT / "Pesos_Alpha_Beta.pdf",
        ),
    ]

    cols = st.columns(3)
    for col, (titulo, descricao, path) in zip(cols, docs):
        with col:
            st.markdown(f"**{titulo}**")
            st.caption(descricao)
            if not path.exists():
                st.error(f"Não encontrado: `{path.name}`")
                continue
            st.download_button(
                label=f"Baixar {path.name}",
                data=path.read_bytes(),
                file_name=path.name,
                mime="application/pdf",
                key=f"dl_doc_{path.stem}",
                use_container_width=True,
            )

    st.markdown("---")
    st.markdown("### Glossário")

    glossario = [
        (
            "Ex-Ante",
            "Abordagem **preditiva**: estima o potencial de benefício com IA **antes** de observar "
            "adoção real, discursos ou gastos em tecnologia (oposto de Ex-Post).",
        ),
        (
            "ExAnte-AI (B3)",
            "Nome do indicador deste projeto: exposição e potencial de benefício por IA para "
            "companhias abertas com DFP na CVM / universo B3.",
        ),
        (
            "α (alpha)",
            "Fator de suscetibilidade da **linha contábil agregada**. Fração da conta considerada "
            "afetável por IA (ex.: SG&A α = 0,30). Ajustado pelo multiplicador setorial e limitado por α_max.",
        ),
        (
            "β (beta)",
            "Peso de **sublinhas / buckets** nas notas explicativas (atendimento, aluguel, etc.). "
            "**Ainda não aplicado** na v0.1 — previsto na taxonomia de sublinhas.",
        ),
        (
            "ρ (rho) — taxa de captura",
            "Fração do teto teoricamente capturável mesmo com capacidade financeira plena. "
            "Cenário-base: 0,70. Entra em: Viável = Teto × F × ρ. É **parâmetro de nível, não "
            "de ordenação**: por ser constante para todas as empresas, é cancelada pela "
            "normalização min–max, e o `score_0_100` e o `rank` não mudam com ρ (ver 3.2.1). "
            "Cenários de sensibilidade em `rho_cenarios`: 0,50 / 0,70 / 0,90.",
        ),
        (
            "φ (phi) — execução base",
            "Fração do viável realizada **sem** readiness digital. Cenário-base: 0,85. "
            "Com readiness, o fator sobe até 1,0: Final = Viável × (φ + (1−φ)×R_eff).",
        ),
        (
            "λ (lambda)",
            "Parâmetro de **curvatura** do readiness na execução: R_eff = R^(1/(1+λ)). "
            "Cenário-base: 0,10. Estritamente crescente e sem saturação — não cria potencial "
            "acima do viável nem empata o topo do painel. Com λ = 0, R_eff = R.",
        ),
        (
            "F / F^fin — capacidade financeira",
            "F = f(Caixa/Ativo) × g(DL/EBITDA) × h(FCO/ROL). Penaliza empresas sem liquidez, muito "
            "alavancadas ou que queimam caixa. F = 1,0 (100/100) = sem desconto financeiro.",
        ),
        (
            "h (FCO/ROL)",
            "Componente de F pela geração de caixa operacional (DFC 6.01): FCO < 0 → 0,85; ≥ 0 → 1,00. "
            "Sem DFC ou instituição financeira → 1,00.",
        ),
        (
            "FCO",
            "Caixa líquido das atividades operacionais — DFC conta 6.01 (método indireto ou direto).",
        ),
        (
            "f (caixa/ativo)",
            "Componente de F pela liquidez: <3% → 0,75; 3–8% → 0,90; ≥8% → 1,00.",
        ),
        (
            "g (alavancagem)",
            "Componente de F pela dívida: DL/EBITDA <2× → 1,00; 2× a 3,5× → 0,70; ≥3,5× → 0,40; "
            "EBITDA ≤ 0 → 0,25. Instituições financeiras: g fixo (`g_financeiro`).",
        ),
        (
            "R / Readiness",
            "Proxy de capacidade digital no balanço: combinação de Software/Ativo e Intangível/Ativo "
            "(pesos w_soft e w_intang), expressa como **percentil** no painel válido do ano (0–1). "
            "Modos alternativos: `escala` (r / q90) e `bruto` (clip).",
        ),
        (
            "Pessoal líquido (pessoal_modo)",
            "A folha (DVA 7.08.01) já está dentro de CPV, SG&A e vendas. No modo `liquido` ela é retirada "
            "pro rata dessas linhas e recebe seu próprio α; `separado` soma tudo (dupla contagem); "
            "`excluir` ignora a linha. Coluna `fator_pessoal_liquido` = 1 − Pessoal/(CPV+SG&A+Vendas).",
        ),
        (
            "R_eff",
            "Readiness efetiva usada na execução: R^(1/(1+λ)). Coluna `readiness_efetiva`.",
        ),
        (
            "Teto (Objetivo 1)",
            "Ganho máximo teórico em R$: soma das linhas afetáveis × α (com teto L/ROL). "
            "Também expresso como % da receita.",
        ),
        (
            "Potencial viável (Objetivo 2)",
            "Teto após F e ρ: Viável = Teto × F × ρ. Quanto do máximo é capturável financeiramente.",
        ),
        (
            "Potencial final (Objetivo 3)",
            "Viável após execução/readiness: Final = Viável × (φ + (1−φ)×R_eff). "
            "Principal resultado em R$ na ficha da empresa.",
        ),
        (
            "Exposição / Expo",
            "Versão do teto em razão da receita: Expo = Teto / ROL. Base do score relativo.",
        ),
        (
            "Score / score_0_100",
            "Score bruto = min(Expo, p99) × F × ρ × fator de execução; depois normalizado **min–max** "
            "em 0–100 só entre empresas válidas do mesmo ano. Serve ao ranking relativo.",
        ),
        (
            "Winsorização (winsor_exposicao_pct)",
            "A exposição usada no score é truncada no percentil 99 do painel válido para que uma DFP "
            "atípica não comprima a escala 0–100 das demais. O teto em R$ não é alterado.",
        ),
        (
            "Rank",
            "Posição da empresa no painel do ano ordenada pelo score_0_100 (#1 = maior score).",
        ),
        (
            "ROL / Receita",
            "Receita operacional líquida (conta típica 3.01). Denominador de % da receita e Expo.",
        ),
        (
            "α_max",
            "Teto do α efetivo após ajuste setorial. Cenário-base: 0,60.",
        ),
        (
            "E_s / Ē — multiplicador setorial",
            "Prior que escala α por setor (ex.: financeiro 1,25; commodities 0,75). "
            "O setor vem do SETOR_ATIV do cadastro CVM (fallback: nome).",
        ),
        (
            "setor_fonte",
            "De onde veio o setor: `cvm` (cadastro), `nome` (palavras-chave), `template` (plano de contas "
            "financeiro) ou `padrao` (sem regra → outros).",
        ),
        (
            "Categoria A / B (CVM)",
            "Registro de emissor: **A** pode ter ações em bolsa; **B** só outros valores mobiliários (dívida). "
            "Subsidiárias e SPEs são tipicamente B e, se entram só pela DFP individual, ficam fora do painel.",
        ),
        (
            "origem_dfp",
            "Se as demonstrações usadas são `consolidado` ou `individual` (companhia sem controladas).",
        ),
        (
            "DFP",
            "Demonstrações Financeiras Padronizadas — arquivo anual aberto da CVM usado como fonte.",
        ),
        (
            "CVM",
            "Comissão de Valores Mobiliários. Portal de dados abertos de onde vêm as DFPs.",
        ),
        (
            "B3",
            "Bolsa brasileira; universo-alvo do indicador (companhias abertas com DFP).",
        ),
        (
            "DRE / BPA / BPP / DVA / DFC",
            "Demonstrações usadas na extração: Resultado, Ativo, Passivo, Valor Adicionado e Fluxo de Caixa "
            "(consolidado; individual quando a companhia não publica consolidado).",
        ),
        (
            "SG&A",
            "Despesas gerais e administrativas — linha-núcleo de exposição a GenAI/RPA/colarinho branco.",
        ),
        (
            "CPV / COGS",
            "Custo dos produtos/serviços vendidos — entra com α menor (mais commodity).",
        ),
        (
            "PDD / PeLD",
            "Provisão para créditos de liquidação duvidosa — DRE por texto, fallback DVA 7.01.04. "
            "α = 0,40 em financeiras e 0,15 nas demais (`alpha_pdd_nao_financeiro`).",
        ),
        (
            "EBITDA (proxy)",
            "Aproximação: resultado antes do financeiro + depreciação. Usado em g(DL/EBITDA).",
        ),
        (
            "DL — dívida líquida",
            "DL = Dívida − Caixa. Numerador da alavancagem em g.",
        ),
        (
            "CNAE",
            "Classificação oficial de atividade econômica. Ainda não usada; setor hoje é por palavras no nome.",
        ),
        (
            "AIIE (Felten)",
            "AI Industry Exposure — exposição ocupacional agregada por indústria (Felten, Raj & Seamans). "
            "Referência externa para validação setorial futura.",
        ),
        (
            "Empresa válida",
            "Passa nos filtros: receita mínima, exposição > 0, sem “RECUPERA” no nome (se ativo), "
            "e ao menos uma entre SG&A/vendas/pessoal.",
        ),
        (
            "Painel do ano",
            "Conjunto de empresas válidas da DFP daquele ano. Score 0–100 e rank são relativos a esse painel.",
        ),
    ]

    def _gloss_sort_key(termo: str) -> str:
        """Ordem alfabética; símbolos gregos usam o nome em latim entre parênteses."""
        import re
        import unicodedata

        t = termo.strip()
        m = re.match(r"^[αβρφλ]\s*\(([^)]+)\)", t)
        if m:
            t = m.group(1)
        t = unicodedata.normalize("NFKD", t)
        t = "".join(c for c in t if not unicodedata.combining(c))
        return t.casefold()

    glossario = sorted(glossario, key=lambda x: _gloss_sort_key(x[0]))

    mapa = {t: s for t, s in glossario}
    g1, g2 = st.columns([1.1, 2.9])
    with g1:
        termo = st.selectbox(
            "Termo",
            [t for t, _ in glossario],
            label_visibility="collapsed",
            key="glossario_termo",
        )
    with g2:
        st.markdown(mapa[termo])


def main() -> None:
    st.title(PRODUCT_NAME)
    st.caption(
        "Índice de Exposição e Potencial de Benefício por IA "
        "(Ex-Ante: antes da adoção — abordagem preditiva)"
    )

    years = list_years()

    # Cabeçalho de navegação (sem emojis)
    nav_cols = st.columns([3, 1])
    with nav_cols[0]:
        pagina = st.radio(
            "Navegação",
            ["Empresa", "Ranking", "Config", "Sobre"],
            horizontal=True,
            label_visibility="collapsed",
            key="nav_principal",
        )
    with nav_cols[1]:
        if years:
            ano_l, ano_s = st.columns([0.35, 1.65])
            with ano_l:
                st.markdown(
                    "<div style='padding-top:0.55rem;font-weight:500;'>Ano</div>",
                    unsafe_allow_html=True,
                )
            with ano_s:
                year = st.selectbox(
                    "Ano",
                    years,
                    index=0,
                    label_visibility="collapsed",
                )
        else:
            year = None

    st.markdown("---")

    if pagina == "Config":
        pagina_config(years, year)
        return

    if not years:
        st.error("Nenhum ranking em `output/`. Rode: `python main.py --year 2025`")
        if pagina == "Sobre":
            pagina_sobre()
        return

    mtime = (OUTPUT / f"ranking_ia_exante_{year}.csv").stat().st_mtime
    df = load_ranking(year, mtime)

    if not has_objetivos(df):
        st.warning(
            f"Ranking de {year} sem campos de potencial em R$. "
            f"Recalcule com: `python main.py --year {year}`"
        )
        st.cache_data.clear()

    if pagina == "Empresa":
        pagina_empresa(df, year)
    elif pagina == "Ranking":
        pagina_ranking(df, year)
    else:
        pagina_sobre()


if __name__ == "__main__":
    main()
