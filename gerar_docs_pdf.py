# -*- coding: utf-8 -*-
"""Gera PDFs: Consenso_Linhas_Contabeis.pdf e Base_Teorica.pdf."""

from pathlib import Path

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BASE = Path(__file__).resolve().parent
TMP = BASE / "_formula_imgs"
TMP.mkdir(exist_ok=True)


def formula_image(latex: str, filename: str, fontsize: int = 15, dpi: int = 200) -> Image:
    path = TMP / filename
    fig = plt.figure(figsize=(8.5, 0.85))
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.5, 0.5, f"${latex}$", fontsize=fontsize, ha="center", va="center")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.15, facecolor="white")
    plt.close(fig)
    img = Image(str(path))
    max_w = 16 * cm
    aspect = img.imageHeight / float(img.imageWidth)
    img.drawWidth = max_w
    img.drawHeight = max_w * aspect
    if img.drawHeight > 2.0 * cm:
        scale = (2.0 * cm) / img.drawHeight
        img.drawWidth *= scale
        img.drawHeight *= scale
    return img


def make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleBR", parent=styles["Title"], fontSize=15, leading=19, spaceAfter=6, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="SubBR", parent=styles["Normal"], fontSize=9.5, leading=12, alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=12))
    styles.add(ParagraphStyle(name="H1BR", parent=styles["Heading1"], fontSize=12, leading=15, spaceBefore=12, spaceAfter=7, textColor=colors.HexColor("#1a1a1a")))
    styles.add(ParagraphStyle(name="H2BR", parent=styles["Heading2"], fontSize=10.5, leading=13, spaceBefore=9, spaceAfter=5, textColor=colors.HexColor("#222222")))
    styles.add(ParagraphStyle(name="BodyBR", parent=styles["Normal"], fontSize=9, leading=12, alignment=TA_JUSTIFY, spaceAfter=5))
    styles.add(ParagraphStyle(name="NoteBR", parent=styles["Normal"], fontSize=8, leading=10.5, textColor=colors.HexColor("#444444"), spaceAfter=5))
    styles.add(ParagraphStyle(name="BulletBR", parent=styles["Normal"], fontSize=9, leading=12, leftIndent=8, spaceAfter=2))
    styles.add(ParagraphStyle(name="Cell", parent=styles["Normal"], fontSize=7.5, leading=9.5, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name="CellCenter", parent=styles["Normal"], fontSize=7.5, leading=9.5, alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Cite", parent=styles["Normal"], fontSize=8, leading=10.5, textColor=colors.HexColor("#1f3a5f"), spaceAfter=4, leftIndent=6))
    return styles


def styled_table(data, col_widths):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#99aacc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def P(text, style):
    return Paragraph(text, style)


def bullets(items, style):
    return [P(f"• {x}", style) for x in items]


def footer_factory(label):
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.7 * cm, 1.0 * cm, label)
        canvas.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, f"Página {doc.page}")
        canvas.restoreState()

    return footer


def build_doc(path, story, label):
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=path.stem,
        author="Metodologia Ex-Ante IA B3",
    )
    doc.build(story, onFirstPage=footer_factory(label), onLaterPages=footer_factory(label))
    print(f"PDF gerado: {path}")


# =============================================================================
# CONSENSO
# =============================================================================
def build_consenso():
    styles = make_styles()
    C, CC = styles["Cell"], styles["CellCenter"]
    story = []

    story.append(P("Consenso Metodológico", styles["TitleBR"]))
    story.append(
        P(
            "Índice de Exposição e Potencial de Benefício por IA (Ex-Ante) — Empresas da B3<br/>"
            "Síntese do Plano + respostas Gemini, GPT, Grok e Claude",
            styles["SubBR"],
        )
    )

    story.append(P("1. Ponto de partida", styles["H1BR"]))
    story.append(
        P(
            "O indicador <b>não</b> mede “quanto a empresa já gasta com IA/TI”. "
            "Ele mede, <b>ex-ante</b>:",
            styles["BodyBR"],
        )
    )
    story.extend(
        bullets(
            [
                "Onde a estrutura de custos/ativos permite ganho (teto de eficiência)",
                "Se a empresa consegue financiar a adoção (viabilidade)",
                "Opcionalmente, se já tem base digital mínima (capacidade de absorção)",
            ],
            styles["BulletBR"],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        P(
            "<b>Atenção — tensão entre as respostas:</b> Grok e Claude privilegiam Intangível/Software "
            "como núcleo. Isso é útil como <b>capacidade/maturidade</b>, não como proxy principal de exposição. "
            "Se Intangível for o núcleo, o índice vira “quem já é digital”, e não “quem tem teto de margem "
            "a expandir com IA” — diferencial do Plano.",
            styles["NoteBR"],
        )
    )

    story.append(P("2. Três blocos de linhas (não misturar)", styles["H1BR"]))

    story.append(P("2.1 Bloco A — Exposição / teto de oportunidade (núcleo)", styles["H2BR"]))
    story.append(P("Linhas que a IA pode comprimir ou otimizar:", styles["BodyBR"]))
    bloco_a = [
        [P("<b>Prioridade</b>", CC), P("<b>Linha</b>", CC), P("<b>Fonte</b>", CC), P("<b>Por quê</b>", C)],
        [P("Alta", CC), P("SG&A (Despesas gerais e administrativas)", C), P("DRE", CC), P("Colarinho branco / processos cognitivos (GenAI, RPA)", C)],
        [P("Alta", CC), P("Despesas com vendas / comerciais", C), P("DRE", CC), P("Atendimento, churn, precificação, recomendação", C)],
        [P("Alta", CC), P("CPV / COGS", C), P("DRE", CC), P("Manutenção preditiva, qualidade, eficiência operacional", C)],
        [P("Alta", CC), P("Despesas com pessoal (salários + encargos)", C), P("Notas / DRE", CC), P("Melhor proxy de automação de produtividade", C)],
        [P("Média-Alta", CC), P("PDD / PeLD", C), P("DRE / Notas", CC), P("Crítico em bancos, varejo, serviços (ML crédito/fraude)", C)],
        [P("Média", CC), P("Estoques", C), P("BP", CC), P("Previsão de demanda → PME ↓ → liberação de caixa", C)],
    ]
    story.append(styled_table(bloco_a, [2.2 * cm, 5.2 * cm, 2.4 * cm, 6.4 * cm]))
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        P(
            "<b>Normalização obrigatória:</b> todas as linhas do Bloco A ÷ Receita Operacional Líquida (ROL). "
            "<b>Fator α:</b> não tratar CPV como igualmente automatizável que SG&A (matéria-prima ≠ processos administrativos).",
            styles["NoteBR"],
        )
    )

    story.append(P("2.2 Bloco B — Viabilidade financeira", styles["H2BR"]))
    bloco_b = [
        [P("<b>Linha</b>", CC), P("<b>Fonte</b>", CC), P("<b>Uso no índice</b>", C)],
        [P("Caixa e equivalentes (+ aplicações líquidas)", C), P("BP", CC), P("Capacidade imediata de investir", C)],
        [P("Dívida líquida / EBITDA", C), P("BP + DRE", CC), P("Restrição de alavancagem", C)],
        [P("Fluxo de caixa operacional / FCF", C), P("DFC", CC), P("Relevância econômica do benefício", C)],
        [P("EBITDA / margem EBITDA", C), P("DRE", CC), P("Base para traduzir ganho em margem", C)],
    ]
    story.append(styled_table(bloco_b, [7.0 * cm, 2.8 * cm, 6.4 * cm]))

    story.append(P("2.3 Bloco C — Capacidade de absorção (secundário)", styles["H2BR"]))
    story.append(P("Ponderação complementar (Grok/Claude/GPT) — não é o coração do score:", styles["BodyBR"]))
    bloco_c = [
        [P("<b>Linha</b>", CC), P("<b>Fonte</b>", CC), P("<b>Uso</b>", C)],
        [P("Software / sistemas (dentro de Intangível)", C), P("BP + Notas", CC), P("Base digital instalada", C)],
        [P("Ativo intangível (desenvolvimento capitalizado)", C), P("BP + Notas", CC), P("Intensidade tecnológica", C)],
        [P("P&amp;D (quando divulgado)", C), P("DRE / Notas", CC), P("Inovação complementar", C)],
        [P("CAPEX / TI (quando aberto)", C), P("DFC / Notas", CC), P("Capacidade de execução", C)],
        [P("Goodwill / participações em tech", C), P("BP", CC), P("Sinal fraco/ruidoso — parcimônia", C)],
    ]
    story.append(styled_table(bloco_c, [7.0 * cm, 2.8 * cm, 6.4 * cm]))
    story.append(
        P(
            "<b>Por que não é núcleo:</b> na B3, software/IA costuma ir para opex/nuvem. "
            "Usar só Intangível subestima quem consome via nuvem e superestima quem capitalizou software legado.",
            styles["NoteBR"],
        )
    )

    story.append(P("3. Fórmula conceitual de consenso", styles["H1BR"]))
    story.append(
        formula_image(
            r"Score_i \;=\; \left[\sum_k \left(\frac{L_{i,k}}{ROL_i}\times\alpha_k\right)\right]"
            r"\;\times\; F^{fin}_i \;\times\; (1+\lambda\, R_i)",
            "consenso_score.png",
            fontsize=12,
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.extend(
        bullets(
            [
                "Σ (L/ROL × α) = Exposição (Bloco A)",
                "F<sup>fin</sup> = Viabilidade financeira (Bloco B)",
                "(1 + λ · R) = Readiness (Bloco C) — opcional e leve",
                "L<sub>k</sub> = SG&amp;A, Vendas, Pessoal, CPV (ajustado), PDD, Estoques",
                "λ pequeno, para não distorcer o caráter ex-ante",
            ],
            styles["BulletBR"],
        )
    )
    story.append(
        P(
            "Preserva a tese: estrutura de custos auditada → teto de margem, "
            "sem cair em AI-washing narrativo.",
            styles["BodyBR"],
        )
    )

    story.append(P("4. O que deixar de fora (ou etapa 2)", styles["H1BR"]))
    story.extend(
        bullets(
            [
                "Menções a IA em MD&amp;A / teleconferências / press releases → ex-post / validação",
                "“Despesas com TI” genéricas sem breakdown comparável",
                "Goodwill total sem filtro de aquisições tech (ruído)",
            ],
            styles["BulletBR"],
        )
    )

    story.append(P("5. Lista mínima prática (CVM/DFP)", styles["H1BR"]))
    story.append(P("<b>Essenciais (v1):</b> Receita líquida; SG&amp;A; Despesas com vendas; CPV/COGS; Pessoal (notas); PDD; Estoques; Caixa; Dívida líquida e EBITDA.", styles["BodyBR"]))
    story.append(P("<b>Complementares (v1.1):</b> Software/intangível (notas); P&amp;D / CAPEX tech; FCO.", styles["BodyBR"]))

    story.append(P("6. Veredito", styles["H1BR"]))
    story.append(
        P(
            "O núcleo deve ser a <b>intensidade de custos afetáveis pela IA / receita</b> "
            "(SG&amp;A, vendas, pessoal, CPV ponderado, PDD, estoques), ajustado por capacidade financeira. "
            "Intangível/Software entram como ajuste leve de readiness. "
            "Isso une Gemini (fiel ao Plano), GPT (três dimensões) e corrige o viés Grok/Claude "
            "de transformar o índice em “estoque de software”.",
            styles["BodyBR"],
        )
    )

    build_doc(BASE / "Consenso_Linhas_Contabeis.pdf", story, "Consenso Metodológico — Indicador Ex-Ante de IA (B3)")


# =============================================================================
# BASE TEORICA
# =============================================================================
def ref_block(story, styles, title, citacao, ideia, uso, linhas):
    story.append(P(title, styles["H2BR"]))
    story.append(P(f"<b>Citação:</b> {citacao}", styles["Cite"]))
    story.append(P(f"<b>Ideia central:</b> {ideia}", styles["BodyBR"]))
    story.append(P(f"<b>Como usar:</b> {uso}", styles["BodyBR"]))
    story.append(P(f"<b>Linhas/sublinhas:</b> {linhas}", styles["NoteBR"]))


def build_base_teorica():
    styles = make_styles()
    C, CC = styles["Cell"], styles["CellCenter"]
    story = []

    story.append(P("Base Teórica Acadêmica", styles["TitleBR"]))
    story.append(
        P(
            "Índice de Exposição e Potencial de Benefício por IA (Ex-Ante) — Empresas da B3<br/>"
            "Amparo bibliográfico para linhas, sublinhas e pesos α/β",
            styles["SubBR"],
        )
    )

    story.append(P("0. Posicionamento geral (frase-chave para a banca)", styles["H1BR"]))
    story.append(
        P(
            "A literatura de exposição à IA mede, em geral, potencial econômico via <b>ocupações e tarefas</b> "
            "(não via plano de contas). Esta pesquisa <b>operacionaliza</b> essa tradição para o nível da firma na B3, "
            "usando a estrutura de <b>custos e despesas auditadas (CVM/DFP)</b> como <b>proxy firm-level</b> "
            "de exposição e potencial de benefício ex-ante.",
            styles["BodyBR"],
        )
    )
    story.append(
        P(
            "<b>Justificativa da proxy:</b> no Brasil não há breakdown ocupacional público, comparável e contínuo "
            "para todas as companhias abertas. As DFPs da CVM oferecem a melhor base auditada disponível.",
            styles["NoteBR"],
        )
    )
    story.extend(
        bullets(
            [
                "Fundamentação teórica → exposição a IA = potencial sobre tarefas",
                "Operacionalização → intensidade de custos afetáveis / receita",
                "Validação empírica → correlacionar com exposição setorial e outcomes",
            ],
            styles["BulletBR"],
        )
    )

    story.append(P("1. Tradição-mãe: exposição à IA / automação", styles["H1BR"]))

    ref_block(
        story, styles,
        "1.1 Felten, Raj &amp; Seamans (2021)",
        "Felten, E., Raj, M., &amp; Seamans, R. (2021). Occupational, industry, and geographic exposure to artificial intelligence. <i>Strategic Management Journal</i>, 42(12), 2195–2217.",
        "Constrói o AIOE e agrega para indústria (AIIE) e geografia (AIGE); caminhos para medida firm-level.",
        "Âncora principal de exposição. O índice é a tradução contábil dessa lógica para a B3. Validar média setorial B3 × AIIE.",
        "Pessoal/ROL; SG&amp;A/ROL; Vendas/ROL; α setorial.",
    )
    ref_block(
        story, styles,
        "1.2 Felten, Raj &amp; Seamans (2018)",
        "Felten, E. W., Raj, M., &amp; Seamans, R. (2018). A method to link advances in artificial intelligence to occupational abilities. <i>AEA Papers and Proceedings</i>, 108, 54–57.",
        "Liga capacidades de IA a abilities ocupacionais (O*NET).",
        "Fundamenta α diferenciado: nem toda ocupação/custo é igualmente afetável.",
        "α por bucket (cognitivo, atendimento, físico, contractual).",
    )
    ref_block(
        story, styles,
        "1.3 Eloundou, Manning, Mishkin &amp; Rock (2023/2024)",
        "Eloundou, T., Manning, S., Mishkin, P., &amp; Rock, D. (2023). GPTs are GPTs. arXiv:2303.10130.",
        "Exposição a LLMs por tarefas; LLMs como tecnologia de propósito geral.",
        "Justifica foco em colarinho branco / linguagem / documento / atendimento.",
        "SG&amp;A cognitivo; vendas/SAC; pessoal administrativo; buckets jurídico/contábil/RH/atendimento.",
    )
    ref_block(
        story, styles,
        "1.4 Labaschin et al. (2025)",
        "Labaschin, B., Eloundou, T., Manning, S., Mishkin, P., &amp; Rock, D. (2025). Extending “GPTs Are GPTs” to Firms. <i>AEA Papers and Proceedings</i>, 115, 51–55.",
        "Estende exposição a LLMs para o nível da firma.",
        "Mostra demanda por medida firm-level; contribuição = proxy contábil CVM/B3.",
        "Score por empresa (não só setorial).",
    )
    ref_block(
        story, styles,
        "1.5 Brynjolfsson, Mitchell &amp; Rock (SML, 2018+)",
        "Brynjolfsson, E., Mitchell, T., &amp; Rock, D. (2018). What can machine learning do? Workforce implications (e trabalhos de Suitability for Machine Learning).",
        "Nem toda tarefa é igualmente adequada a ML.",
        "Fundamenta α<sub>k</sub> e β<sub>j</sub>; evita tratar CPV commodity como SG&amp;A.",
        "α(SG&amp;A) &gt; α(CPV commodities); buckets rotina cognitiva vs. físico.",
    )
    ref_block(
        story, styles,
        "1.6 Webb (2020)",
        "Webb, M. (2020). The impact of artificial intelligence on the labor market. Working paper (Stanford).",
        "Exposição ocupacional via overlap de patentes/tarefas.",
        "Referência alternativa em robustez de rankings setoriais.",
        "α setorial alternativo.",
    )
    ref_block(
        story, styles,
        "1.7 Frey &amp; Osborne (2017)",
        "Frey, C. B., &amp; Osborne, M. A. (2017). The future of employment. <i>Technological Forecasting and Social Change</i>, 114, 254–280.",
        "Probabilidade de automação por ocupação (rotinas).",
        "Apoia suscetibilidade rotina vs. não-rotina (citar com ressalva: foco da pesquisa é IA/ML/GenAI).",
        "Pessoal/SG&amp;A; penalização de buckets físicos no curto prazo.",
    )

    story.append(PageBreak())
    story.append(P("2. Evidência de canal: onde a IA gera ganho", styles["H1BR"]))

    ref_block(
        story, styles,
        "2.1 Brynjolfsson, Li &amp; Raymond (2023)",
        "Brynjolfsson, E., Li, D., &amp; Raymond, L. (2023). Generative AI at Work. NBER WP 31161.",
        "GenAI em call center: ~+14% produtividade; efeito maior em novatos.",
        "Evidência causal para atendimento → despesas com vendas/SAC.",
        "Vendas/comerciais; SAC/call center; bucket atendimento (β alto).",
    )
    ref_block(
        story, styles,
        "2.2 ML e risco de crédito / PDD",
        "Literatura de ML para PD/ECL (IFRS 9 / CECL); forecast de credit loss e loan-loss provisions.",
        "ML melhora previsão de default e informa provisões.",
        "Incluir PDD sobretudo em bancos, financeiras e varejo com crédito.",
        "PDD/PeLD; condicionar peso por setor financeiro.",
    )
    ref_block(
        story, styles,
        "2.3 Estoques / forecast / OM",
        "Tradição de demand forecasting e inventory optimization (Silver/Pyke/Peterson; Syntetos) + ML moderno.",
        "Melhor previsão reduz estoque de segurança, PME e capital parado.",
        "Estoques como proxy de ineficiência informacional atacável por IA preditiva.",
        "Estoques/ROL; PME; mercadorias cicláveis; penalizar estoque estratégico/regulatório.",
    )
    ref_block(
        story, styles,
        "2.4 CPV / manutenção preditiva / Indústria 4.0",
        "Predictive maintenance, qualidade com visão computacional, smart manufacturing reviews.",
        "IA reduz downtime/retrabalho — mas não “automatiza” commodity da mesma forma.",
        "CPV com α moderado; preferir sublinhas operacionais quando a nota permitir.",
        "CPV operacional (alta); MP/commodities/royalties (baixa).",
    )

    story.append(P("3. Capacidade de absorção e viabilidade (Blocos B e C)", styles["H1BR"]))
    ref_block(
        story, styles,
        "3.1 Cohen &amp; Levinthal (1990) — Absorptive Capacity",
        "Cohen, W. M., &amp; Levinthal, D. A. (1990). Absorptive capacity. <i>Administrative Science Quarterly</i>, 35(1), 128–152.",
        "Capacidade de reconhecer, assimilar e aplicar conhecimento externo.",
        "Fundamenta Bloco C: ter teto ≠ capturar benefício. Intangíveis/P&amp;D = moderadores.",
        "Intangível/software; P&amp;D/ROL; CAPEX tech.",
    )
    ref_block(
        story, styles,
        "3.2 Financing constraints (Corporate Finance)",
        "Fazzari, Hubbard &amp; Petersen (1988); Kaplan &amp; Zingales (1997); literatura de cash holdings.",
        "Firmas constrangidas investem menos mesmo com oportunidades de NPV positivo.",
        "Fundamenta Bloco B: caixa, DL/EBITDA, FCO.",
        "Caixa; Dívida líquida/EBITDA; FCO/FCF; margem EBITDA.",
    )
    ref_block(
        story, styles,
        "3.3 GPT econômicos e complementaridades",
        "Bresnahan &amp; Trajtenberg (1995); Brynjolfsson &amp; Hitt; Eloundou et al.",
        "Benefício depende de complementos (dados, processos, capital humano, organização).",
        "Justifica Score = Exposição × Capacidade (não só custos) e rejeita AI-washing.",
        "Estrutura A × B × C leve.",
    )

    story.append(P("4. Mapa rápido: linha → força do amparo", styles["H1BR"]))
    mapa = [
        [P("<b>Linha</b>", CC), P("<b>Força</b>", CC), P("<b>Âncoras principais</b>", C)],
        [P("Pessoal / salários e encargos", C), P("Alta", CC), P("Felten; Eloundou; Frey-Osborne", C)],
        [P("SG&amp;A (agregado)", C), P("Alta", CC), P("Felten; Eloundou; SML", C)],
        [P("Despesas com vendas / SAC", C), P("Alta", CC), P("Eloundou; Brynjolfsson-Li-Raymond", C)],
        [P("CPV (parcela operacional)", C), P("Média", CC), P("Predictive maint.; Indústria 4.0; SML", C)],
        [P("CPV (commodity / MP)", C), P("Baixa", CC), P("α baixo — teoria de não-equivalência", C)],
        [P("PDD / crédito", C), P("Alta*", CC), P("ML credit risk / IFRS 9 (*setorial)", C)],
        [P("Estoques", C), P("Alta", CC), P("Forecasting / inventory OM", C)],
        [P("Caixa / alavancagem / FCO", C), P("Alta", CC), P("Financing constraints", C)],
        [P("Intangível / software / P&amp;D", C), P("Média", CC), P("Absorptive capacity (readiness)", C)],
        [P("Goodwill / M&amp;A tech", C), P("Baixa", CC), P("Usar com parcimônia (ruído)", C)],
    ]
    story.append(styled_table(mapa, [5.5 * cm, 2.0 * cm, 8.7 * cm]))

    story.append(P("5. Sublinhas (buckets): taxonomia derivada de tarefas", styles["H1BR"]))
    story.append(
        P(
            "A literatura <b>não</b> entrega um catálogo contábil universal de subcontas. "
            "Entrega classificação por <b>tipo de tarefa/processo</b>. As sublinhas são taxonomia derivada:",
            styles["BodyBR"],
        )
    )
    buckets = [
        [P("<b>Bucket</b>", CC), P("<b>Lógica teórica</b>", CC), P("<b>Exemplos contábeis</b>", C)],
        [P("Cognitivo / documental", C), P("Alta exposição LLM/AIOE", C), P("jurídico, contábil, compliance, RH adm.", C)],
        [P("Atendimento / comercial", C), P("Evidência GenAI at work", C), P("SAC, call center, CRM operacional", C)],
        [P("Backoffice transacional", C), P("Alta SML / rotina cognitiva", C), P("faturamento, AP/AR, conciliação", C)],
        [P("Análise / decisão", C), P("ML preditivo", C), P("crédito, pricing, planning", C)],
        [P("Operacional industrial", C), P("Predictive maint./visão", C), P("manutenção, qualidade, logística", C)],
        [P("Físico / contractual", C), P("Baixa exposição curto prazo", C), P("aluguel, seguros, depreciação", C)],
        [P("Insumo / commodity", C), P("Baixa GenAI direta", C), P("MP, energia base, royalties fixos", C)],
    ]
    story.append(styled_table(buckets, [4.2 * cm, 4.8 * cm, 7.2 * cm]))
    story.append(
        P(
            "Pesos β = hipóteses operacionais calibradas + sensibilidade (±20%). "
            "Sem abertura na nota → α setorial da linha-mãe.",
            styles["NoteBR"],
        )
    )

    story.append(P("6. Teoria vs. contribuição da dissertação", styles["H1BR"]))
    story.append(P("<b>Já estabelecido:</b> AI exposure; heterogeneidade de suscetibilidade; canais empíricos; absorptive capacity; financing constraints.", styles["BodyBR"]))
    story.append(P("<b>Sua contribuição:</b> proxy contábil ex-ante B3 (CVM/DFP); catálogo + buckets BR; Score = Exposição × Viabilidade × Readiness(leve); calibração α/β; validação BR; (opcional) precificação / Q de Tobin.", styles["BodyBR"]))
    story.append(P("O valor exato de um α (ex.: 0,35) <b>não</b> precisa de um paper único — justifica-se e testa-se por robustez (padrão de índices compostos).", styles["NoteBR"]))
    story.append(
        formula_image(
            r"Score \;=\; Expo \times F^{fin} \times (1+\lambda R)",
            "teoria_score.png",
            fontsize=14,
        )
    )

    story.append(P("7. Validação empírica sugerida", styles["H1BR"]))
    story.extend(
        bullets(
            [
                "<b>V1 Constructo:</b> média setorial do índice × AIIE (Felten) / exposição Eloundou",
                "<b>V2 Discriminante:</b> bancos/serviços acima de commodities no Bloco A (ceteris paribus)",
                "<b>V3 Robustez:</b> α/β alternativos; estabilidade do top/bottom quartil",
                "<b>V4 Ex-post:</b> relação com margem EBITDA, ROIC, produtividade ou Q de Tobin",
            ],
            styles["BulletBR"],
        )
    )

    story.append(P("8. Roteiro do capítulo de revisão de literatura", styles["H1BR"]))
    story.extend(
        bullets(
            [
                "8.1 IA como GPT econômico — Bresnahan &amp; Trajtenberg; Brynjolfsson; Eloundou",
                "8.2 Medidas de exposição — Frey &amp; Osborne; Webb; Felten; Labaschin",
                "8.3 Canais de benefício — Brynjolfsson-Li-Raymond; ML crédito; OM; Indústria 4.0",
                "8.4 Adoção — Cohen &amp; Levinthal; Fazzari / Kaplan-Zingales",
                "8.5 Lacuna — ausência de proxy contábil ex-ante comparável na B3",
                "8.6 Operacionalização — linhas CVM/DFP + taxonomia de buckets",
            ],
            styles["BulletBR"],
        )
    )

    story.append(P("9. Referências mínimas", styles["H1BR"]))
    refs = [
        "Bresnahan, T. F., &amp; Trajtenberg, M. (1995). General purpose technologies: Engines of growth? <i>Journal of Econometrics</i>.",
        "Brynjolfsson, E., Li, D., &amp; Raymond, L. (2023). Generative AI at Work. NBER WP 31161.",
        "Brynjolfsson, E., Mitchell, T., &amp; Rock, D. (2018). What can machine learning do? Workforce implications.",
        "Cohen, W. M., &amp; Levinthal, D. A. (1990). Absorptive capacity. <i>ASQ</i>, 35(1), 128–152.",
        "Eloundou, T., Manning, S., Mishkin, P., &amp; Rock, D. (2023). GPTs are GPTs. arXiv:2303.10130.",
        "Fazzari, S. M., Hubbard, R. G., &amp; Petersen, B. C. (1988). Financing constraints and corporate investment. <i>BPEA</i>.",
        "Felten, E., Raj, M., &amp; Seamans, R. (2021). Occupational, industry, and geographic exposure to AI. <i>SMJ</i>.",
        "Felten, E. W., Raj, M., &amp; Seamans, R. (2018). Linking AI advances to occupational abilities. <i>AEA P&amp;P</i>.",
        "Frey, C. B., &amp; Osborne, M. A. (2017). The future of employment. <i>TFSC</i>, 114, 254–280.",
        "Kaplan, S. N., &amp; Zingales, L. (1997). Do investment-cash flow sensitivities…? <i>QJE</i>.",
        "Labaschin, B. et al. (2025). Extending “GPTs Are GPTs” to Firms. <i>AEA P&amp;P</i>, 115, 51–55.",
        "Webb, M. (2020). The impact of artificial intelligence on the labor market. Working paper.",
    ]
    for r in refs:
        story.append(P(f"• {r}", styles["NoteBR"]))

    story.append(Spacer(1, 0.3 * cm))
    story.append(
        P(
            "<b>Nota final:</b> linhas ancoradas em tradição publicada; sublinhas em taxonomia de tarefas; "
            "pesos α/β como parâmetros calibráveis com robustez — padrão acadêmico aceitável para índices compostos.",
            styles["BodyBR"],
        )
    )

    build_doc(BASE / "Base_Teorica.pdf", story, "Base Teórica Acadêmica — Indicador Ex-Ante de IA (B3)")


if __name__ == "__main__":
    build_consenso()
    build_base_teorica()
    # limpa imagens temporarias
    import shutil

    shutil.rmtree(TMP, ignore_errors=True)
