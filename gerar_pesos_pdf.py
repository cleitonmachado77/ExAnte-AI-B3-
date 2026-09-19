# -*- coding: utf-8 -*-
"""Gera PDF com pesos alpha/beta e formulas do indice de exposicao a IA."""

from pathlib import Path
import io

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).resolve().parent / "Pesos_Alpha_Beta.pdf"
TMP = Path(__file__).resolve().parent / "_formula_imgs"
TMP.mkdir(exist_ok=True)


def formula_image(latex: str, filename: str, fontsize: int = 16, dpi: int = 200) -> Image:
    """Renderiza formula LaTeX (mathtext) em PNG e retorna Image do ReportLab."""
    path = TMP / filename
    fig = plt.figure(figsize=(8.5, 0.9))
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.text(0.5, 0.5, f"${latex}$", fontsize=fontsize, ha="center", va="center")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.15, facecolor="white")
    plt.close(fig)
    img = Image(str(path))
    # escala proporcional a largura util ~16cm
    max_w = 16 * cm
    aspect = img.imageHeight / float(img.imageWidth)
    img.drawWidth = max_w
    img.drawHeight = max_w * aspect
    if img.drawHeight > 2.2 * cm:
        scale = (2.2 * cm) / img.drawHeight
        img.drawWidth *= scale
        img.drawHeight *= scale
    return img


def make_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleBR",
            parent=styles["Title"],
            fontSize=16,
            leading=20,
            spaceAfter=8,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubBR",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#333333"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1BR",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#1a1a1a"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2BR",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#222222"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyBR",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="NoteBR",
            parent=styles["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#444444"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CellCenter",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
        )
    )
    return styles


def styled_table(data, col_widths):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#99aacc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def P(text, style):
    return Paragraph(text, style)


def build():
    styles = make_styles()
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Pesos Alpha Beta - Indice de Exposicao a IA (B3)",
        author="Metodologia Ex-Ante",
    )
    story = []
    C = styles["Cell"]
    CC = styles["CellCenter"]

    story.append(P("Pesos do Indicador (α, β, F<sup>fin</sup>, λ)", styles["TitleBR"]))
    story.append(
        P(
            "Índice de Exposição e Potencial de Benefício por IA (Ex-Ante) — Empresas da B3<br/>"
            "Cenário-base para calibração · priors teóricos · protocolo de robustez",
            styles["SubBR"],
        )
    )

    story.append(P("1. Princípio de atribuição dos pesos", styles["H1BR"]))
    story.append(
        P(
            "Os pesos <b>não são observados</b> nas demonstrações contábeis. São <b>parâmetros do modelo</b>, "
            "definidos em três etapas: (i) ordenação pela literatura de exposição a tarefas/LLM; "
            "(ii) calibração numérica (priors); (iii) testes de sensibilidade. "
            "Os valores abaixo constituem o <b>cenário-base</b> da dissertação — não uma constante universal.",
            styles["BodyBR"],
        )
    )

    story.append(P("2. Fórmulas do score", styles["H1BR"]))
    story.append(
        P(
            "Funil implementado (v0.1): teto → viável → final. O score relativo replica o funil "
            "em razão da receita.",
            styles["BodyBR"],
        )
    )
    story.append(
        formula_image(
            r"Teto_i = \sum_k \min(|\tilde L_{i,k}|,\,3\,ROL_i)\,\alpha_{k,s(i)}"
            r"\quad;\quad"
            r"Viavel_i = Teto_i \times F^{fin}_i \times \rho",
            "f_funil1.png",
            fontsize=13,
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        formula_image(
            r"\tilde L_{i,k} = L_{i,k}\left(1 - \frac{Pessoal_i}{CPV_i + SGA_i + Vendas_i}\right)"
            r"\quad k \in \{CPV, SGA, Vendas\}",
            "f_pessoal.png",
            fontsize=12,
        )
    )
    story.append(
        P(
            "<b>Sem dupla contagem de pessoal.</b> A folha (DVA 7.08.01) já está embutida em CPV, SG&A e vendas; "
            "no cenário-base (<i>pessoal_modo = liquido</i>) ela é retirada pro rata dessas linhas e recebe seu "
            "próprio α<sub>pessoal</sub>. Em bancos “Despesas de Pessoal” já é linha separada — nada é subtraído.",
            styles["NoteBR"],
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        formula_image(
            r"Final_i = Viavel_i \times \left(\phi + (1-\phi)\,R^{eff}_i\right)"
            r"\quad;\quad"
            r"R^{eff}_i = \mathrm{clip}_{[0,1]}\left(R_i(1+\lambda)\right)",
            "f_funil2.png",
            fontsize=13,
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(P("Score relativo da empresa <i>i</i> (base do ranking 0–100):", styles["BodyBR"]))
    story.append(
        formula_image(
            r"Score_i \;=\; \min(Expo_i, q_{99}) \times F^{fin}_i \times \rho \times \left(\phi + (1-\phi)\,R^{eff}_i\right)",
            "f_score.png",
            fontsize=14,
        )
    )
    story.append(
        P(
            "Cenário-base: ρ = 0,70 (taxa de captura), φ = 0,85 (execução sem readiness), λ = 0,10. "
            "A forma conceitual <i>Expo × F × (1 + λR)</i> dos documentos de consenso foi substituída "
            "por esta especificação multiplicativa, em que o Bloco C nunca eleva o potencial acima do viável. "
            "A exposição que entra no score é <b>winsorizada</b> no percentil 99 do painel válido "
            "(<i>winsor_exposicao_pct</i>), para que uma DFP atípica não comprima a escala 0–100 das demais; "
            "o teto em R$ não é alterado.",
            styles["NoteBR"],
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(P("Exposição (Bloco A) — linha agregada:", styles["BodyBR"]))
    story.append(
        formula_image(
            r"Expo_i \;=\; \sum_{k \in K} \left( \frac{L_{i,k}}{ROL_i} \times \alpha_{k,\,s(i)} \right)",
            "f_exp.png",
            fontsize=14,
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(P("Quando houver sublinhas/buckets na nota explicativa:", styles["BodyBR"]))
    story.append(
        formula_image(
            r"L^{af}_{i,k} \;=\; \sum_{j \in J_k} item_{i,j} \times \beta_j"
            r"\qquad;\qquad"
            r"c_{i,k} \;=\; \frac{L^{af}_{i,k}}{ROL_i}",
            "f_sub.png",
            fontsize=13,
        )
    )
    story.append(Spacer(1, 0.25 * cm))
    story.append(P("Ajuste setorial do α (âncora Felten/Eloundou):", styles["BodyBR"]))
    story.append(
        formula_image(
            r"\alpha_{k,s} \;=\; \alpha^{base}_k \times \frac{E_s}{\bar{E}}",
            "f_setor.png",
            fontsize=14,
        )
    )
    story.append(
        P(
            "onde <i>E<sub>s</sub></i> é a exposição setorial da literatura e "
            "<i>Ē</i> é a média (ou mediana) cross-setorial. Na ausência de <i>E<sub>s</sub></i>, use "
            "<i>α<sub>k,s</sub> = α<sup>base</sup><sub>k</sub></i>.",
            styles["NoteBR"],
        )
    )

    story.append(P("3. Cenário-base — α por linha contábil (α<sup>base</sup><sub>k</sub>)", styles["H1BR"]))
    story.append(
        P(
            "Interpretação: α é a fração da linha considerada <b>realisticamente afetável</b> por IA "
            "no horizonte do estudo (não a fração já automatizada).",
            styles["BodyBR"],
        )
    )

    alpha_header = [
        P("<b>Linha k</b>", CC),
        P("<b>α<sup>base</sup></b>", CC),
        P("<b>Faixa de robustez</b>", CC),
        P("<b>Âncora teórica</b>", CC),
        P("<b>Observação</b>", C),
    ]
    alpha_rows = [
        alpha_header,
        [
            P("Pessoal (salários + encargos)", C),
            P("<b>0,35</b>", CC),
            P("0,25 – 0,45", CC),
            P("Felten; Eloundou; Frey-Osborne", C),
            P("Proxy central de automação de produtividade", C),
        ],
        [
            P("SG&A (Desp. gerais e adm.)", C),
            P("<b>0,30</b>", CC),
            P("0,20 – 0,40", CC),
            P("Felten; Eloundou; SML", C),
            P("Parte contractual (aluguel etc.) fica de fora via β", C),
        ],
        [
            P("Despesas com vendas / comerciais", C),
            P("<b>0,32</b>", CC),
            P("0,25 – 0,40", CC),
            P("Brynjolfsson-Li-Raymond; Eloundou", C),
            P("Canal empírico forte (SAC / atendimento)", C),
        ],
        [
            P("PDD / PeLD (setores de crédito)", C),
            P("<b>0,40</b>", CC),
            P("0,30 – 0,50", CC),
            P("ML crédito / IFRS 9", C),
            P("Fora de financeiro: <b>0,15</b> (implementado: <i>alpha_pdd_nao_financeiro</i>)", C),
        ],
        [
            P("CPV / COGS (total, sem abrir)", C),
            P("<b>0,10</b>", CC),
            P("0,05 – 0,15", CC),
            P("SML; Indústria 4.0", C),
            P("Commodities dominam; α baixo por construção", C),
        ],
        [
            P("CPV operacional (manutenção, qualidade, logística)", C),
            P("<b>0,22</b>", CC),
            P("0,15 – 0,30", CC),
            P("Predictive maintenance / visão", C),
            P("Usar só se a nota permitir separar", C),
        ],
        [
            P("Estoques", C),
            P("<b>0,18</b>", CC),
            P("0,10 – 0,25", CC),
            P("Demand forecasting / OM", C),
            P("Ganho via PME / capital de giro", C),
        ],
    ]
    story.append(styled_table(alpha_rows, [4.2 * cm, 1.6 * cm, 2.4 * cm, 4.0 * cm, 4.0 * cm]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        P(
            "<b>Regra de fallback:</b> se a empresa não abrir sublinhas, aplique apenas "
            "α<sup>base</sup><sub>k</sub> (ou α<sub>k,s</sub>) sobre a linha agregada CVM.",
            styles["NoteBR"],
        )
    )

    story.append(P("4. Cenário-base — β por bucket (sublinhas)", styles["H1BR"]))
    story.append(
        P(
            "β<sub>j</sub> ∈ [0, 1] multiplica o valor do item da nota. Itens sem match no dicionário "
            "não entram no detalhe (permanecem só no agregado da linha-mãe).",
            styles["BodyBR"],
        )
    )

    beta_header = [
        P("<b>Bucket j</b>", CC),
        P("<b>β</b>", CC),
        P("<b>Faixa</b>", CC),
        P("<b>Linhas-mãe típicas</b>", CC),
        P("<b>Exemplos de sinônimos em nota</b>", C),
    ]
    beta_rows = [
        beta_header,
        [
            P("Cognitivo / documental", C),
            P("<b>0,50</b>", CC),
            P("0,40–0,60", CC),
            P("SG&A, Pessoal", CC),
            P("jurídico, contábil, compliance, RH administrativo", C),
        ],
        [
            P("Atendimento / SAC / comercial", C),
            P("<b>0,50</b>", CC),
            P("0,40–0,60", CC),
            P("Vendas, SG&A", CC),
            P("call center, SAC, CRM, teleatendimento", C),
        ],
        [
            P("Backoffice transacional", C),
            P("<b>0,40</b>", CC),
            P("0,30–0,50", CC),
            P("SG&A", CC),
            P("faturamento, contas a pagar/receber, conciliação", C),
        ],
        [
            P("Análise / decisão / crédito", C),
            P("<b>0,40</b>", CC),
            P("0,30–0,50", CC),
            P("SG&A, PDD", CC),
            P("crédito, pricing, planejamento, risk scoring", C),
        ],
        [
            P("Operacional industrial", C),
            P("<b>0,22</b>", CC),
            P("0,15–0,30", CC),
            P("CPV", CC),
            P("manutenção, qualidade, logística, ociosidade", C),
        ],
        [
            P("Forecast / estoque ciclável", C),
            P("<b>0,20</b>", CC),
            P("0,10–0,25", CC),
            P("Estoques", CC),
            P("mercadorias, produtos acabados, estoque operacional", C),
        ],
        [
            P("Contractual / físico", C),
            P("<b>0,03</b>", CC),
            P("0,00–0,05", CC),
            P("SG&A", CC),
            P("aluguel, condomínio, seguros, depreciação", C),
        ],
        [
            P("Commodity / insumo bruto", C),
            P("<b>0,02</b>", CC),
            P("0,00–0,05", CC),
            P("CPV", CC),
            P("matéria-prima, royalties fixos, energia base", C),
        ],
    ]
    story.append(styled_table(beta_rows, [3.6 * cm, 1.4 * cm, 2.0 * cm, 2.8 * cm, 6.4 * cm]))

    story.append(PageBreak())
    story.append(P("5. Viabilidade financeira — F<sup>fin</sup>", styles["H1BR"]))
    story.append(P("Não misturar com α. Função sugerida (simples e auditável):", styles["BodyBR"]))
    story.append(
        formula_image(
            r"F^{fin}_i \;=\; f\!\left(\frac{Caixa_i}{Ativo_i}\right)"
            r"\;\times\;"
            r"g\!\left(\frac{DL_i}{EBITDA_i}\right)"
            r"\;\times\;"
            r"h\!\left(\frac{FCO_i}{ROL_i}\right)",
            "f_fin.png",
            fontsize=14,
        )
    )
    story.append(Spacer(1, 0.3 * cm))
    story.append(
        P("Notação: <i>DL</i> = Dívida Líquida; <i>FCO</i> = caixa líquido das atividades operacionais (DFC 6.01).", styles["NoteBR"]),
    )

    story.append(P("5.1 Função g — restrição de alavancagem", styles["H2BR"]))
    g_rows = [
        [P("<b>Dívida Líquida / EBITDA</b>", CC), P("<b>g(·)</b>", CC), P("<b>Interpretação</b>", C)],
        [P("≤ 2,0×", CC), P("<b>1,00</b>", CC), P("Capacidade plena de investir em tecnologia", C)],
        [P("2,0× &lt; x ≤ 3,5×", CC), P("<b>0,70</b>", CC), P("Restrição moderada", C)],
        [P("&gt; 3,5×", CC), P("<b>0,40</b>", CC), P("Alavancagem crítica — penalização forte", C)],
        [P("EBITDA ≤ 0", CC), P("<b>0,25</b>", CC), P("Sem geração operacional para financiar adoção", C)],
        [P("Instituição financeira", CC), P("<b>1,00</b>", CC), P("DL/EBITDA não definido (captação por depósitos) — g fixo, só f(·) diferencia", C)],
    ]
    story.append(styled_table(g_rows, [5.5 * cm, 2.5 * cm, 8.2 * cm]))
    story.append(Spacer(1, 0.25 * cm))

    story.append(P("5.2 Função f — capacidade de caixa (opcional, leve)", styles["H2BR"]))
    f_rows = [
        [P("<b>Caixa / Ativo</b>", CC), P("<b>f(·)</b>", CC), P("<b>Interpretação</b>", C)],
        [P("≥ 8%", CC), P("<b>1,00</b>", CC), P("Liquidez confortável", C)],
        [P("3% ≤ x &lt; 8%", CC), P("<b>0,90</b>", CC), P("Liquidez adequada", C)],
        [P("&lt; 3%", CC), P("<b>0,75</b>", CC), P("Caixa apertado — leve freio", C)],
    ]
    story.append(styled_table(f_rows, [5.5 * cm, 2.5 * cm, 8.2 * cm]))
    story.append(
        P(
            "Se preferir especificação ainda mais parcimoniosa no capítulo empírico, use apenas "
            "<i>g(·)</i> e fixe <i>f = h = 1</i>.",
            styles["NoteBR"],
        )
    )

    story.append(P("5.3 Função h — geração de caixa operacional (DFC)", styles["H2BR"]))
    h_rows = [
        [P("<b>FCO / ROL</b>", CC), P("<b>h(·)</b>", CC), P("<b>Interpretação</b>", C)],
        [P("≥ 0", CC), P("<b>1,00</b>", CC), P("Operação gera caixa — sem freio adicional", C)],
        [P("&lt; 0", CC), P("<b>0,85</b>", CC), P("Queima de caixa: menos folga para investir em IA mesmo com caixa em balanço", C)],
        [P("Sem DFC / inst. financeira", CC), P("<b>1,00</b>", CC), P("Bancos: FCO oscila com carteira/captação — não é sinal de folga", C)],
    ]
    story.append(styled_table(h_rows, [5.5 * cm, 2.5 * cm, 8.2 * cm]))

    story.append(P("6. Readiness — λ e R<sub>i</sub> (Bloco C, opcional e leve)", styles["H1BR"]))
    story.append(
        formula_image(
            r"r_i \;=\; w_1\frac{Soft_i}{Ativo_i}"
            r" + w_2\frac{PeD_i}{ROL_i}"
            r" + w_3\frac{Intang_i}{Ativo_i}"
            r"\qquad R_i \;=\; \mathrm{percentil}_{painel}(r_i)\in[0,1]",
            "f_ready.png",
            fontsize=12,
        )
    )
    story.append(Spacer(1, 0.2 * cm))
    story.append(
        P(
            "Notação: <i>Soft</i> = software/sistemas; <i>PeD</i> = P&amp;D; "
            "<i>Intang</i> = ativo intangível. Como as razões contábeis ficam abaixo de 0,05 na quase "
            "totalidade das companhias, <i>clip<sub>[0,1]</sub>(r)</i> deixaria o Bloco C inerte; "
            "<i>R<sub>i</sub></i> é a posição relativa de <i>r<sub>i</sub></i> no painel válido do ano "
            "(<i>readiness_modo = percentil</i>; alternativas: <i>escala</i> = r/q<sub>90</sub>, <i>bruto</i> = clip).",
            styles["NoteBR"],
        )
    )
    ready_rows = [
        [P("<b>Parâmetro</b>", CC), P("<b>Valor-base</b>", CC), P("<b>Faixa</b>", CC), P("<b>Motivo</b>", C)],
        [P("ρ (taxa de captura)", CC), P("<b>0,70</b>", CC), P("0,50 – 0,90", CC), P("Nem todo teto teórico se realiza", C)],
        [P("φ (execução sem readiness)", CC), P("<b>0,85</b>", CC), P("0,70 – 1,00", CC), P("Bloco C só modula (1−φ) do viável", C)],
        [P("λ (amplificação de R)", CC), P("<b>0,10</b>", CC), P("0,00 – 0,15", CC), P("Não transformar o índice em estoque de software", C)],
        [P("w<sub>1</sub> (software/ativo)", CC), P("<b>0,50</b>", CC), P("—", CC), P("Proxy mais direto de base digital", C)],
        [P("w<sub>2</sub> (P&D/ROL)", CC), P("<b>0,30</b>", CC), P("—", CC), P("Reservado — ainda não extraído da DFP (não entra na v0.1)", C)],
        [P("w<sub>3</sub> (intangível/ativo)", CC), P("<b>0,20</b>", CC), P("—", CC), P("Sinal mais ruidoso; peso menor", C)],
        [P("Cenário sem Bloco C", CC), P("<b>φ = 1</b>", CC), P("obrigatório em robustez", CC), P("Fator de execução = 1 para todos; isola o núcleo ex-ante de custos", C)],
    ]
    story.append(styled_table(ready_rows, [4.5 * cm, 2.5 * cm, 3.5 * cm, 5.7 * cm]))

    story.append(P("7. Multiplicadores setoriais iniciais (E<sub>s</sub> / Ē)", styles["H1BR"]))
    story.append(
        P(
            "Priors relativos para o Brasil (ajustáveis quando mapear AIIE/Eloundou formalmente). "
            "Multiplicam α<sup>base</sup><sub>k</sub>. Limitar o produto a α<sub>k,s</sub> ≤ 0,60.",
            styles["BodyBR"],
        )
    )
    setor_rows = [
        [P("<b>Grupo setorial (B3)</b>", CC), P("<b>E<sub>s</sub>/Ē</b>", CC), P("<b>Efeito esperado no Bloco A</b>", C)],
        [P("Bancos / serviços financeiros / seguros", C), P("<b>1,25</b>", CC), P("↑ SG&A, pessoal, PDD", C)],
        [P("Software / TI / serviços empresariais", C), P("<b>1,20</b>", CC), P("↑ pessoal e SG&A cognitivos", C)],
        [P("Varejo / e-commerce / consumo cíclico", C), P("<b>1,10</b>", CC), P("↑ vendas/SAC, estoques, PDD (se houver crédito)", C)],
        [P("Saúde / educação / serviços diversos", C), P("<b>1,05</b>", CC), P("Levemente acima da média", C)],
        [P("Indústria de transformação / bens de capital", C), P("<b>1,00</b>", CC), P("Referência; CPV operacional importa mais", C)],
        [P("Utilities / telecom / infraestrutura", C), P("<b>0,90</b>", CC), P("Mix operacional + backoffice", C)],
        [P("Commodities / mineração / óleo e gás / agro", C), P("<b>0,75</b>", CC), P("↓ α efetivo: CPV commodity domina", C)],
        [P("Construção civil / incorporação", C), P("<b>0,85</b>", CC), P("Menor densidade cognitivo-digital média", C)],
    ]
    story.append(styled_table(setor_rows, [7.5 * cm, 2.5 * cm, 6.2 * cm]))
    story.append(
        P(
            "Atribuição do setor na implementação: campo oficial <i>SETOR_ATIV</i> do cadastro de companhias "
            "abertas da CVM, mapeado para os grupos acima em <i>config/setor_cvm.yaml</i> (holdings "
            "“Emp. Adm. Part. – X” herdam o setor X); heurística por nome só como fallback; plano de contas "
            "de instituição financeira sempre força o grupo financeiro. Transporte/logística, turismo e "
            "holdings sem setor principal ficam em “outros” (multiplicador 1,00). "
            "Subsidiárias/SPEs (DFP individual + Categoria B) ficam fora do painel.",
            styles["NoteBR"],
        )
    )

    story.append(P("8. Exemplo numérico (ilustrativo)", styles["H1BR"]))
    story.append(
        P(
            "Empresa hipotética de varejo: ROL = 1.000; SG&A = 120; Vendas = 80; Pessoal (DVA) = 90; "
            "Estoques = 150; CPV = 600; Caixa/Ativo = 5%; DL/EBITDA = 2,8×; FCO &gt; 0; setor multiplicador = 1,10; "
            "sem abertura de buckets (usa só α). Pessoal líquido: 90 / (600 + 120 + 80) = 11,25% ⇒ "
            "fator 0,8875 sobre CPV, SG&A e Vendas (CPV~ = 532,5; SG&A~ = 106,5; Vendas~ = 71,0).",
            styles["BodyBR"],
        )
    )
    story.append(
        formula_image(
            r"Expo ="
            r"\frac{106.5}{1000}(0.30\cdot 1.10)"
            r"+\frac{71}{1000}(0.32\cdot 1.10)"
            r"+\frac{90}{1000}(0.35\cdot 1.10)"
            r"+\frac{150}{1000}(0.18\cdot 1.10)"
            r"+\frac{532.5}{1000}(0.10\cdot 1.10)",
            "f_exemplo.png",
            fontsize=10,
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        formula_image(
            r"= 0.0351 + 0.0250 + 0.0347 + 0.0297 + 0.0586"
            r"\;=\; 0.1831",
            "f_exemplo2.png",
            fontsize=12,
        )
    )
    story.append(Spacer(1, 0.15 * cm))
    story.append(
        P(
            "Com <i>f = 0,90</i>, <i>g = 0,70</i> e <i>h = 1,00</i> ⇒ <i>F<sup>fin</sup> = 0,63</i>. "
            "Teto = 0,1831 × 1.000 = 183,1; Viável = 183,1 × 0,63 × 0,70 = 80,7; "
            "com R = 0,50 (mediana do painel) ⇒ R<sup>eff</sup> = 0,55 e fator de execução = 0,85 + 0,15 × 0,55 = 0,9325: "
            "Final = 80,7 × 0,9325 ≈ 75,3 (7,5% da ROL). "
            "<b>Score ≈ 0,1831 × 0,63 × 0,70 × 0,9325 ≈ 0,075</b>. "
            "(No modo <i>separado</i>, sem o netting de pessoal, Expo seria 0,1982 — 8% maior — por dupla contagem.) "
            "Na implementação, normalizar o painel B3 para escala 0–100 (min–max entre válidas do ano, exposição winsorizada no p99).",
            styles["BodyBR"],
        )
    )

    story.append(P("9. Protocolo de robustez (obrigatório)", styles["H1BR"]))
    rob_rows = [
        [P("<b>#</b>", CC), P("<b>Cenário</b>", C), P("<b>O que mudar</b>", C), P("<b>O que reportar</b>", C)],
        [P("R0", CC), P("Base", C), P("Pesos deste PDF", C), P("Ranking completo", C)],
        [P("R1", CC), P("α ±20%", C), P("Multiplicar todos α por 0,8 e 1,2", C), P("Estabilidade do top/bottom quartil", C)],
        [P("R2", CC), P("Equal weights", C), P("α<sub>k</sub> = 0,25 ∀k", C), P("Correlação de Spearman com R0", C)],
        [P("R3", CC), P("Só pessoal + SG&A + vendas", C), P("Demais α = 0", C), P("Se o núcleo cognitivo basta", C)],
        [P("R4", CC), P("Sem Bloco C", C), P("φ = 1 (λ = 0 sozinho não desliga R)", C), P("Isolar teto de custos", C)],
        [P("R5", CC), P("Sem ajuste setorial", C), P("E<sub>s</sub>/Ē = 1", C), P("Papel do multiplicador setorial", C)],
        [P("R6", CC), P("Só g(·)", C), P("f = 1", C), P("Sensibilidade à liquidez", C)],
    ]
    story.append(styled_table(rob_rows, [1.2 * cm, 4.0 * cm, 5.5 * cm, 5.5 * cm]))

    story.append(P("10. Regras de implementação no código", styles["H1BR"]))
    story.append(
        P(
            "1. Guardar α, β, f/g, λ e multiplicadores setoriais em <b>arquivo de calibração versionado</b> "
            "(CSV/YAML) — nunca hardcode espalhado.<br/>"
            "2. Se cobertura das notas &lt; 60% da linha-mãe, <b>ignorar β</b> e usar só α na linha agregada.<br/>"
            "3. Truncar α<sub>k,s</sub> em [0, 0,60].<br/>"
            "4. Normalizar Score para 0–100 <b>depois</b> de calcular o painel completo do ano.<br/>"
            "5. No texto da dissertação: declarar pesos como <b>priors calibrados</b> + apêndice de robustez.",
            styles["BodyBR"],
        )
    )

    story.append(Spacer(1, 0.4 * cm))
    story.append(
        P(
            "<b>Veredito metodológico:</b> a <i>ordem</i> dos pesos vem da teoria de exposição a tarefas; "
            "o <i>número</i> vem deste cenário-base; a <i>credibilidade</i> vem da estabilidade sob R1–R6.",
            styles["BodyBR"],
        )
    )

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawString(1.7 * cm, 1.0 * cm, "Pesos α/β — Indicador Ex-Ante de IA (B3) · Cenário-base")
        canvas.drawRightString(A4[0] - 1.7 * cm, 1.0 * cm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"PDF gerado: {OUT}")


if __name__ == "__main__":
    build()
