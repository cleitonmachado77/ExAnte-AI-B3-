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


def _split_list(text: str) -> list[str]:
    parts: list[str] = []
    for chunk in (text or "").replace(";", "\n").splitlines():
        for item in chunk.split(","):
            s = item.strip()
            if s:
                parts.append(s)
    return parts


def _join_list(items: list[Any] | None) -> str:
    if not items:
        return ""
    return ", ".join(str(x) for x in items)


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

        st.markdown("#### Palavras-chave de classificação setorial")
        st.caption("Ordem importa: a primeira batida no nome da empresa define o setor.")
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

        g_neg = st.number_input(
            "g quando EBITDA ≤ 0",
            min_value=0.0,
            max_value=1.0,
            value=float(pesos.get("g_ebitda_negativo", 0.25)),
            step=0.05,
            key="cfg_g_neg",
        )
        if float(pesos.get("g_ebitda_negativo", 0.25)) != float(g_neg):
            pesos["g_ebitda_negativo"] = float(g_neg)
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
                help="Fração do teto teoricamente capturável mesmo com caixa pleno.",
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
        st.info(
            "R = clip(w_software·Soft/Ativo + w_intangivel·Intang/Ativo). "
            "Viável = Teto×F×ρ. Final = Viável×(φ+(1−φ)×R_eff)."
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
            norm = st.checkbox(
                "Normalizar score em 0–100 no painel do ano",
                value=bool(pesos.get("normalizar_score_0_100", True)),
                key="cfg_norm",
            )
        with f2:
            exigir = pesos.get("exigir_ao_menos_uma_de") or []
            exigir_sel = st.multiselect(
                "Exigir ao menos uma destas linhas",
                options=EXIGIR_OPCOES,
                default=[e for e in exigir if e in EXIGIR_OPCOES],
                key="cfg_exigir",
            )

        changed = False
        if float(pesos.get("min_receita", 50_000_000.0)) != float(min_rec):
            pesos["min_receita"] = float(min_rec)
            changed = True
        if bool(pesos.get("excluir_recuperacao_judicial", True)) != bool(excl_rj):
            pesos["excluir_recuperacao_judicial"] = bool(excl_rj)
            changed = True
        if bool(pesos.get("usar_consolidado", True)) != bool(usar_cons):
            pesos["usar_consolidado"] = bool(usar_cons)
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
            "Códigos `CD_CONTA` e padrões regex de `DS_CONTA` (case-insensitive no pipeline). "
            "Separe múltiplos valores por vírgula."
        )
        map_rows = []
        for key, cfg in mapa.items():
            if not isinstance(cfg, dict):
                continue
            map_rows.append(
                {
                    "chave": key,
                    "Variável": MAPA_LABELS.get(key, key),
                    "Códigos CD_CONTA": _join_list(cfg.get("cd_conta")),
                    "Padrões DS_CONTA (regex)": _join_list(cfg.get("ds_patterns")),
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
            new_mapa[key] = {
                "cd_conta": _split_list(str(r.get("Códigos CD_CONTA", ""))),
                "ds_patterns": _split_list(str(r.get("Padrões DS_CONTA (regex)", ""))),
            }
        # preserva chaves existentes com labels conhecidos
        # compara estrutura simplificada
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
