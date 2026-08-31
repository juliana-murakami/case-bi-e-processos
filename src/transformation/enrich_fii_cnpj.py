"""
enrich_fii_cnpj.py

Finalidade
----------
A ficha pública de FII na XP não expõe CNPJ (limitação estrutural do
template, documentada em docs/metodologia.md). Isso impedia cruzar os 7
FIIs Kinea com a CVM para descobrir o universo competitivo.

Este script preenche o CNPJ desses 7 fundos em data/processed/universo_kinea.csv,
usando uma fonte diferente: o CNPJ foi encontrado cruzando o NOME do fundo
(não o ticker) dentro de registro_fundo.csv da CVM (filtrando
Denominacao_Social contendo "KINEA" e Tipo_Fundo em ["FII","FIAGRO"]),
com confirmação cruzada em fontes de mercado (Investidor10, StatusInvest,
PDF oficial Kinea) para o caso do KDIF11 especificamente.

IMPORTANTE - divergência documentada
--------------------------------------
KDIF11 (CNPJ 26.324.298/0001-89) aparece com Situacao="Cancelado" no
registro_fundo.csv da CVM, mas negocia normalmente na B3 segundo múltiplas
fontes de mercado independentes. Não investigamos a causa dessa
divergência (pode ser reestruturação societária não refletida no cadastro,
ou um registro anterior sobreposto por um mais recente não capturado).
Documentado aqui e em docs/fontes.md - não escondido.

Como executar
--------------
    python src/transformation/enrich_fii_cnpj.py
"""
import argparse
from pathlib import Path

import pandas as pd

# ticker -> (CNPJ, fonte, observação)
CNPJ_FII_KINEA = {
    "KNCR11": ("16.706.958/0001-32", "CVM registro_fundo.csv (cruzado por nome)", "Em Funcionamento Normal"),
    "KNRI11": ("12.005.956/0001-65", "CVM registro_fundo.csv (cruzado por nome)", "Em Funcionamento Normal"),
    "KNIP11": ("24.960.430/0001-13", "CVM registro_fundo.csv (cruzado por nome)", "Em Funcionamento Normal"),
    "KNHY11": ("30.130.708/0001-28", "CVM registro_fundo.csv (cruzado por nome)", "Em Funcionamento Normal"),
    "KFOF11": ("30.091.444/0001-40", "CVM registro_fundo.csv (cruzado por nome)", "Em Funcionamento Normal"),
    "KNCA11": ("41.745.701/0001-37", "CVM registro_fundo.csv (cruzado por nome, Tipo_Fundo=FIAGRO)", "Em Funcionamento Normal"),
    "KDIF11": ("26.324.298/0001-89", "CVM registro_fundo.csv + confirmado em fontes de mercado (Investidor10, StatusInvest, PDF oficial Kinea)", "DIVERGENTE: CVM mostra Cancelado, mercado mostra ativo - ver docs/metodologia.md"),
}


def extrair_ticker(nome: str, ticker_coluna=None):
    if ticker_coluna and str(ticker_coluna) in CNPJ_FII_KINEA:
        return str(ticker_coluna)
    for ticker in CNPJ_FII_KINEA:
        if ticker in str(nome):
            return ticker
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/processed/universo_kinea.csv")
    parser.add_argument("--output", default="data/processed/universo_kinea.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df["ticker_extraido"] = df.apply(
        lambda row: extrair_ticker(row["nome_padronizado"], row.get("ticker")), axis=1
    )

    atualizados = 0
    for idx, row in df.iterrows():
        ticker = row["ticker_extraido"]
        if ticker and ticker in CNPJ_FII_KINEA and pd.isna(row.get("cnpj")):
            cnpj, fonte, obs = CNPJ_FII_KINEA[ticker]
            df.at[idx, "cnpj"] = cnpj
            df.at[idx, "fund_key"] = f"CNPJ:{cnpj}"  # chave robusta agora pode usar CNPJ, não só ticker
            print(f"{ticker}: CNPJ preenchido ({cnpj}) - {obs}")
            atualizados += 1

    df = df.drop(columns=["ticker_extraido"])
    df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"\n{atualizados} FII(s) enriquecido(s) com CNPJ. Salvo em: {args.output}")


if __name__ == "__main__":
    main()
