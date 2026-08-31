"""
build_competitive_universe.py

Finalidade
----------
Monta o universo competitivo de cada fundo Kinea a partir das bases públicas
da CVM, cobrindo as QUATRO estruturas regulatórias em que os fundos Kinea
aparecem:

  1. registro_classe.csv (RCVM175)      -> fundos abertos/previdência adaptados
  2. cad_fi.csv (legado)                -> fundos não adaptados
  3. inf_mensal_fii (geral+complemento) -> FIIs (segmento Multicategoria)
  4. inf_mensal_fiagro                  -> FIAGRO (KNCA11)

Pré-requisito interno: os 7 FIIs Kinea não têm CNPJ na ficha bruta da XP
(limitação estrutural do template, ver docs/metodologia.md). Este módulo
enriquece o CNPJ desses 7 fundos usando o mapa ticker->CNPJ já validado em
`src/transformation/enrich_fii_cnpj.py` (fonte única - não duplicado aqui)
ANTES de qualquer join. Sem isso, os FIIs ficam sem chave pra cruzar com a
CVM e desaparecem do universo (bug real já corrigido uma vez).

Toda a lógica é exposta como funções importáveis - o notebook
`universo_competitivo.ipynb` só chama `montar_universo_competitivo`, não
reimplementa nada. `main()` mantém a execução via linha de comando.

Regras críticas
----------------
- Join sempre por CNPJ (nunca por nome).
- NUNCA fazer merge com CNPJ ausente na chave: em pandas, `NaN` em coluna
  string pode virar a string literal "nan" via `.astype(str)`, e várias
  linhas "nan" casam entre si no merge (produto cartesiano). Sempre separar
  linhas com/sem CNPJ ANTES do merge - nunca usar `.astype(str)` cru numa
  coluna de CNPJ que pode ter NaN. Usar sempre `clean_cnpj` (retorna None,
  não a string "nan").
- Duas fontes cadastrais unidas sem duplicar (um fundo está em uma OU noutra).
- PL dos FIIs vem do `inf_mensal_fii_complemento` (o `_geral` não tem PL).
- Informe mensal pode ter retificação (Versao) - usar a mais recente por CNPJ.
- Taxa de administração dos concorrentes: só existe estruturada na fonte de
  FII (`inf_mensal_fii_complemento`, campo `Percentual_Despesas_Taxa_Administracao`
  - despesa MENSAL reportada, não necessariamente igual à taxa contratual
  anual da ficha XP, usar como proxy). NÃO existe em nenhuma das fontes
  RCVM175 (registro_classe.csv, registro_fundo.csv, registro_subclasse.csv -
  confirmado inspecionando as 3). Por isso essa coluna fica `None` pros
  universos de Alpes Prev (Previdência) e KDIF11 (Renda Fixa) - ausência
  estrutural da fonte pública, documentada em docs/metodologia.md, não
  escondida. Coleta manual/scraper complementar pra esses dois fica na
  camada de aprofundamento (ver docs/log_ia.md).

Como executar
--------------
    python src/ingestion/cvm_download.py
    python src/analysis/build_competitive_universe.py
"""
import argparse
import io
import sys
import zipfile
from pathlib import Path
from typing import Tuple

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.transformation.standardize import clean_cnpj
from src.transformation.enrich_fii_cnpj import CNPJ_FII_KINEA, extrair_ticker

URL_INF_MENSAL_FII = (
    "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_2026.zip"
)
URL_INF_MENSAL_FIAGRO = (
    "https://dados.cvm.gov.br/dados/FIAGRO/DOC/INF_MENSAL/DADOS/inf_mensal_fiagro_202607.zip"
)


def enriquecer_cnpj_fii(df_kinea: pd.DataFrame) -> pd.DataFrame:
    """Preenche o CNPJ dos FIIs/FIAGRO que ainda não têm (ficha XP não expõe
    CNPJ de FII). Usa o mesmo mapa validado de `enrich_fii_cnpj.py` - não
    duplica a fonte da verdade. Idempotente: fundos que já têm CNPJ não são
    tocados."""
    df = df_kinea.copy()
    for idx, row in df.iterrows():
        if pd.notna(row.get("cnpj")):
            continue
        ticker = extrair_ticker(row.get("nome_padronizado", ""), row.get("ticker"))
        if ticker and ticker in CNPJ_FII_KINEA:
            cnpj, _fonte, _obs = CNPJ_FII_KINEA[ticker]
            df.at[idx, "cnpj"] = cnpj
    return df


def carregar_registro_classe_fundo(zip_path: Path) -> pd.DataFrame:
    """Fonte 1 (primária): fundos/classes adaptados à RCVM175."""
    with zipfile.ZipFile(zip_path) as z:
        nomes = z.namelist()
        nome_classe = next(n for n in nomes if "classe" in n.lower() and "sub" not in n.lower())
        nome_fundo = next(n for n in nomes if "fundo" in n.lower() and "classe" not in n.lower())
        with z.open(nome_classe) as f:
            df_classe = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
        with z.open(nome_fundo) as f:
            df_fundo = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
    df_classe.columns = [c.strip() for c in df_classe.columns]
    df_fundo.columns = [c.strip() for c in df_fundo.columns]

    df_classe_ativas = df_classe[
        df_classe["Situacao"].astype(str).str.contains("FUNCIONAMENTO NORMAL", case=False, na=False)
    ].copy()
    df_join = df_classe_ativas.merge(
        df_fundo[["ID_Registro_Fundo", "Gestor"]], on="ID_Registro_Fundo", how="left"
    )
    df_join["cnpj_limpo"] = df_join["CNPJ_Classe"].apply(clean_cnpj)
    return pd.DataFrame({
        "cnpj_limpo": df_join["cnpj_limpo"],
        "nome": df_join["Denominacao_Social"],
        "classe_anbima": df_join["Classificacao_Anbima"],
        "gestor": df_join["Gestor"],
        "patrimonio_liquido": df_join["Patrimonio_Liquido"],
        "publico_alvo": df_join["Publico_Alvo"],
        "taxa_administracao_cvm_mensal_pct": None,  # não existe nesta fonte (ver docstring do módulo)
        "fonte": "CVM registro_classe.csv (RCVM175, fundos adaptados)",
    })


def carregar_cadastro_legado(path: Path) -> pd.DataFrame:
    """Fonte 2 (fallback): cadastro legado, fundos NÃO adaptados à RCVM175."""
    df = pd.read_csv(path, sep=";", encoding="latin-1", low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    col_cnpj = "CNPJ_FUNDO_CLASSE" if "CNPJ_FUNDO_CLASSE" in df.columns else "CNPJ_FUNDO"
    df_ativos = df[df["SIT"].astype(str).str.contains("FUNCIONAMENTO NORMAL", case=False, na=False)].copy()
    df_ativos["cnpj_limpo"] = df_ativos[col_cnpj].apply(clean_cnpj)
    return pd.DataFrame({
        "cnpj_limpo": df_ativos["cnpj_limpo"],
        "nome": df_ativos["DENOM_SOCIAL"],
        "classe_anbima": df_ativos["CLASSE_ANBIMA"],
        "gestor": df_ativos["GESTOR"],
        "patrimonio_liquido": df_ativos["VL_PATRIM_LIQ"],
        "publico_alvo": df_ativos["PUBLICO_ALVO"],
        "taxa_administracao_cvm_mensal_pct": None,  # existe como TAXA_ADM nesta fonte, mas nenhum
        # dos 17 fundos Kinea usa esta fonte pro universo de concorrentes (ver docs/metodologia.md)
        "fonte": "CVM cad_fi.csv (legado, fundos não adaptados)",
    })


def carregar_universo_fii(url: str = URL_INF_MENSAL_FII) -> pd.DataFrame:
    """Fonte 3: FIIs Multicategoria, com PL e taxa (do complemento, não do geral)."""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(resp.content))

    with z.open("inf_mensal_fii_geral_2026.csv") as f:
        df_geral = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
    df_geral.columns = [c.strip() for c in df_geral.columns]
    df_geral["cnpj_limpo"] = df_geral["CNPJ_Fundo_Classe"].apply(clean_cnpj)

    with z.open("inf_mensal_fii_complemento_2026.csv") as f:
        df_compl = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
    df_compl.columns = [c.strip() for c in df_compl.columns]
    df_compl["cnpj_limpo"] = df_compl["CNPJ_Fundo_Classe"].apply(clean_cnpj)
    df_compl_recente = (
        df_compl.dropna(subset=["cnpj_limpo"])
        .sort_values(["cnpj_limpo", "Data_Referencia", "Versao"])
        .drop_duplicates(subset="cnpj_limpo", keep="last")
    )[["cnpj_limpo", "Patrimonio_Liquido"]]

    # Taxa de administração dos FIIs: só existe no Informe Mensal (campo
    # "Percentual_Despesas_Taxa_Administracao", despesa mensal reportada -
    # NÃO existe em nenhuma das fontes RCVM175/legado usadas pros outros
    # 3 universos, então essa coluna fica None pra eles (ausência estrutural
    # da fonte, documentada). É despesa mensal, não necessariamente igual
    # à taxa contratual anual da ficha XP - usar como proxy, com nota de
    # metodologia.
    df_compl_taxa = (
        df_compl.dropna(subset=["cnpj_limpo"])
        .sort_values(["cnpj_limpo", "Data_Referencia", "Versao"])
        .drop_duplicates(subset="cnpj_limpo", keep="last")
    )[["cnpj_limpo", "Percentual_Despesas_Taxa_Administracao"]]

    df_mc = df_geral[df_geral["Segmento_Atuacao"] == "Multicategoria"].drop_duplicates(subset="cnpj_limpo")
    df_mc = df_mc.merge(df_compl_recente, on="cnpj_limpo", how="left")
    df_mc = df_mc.merge(df_compl_taxa, on="cnpj_limpo", how="left")
    return pd.DataFrame({
        "cnpj_limpo": df_mc["cnpj_limpo"],
        "nome": df_mc["Nome_Fundo_Classe"],
        "classe_anbima": "FII - Multicategoria",
        "gestor": None,
        "patrimonio_liquido": df_mc["Patrimonio_Liquido"],
        "publico_alvo": None,  # FII negociado em bolsa, aberto ao público em geral - sem restrição estruturada nesta fonte
        "taxa_administracao_cvm_mensal_pct": df_mc["Percentual_Despesas_Taxa_Administracao"],
        "fonte": "CVM inf_mensal_fii_geral (Segmento_Atuacao) + inf_mensal_fii_complemento (Patrimonio_Liquido, Percentual_Despesas_Taxa_Administracao)",
    })


def carregar_universo_fiagro(url: str = URL_INF_MENSAL_FIAGRO) -> pd.DataFrame:
    """Fonte 4: FIAGRO, com PL."""
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(resp.content))
    nome_csv = next(n for n in z.namelist() if n.endswith(".csv"))
    with z.open(nome_csv) as f:
        df = pd.read_csv(f, sep=";", encoding="latin-1", low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    df["cnpj_limpo"] = df["CNPJ_Classe"].apply(clean_cnpj)
    df_fiagro = df[df["Classificacao_Autorregulada"] == "FIAGRO"].drop_duplicates(subset="cnpj_limpo")
    return pd.DataFrame({
        "cnpj_limpo": df_fiagro["cnpj_limpo"],
        "nome": df_fiagro["Nome_Classe"],
        "classe_anbima": "FIAGRO",
        "gestor": df_fiagro.get("Nome_Gestor"),
        "patrimonio_liquido": df_fiagro.get("Patrimonio_Liquido"),
        "publico_alvo": None,  # não existe estruturado nesta fonte
        "taxa_administracao_cvm_mensal_pct": None,  # não existe nesta fonte
        "fonte": "CVM inf_mensal_fiagro (Classificacao_Autorregulada)",
    })


def montar_universo_competitivo(
    df_kinea: pd.DataFrame, project_root: Path
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Pipeline completo: enriquece CNPJ dos FIIs, carrega as 4 fontes CVM,
    descobre a classe de cada fundo Kinea por CNPJ e monta (resumo,
    concorrentes) para os 17.

    Baixa FII/FIAGRO da internet; lê cadastro/registro de `data/raw/`."""
    raw = project_root / "data" / "raw"
    zip_novo = raw / "cvm_registro_fundo_classe.zip"
    csv_legado = raw / "cvm_cad_fi.csv"

    partes = []
    if zip_novo.exists():
        partes.append(carregar_registro_classe_fundo(zip_novo))
    if csv_legado.exists():
        partes.append(carregar_cadastro_legado(csv_legado))
    if not partes:
        raise FileNotFoundError("Fontes cadastrais CVM ausentes. Rode src/ingestion/cvm_download.py.")
    partes.append(carregar_universo_fii())
    partes.append(carregar_universo_fiagro())
    df_cvm = pd.concat(partes, ignore_index=True)

    # Enriquece o CNPJ dos FIIs ANTES de qualquer join - sem isso eles não
    # têm chave pra cruzar e desaparecem do universo inteiro.
    df_k = enriquecer_cnpj_fii(df_kinea)
    df_k["cnpj_limpo"] = df_k["cnpj"].apply(clean_cnpj)

    # NUNCA fazer merge com CNPJ ausente na chave - separar antes.
    df_k_com_cnpj = df_k[df_k["cnpj_limpo"].notna()].copy()
    df_k_sem_cnpj = df_k[df_k["cnpj_limpo"].isna()].copy()
    df_cvm_com_cnpj = df_cvm[df_cvm["cnpj_limpo"].notna()]

    # Descarta linhas com classe_anbima vazia ANTES de deduplicar por CNPJ.
    # O cadastro legado tem entradas para FII/FIAGRO com classe_anbima em
    # branco (FII não tem classificação ANBIMA tradicional); como o legado
    # entra no concat antes das fontes específicas de FII/FIAGRO,
    # drop_duplicates(keep="first") mantinha essa linha vazia em vez da
    # classe correta vinda de inf_mensal_fii/fiagro. Bug real encontrado ao
    # rodar contra os 17 fundos reais.
    df_cvm_classe_valida = df_cvm_com_cnpj[
        df_cvm_com_cnpj["classe_anbima"].notna()
        & (df_cvm_com_cnpj["classe_anbima"].astype(str).str.strip() != "")
    ]
    join_com_cnpj = df_k_com_cnpj.merge(
        df_cvm_classe_valida[["cnpj_limpo", "classe_anbima"]].drop_duplicates("cnpj_limpo"),
        on="cnpj_limpo", how="left",
    )
    if "classe_anbima" not in df_k_sem_cnpj.columns:
        df_k_sem_cnpj["classe_anbima"] = None
    join = pd.concat([join_com_cnpj, df_k_sem_cnpj], ignore_index=True, sort=False)

    linhas_resumo, todos_concorrentes = [], []
    for _, fundo in join.iterrows():
        classe = fundo.get("classe_anbima")
        if pd.isna(classe) or classe is None:
            linhas_resumo.append({
                "fundo_kinea": fundo["nome_padronizado"],
                "categoria_xp": fundo.get("categoria_padronizada"),
                "classe_anbima_cvm": None,
                "n_universo_inicial": None,
                "observacao": "Sem CNPJ ou sem correspondência em nenhuma fonte CVM - universo não calculado",
            })
            continue

        # Dedup por CNPJ ANTES de contar/montar: um mesmo fundo pode aparecer
        # em mais de uma fonte CVM concatenada em df_cvm (ex: legado E
        # inf_mensal_fiagro ambos com classe_anbima="FIAGRO" pro mesmo CNPJ),
        # o que inflava n_universo_inicial (contagem dupla) mesmo já havendo
        # um drop_duplicates no df_concorrentes final. Bug real encontrado
        # comparando n_universo_inicial do resumo (8) com a contagem real de
        # concorrentes do KNCA11 (5) - mesma causa também inflava o universo
        # de FII-Multicategoria (659 -> 647 reais).
        universo = df_cvm[df_cvm["classe_anbima"] == classe].drop_duplicates(subset="cnpj_limpo")
        n_kinea_na_categoria = universo["nome"].str.lower().str.contains("kinea", na=False).sum()
        linhas_resumo.append({
            "fundo_kinea": fundo["nome_padronizado"],
            "categoria_xp": fundo.get("categoria_padronizada"),
            "classe_anbima_cvm": classe,
            "n_universo_inicial": len(universo),
            "n_concorrentes_diretos": len(universo) - n_kinea_na_categoria,
            "observacao": f"n_universo_inicial = categoria inteira (inclui {n_kinea_na_categoria} fundo(s) "
                          f"da própria Kinea nessa classe); n_concorrentes_diretos = excluindo Kinea, "
                          f"é a base usada nas comparações de Liquidez/custos e Retorno/risco.",
        })
        for _, c in universo.iterrows():
            todos_concorrentes.append({
                "fund_key": f"CNPJ:{c['cnpj_limpo']}",
                "nome": c["nome"],
                "cnpj": c["cnpj_limpo"],
                "gestor": c["gestor"],
                "classe_anbima": c["classe_anbima"],
                "patrimonio_liquido": c["patrimonio_liquido"],
                "publico_alvo": c.get("publico_alvo"),
                "taxa_administracao_cvm_mensal_pct": c.get("taxa_administracao_cvm_mensal_pct"),
                "referencia_fundo_kinea": fundo["nome_padronizado"],
                "eh_fundo_kinea": "kinea" in str(c["nome"]).lower(),
                "source": c["fonte"],
            })

    df_resumo = pd.DataFrame(linhas_resumo)
    df_concorrentes = pd.DataFrame(todos_concorrentes).drop_duplicates(
        subset=["fund_key", "referencia_fundo_kinea"]
    )
    return df_resumo, df_concorrentes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    project_root = Path(args.project_root).resolve()

    df_kinea = pd.read_csv(project_root / "data" / "processed" / "universo_kinea.csv")
    df_resumo, df_concorrentes = montar_universo_competitivo(df_kinea, project_root)

    out_resumo = project_root / "data" / "processed" / "universo_competitivo_resumo.csv"
    out_concorrentes = project_root / "data" / "processed" / "fundos_concorrentes.csv"
    out_resumo.parent.mkdir(parents=True, exist_ok=True)
    df_resumo.to_csv(out_resumo, index=False, encoding="utf-8")
    df_concorrentes.to_csv(out_concorrentes, index=False, encoding="utf-8")

    print(f"Resumo salvo: {out_resumo}")
    print(df_resumo.to_string(index=False))
    print(f"\nConcorrentes salvos: {out_concorrentes} ({len(df_concorrentes)} linhas)")


if __name__ == "__main__":
    main()