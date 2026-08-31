"""
app.py - Dashboard do Case BI Kinea

Como executar
--------------
    pip install streamlit pandas plotly
    streamlit run app.py        # No macbook: python3 -m streamlit run app.py

Espera encontrar (a partir da raiz do repo), em data/processed/:
    universo_kinea_completo.csv
    fundos_concorrentes.csv
    scorecard_posicionamento.csv
    aprofundamento_liquidez_custos.csv
    aprofundamento_conteudo.csv
    aprofundamento_retorno_risco.csv
    recomendacoes.csv
E na raiz do repo (ou em docs/): dicionario_dados.md, fontes.md, log_ia.md, metodologia.md
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Kinea x XP - Inteligência Competitiva",
    page_icon="◆",
    layout="wide",
)

# Encontra a raiz do repo subindo a partir de onde o app.py está - funciona
# tanto rodando de dashboard/app.py quanto de app.py solto na raiz, sem
# depender de onde o comando streamlit foi disparado.
def _achar_raiz_repo(inicio: Path) -> Path:
    for candidato in [inicio, *inicio.parents]:
        if (candidato / "data" / "processed").exists():
            return candidato
    return inicio  # fallback - mostra erro claro mais abaixo se não achar os CSVs

ROOT = _achar_raiz_repo(Path(__file__).resolve().parent)
DATA = ROOT / "data" / "processed"

FUNDOS_PRIORIZADOS = [
    "Kinea Indices de Precos FII (KNIP11)",
    "Kinea Infra FII (KDIF11)",
    "Kinea High Yield CRI FII (KNHY11)",
]

# ---------------------------------------------------------------------------
# Estilo - identidade visual Kinea: fundo branco, navy escuro + azul claro
# de accent, títulos em negrito com barra azul embaixo, valor sempre escrito
# direto na barra (não escondido em eixo/legenda) - mesmo padrão dos
# relatórios públicos da própria Kinea.
# ---------------------------------------------------------------------------
NAVY = "#0B2545"
NAVY_LIGHT = "#13315C"
BLUE_ACCENT = "#4A90D9"
BLUE_PALE = "#DCEAF7"
GRAY_TEXT = "#5B6472"
RED_ALERTA = "#B4453A"
GREEN_OK = "#2E7D5B"
AMBER = "#C98A2B"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: #FFFFFF; }}
    h1, h2, h3 {{
        color: {NAVY};
        font-weight: 800;
        letter-spacing: -0.01em;
    }}
    h1 {{ border-bottom: 4px solid {BLUE_ACCENT}; padding-bottom: 0.3rem; display: inline-block; }}
    div[data-testid="stMetric"] {{
        background-color: #FFFFFF;
        border: 1px solid #E3E8EE;
        border-radius: 4px;
        padding: 0.9rem 1rem;
    }}
    div[data-testid="stMetricValue"] {{ color: {NAVY}; font-weight: 700; }}
    div[data-testid="stMetricLabel"] {{ color: {GRAY_TEXT}; }}
    .fonte-caption {{ color: #9AA3AF; font-size: 0.78rem; margin-top: -0.4rem; }}
    .achado-box {{
        background-color: #FBEEEC;
        border-left: 4px solid {RED_ALERTA};
        border-radius: 3px;
        padding: 0.85rem 1.1rem;
        margin: 0.6rem 0;
        font-size: 0.94rem;
    }}
    .ok-box {{
        background-color: {BLUE_PALE};
        border-left: 4px solid {NAVY};
        border-radius: 3px;
        padding: 0.85rem 1.1rem;
        margin: 0.6rem 0;
        font-size: 0.94rem;
    }}
    .reco-card {{
        background-color: #FFFFFF;
        border: 1px solid #E3E8EE;
        border-top: 3px solid {BLUE_ACCENT};
        border-radius: 4px;
        padding: 1.2rem 1.4rem;
        margin: 0.8rem 0 1.4rem 0;
    }}
    .reco-label {{
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: {GRAY_TEXT};
        margin-top: 0.7rem;
        margin-bottom: 0.15rem;
    }}
    .reco-tag {{
        display: inline-block;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        padding: 0.08rem 0.45rem;
        border-radius: 3px;
        margin-left: 0.5rem;
        vertical-align: middle;
    }}
    .tag-fato {{ background-color: {BLUE_PALE}; color: {NAVY}; }}
    .tag-inferencia {{ background-color: #FBF1E1; color: {AMBER}; }}
    .tag-hipotese {{ background-color: #F1EEF7; color: #6B4E9E; }}

    .status-badge {{
        display: inline-block;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 0.15rem 0.55rem;
        border-radius: 3px;
        text-align: center;
        width: 100%;
    }}
    .status-bem {{ background-color: #E4F2EA; color: {GREEN_OK}; }}
    .status-desv {{ background-color: #FBEEEC; color: {RED_ALERTA}; }}
    .status-mal {{ background-color: #FBF1E1; color: {AMBER}; }}
    .status-lim {{ background-color: #EFEFEF; color: {GRAY_TEXT}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

BARRA_TITULO = f'<div style="width:64px; height:4px; background-color:{BLUE_ACCENT}; margin:0.2rem 0 0.9rem 0;"></div>'


def titulo_secao(texto: str):
    st.markdown(f"#### {texto}")
    st.markdown(BARRA_TITULO, unsafe_allow_html=True)


def fonte(texto: str):
    st.markdown(f'<p class="fonte-caption">Fonte: {texto}</p>', unsafe_allow_html=True)


STATUS_CLASSE = {
    "bem posicionado": "status-bem",
    "desvantagem": "status-desv",
    "mal comunicado": "status-mal",
    "limitação de categoria/plataforma": "status-lim",
}
STATUS_ROTULO_CURTO = {
    "bem posicionado": "Bem posicionado",
    "desvantagem": "Desvantagem",
    "mal comunicado": "Mal comunicado",
    "limitação de categoria/plataforma": "Limitação de categoria",
}


def badge_status(status: str) -> str:
    if pd.isna(status):
        return ""
    classe = STATUS_CLASSE.get(status, "status-lim")
    rotulo = STATUS_ROTULO_CURTO.get(status, status)
    return f'<span class="status-badge {classe}">{rotulo}</span>'


# ---------------------------------------------------------------------------
# Carregamento de dados
# ---------------------------------------------------------------------------
@st.cache_data
def carregar_csv(nome_arquivo: str) -> pd.DataFrame:
    caminho = DATA / nome_arquivo
    if not caminho.exists():
        return pd.DataFrame()
    return pd.read_csv(caminho)


def pct_to_float(valor) -> float:
    if pd.isna(valor):
        return float("nan")
    texto = str(valor).replace("%", "").replace(",", ".").strip()
    try:
        return float(texto)
    except ValueError:
        return float("nan")


df_universo = carregar_csv("universo_kinea_completo.csv")
df_concorrentes = carregar_csv("fundos_concorrentes.csv")
df_scorecard = carregar_csv("scorecard_posicionamento.csv")
df_liquidez_aprof = carregar_csv("aprofundamento_liquidez_custos.csv")
df_conteudo_aprof = carregar_csv("aprofundamento_conteudo.csv")
df_retorno_aprof = carregar_csv("aprofundamento_retorno_risco.csv")
df_recomendacoes = carregar_csv("recomendacoes.csv")

if df_universo.empty:
    st.error(
        "Não encontrei `data/processed/universo_kinea_completo.csv`. "
        "Rode o dashboard a partir da raiz do repositório."
    )
    st.stop()

st.title("Kinea × XP")
st.markdown(
    f'<p style="color:{GRAY_TEXT}; font-size:1.05rem; margin-top:0.6rem;">'
    f"Inteligência competitiva na prateleira pública da XP · {len(df_universo)} fundos mapeados</p>",
    unsafe_allow_html=True,
)

tab_geral, tab_scorecard, tab_recomendacoes, tab_aprofundamento, tab_governanca = st.tabs(
    ["Visão Geral", "Scorecard de Posicionamento", "Recomendações", "Aprofundamento (3 fundos)", "Governança e fontes"]
)

# ===========================================================================
# ABA 1 - VISÃO GERAL (17 fundos)
# ===========================================================================
with tab_geral:
    titulo_secao("A prateleira Kinea na XP")

    ROTULO_CATEGORIA_CURTO = {
        "Fundo Imobiliário (FII)": "FII",
        "Multimercado - Macro": "MM Macro",
        "Multimercado": "Multimercado",
        "Renda Fixa": "Renda Fixa",
        "Ações": "Ações",
        "Outros": "Outros",
    }
    ROTULO_TIPO_CURTO = {
        "fii": "FII",
        "fundo_aberto": "Fundo aberto",
        "previdencia": "Previdência",
    }

    col_f1, col_f2 = st.columns(2)
    categorias = sorted(df_universo["categoria_padronizada"].dropna().unique())
    tipos = sorted(df_universo["tipo_pagina"].dropna().unique())
    filtro_categoria = col_f1.multiselect(
        "Categoria", categorias, default=categorias,
        format_func=lambda c: ROTULO_CATEGORIA_CURTO.get(c, c),
    )
    filtro_tipo = col_f2.multiselect(
        "Tipo de página", tipos, default=tipos,
        format_func=lambda t: ROTULO_TIPO_CURTO.get(t, t),
    )

    df_filtrado = df_universo[
        df_universo["categoria_padronizada"].isin(filtro_categoria)
        & df_universo["tipo_pagina"].isin(filtro_tipo)
    ]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Fundos na prateleira", len(df_filtrado))
    n_completo = (df_filtrado["status_confirmacao"] == "ficha_coletada").sum()
    k2.metric("Ficha coletada", f"{n_completo}/{len(df_filtrado)}")
    taxa_media = df_filtrado["taxa_administracao_pct"].mean()
    k3.metric("Taxa de adm. média", f"{taxa_media:.2f}%" if pd.notna(taxa_media) else "—")
    n_categorias = df_filtrado["categoria_padronizada"].nunique()
    k4.metric("Categorias", n_categorias)

    titulo_secao("Fundos por categoria")
    contagem_categoria = (
        df_filtrado.groupby("categoria_padronizada")
        .size()
        .sort_values(ascending=True)
        .reset_index(name="n_fundos")
    )
    fig_categoria = go.Figure(
        go.Bar(
            x=contagem_categoria["n_fundos"],
            y=contagem_categoria["categoria_padronizada"],
            orientation="h",
            marker_color=NAVY,
            text=contagem_categoria["n_fundos"],
            textposition="outside",
            textfont=dict(color=NAVY, size=14, family="Arial Black"),
        )
    )
    fig_categoria.update_layout(
        height=max(220, 45 * len(contagem_categoria)),
        margin=dict(l=10, r=30, t=10, b=10),
        xaxis_title=None, xaxis_visible=False,
        yaxis_title=None,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=14, color=NAVY),
    )
    st.plotly_chart(fig_categoria, config={"displayModeBar": False})
    fonte("coleta própria via conteudos.xpi.com.br")

    if "percentil_pl" in df_filtrado.columns:
        titulo_secao("Porte relativo (percentil de PL dentro da categoria)")
        st.caption(
            "Percentil calculado contra o universo competitivo da mesma categoria "
            "via CVM Dados Abertos. Quanto mais perto de 0, menor o fundo relativo "
            "aos concorrentes diretos."
        )
        df_pl = df_filtrado[df_filtrado["status_pl"] == "encontrado"][
            ["nome_padronizado", "categoria_padronizada", "percentil_pl"]
        ].sort_values("percentil_pl", ascending=True)
        if not df_pl.empty:
            fig_pl = go.Figure(
                go.Bar(
                    x=df_pl["percentil_pl"],
                    y=df_pl["nome_padronizado"],
                    orientation="h",
                    marker_color=BLUE_ACCENT,
                    text=df_pl["percentil_pl"].map(lambda v: f"{v:.0f}"),
                    textposition="outside",
                    textfont=dict(color=NAVY, size=12),
                )
            )
            fig_pl.update_layout(
                height=max(300, 32 * len(df_pl)),
                margin=dict(l=10, r=30, t=10, b=10),
                xaxis_title="Percentil de PL na categoria",
                xaxis_range=[0, 112],
                yaxis_title=None,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(size=13, color=NAVY),
            )
            st.plotly_chart(fig_pl, config={"displayModeBar": False})
            fonte("CVM Dados Abertos (RCVM175, cad_fi, inf_mensal_fii, inf_mensal_fiagro)")
        else:
            st.info("Nenhum fundo com PL comparável no filtro atual.")

    with st.expander("Ver tabela completa"):
        RENOMEAR_COLUNAS = {
            "nome_padronizado": "Fundo",
            "categoria_padronizada": "Categoria",
            "tipo_pagina": "Tipo",
            "taxa_administracao_pct": "Taxa adm. (%)",
            "status_pl": "Status PL",
            "percentil_pl": "Percentil PL",
            "url": "Ficha XP",
        }
        colunas_exibir = [c for c in RENOMEAR_COLUNAS if c in df_filtrado.columns]
        df_tabela = df_filtrado[colunas_exibir].rename(columns=RENOMEAR_COLUNAS)
        st.dataframe(
            df_tabela,
            width="stretch",
            hide_index=True,
            column_config={
                "Ficha XP": st.column_config.LinkColumn("Ficha XP", display_text="Abrir ↗")
            },
        )


# ===========================================================================
# ABA 2 - SCORECARD DE POSICIONAMENTO (17 fundos x 4 dimensões)
# ===========================================================================
with tab_scorecard:
    titulo_secao("Onde a Kinea está bem posicionada, em desvantagem ou mal comunicada")
    st.caption(
        "Matriz de 17 fundos × 4 dimensões do case. Critérios: Liquidez e custos = "
        "desvantagem se taxa > 30% acima da mediana concorrente; Retorno e risco = "
        "desvantagem se retorno < -2 p.p. vs. mediana; ausência de dado conta como "
        "'mal comunicado' só quando o concorrente direto tem o dado e a Kinea não "
        "(assimetria real) - se nenhum dos dois tem, é limitação de categoria/plataforma, "
        "não desvantagem competitiva. Ver metodologia.md para detalhes."
    )

    if df_scorecard.empty:
        st.warning("`scorecard_posicionamento.csv` não encontrado.")
    else:
        # KPIs de resumo do portfólio inteiro
        k1, k2, k3 = st.columns(3)
        k1.metric("Total 'bem posicionado'", int(df_scorecard["n_bem_posicionado"].sum()))
        k2.metric("Total 'desvantagem'", int(df_scorecard["n_desvantagem"].sum()))
        k3.metric("Total 'mal comunicado'", int(df_scorecard["n_mal_comunicado"].sum()))

        titulo_secao("Matriz completa")
        col_ordenar, col_filtro_status = st.columns([1, 2])
        ordenar_por = col_ordenar.selectbox(
            "Ordenar por", ["Fundo (A-Z)", "Mais desvantagens primeiro", "Mais mal comunicados primeiro"]
        )
        status_disponiveis = list(STATUS_ROTULO_CURTO.values())
        status_filtro = col_filtro_status.multiselect(
            "Filtrar por status (qualquer dimensão)", status_disponiveis, default=status_disponiveis
        )

        df_sc = df_scorecard.copy()
        if ordenar_por == "Mais desvantagens primeiro":
            df_sc = df_sc.sort_values("n_desvantagem", ascending=False)
        elif ordenar_por == "Mais mal comunicados primeiro":
            df_sc = df_sc.sort_values("n_mal_comunicado", ascending=False)
        else:
            df_sc = df_sc.sort_values("nome_padronizado")

        status_selecionados_raw = [
            k for k, v in STATUS_ROTULO_CURTO.items() if v in status_filtro
        ]
        mask = (
            df_sc["status_produto"].isin(status_selecionados_raw)
            | df_sc["status_liquidez"].isin(status_selecionados_raw)
            | df_sc["status_retorno"].isin(status_selecionados_raw)
            | df_sc["status_conteudo"].isin(status_selecionados_raw)
        )
        df_sc = df_sc[mask]

        cols_header = st.columns([2.4, 1, 1, 1, 1])
        for col, titulo in zip(
            cols_header, ["Fundo", "Produto", "Liquidez e custos", "Retorno e risco", "Conteúdo"]
        ):
            col.markdown(f"**{titulo}**")

        for _, row in df_sc.iterrows():
            cols = st.columns([2.4, 1, 1, 1, 1])
            cols[0].markdown(f"{row['nome_padronizado']}")
            cols[1].markdown(badge_status(row["status_produto"]), unsafe_allow_html=True)
            cols[2].markdown(badge_status(row["status_liquidez"]), unsafe_allow_html=True)
            cols[3].markdown(badge_status(row["status_retorno"]), unsafe_allow_html=True)
            cols[4].markdown(badge_status(row["status_conteudo"]), unsafe_allow_html=True)

        st.markdown("---")
        fonte("scorecard_posicionamento.csv — critérios documentados em docs/metodologia.md")


# ===========================================================================
# ABA 3 - RECOMENDAÇÕES (para os 90 dias, conforme pedido pelo case)
# ===========================================================================
with tab_recomendacoes:
    titulo_secao("O que Comercial e Marketing deveriam priorizar nos próximos 90 dias")
    st.caption(
        "Cada recomendação segue a estrutura pedida: problema/oportunidade, evidência, "
        "ação proposta, responsável sugerido, impacto esperado, métrica de acompanhamento "
        "e dependências. As tags indicam se o trecho é FATO (observado nos dados), "
        "INFERÊNCIA (conclusão razoável a partir do fato) ou HIPÓTESE (efeito esperado, "
        "ainda não medido)."
    )

    def _tag(tipo: str) -> str:
        classe = {"FATO": "tag-fato", "INFERÊNCIA": "tag-inferencia", "HIPÓTESE": "tag-hipotese"}
        return f'<span class="reco-tag {classe.get(tipo, "tag-fato")}">{tipo}</span>'

    def _campo(rotulo: str, valor: str, tag: str = "") -> str:
        return f'<div class="reco-label">{rotulo}{tag}</div><div>{valor}</div>'

    if df_recomendacoes.empty:
        st.warning("`recomendacoes.csv` não encontrado.")
    else:
        filtro_fundo = st.multiselect(
            "Filtrar por fundo",
            sorted(df_recomendacoes["fundo_kinea"].unique()),
            default=[],
        )
        df_reco_filtrado = (
            df_recomendacoes[df_recomendacoes["fundo_kinea"].isin(filtro_fundo)]
            if filtro_fundo else df_recomendacoes
        )

        for _, r in df_reco_filtrado.iterrows():
            partes = [
                '<div class="reco-card">',
                f'<h4 style="margin-top:0; color:{NAVY};">{r["fundo_kinea"]}</h4>',
                f'<p style="font-size:1.02rem; font-weight:700; color:{BLUE_ACCENT}; '
                f'margin-bottom:0.6rem;">{r["titulo"]}</p>',
                _campo("Problema / oportunidade", r["problema_oportunidade"], _tag(r["tipo_evidencia_problema"])),
                _campo("Evidência", r["evidencia"], _tag(r["tipo_evidencia_evidencia"])),
                _campo("Ação proposta", r["acao_proposta"], _tag(r["tipo_evidencia_acao"])),
                _campo("Responsável sugerido", r["responsavel_sugerido"]),
                _campo("Impacto esperado", r["impacto_esperado"], _tag(r["tipo_evidencia_impacto"])),
                _campo("Métrica de acompanhamento", r["metrica_acompanhamento"]),
                _campo("Dependências", r["dependencias"]),
                '</div>',
            ]
            st.markdown("".join(partes), unsafe_allow_html=True)


# ===========================================================================
# ABA 4 - APROFUNDAMENTO (3 fundos priorizados)
# ===========================================================================

# Diagnóstico resumido de cada fundo priorizado - a manchete que dá sentido
# às métricas soltas abaixo. Escrito à mão porque é síntese editorial (não
# um cálculo), mas toda a métrica que sustenta cada frase está nos gráficos
# logo abaixo. Cada resumo toca explicitamente nos 3 critérios que o case
# define para "Conteúdo e diferenciação": clareza da proposta, completude
# das informações e narrativa competitiva.
DIAGNOSTICO_APROFUNDAMENTO = {
    "Kinea Indices de Precos FII (KNIP11)": {
        "manchete": "Retorno negativo num ano em que o mercado foi positivo — o maior desvio do portfólio",
        "status": "status-desv",
        "resumo": "É o pior caso de performance dos 17 fundos: enquanto os concorrentes diretos de "
                   "papel/recebíveis (XPCI11, CPTS11) entregaram em média +9,24% no ano, o KNIP11 ficou "
                   "em -2,96% — um desvio de -12,2 pontos percentuais. A taxa de administração também "
                   "está acima da mediana ampla do mercado FII. Mas na dimensão Conteúdo, a proposta é "
                   "clara e a ficha é 100% completa — e o fundo vai além: tem um relatório publicado com "
                   "recomendação de compra e explicação de estratégia, uma narrativa competitiva que "
                   "nenhum dos outros 2 fundos aprofundados tem. Esse é o único dos 3 aprofundados com "
                   "problema real de performance, não de comunicação — a Kinea já está falando sobre o "
                   "fundo, só precisa explicar o resultado.",
    },
    "Kinea Infra FII (KDIF11)": {
        "manchete": "Retorno acima do mercado, mas a ficha pública na XP está quebrada",
        "status": "status-mal",
        "resumo": "O fundo entrega 15,28% em 12 meses contra uma mediana de 9,53% dos pares diretos de "
                   "debênture incentivada — um resultado bom. O problema é completude e clareza: a tabela "
                   "de Rentabilidade da própria ficha XP retorna \"0%\" em todas as janelas, e faltam "
                   "campos que os concorrentes diretos expõem (quantidade de cotistas, PL) — a ficha está "
                   "50% incompleta. Na narrativa competitiva, isso pesa contra o fundo: concorrentes "
                   "diretos como Devant (DEVA11) e Valora (VGIP11) mostram publicamente esses mesmos "
                   "dados, reforçando uma transparência que o KDIF11 hoje não consegue transmitir. O "
                   "produto está bem; a vitrine está quebrada.",
    },
    "Kinea High Yield CRI FII (KNHY11)": {
        "manchete": "Taxa muito acima do mercado, mas perdeu menos que os pares num ano ruim para o setor",
        "status": "status-mal",
        "resumo": "A taxa de administração (1,60%) está 272% acima da mediana ampla do mercado de FII "
                   "(0,43%) — o maior desvio de taxa entre os 17 fundos Kinea. A ficha em si é completa e "
                   "a proposta do fundo é clara — o problema não é falta de dado, é falta de narrativa "
                   "competitiva: o retorno no ano (-1,90%) foi na verdade melhor que a mediana dos pares "
                   "diretos de CRI (-7,38%), já que o segmento inteiro sofreu, mas nada na comunicação "
                   "pública do fundo conta essa história. Sem esse contraste, a taxa alta fica sem "
                   "contexto e parece pior do que é.",
    },
}

with tab_aprofundamento:
    titulo_secao("Os 3 fundos priorizados para aprofundamento")
    st.caption(
        "Priorizados por sinal de desvio já visível na Visão Completa (taxa acima da "
        "mediana, rótulo de categoria inconsistente, ou universo competitivo atipicamente "
        "pequeno). O aprofundamento confirma se o sinal inicial é problema real ou não."
    )

    fundo_selecionado = st.selectbox("Selecione o fundo", FUNDOS_PRIORIZADOS)

    diagnostico = DIAGNOSTICO_APROFUNDAMENTO.get(fundo_selecionado)
    if diagnostico:
        st.markdown(
            f"""
            <div style="border:1px solid #E3E8EE; border-left:5px solid {NAVY};
                        border-radius:4px; padding:1.1rem 1.4rem; margin:0.8rem 0 1.3rem 0;">
                <span class="status-badge {diagnostico['status']}" style="width:auto; padding:0.2rem 0.7rem;">
                    {STATUS_ROTULO_CURTO.get(
                        {"status-desv": "desvantagem", "status-mal": "mal comunicado",
                         "status-bem": "bem posicionado", "status-lim": "limitação de categoria/plataforma"}[diagnostico['status']],
                        ""
                    )}
                </span>
                <p style="font-size:1.25rem; font-weight:700; color:{NAVY}; margin:0.5rem 0 0.5rem 0;">
                    {diagnostico['manchete']}
                </p>
                <p style="color:{GRAY_TEXT}; font-size:0.98rem; margin:0;">{diagnostico['resumo']}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    titulo_secao("O que os dados mostram")
    col_liq, col_ret = st.columns(2)

    with col_liq:
        st.markdown(f"**Liquidez e custos**")
        if not df_liquidez_aprof.empty:
            linha = df_liquidez_aprof[df_liquidez_aprof["fundo_kinea"] == fundo_selecionado]
            if not linha.empty:
                linha = linha.iloc[0]
                c1, c2 = st.columns(2)
                c1.metric("Taxa Kinea", f"{linha['taxa_kinea_pct']:.2f}%")
                c2.metric(
                    "vs. mediana concorrente",
                    f"{linha['mediana_concorrentes_pct']:.2f}%",
                    delta=f"{linha['desvio_relativo_pct']:+.1f}%",
                    delta_color="inverse",
                )
                fonte(linha["fonte"])
            else:
                st.info("Sem dado de Liquidez e custos para este fundo.")
        else:
            st.warning("`aprofundamento_liquidez_custos.csv` não encontrado.")

    with col_ret:
        st.markdown(f"**Retorno e risco**")
        if not df_retorno_aprof.empty:
            linhas = df_retorno_aprof[df_retorno_aprof["fundo_kinea"] == fundo_selecionado]
            if not linhas.empty:
                for _, linha in linhas.iterrows():
                    desvio = linha["desvio_vs_mediana"]
                    st.metric(
                        linha["metrica"],
                        f"{linha['valor_kinea']:.2f}",
                        delta=f"{desvio:+.2f} vs. mediana" if pd.notna(desvio) else None,
                    )
                fonte(linhas["fonte"].iloc[0])

                observacoes = linhas["observacao"].dropna()
                observacoes = observacoes[observacoes.astype(str).str.len() > 0]
                if not observacoes.empty:
                    st.markdown(f'<div class="achado-box">{observacoes.iloc[0]}</div>', unsafe_allow_html=True)
            else:
                st.info("Sem dado de Retorno e risco para este fundo.")
        else:
            st.warning("`aprofundamento_retorno_risco.csv` não encontrado.")

    titulo_secao("Conteúdo e diferenciação")
    if not df_conteudo_aprof.empty:
        linha = df_conteudo_aprof[df_conteudo_aprof["fundo_kinea"] == fundo_selecionado]
        if not linha.empty:
            linha = linha.iloc[0]
            classe = "achado-box" if "Sem achado" not in str(linha["achado"]) else "ok-box"
            st.markdown(
                f"""<div class="{classe}">
                <b>{linha['achado']}</b><br/>
                <span style="color:{GRAY_TEXT}; font-size:0.9rem;">{linha['evidencia']}</span>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.info("Sem dado de Conteúdo para este fundo.")
    else:
        st.warning("`aprofundamento_conteudo.csv` não encontrado.")

    titulo_secao("O que fazer")
    if not df_recomendacoes.empty:
        recos_fundo = df_recomendacoes[df_recomendacoes["fundo_kinea"] == fundo_selecionado]
        if not recos_fundo.empty:

            def _tag_aprof(tipo: str) -> str:
                classe = {"FATO": "tag-fato", "INFERÊNCIA": "tag-inferencia", "HIPÓTESE": "tag-hipotese"}
                return f'<span class="reco-tag {classe.get(tipo, "tag-fato")}">{tipo}</span>'

            def _campo_aprof(rotulo: str, valor: str, tag: str = "") -> str:
                return f'<div class="reco-label">{rotulo}{tag}</div><div>{valor}</div>'

            for _, r in recos_fundo.iterrows():
                partes = [
                    '<div class="reco-card">',
                    f'<p style="font-size:1.05rem; font-weight:700; color:{BLUE_ACCENT}; '
                    f'margin-top:0; margin-bottom:0.6rem;">{r["titulo"]}</p>',
                    _campo_aprof("Ação proposta", r["acao_proposta"], _tag_aprof(r["tipo_evidencia_acao"])),
                    _campo_aprof("Responsável sugerido", r["responsavel_sugerido"]),
                    _campo_aprof("Impacto esperado", r["impacto_esperado"], _tag_aprof(r["tipo_evidencia_impacto"])),
                    _campo_aprof("Métrica de acompanhamento", r["metrica_acompanhamento"]),
                    '</div>',
                ]
                st.markdown("".join(partes), unsafe_allow_html=True)
        else:
            st.info("Nenhuma recomendação registrada para este fundo em `recomendacoes.csv`.")
    else:
        st.warning("`recomendacoes.csv` não encontrado.")


# ===========================================================================
# ABA 5 - GOVERNANÇA E FONTES
# ===========================================================================
with tab_governanca:
    titulo_secao("Governança, fontes e uso de IA")

    def ler_markdown(nome: str):
        for base in (ROOT, ROOT / "docs"):
            caminho = base / nome
            if caminho.exists():
                return caminho.read_text(encoding="utf-8")
        return None

    sub1, sub2, sub3, sub4 = st.tabs(["Metodologia", "Dicionário de dados", "Registro de fontes", "Log de IA"])

    with sub1:
        conteudo = ler_markdown("metodologia.md")
        if conteudo:
            st.markdown(conteudo)
        else:
            st.info("`metodologia.md` não encontrado.")
    with sub2:
        conteudo = ler_markdown("dicionario_dados.md")
        if conteudo:
            st.markdown(conteudo)
        else:
            st.info("`dicionario_dados.md` não encontrado.")
    with sub3:
        conteudo = ler_markdown("fontes.md")
        if conteudo:
            st.markdown(conteudo)
        else:
            st.info("`fontes.md` não encontrado.")
    with sub4:
        conteudo = ler_markdown("log_ia.md")
        if conteudo:
            st.markdown(conteudo)
        else:
            st.info("`log_ia.md` não encontrado.")