"""Página Config — edição da metodologia (pesos, filtros, mapeamento CVM)."""

from __future__ import annotations

import io
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config"
PESOS_PATH = CONFIG / "pesos.yaml"
MAPA_PATH = CONFIG / "mapeamento_contas.yaml"

ALPHA_LABELS = {
    "pessoal": "Pessoal (DVA)",
    "sga": "SG&A",
    "vendas": "Despesas com vendas",
    "pdd": "PDD",
    "cpv": "CPV",
    "estoques": "Estoques",
}

MAPA_LABELS = {
    "receita": "Receita (ROL)",
    "cpv": "CPV",
    "vendas": "Despesas com vendas",
    "sga": "SG&A",
    "ebit": "EBIT (proxy)",
    "pdd": "PDD",
    "caixa": "Caixa",
    "estoques": "Estoques",
    "ativo_total": "Ativo total",
    "intangivel": "Intangível",
    "software": "Software",
    "divida": "Dívida",
    "pessoal_dva": "Pessoal (DVA)",
    "depreciacao": "Depreciação",
    "pdd_dva": "PDD (DVA 7.01.04 — fallback)",
    "receita_dva": "Receitas DVA (só checagem)",
    "fco": "FCO (DFC 6.01)",
}

EXIGIR_OPCOES = ["sga", "vendas", "pessoal", "cpv", "pdd", "estoques"]


def _load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML inválido em {path}")
    return data


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=100,
        )


def _split_list(text: str, sep_comma: bool = True) -> list[str]:
    """Quebra por ';' / nova linha e, se ``sep_comma``, também por ','.

    Regex podem conter vírgulas (ex.: ``{1,3}``) — para padrões use
    ``sep_comma=False`` e separe por ';'.
    """
    parts: list[str] = []
    for chunk in (text or "").replace(";", "\n").splitlines():
        items = chunk.split(",") if sep_comma else [chunk]
        for item in items:
            s = item.strip()
            if s:
                parts.append(s)
    return parts


def _join_list(items: list[Any] | None, sep: str = ", ") -> str:
    if not items:
        return ""
    return sep.join(str(x) for x in items)


def _nullify(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, str) and v.strip().lower() in {"", "none", "null", "nan"}:
        return None
    return v


def _rules_to_df(rules: list[dict] | None) -> pd.DataFrame:
    rows = []
    for r in rules or []:
        rows.append(
            {
                "max_exclusive": r.get("max_exclusive"),
                "valor": float(r.get("valor", 1.0)),
            }
        )
    if not rows:
        rows = [{"max_exclusive": None, "valor": 1.0}]
    return pd.DataFrame(rows)


def _df_to_rules(df: pd.DataFrame) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        mx = _nullify(row.get("max_exclusive"))
        if mx is not None:
            mx = float(mx)
        rules.append({"max_exclusive": mx, "valor": float(row["valor"])})
    return rules


def _ensure_session() -> None:
    if "cfg_pesos" not in st.session_state:
        st.session_state.cfg_pesos = _load_yaml(PESOS_PATH)
    if "cfg_mapa" not in st.session_state:
        st.session_state.cfg_mapa = _load_yaml(MAPA_PATH)
    if "cfg_dirty" not in st.session_state:
        st.session_state.cfg_dirty = False


def _reload_from_disk() -> None:
    st.session_state.cfg_pesos = _load_yaml(PESOS_PATH)
    st.session_state.cfg_mapa = _load_yaml(MAPA_PATH)
    st.session_state.cfg_dirty = False


def _mark_dirty() -> None:
    st.session_state.cfg_dirty = True


def _salvar() -> None:
    pesos = deepcopy(st.session_state.cfg_pesos)
    mapa = deepcopy(st.session_state.cfg_mapa)
    _dump_yaml(PESOS_PATH, pesos)
    _dump_yaml(MAPA_PATH, mapa)
    st.session_state.cfg_dirty = False


def _recalcular(year: int) -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from indicador_ia.pipeline import run  # noqa: WPS433

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        run(year=year, force_download=False)
    finally:
        sys.stdout = old
    return buf.getvalue()


def pagina_config(years: list[int], year_default: int | None) -> None:
    st.subheader("Configuração da metodologia")
    st.caption(
        "ExAnte-AI (B3) — edite pesos α, multiplicadores setoriais, viabilidade financeira, "
        "readiness, filtros de qualidade e o mapeamento de contas CVM. Salve e recalcule o ranking."
    )

    _ensure_session()
    pesos: dict[str, Any] = st.session_state.cfg_pesos
    mapa: dict[str, Any] = st.session_state.cfg_mapa

    # ---- barra de ações ----
    a1, a2, a3, a4 = st.columns([1.1, 1.1, 1.4, 1.6])
    with a1:
        if st.button("Salvar no YAML", type="primary", use_container_width=True):
            try:
                _salvar()
                st.success(f"Salvo em `{PESOS_PATH.name}` e `{MAPA_PATH.name}`.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha ao salvar: {exc}")
    with a2:
        if st.button("Recarregar do disco", use_container_width=True):
            _reload_from_disk()
            st.rerun()
    with a3:
        anos = years or ([year_default] if year_default else [2025])
        idx = 0
        if year_default in anos:
            idx = anos.index(year_default)
        y_l, y_s = st.columns([1.15, 1.2])
        with y_l:
            st.markdown(
                "<div style='padding-top:0.55rem;font-weight:500;'>Ano para recalcular</div>",
                unsafe_allow_html=True,
            )
        with y_s:
            year_run = st.selectbox(
                "Ano para recalcular",
                anos,
                index=idx,
                key="cfg_year_run",
                label_visibility="collapsed",
            )
    with a4:
        if st.button("Salvar e recalcular ranking", use_container_width=True):
            try:
                _salvar()
                with st.spinner(f"Recalculando DFP {year_run}..."):
                    log = _recalcular(int(year_run))
                st.cache_data.clear()
                st.success(f"Ranking de {year_run} atualizado.")
                with st.expander("Log do pipeline"):
                    st.code(log or "(sem saída)")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Falha no recálculo: {exc}")

    if st.session_state.cfg_dirty:
        st.warning("Há alterações não salvas.")

    tabs = st.tabs(
        [
            "Pesos α",
            "Setores",
            "Viabilidade financeira",
            "Readiness",
            "Filtros",
            "Mapeamento CVM",
            "YAML bruto",
        ]
    )

    # ---- 1. Pesos α ----
    with tabs[0]:
        st.markdown("#### Fatores de suscetibilidade (α base)")
        st.caption(
            "Percentual da linha contábil considerado afetável por IA. "
            "α efetivo = min(α_base × multiplicador setorial, α_max)."
        )
        alpha = dict(pesos.get("alpha_base") or {})
        rows = []
        for key in ["pessoal", "sga", "vendas", "pdd", "cpv", "estoques"]:
            rows.append(
                {
                    "chave": key,
                    "Linha": ALPHA_LABELS.get(key, key),
                    "α base": float(alpha.get(key, 0.0)),
                }
            )
        alpha_df = pd.DataFrame(rows)
        edited_alpha = st.data_editor(
            alpha_df,
            hide_index=True,
            use_container_width=True,
            disabled=["chave", "Linha"],
            column_config={
                "chave": None,
                "α base": st.column_config.NumberColumn(min_value=0.0, max_value=1.0, step=0.01, format="%.2f"),
            },
            key="cfg_alpha_editor",
        )
        new_alpha = {
            str(r["chave"]): float(r["α base"])
            for _, r in edited_alpha.iterrows()
        }
        if new_alpha != alpha:
            pesos["alpha_base"] = new_alpha
            _mark_dirty()

        c1, c2 = st.columns(2)
        with c1:
            alpha_max = st.number_input(
                "α máximo (teto após ajuste setorial)",
                min_value=0.0,
                max_value=1.0,
                value=float(pesos.get("alpha_max", 0.60)),
                step=0.01,
                key="cfg_alpha_max",
            )
            if float(pesos.get("alpha_max", 0.60)) != float(alpha_max):
                pesos["alpha_max"] = float(alpha_max)
                _mark_dirty()
        with c2:
            max_l = st.number_input(
                "Teto L/ROL por linha (max_linha_sobre_receita)",
                min_value=0.1,
                max_value=20.0,
                value=float(pesos.get("max_linha_sobre_receita", 3.0)),
                step=0.1,
                key="cfg_max_lrol",
            )
            if float(pesos.get("max_linha_sobre_receita", 3.0)) != float(max_l):
                pesos["max_linha_sobre_receita"] = float(max_l)
                _mark_dirty()

        st.markdown("#### Ajustes de base afetável")
        p1, p2 = st.columns(2)
        with p1:
            modos = ["liquido", "separado", "excluir"]
            modo_atual = str(pesos.get("pessoal_modo", "liquido")).lower()
            pessoal_modo = st.selectbox(
                "Pessoal (DVA 7.08.01) — tratamento",
                options=modos,
                index=modos.index(modo_atual) if modo_atual in modos else 0,
                key="cfg_pessoal_modo",
                help=(
                    "liquido: retira a folha de CPV/SG&A/Vendas (pro rata) e aplica α_pessoal só sobre Pessoal "
                    "(sem dupla contagem). separado: soma tudo como linhas independentes (versão antiga). "
                    "excluir: ignora Pessoal."
                ),
            )
            if modo_atual != pessoal_modo:
                pesos["pessoal_modo"] = pessoal_modo
                _mark_dirty()
        with p2:
            apdd_atual = pesos.get("alpha_pdd_nao_financeiro")
            usar_apdd = st.checkbox(
                "α da PDD diferente fora do setor financeiro",
                value=apdd_atual is not None,
                key="cfg_usar_apdd",
            )
            apdd = st.number_input(
                "α PDD (não-financeiras)",
                min_value=0.0,
                max_value=1.0,
                value=float(apdd_atual if apdd_atual is not None else 0.15),
                step=0.01,
                key="cfg_apdd",
                disabled=not usar_apdd,
                help="Pesos_Alpha_Beta §3: 0,15 (ou 0 = excluir) fora de bancos/financeiras.",
            )
            novo = float(apdd) if usar_apdd else None
            if novo != apdd_atual:
                pesos["alpha_pdd_nao_financeiro"] = novo
                _mark_dirty()

    # ---- 2. Setores ----
    with tabs[1]:
        st.markdown("#### Multiplicadores setoriais (E_s / Ē)")
        setor_mult = dict(pesos.get("setor_mult") or {})
        sm_rows = [
            {"Setor": k, "Multiplicador": float(v)}
            for k, v in setor_mult.items()
        ]
        if not sm_rows:
            sm_rows = [{"Setor": "outros", "Multiplicador": 1.0}]
        sm_df = pd.DataFrame(sm_rows)
        edited_sm = st.data_editor(
            sm_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Multiplicador": st.column_config.NumberColumn(min_value=0.0, max_value=3.0, step=0.05, format="%.2f"),
            },
            key="cfg_setor_mult_editor",
        )
        new_sm = {
            str(r["Setor"]).strip(): float(r["Multiplicador"])
            for _, r in edited_sm.iterrows()
            if str(r.get("Setor", "")).strip()
        }
        if new_sm != setor_mult:
            pesos["setor_mult"] = new_sm
            _mark_dirty()

        usar_cvm = st.checkbox(
            "Usar SETOR_ATIV do cadastro CVM (config/setor_cvm.yaml) antes da heurística por nome",
            value=bool(pesos.get("usar_setor_cvm", True)),
            key="cfg_usar_setor_cvm",
            help="Ordem: cadastro CVM → palavras-chave no nome → 'outros'. Plano de contas financeiro sempre vence.",
        )
        if bool(pesos.get("usar_setor_cvm", True)) != bool(usar_cvm):
            pesos["usar_setor_cvm"] = bool(usar_cvm)
            _mark_dirty()

        st.markdown("#### Palavras-chave de classificação setorial (fallback)")
        st.caption("Usadas quando o cadastro CVM não tem regra. Ordem importa: a primeira batida no nome define o setor.")
        keywords = dict(pesos.get("setor_keywords") or {})
        kw_rows = []
        for setor in list(setor_mult.keys()) + [k for k in keywords if k not in setor_mult]:
            if setor == "outros":
                continue
            kw_rows.append(
                {
                    "Setor": setor,
                    "Palavras-chave (separadas por vírgula)": _join_list(keywords.get(setor, [])),
                }
            )
        if not kw_rows:
            kw_rows = [{"Setor": "financeiro", "Palavras-chave (separadas por vírgula)": ""}]
        kw_df = pd.DataFrame(kw_rows)
        edited_kw = st.data_editor(
            kw_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="cfg_setor_kw_editor",
        )
        new_kw = {
            str(r["Setor"]).strip(): _split_list(str(r.get("Palavras-chave (separadas por vírgula)", "")))
            for _, r in edited_kw.iterrows()
            if str(r.get("Setor", "")).strip()
        }
        if new_kw != keywords:
            pesos["setor_keywords"] = new_kw
            _mark_dirty()

    # ---- 3. Viabilidade financeira ----
    with tabs[2]:
        st.markdown("#### f(Caixa / Ativo)")
        st.caption("Faixas ordenadas. Deixe `max_exclusive` vazio na última linha (sem teto).")
        f_df = _rules_to_df(pesos.get("f_caixa"))
        edited_f = st.data_editor(
            f_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "max_exclusive": st.column_config.NumberColumn(
                    "Limite exclusivo (<)",
                    help="Valor máximo exclusivo da faixa; vazio = última faixa",
                    format="%.4f",
                ),
                "valor": st.column_config.NumberColumn("f", min_value=0.0, max_value=2.0, step=0.05, format="%.2f"),
            },
            key="cfg_f_caixa_editor",
        )
        new_f = _df_to_rules(edited_f)
        if new_f != (pesos.get("f_caixa") or []):
            pesos["f_caixa"] = new_f
            _mark_dirty()

        st.markdown("#### g(DL / EBITDA)")
        g_df = _rules_to_df(pesos.get("g_alavancagem"))
        edited_g = st.data_editor(
            g_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "max_exclusive": st.column_config.NumberColumn(
                    "Limite exclusivo (<)",
                    format="%.2f",
                ),
                "valor": st.column_config.NumberColumn("g", min_value=0.0, max_value=2.0, step=0.05, format="%.2f"),
            },
            key="cfg_g_alav_editor",
        )
        new_g = _df_to_rules(edited_g)
        if new_g != (pesos.get("g_alavancagem") or []):
            pesos["g_alavancagem"] = new_g
            _mark_dirty()

        gn1, gn2 = st.columns(2)
        with gn1:
            g_neg = st.number_input(
                "g quando EBITDA ≤ 0",
                min_value=0.0,
                max_value=1.0,
                value=float(pesos.get("g_ebitda_negativo", 0.25)),
                step=0.05,
                key="cfg_g_neg",
            )
        with gn2:
            g_fin = st.number_input(
                "g para instituições financeiras (DL/EBITDA não definido)",
                min_value=0.0,
                max_value=1.0,
                value=float(pesos.get("g_financeiro", 1.0)),
                step=0.05,
                key="cfg_g_fin",
            )
        if float(pesos.get("g_ebitda_negativo", 0.25)) != float(g_neg):
            pesos["g_ebitda_negativo"] = float(g_neg)
            _mark_dirty()
        if float(pesos.get("g_financeiro", 1.0)) != float(g_fin):
            pesos["g_financeiro"] = float(g_fin)
            _mark_dirty()

        st.markdown("#### h(FCO / ROL) — geração de caixa operacional (DFC 6.01)")
        usar_fco = st.checkbox(
            "Usar FCO da DFC no F financeiro (F = f × g × h)",
            value=bool(pesos.get("usar_fco", True)),
            key="cfg_usar_fco",
            help="Sem DFC ou instituição financeira → h = 1,0.",
        )
        if bool(pesos.get("usar_fco", True)) != bool(usar_fco):
            pesos["usar_fco"] = bool(usar_fco)
            _mark_dirty()
        h_df = _rules_to_df(pesos.get("h_fco"))
        edited_h = st.data_editor(
            h_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "max_exclusive": st.column_config.NumberColumn("Limite exclusivo (<)", format="%.2f"),
                "valor": st.column_config.NumberColumn("h", min_value=0.0, max_value=2.0, step=0.05, format="%.2f"),
            },
            key="cfg_h_fco_editor",
            disabled=not usar_fco,
        )
        new_h = _df_to_rules(edited_h)
        if new_h != (pesos.get("h_fco") or []):
            pesos["h_fco"] = new_h
            _mark_dirty()

    # ---- 4. Readiness / funil ----
    with tabs[3]:
        st.markdown("#### Funil Teto → Viável → Final")
        st.caption(
            "Viável = Teto × F financeiro × ρ captura. "
            "Final = Viável × (φ + (1−φ)×R). Com ρ&lt;1 e φ&lt;1 o funil sempre afunila."
        )
        f1, f2 = st.columns(2)
        with f1:
            rho = st.number_input(
                "ρ captura (rho_captura)",
                min_value=0.05,
                max_value=1.0,
                value=float(pesos.get("rho_captura", 0.70)),
                step=0.05,
                key="cfg_rho",
                help=(
                    "Fração do teto teoricamente capturável mesmo com caixa pleno. "
                    "Altera só o nível em R$: por ser constante entre empresas, é cancelada "
                    "pela normalização min–max e não muda o score 0–100 nem o rank."
                ),
            )
        with f2:
            phi = st.number_input(
                "φ execução base (phi_execucao_base)",
                min_value=0.05,
                max_value=1.0,
                value=float(pesos.get("phi_execucao_base", 0.85)),
                step=0.05,
                key="cfg_phi",
                help="Sem readiness, só esta fração do viável se realiza; R eleva até 100%.",
            )

        st.markdown("#### Bloco C — readiness digital")
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            lam = st.number_input(
                "λ (lambda_ready)",
                min_value=0.0,
                max_value=1.0,
                value=float(pesos.get("lambda_ready", 0.10)),
                step=0.01,
                key="cfg_lambda",
                help="Curvatura da readiness na execução: R_eff = R^(1/(1+λ)). λ = 0 → R_eff = R.",
            )
        with r2:
            w_soft = st.number_input(
                "Peso software",
                min_value=0.0,
                max_value=2.0,
                value=float(pesos.get("w_software", 0.50)),
                step=0.05,
                key="cfg_w_soft",
            )
        with r3:
            w_int = st.number_input(
                "Peso intangível",
                min_value=0.0,
                max_value=2.0,
                value=float(pesos.get("w_intangivel", 0.20)),
                step=0.05,
                key="cfg_w_int",
            )
        with r4:
            w_ped = st.number_input(
                "Peso P&D (reservado)",
                min_value=0.0,
                max_value=2.0,
                value=float(pesos.get("w_ped", 0.30)),
                step=0.05,
                key="cfg_w_ped",
            )
        changed = False
        if float(pesos.get("rho_captura", 0.70)) != float(rho):
            pesos["rho_captura"] = float(rho)
            changed = True
        if float(pesos.get("phi_execucao_base", 0.85)) != float(phi):
            pesos["phi_execucao_base"] = float(phi)
            changed = True
        if float(pesos.get("lambda_ready", 0.10)) != float(lam):
            pesos["lambda_ready"] = float(lam)
            changed = True
        if float(pesos.get("w_software", 0.50)) != float(w_soft):
            pesos["w_software"] = float(w_soft)
            changed = True
        if float(pesos.get("w_intangivel", 0.20)) != float(w_int):
            pesos["w_intangivel"] = float(w_int)
            changed = True
        if float(pesos.get("w_ped", 0.30)) != float(w_ped):
            pesos["w_ped"] = float(w_ped)
            changed = True
        if changed:
            _mark_dirty()

        rm1, rm2 = st.columns(2)
        with rm1:
            rmodos = ["percentil", "escala", "bruto"]
            rmodo_atual = str(pesos.get("readiness_modo", "percentil")).lower()
            rmodo = st.selectbox(
                "Escala do readiness (readiness_modo)",
                options=rmodos,
                index=rmodos.index(rmodo_atual) if rmodo_atual in rmodos else 0,
                key="cfg_readiness_modo",
                help=(
                    "percentil: posição relativa no painel válido. escala: r / quantil de referência. "
                    "bruto: clip(r,0,1) — razões Soft/Ativo < 0,05 deixam o bloco inerte."
                ),
            )
            if rmodo_atual != rmodo:
                pesos["readiness_modo"] = rmodo
                _mark_dirty()
        with rm2:
            rq = st.number_input(
                "Quantil de referência (modo escala)",
                min_value=0.5,
                max_value=1.0,
                value=float(pesos.get("readiness_quantil_ref", 0.90)),
                step=0.01,
                key="cfg_readiness_q",
                disabled=rmodo != "escala",
            )
            if float(pesos.get("readiness_quantil_ref", 0.90)) != float(rq):
                pesos["readiness_quantil_ref"] = float(rq)
                _mark_dirty()
        st.info(
            "r = w_software·Soft/Ativo + w_intangivel·Intang/Ativo → R pela escala escolhida (0–1). "
            "Viável = Teto×F×ρ. Final = Viável×(φ+(1−φ)×R_eff), com R_eff = R^(1/(1+λ))."
        )

    # ---- 5. Filtros ----
    with tabs[4]:
        st.markdown("#### Filtros de qualidade do ranking")
        f1, f2 = st.columns(2)
        with f1:
            min_rec = st.number_input(
                "Receita mínima (R$)",
                min_value=0.0,
                value=float(pesos.get("min_receita", 50_000_000.0)),
                step=1_000_000.0,
                format="%.0f",
                key="cfg_min_rec",
            )
            excl_rj = st.checkbox(
                "Excluir recuperação judicial (nome contém RECUPERA)",
                value=bool(pesos.get("excluir_recuperacao_judicial", True)),
                key="cfg_excl_rj",
            )
            usar_cons = st.checkbox(
                "Usar demonstrações consolidadas",
                value=bool(pesos.get("usar_consolidado", True)),
                key="cfg_usar_cons",
            )
            fb_ind = st.checkbox(
                "Incluir pela individual quem não publica consolidado",
                value=bool(pesos.get("fallback_individual", True)),
                key="cfg_fb_ind",
                disabled=not usar_cons,
            )
            excl_ind_b = st.checkbox(
                "Excluir subsidiárias/SPEs (individual + Categoria B na CVM)",
                value=bool(pesos.get("excluir_individual_categoria_b", True)),
                key="cfg_excl_ind_b",
                help="Malhas da Rumo, distribuidoras de holdings listadas, concessionárias… evita contar controlada + holding.",
            )
            so_cat_a = st.checkbox(
                "Apenas Categoria A (emissoras de ações)",
                value=bool(pesos.get("apenas_categoria_a", False)),
                key="cfg_so_cat_a",
            )
            excl_alerta = st.checkbox(
                "Excluir empresas com alerta_receita (DRE < 50% da DVA)",
                value=bool(pesos.get("excluir_alerta_receita", False)),
                key="cfg_excl_alerta",
            )
        with f2:
            exigir = pesos.get("exigir_ao_menos_uma_de") or []
            exigir_sel = st.multiselect(
                "Exigir ao menos uma destas linhas",
                options=EXIGIR_OPCOES,
                default=[e for e in exigir if e in EXIGIR_OPCOES],
                key="cfg_exigir",
            )
            norm = st.checkbox(
                "Normalizar score em 0–100 no painel do ano",
                value=bool(pesos.get("normalizar_score_0_100", True)),
                key="cfg_norm",
            )
            nmodos = ["minmax", "percentil"]
            nmodo_atual = str(pesos.get("normalizacao_score", "minmax")).lower()
            nmodo = st.selectbox(
                "Escala 0–100 do score",
                options=nmodos,
                index=nmodos.index(nmodo_atual) if nmodo_atual in nmodos else 0,
                key="cfg_norm_modo",
                disabled=not norm,
                help="minmax: 100 = maior score_bruto do painel. percentil: 100 = topo da distribuição.",
            )
            w_atual = pesos.get("winsor_exposicao_pct")
            usar_w = st.checkbox(
                "Winsorizar exposição no score (teto em R$ não muda)",
                value=w_atual is not None,
                key="cfg_usar_winsor",
            )
            wpct = st.number_input(
                "Percentil de truncamento",
                min_value=0.80,
                max_value=1.0,
                value=float(w_atual if w_atual is not None else 0.99),
                step=0.005,
                format="%.3f",
                key="cfg_winsor_pct",
                disabled=not usar_w,
            )

        changed = False
        if bool(pesos.get("excluir_individual_categoria_b", True)) != bool(excl_ind_b):
            pesos["excluir_individual_categoria_b"] = bool(excl_ind_b)
            changed = True
        if bool(pesos.get("apenas_categoria_a", False)) != bool(so_cat_a):
            pesos["apenas_categoria_a"] = bool(so_cat_a)
            changed = True
        if bool(pesos.get("excluir_alerta_receita", False)) != bool(excl_alerta):
            pesos["excluir_alerta_receita"] = bool(excl_alerta)
            changed = True
        if nmodo_atual != nmodo:
            pesos["normalizacao_score"] = nmodo
            changed = True
        novo_w = float(wpct) if usar_w else None
        if novo_w != w_atual:
            pesos["winsor_exposicao_pct"] = novo_w
            changed = True
        if float(pesos.get("min_receita", 50_000_000.0)) != float(min_rec):
            pesos["min_receita"] = float(min_rec)
            changed = True
        if bool(pesos.get("excluir_recuperacao_judicial", True)) != bool(excl_rj):
            pesos["excluir_recuperacao_judicial"] = bool(excl_rj)
            changed = True
        if bool(pesos.get("usar_consolidado", True)) != bool(usar_cons):
            pesos["usar_consolidado"] = bool(usar_cons)
            changed = True
        if bool(pesos.get("fallback_individual", True)) != bool(fb_ind):
            pesos["fallback_individual"] = bool(fb_ind)
            changed = True
        if bool(pesos.get("normalizar_score_0_100", True)) != bool(norm):
            pesos["normalizar_score_0_100"] = bool(norm)
            changed = True
        if list(exigir_sel) != list(exigir):
            pesos["exigir_ao_menos_uma_de"] = list(exigir_sel)
            changed = True
        if changed:
            _mark_dirty()

    # ---- 6. Mapeamento CVM ----
    with tabs[5]:
        st.markdown("#### Mapeamento de contas CVM → variáveis")
        st.caption(
            "Códigos `CD_CONTA` (separe por vírgula) e padrões regex de `DS_CONTA` "
            "(separe por `;` — vírgulas fazem parte da regex). "
            "Se houver código casando, só ele é usado; os padrões são fallback. "
            "A seção `financeiro` (bancos/seguradoras) é editável na aba **YAML bruto**."
        )
        # Só entradas simples do template padrão; `financeiro` e flags extras
        # (ex.: `agregar`) são preservados intactos ao reconstruir o mapa.
        editable_keys = [
            k for k, cfg in mapa.items()
            if k != "financeiro" and isinstance(cfg, dict)
            and ("cd_conta" in cfg or "ds_patterns" in cfg)
        ]
        map_rows = []
        for key in editable_keys:
            cfg = mapa[key]
            map_rows.append(
                {
                    "chave": key,
                    "Variável": MAPA_LABELS.get(key, key),
                    "Códigos CD_CONTA": _join_list(cfg.get("cd_conta")),
                    "Padrões DS_CONTA (regex)": _join_list(cfg.get("ds_patterns"), sep="; "),
                }
            )
        map_df = pd.DataFrame(map_rows)
        edited_map = st.data_editor(
            map_df,
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            disabled=["chave"] if "chave" in map_df.columns else [],
            column_config={"chave": None},
            key="cfg_mapa_editor",
            height=420,
        )
        new_mapa: dict[str, Any] = {}
        for _, r in edited_map.iterrows():
            key = str(r.get("chave") or "").strip()
            if not key:
                # nova linha: usa o rótulo como chave slug
                label = str(r.get("Variável") or "").strip()
                if not label:
                    continue
                key = label.lower().replace(" ", "_")
            entry = dict(mapa.get(key) or {})  # preserva flags extras (agregar…)
            entry["cd_conta"] = _split_list(str(r.get("Códigos CD_CONTA", "")))
            entry["ds_patterns"] = _split_list(
                str(r.get("Padrões DS_CONTA (regex)", "")), sep_comma=False
            )
            new_mapa[key] = entry
        # chaves não editáveis aqui (ex.: `financeiro`) seguem como estão
        for k, cfg in mapa.items():
            if k not in editable_keys and k not in new_mapa:
                new_mapa[k] = cfg
        if new_mapa != mapa:
            st.session_state.cfg_mapa = new_mapa
            _mark_dirty()

    # ---- 7. YAML bruto ----
    with tabs[6]:
        st.markdown("#### Edição avançada (YAML)")
        st.caption("Edite o texto e clique em Aplicar para carregar na sessão (ainda precisa Salvar).")
        y1, y2 = st.columns(2)
        with y1:
            st.markdown("`pesos.yaml`")
            pesos_txt = st.text_area(
                "pesos",
                value=yaml.dump(pesos, allow_unicode=True, default_flow_style=False, sort_keys=False),
                height=420,
                label_visibility="collapsed",
                key="cfg_pesos_raw",
            )
            if st.button("Aplicar pesos.yaml", key="cfg_apply_pesos"):
                try:
                    parsed = yaml.safe_load(pesos_txt) or {}
                    if not isinstance(parsed, dict):
                        raise ValueError("O YAML de pesos deve ser um mapeamento.")
                    st.session_state.cfg_pesos = parsed
                    _mark_dirty()
                    st.success("Pesos aplicados na sessão.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"YAML inválido: {exc}")
        with y2:
            st.markdown("`mapeamento_contas.yaml`")
            mapa_txt = st.text_area(
                "mapa",
                value=yaml.dump(
                    st.session_state.cfg_mapa,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                ),
                height=420,
                label_visibility="collapsed",
                key="cfg_mapa_raw",
            )
            if st.button("Aplicar mapeamento_contas.yaml", key="cfg_apply_mapa"):
                try:
                    parsed = yaml.safe_load(mapa_txt) or {}
                    if not isinstance(parsed, dict):
                        raise ValueError("O YAML de mapeamento deve ser um mapeamento.")
                    st.session_state.cfg_mapa = parsed
                    _mark_dirty()
                    st.success("Mapeamento aplicado na sessão.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"YAML inválido: {exc}")
