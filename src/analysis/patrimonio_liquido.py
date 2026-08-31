"""Patrimônio líquido comparável dos fundos Kinea vs universo competitivo.

Toda a lógica de PL vive aqui (fonte de verdade). O notebook
`universo_competitivo.ipynb` apenas importa e orquestra estas funções.

Conceito de PL adotado (mesma fonte usada para os concorrentes):
  - Fundos abertos / previdência (RCVM175): campo `Patrimonio_Liquido` do
    `registro_fundo.csv`, a nível de FUNDO (não de subclasse).
  - FIIs "papel/tijolo": campo `Patrimonio_Liquido` do
    `inf_mensal_fii_complemento`, competência mais recente por CNPJ.
  - FIAGRO (KNCA11): campo `Patrimonio_Liquido` do `inf_mensal_fiagro`.

Limitação conhecida: o PL dos fundos abertos é a nível de fundo inteiro
(pode agregar subclasses); não há data-base explícita capturada nessa fonte
específica. FIIs e FIAGRO têm data-base explícita (`Data_Referencia`).

Regra crítica (bug real já corrigido nesta versão)
---------------------------------------------------
`df["cnpj"].astype(str)` transforma `NaN` na STRING literal "nan" - e se
várias linhas tiverem CNPJ ausente, todas viram "nan" e casam entre si num
merge (produto cartesiano: N linhas sem CNPJ x N linhas sem CNPJ). A
correção: usar sempre `clean_cnpj` (que devolve `None`, nunca a string
"nan") e SEPARAR linhas com/sem CNPJ antes de qualquer merge - nunca deixar
uma chave ausente entrar na operação de join.
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import requests

from src.transformation.standardize import clean_cnpj, standardize_category

# Valores de categoria_padronizada que sabemos NÃO serem uma classificação
# real (vieram de fallback pra um campo genérico do template da XP, ex:
# "segmento" em fichas de FII). Quando o valor cai aqui, reconciliamos com
# classe_anbima_cvm em vez de propagar o rótulo ruim adiante.
CATEGORIAS_XP_NAO_CONFIAVEIS = {None, "", "outros", "nan"}

URL_INF_MENSAL_FII = (
    "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_2026.zip"
)


def baixar_pl_fii_complemento(url: str = URL_INF_MENSAL_FII) -> pd.DataFrame:
    """Baixa o Informe Mensal FII e retorna o PL mais recente por CNPJ.

    O arquivo `inf_mensal_fii_geral` NÃO tem PL — o campo mora no
    `inf_mensal_fii_complemento`. Informe mensal pode ter retificação, então
    ficamos com a linha mais recente por CNPJ (maior Data_Referencia, depois
    maior Versao).
    """
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    with z.open("inf_mensal_fii_complemento_2026.csv") as f:
        df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    df["cnpj_limpo"] = df["CNPJ_Fundo_Classe"].apply(clean_cnpj)

    df_recente = (
        df.dropna(subset=["cnpj_limpo"])
        .sort_values(["cnpj_limpo", "Data_Referencia", "Versao"])
        .drop_duplicates(subset="cnpj_limpo", keep="last")
    )
    return df_recente[
        ["cnpj_limpo", "Patrimonio_Liquido", "Total_Numero_Cotistas", "Data_Referencia"]
    ].rename(columns={"cnpj_limpo": "cnpj"})


def _cnpj_limpo(df: pd.DataFrame, col: str = "cnpj") -> pd.Series:
    """SEMPRE usar isto em vez de `.astype(str).str.strip()` numa coluna de
    CNPJ. `clean_cnpj` devolve `None` para valores ausentes/inválidos -
    nunca a string "nan", que casaria com outras linhas ausentes num merge."""
    return df[col].apply(clean_cnpj)


def extrair_pl_kinea(df_kinea: pd.DataFrame, df_concorrentes: pd.DataFrame) -> pd.DataFrame:
    """Extrai o PL de cada fundo Kinea por CNPJ exato.

    Os fundos Kinea já aparecem em `df_concorrentes` como linhas
    auto-casadas (o join da CVM foi por CNPJ contra o universo inteiro da
    categoria). Não é preciso buscar nenhuma fonte nova - só localizar cada
    CNPJ e ler o PL/fonte/classe correspondentes.

    Fundos sem CNPJ (ex: FII não enriquecido a montante) recebem
    status "sem_cnpj" explicitamente, nunca são comparados por igualdade
    de valor ausente.

    Retorna 1 linha por fundo Kinea: status_pl,
    patrimonio_liquido_cvm, fonte_pl, classe_anbima_cvm.
    """
    cnpj_kinea = _cnpj_limpo(df_kinea)
    cnpj_conc = _cnpj_limpo(df_concorrentes)

    linhas = []
    for i, r in df_kinea.iterrows():
        cnpj = cnpj_kinea.loc[i]
        if cnpj is None:
            linhas.append({
                "cnpj": r.get("cnpj"),
                "status_pl": "sem_cnpj",
                "patrimonio_liquido_cvm": None,
                "fonte_pl": None,
                "classe_anbima_cvm": None,
            })
            continue

        match = df_concorrentes[cnpj_conc == cnpj]
        pl_vals = match["patrimonio_liquido"].dropna().unique()
        fonte_vals = match["source"].dropna().unique()
        classe_vals = match["classe_anbima"].dropna().unique()

        if len(match) == 0:
            status, pl = "nao_encontrado", None
        elif len(pl_vals) == 0:
            status, pl = "encontrado_sem_pl", None
        elif len(pl_vals) > 1:
            status, pl = "ambiguo", None
        else:
            status, pl = "encontrado", float(pl_vals[0])

        linhas.append({
            "cnpj": cnpj,
            "status_pl": status,
            "patrimonio_liquido_cvm": pl,
            "fonte_pl": fonte_vals[0] if len(fonte_vals) else None,
            "classe_anbima_cvm": classe_vals[0] if len(classe_vals) else None,
        })

    df_out = pd.DataFrame(linhas)
    assert len(df_out) == len(df_kinea), (
        f"extrair_pl_kinea deveria retornar 1 linha por fundo Kinea "
        f"({len(df_kinea)}), retornou {len(df_out)}"
    )
    return df_out


def calcular_percentil(df_pl: pd.DataFrame, df_concorrentes: pd.DataFrame) -> pd.DataFrame:
    """Adiciona percentil de PL e razão-sobre-mediana dentro de cada categoria.

    O universo de comparação exclui qualquer fundo gerido pela própria Kinea
    e deduplica concorrentes por (cnpj, classe).
    """
    comp = df_concorrentes[df_concorrentes["eh_fundo_kinea"] == False].drop_duplicates(
        subset=["cnpj", "classe_anbima"]
    )

    n_list, pctl_list, razao_list = [], [], []
    for _, r in df_pl.iterrows():
        pl, classe = r["patrimonio_liquido_cvm"], r["classe_anbima_cvm"]
        if pd.isna(pl) or pd.isna(classe):
            n_list.append(None); pctl_list.append(None); razao_list.append(None)
            continue
        universo = comp[comp["classe_anbima"] == classe]["patrimonio_liquido"].dropna()
        n = len(universo)
        if n == 0:
            n_list.append(0); pctl_list.append(None); razao_list.append(None)
            continue
        pctl = float((universo < pl).mean() * 100)
        mediana = universo.median()
        razao = pl / mediana if mediana else None
        n_list.append(n)
        pctl_list.append(round(pctl, 1))
        razao_list.append(round(razao, 2) if razao else None)

    out = df_pl.copy()
    out["n_concorrentes_com_pl"] = n_list
    out["percentil_pl"] = pctl_list
    out["pl_sobre_mediana_universo"] = razao_list
    return out


def montar_universo_kinea_completo(
    df_kinea: pd.DataFrame, df_concorrentes: pd.DataFrame
) -> pd.DataFrame:
    """Pipeline completo: ficha da XP + PL + percentil, numa tabela só.

    Retorna sempre `len(df_kinea)` linhas - nunca mais, nunca menos. Não
    sobrescreve `df_kinea` - retorna uma cópia enriquecida.
    """
    df_pl = extrair_pl_kinea(df_kinea, df_concorrentes)
    df_pl = calcular_percentil(df_pl, df_concorrentes)

    # merge por posição (index), não por CNPJ - df_pl já tem exatamente 1
    # linha por linha de df_kinea, na mesma ordem (garantido pelo assert em
    # extrair_pl_kinea). Isso evita de vez qualquer risco de merge-by-key
    # explodir por chave ausente/repetida.
    df_out = df_kinea.reset_index(drop=True).copy()
    df_pl_indexed = df_pl.reset_index(drop=True).drop(columns=["cnpj"])
    df_out = pd.concat([df_out, df_pl_indexed], axis=1)

    # Reconcilia categoria_padronizada com classe_anbima_cvm quando o rótulo
    # vindo da XP não é confiável (ex: KDIF11 - ficha da XP não trouxe
    # categoria_bruta/classificacao_xp, o fallback pegou "segmento" = "Outros",
    # um bucket genérico de template, não uma classificação real). A CVM já
    # é usada como fonte de verdade pra achar o universo de concorrentes
    # (calcular_percentil usa classe_anbima_cvm, não categoria_padronizada),
    # então aqui só alinhamos o RÓTULO ao que o cálculo já usa - não muda
    # nenhum percentil. categoria_bruta (texto original da XP) permanece
    # intacto como trilha de auditoria.
    categoria_nao_confiavel = df_out["categoria_padronizada"].apply(
        lambda v: str(v).strip().lower() in CATEGORIAS_XP_NAO_CONFIAVEIS
    )
    df_out.loc[categoria_nao_confiavel, "categoria_padronizada"] = (
        df_out.loc[categoria_nao_confiavel, "classe_anbima_cvm"].apply(standardize_category)
    )

    assert len(df_out) == len(df_kinea), "montar_universo_kinea_completo alterou o número de linhas"
    return df_out
