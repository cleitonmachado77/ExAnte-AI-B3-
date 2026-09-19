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

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
PRODUCT_NAME = "ExAnte-AI (B3)"

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

    rank_val = row.get("rank")
    n_painel = len(df)
    if pd.notna(rank_val) and n_painel > 0:
        rank_i = int(rank_val)
        st.markdown(
            """
<style>
/* Nome + posição na mesma linha, lado a lado */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPopover"]) {
  align-items: baseline !important;
  flex-wrap: wrap !important;
  gap: 0.85rem !important;
}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPopover"]) > div[data-testid="column"] {
  width: auto !important;
  flex: 0 1 auto !important;
  min-width: fit-content !important;
}
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stPopover"]) h3 {
  margin: 0 !important;
  padding: 0 !important;
}
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
  font-weight: 600 !important;
  font-size: 1.75rem !important;
  line-height: 1.2 !important;
  margin: 0 !important;
}
div[data-testid="stPopover"] button svg {
  display: none !important;
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
        },
    ]

    cols = st.columns(3)
    for col, o in zip(cols, objetivos):
        with col:
            st.markdown(_card_objetivo(**o), unsafe_allow_html=True)

    # Funil visual dos 3 objetivos
    st.markdown("#### Funil de valor (R$)")

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

    # De onde vem o valor
    st.markdown("#### De onde vem o teto (R$ por linha contábil)")
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
                "Linha": origem.index,
                "Potencial R$": [fmt_money(v) for v in origem.values],
                "% do teto": [
                    fmt_pct(100 * v / safe(row, "obj1_teto_rs"))
                    if safe(row, "obj1_teto_rs")
                    else "—"
                    for v in origem.values
                ],
            }
        )
        st.dataframe(detalhe, hide_index=True, use_container_width=True)
    fpl = row.get("fator_pessoal_liquido") if "fator_pessoal_liquido" in row.index else None
    if fpl is not None and pd.notna(fpl) and float(fpl) < 0.999:
        st.caption(
            f"Pessoal (DVA) = {fmt_pct(100 * (1 - float(fpl)))} de CPV + SG&A + vendas. Essa parcela foi "
            f"retirada dessas três linhas (fator {fmt_num(float(fpl), 2)}) e entra só na linha Pessoal — "
            "sem dupla contagem."
        )

    # Comparativo
    st.markdown("#### Comparativo")
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
    st.dataframe(comp, hide_index=True, use_container_width=True)
    st.caption(f"Posição no setor: #{pos_setor} / {len(peers)}")

    # Linhas brutas
    with st.expander("Ver linhas contábeis brutas usadas no cálculo", expanded=True):
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
                rows_tab.append({"Linha": label, "Valor": "—", "% da receita": "—"})
            else:
                pct = f"{100 * abs(float(val)) / receita:.1f}%" if as_pct and receita else "—"
                rows_tab.append({"Linha": label, "Valor": fmt_money(val), "% da receita": pct})
        st.dataframe(pd.DataFrame(rows_tab), hide_index=True, use_container_width=True)

        v1, v2, v3, v4 = st.columns(4)
        v1.metric("Caixa / Ativo", fmt_pct(100 * safe(row, "caixa_sobre_ativo")))
        dl = row["dl_sobre_ebitda"] if "dl_sobre_ebitda" in row.index else float("nan")
        v2.metric("DL / EBITDA", fmt_num(dl, 2) if pd.notna(dl) else "—")
        fr = row["fco_sobre_receita"] if "fco_sobre_receita" in row.index else float("nan")
        v3.metric("FCO / Receita", fmt_pct(100 * float(fr)) if pd.notna(fr) else "—")
        v4.metric("Multiplicador setorial", fmt_num(row.get("mult_setor", 1), 2))

    st.markdown(f"#### Pares do setor ({setor})")
    peer_cols = [
        c
        for c in [
            "rank", "DENOM_CIA", "obj3_potencial_final_rs",
            "obj1_teto_rs", "score_0_100", "f_fin",
        ]
        if c in peers.columns
    ]
    peers_show = peers.nsmallest(min(10, len(peers)), "rank")[peer_cols].copy()
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
    st.dataframe(peers_show, hide_index=True, use_container_width=True)

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
    st.dataframe(display, use_container_width=True, hide_index=True, height=420)

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

    st.markdown("### 3. Fórmulas")
    st.markdown("#### 3.1 Valor em R$ (o que o painel destaca)")

    st.latex(r"Teto_i = \sum_k \min(|\tilde L_{i,k}|,\, 3\cdot ROL_i)\times \alpha_{k,s(i)}")
    st.markdown(
        "O **teto** é o ganho máximo teórico da empresa $i$: soma, sobre as linhas "
        "de custo afetáveis $\\tilde L_{i,k}$ (SG&A, vendas, pessoal, CPV, PDD, estoques), "
        "o valor absoluto limitado a 3× a receita operacional líquida ($ROL_i$), "
        "multiplicado pelo fator de afetabilidade $\\alpha_{k,s(i)}$ da linha $k$ "
        "no setor da empresa. O teto mede espaço econômico bruto — ainda sem capacidade "
        "financeira nem execução."
    )
    st.latex(
        r"\tilde L_{i,k} = L_{i,k}\times\left(1 - \frac{Pessoal_i}{CPV_i + SGA_i + Vendas_i}\right)"
        r"\quad k \in \{CPV, SGA, Vendas\}"
    )
    st.markdown(
        "**Sem dupla contagem de pessoal.** A linha *Pessoal* (DVA 7.08.01) já está embutida em "
        "CPV, SG&A e despesas com vendas. No modo padrão (`pessoal_modo: liquido`) a folha é "
        "retirada *pro rata* dessas três linhas e recebe seu próprio $\\alpha_{pessoal}$; "
        "as demais linhas ficam só com a parcela não-salarial. Em bancos “Despesas de Pessoal” "
        "já é linha separada e nada é subtraído. Os modos `separado` (versão antiga, superestimava "
        "o teto em ~25%) e `excluir` continuam disponíveis."
    )

    st.latex(
        r"F^{fin}_i = f\!\left(\frac{Caixa_i}{Ativo_i}\right) \times g\!\left(\frac{DL_i}{EBITDA_i}\right)"
        r" \times h\!\left(\frac{FCO_i}{ROL_i}\right)"
    )
    st.markdown(
        "A **viabilidade financeira** $F^{fin}_i$ combina liquidez ($f$: caixa sobre ativo), "
        "alavancagem ($g$: dívida líquida sobre EBITDA) e **geração de caixa operacional** "
        "($h$: FCO da DFC, conta 6.01, sobre a receita — empresa que queima caixa tem menos "
        "folga para investir em IA mesmo com caixa em balanço). Valores próximos de 1 indicam "
        "condição financeira favorável; valores menores comprimem o teto na etapa seguinte. "
        "As faixas de $f$, $g$ e $h$ estão na seção 3.4."
    )

    st.latex(r"Viavel_i = Teto_i \times F^{fin}_i \times \rho")
    st.markdown(
        "O **potencial viável** aplica ao teto a capacidade financeira e a **taxa de captura** "
        "$\\rho$ (cenário-base 0,70): reconhece que nem todo ganho teórico se materializa, "
        "mesmo com caixa e endividamento adequados. É o segundo número do funil no painel."
    )

    st.latex(
        r"r_i = w_{soft}\cdot\frac{Soft_i}{Ativo_i}"
        r" + w_{intang}\cdot\frac{Intang_i}{Ativo_i}"
        r"\qquad R_i = \mathrm{percentil}_{painel}(r_i) \in [0,1]"
    )
    st.markdown(
        "O **readiness** $R_i$ resume a predisposição digital implícita no balanço "
        "(software e intangíveis sobre o ativo total), com pesos $w_{soft}$ e $w_{intang}$. "
        "Como essas razões ficam abaixo de 0,05 na quase totalidade das empresas, um simples "
        "`clip(r, 0, 1)` deixaria o Bloco C inerte; por isso $R_i$ é a **posição relativa** "
        "de $r_i$ entre as empresas válidas do ano (`readiness_modo: percentil`; alternativas "
        "`escala` = $r/q_{90}$ e `bruto`). R não aumenta o teto; só informa a etapa de execução."
    )

    st.latex(r"R^{eff}_i = \mathrm{clip}_{[0,1]}(R_i\cdot(1+\lambda))")
    st.markdown(
        "A **readiness efetiva** amplifica levemente $R_i$ pelo fator $(1+\\lambda)$ "
        "(cenário-base $\\lambda = 0{,}10$) e volta a clipar em [0, 1], evitando que "
        "o ajuste ultrapasse o teto de 100% na execução."
    )

    st.latex(r"Final_i = Viavel_i \times \big(\phi + (1-\phi)\, R^{eff}_i\big)")
    st.markdown(
        "O **potencial final** é o resultado principal em R$: parte do viável e aplica o "
        "**fator de execução** $\\phi + (1-\\phi) R^{eff}_i$. Com $\\phi = 0{,}85$, "
        "mesmo readiness nulo preserva 85% do viável; readiness alto aproxima o final "
        "de 100% do viável. Ordem no código: teto → F → viável (ρ) → R → final (φ)."
    )

    st.markdown(
        """
| Símbolo | Papel | Cenário-base |
|---|---|---|
| **ρ** | Taxa de captura (nem todo teto se realiza) | 0,70 |
| **φ** | Execução base sem readiness | 0,85 |
| **λ** | Amplifica levemente R na execução | 0,10 |
| **w_soft / w_intang** | Pesos do Bloco C | 0,50 / 0,20 |
"""
    )

    st.markdown("#### 3.2 Score relativo (ranking)")
    st.latex(
        r"Score_i = \min(Expo_i,\, q_{99}) \times F^{fin}_i \times \rho"
        r" \times \big(\phi + (1-\phi)\, R^{eff}_i\big)"
    )
    st.markdown(
        "O **score bruto** replica o funil em razão da receita: "
        "$Expo_i = Teto_i / ROL_i$, em seguida os mesmos fatores $F^{fin}$, $\\rho$ "
        "e execução. A exposição é **winsorizada** no percentil 99 do painel válido "
        "(`winsor_exposicao_pct`) para que uma DFP atípica não comprima a escala de todas as "
        "outras; o teto em R$ não é alterado. Serve à **comparação relativa** entre empresas "
        "(não substitui o potencial final em R$). O **rank** ordena pelo `score_0_100`."
    )

    st.markdown("#### 3.3 Ajuste setorial do α")
    st.latex(r"\alpha_{k,s} = \min\left(\alpha^{base}_k \times \frac{E_s}{\bar E},\; 0{,}60\right)")
    st.markdown(
        "O $\\alpha$ da linha $k$ no setor $s$ parte do $\\alpha^{base}_k$ e é "
        "escalado pelo prior setorial $E_s/\\bar E$ (exposição relativa à média), "
        "com teto de 0,60. Assim, setores com maior exposição ocupacional a IA elevam "
        "a afetabilidade das mesmas linhas contábeis. Na v1, $E_s/\\bar E$ são "
        "priors (tabela na seção 5). **Exceção — PDD:** fora do setor financeiro a provisão "
        "para créditos é pequena e pouco automatizável; o $\\alpha^{base}$ da PDD cai de "
        "0,40 para **0,15** (`alpha_pdd_nao_financeiro`), como sugere o documento de pesos."
    )

    st.markdown("#### 3.4 Viabilidade financeira (detalhe de F)")
    st.markdown("Já usada na etapa do viável. Faixas de $f$, $g$ e $h$:")

    c1, c2, c3 = st.columns(3)
    with c3:
        st.markdown("**Função $h$ — geração de caixa**")
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
    with c1:
        st.markdown("**Função $f$ — caixa/ativo**")
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
        st.markdown("**Função $g$ — alavancagem**")
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
    st.caption(
        "Para bancos e seguradoras (plano de contas com “Receitas da Intermediação Financeira”) "
        "DL/EBITDA não é definido — a captação é por depósitos e não há EBITDA — e o FCO oscila "
        "com a carteira de crédito. Usa-se g fixo (`g_financeiro`), h = 1 e apenas f(Caixa/Ativo) diferencia."
    )

    st.markdown("#### 3.5 Readiness e execução")
    st.markdown(
        "O Bloco C não *aumenta* o teto: ele define quanto do **viável** se realiza. "
        "Com φ = 0,85 e R ≈ 0, o final fica em 85% do viável; com R alto, aproxima-se de 100% do viável. "
        "Como R é percentil no painel, o fator de execução se distribui de fato entre 0,85 e 1,0 "
        "(antes, com clip da razão bruta, ficava ≈ 0,85 para quase todas). "
        "P&D (`w_ped`) está reservado na calibração e **ainda não entra** no cálculo da v0.1."
    )

    st.markdown("#### 3.6 Normalização 0–100")
    st.latex(
        r"Score^{0\text{-}100}_i ="
        r" 100 \times \frac{Score_i - \min(Score)}{\max(Score) - \min(Score)}"
    )
    st.markdown(
        "A escala **0–100** é uma normalização min–max do score bruto **somente entre "
        "empresas válidas do mesmo ano**: o pior score do painel vira 0 e o melhor, 100. "
        "Não é percentil (há a opção `normalizacao_score: percentil` na Config). Como a exposição "
        "que entra no score é winsorizada (3.2), o topo da escala corresponde ao percentil 99 de "
        "exposição, não ao outlier. Os índices auxiliares `obj1_0_100`, `obj2_0_100` e `obj3_0_100` "
        "são percentis do valor em R$ (uso interno); a ficha destaca R$ e % da receita."
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
            "Cenário-base: 0,70. Entra em: Viável = Teto × F × ρ.",
        ),
        (
            "φ (phi) — execução base",
            "Fração do viável realizada **sem** readiness digital. Cenário-base: 0,85. "
            "Com readiness, o fator sobe até 1,0: Final = Viável × (φ + (1−φ)×R_eff).",
        ),
        (
            "λ (lambda)",
            "Parâmetro que **amplifica** o readiness na execução: R_eff = clip(R × (1+λ)). "
            "Cenário-base: 0,10. Não cria potencial acima do viável.",
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
            "Readiness efetiva usada na execução: clip(R × (1+λ), 0, 1).",
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
