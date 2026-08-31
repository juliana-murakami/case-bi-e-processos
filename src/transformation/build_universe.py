"""
build_universe.py

Finalidade
----------
Lê data/raw/universo_kinea_raw.csv (dado bruto, tal como coletado) e
produz data/processed/universo_kinea.csv (dado tratado, tipado, com
chave robusta de identificação e lineage completo).

Aceita duas origens de coleta misturadas no mesmo CSV, cada linha com seu
próprio conjunto de colunas preenchidas (as demais ficam vazias):
- Coleta manual via leitura direta de página (Etapa 1): colunas
  com nomes "_bruto"/"_bruta" (ex: nome_bruto, cnpj_bruto).
- Coleta via scraper (notebook curl_cffi ou xp_fund_scraper.py, Etapa 2):
  colunas com nomes finais (ex: nome_referencia, cnpj, classificacao_xp).
Isso é resolvido com cadeias de fallback (linha.get(A) or linha.get(B)),
não com dois pipelines separados - um único tratamento serve para as duas
origens.

Como executar
--------------
    python src/transformation/build_universe.py \
        --input data/raw/universo_kinea_raw.csv \
        --output data/processed/universo_kinea.csv
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # raiz do projeto
from src.transformation.standardize import (
    clean_cnpj, clean_ticker, clean_name, clean_percentage,
    standardize_category, build_fund_key,
)

# Campos fixos, sempre presentes (independente do tipo de fundo).
OUTPUT_FIELDS = [
    "fund_key", "nome_padronizado", "cnpj", "ticker", "tipo_pagina",
    "categoria_padronizada", "categoria_bruta", "publico_alvo",
    "taxa_administracao_pct", "taxa_performance_pct", "aplicacao_minima_bruta",
    "cotizacao_resgate_bruta", "benchmark", "gestor", "administrador",
    "custodiante", "auditor", "data_inicio", "risco_pontuacao_xp",
    "dividend_yield", "valor_patrimonial_bruto", "quantidade_cotistas_bruto",
    "url", "source", "access_timestamp", "extraction_method",
    "status_confirmacao", "objetivo", "rating_morningstar",
]

# Campos de retorno/risco: os nomes variam por tipo de fundo (fundo aberto
# tem "rentabilidade__12_meses", "volatilidade_atual", etc.; FII tem
# "rentab_fundo__dia", "rentab_benchmark__mês", etc.). Em vez de listar
# cada combinação manualmente (arriscado esquecer alguma), qualquer campo
# que bata com um desses prefixos é levado adiante automaticamente.
PREFIXOS_RETORNO_RISCO = (
    "volatilidade_atual", "drawdown_atual",
    "rentabilidade__", "volatilidade__", "índice_de_sharpe__",
    "rentab_fundo__", "rentab_benchmark__", "benchmark_retorno",
)


def _primeiro_valor(linha: dict, *chaves: str):
    """Retorna o primeiro valor não vazio entre várias chaves possíveis -
    resolve a diferença de nomes de coluna entre as duas origens de coleta."""
    for chave in chaves:
        valor = linha.get(chave)
        if valor not in (None, ""):
            return valor
    return None


def transformar_linha(linha: dict) -> dict:
    nome_bruto = _primeiro_valor(linha, "nome_bruto", "nome_referencia")
    cnpj_bruto = _primeiro_valor(linha, "cnpj_bruto", "cnpj")
    ticker_bruto = _primeiro_valor(linha, "ticker_bruto", "ticker")

    cnpj = clean_cnpj(cnpj_bruto)
    # ticker pode vir explícito OU embutido no nome, ex: "Kinea ... FII (KNRI11)"
    ticker = clean_ticker(ticker_bruto) or clean_ticker(nome_bruto)
    nome = clean_name(nome_bruto)

    # categoria: prioriza o que já vier pronto (coleta manual), senão usa
    # classificação XP (mais específica), senão segmento (FII), senão CVM.
    categoria_bruta = _primeiro_valor(
        linha, "categoria_bruta", "classificacao_xp", "segmento", "classificacao_cvm"
    )

    erro = linha.get("erro")
    status_confirmacao = linha.get("status_confirmacao") or (
        "erro_coleta" if erro not in (None, "") else "ficha_coletada"
    )

    campos_fixos = {
        "fund_key": build_fund_key(cnpj=cnpj, ticker=ticker, nome=nome),
        "nome_padronizado": nome,
        "cnpj": cnpj,
        "ticker": ticker,
        "tipo_pagina": linha.get("tipo_pagina"),
        "categoria_padronizada": standardize_category(categoria_bruta),
        "categoria_bruta": categoria_bruta,
        "publico_alvo": clean_name(_primeiro_valor(linha, "publico_alvo_bruto", "publico_alvo")),
        "taxa_administracao_pct": clean_percentage(
            _primeiro_valor(linha, "taxa_administracao_bruta", "taxa_administracao")
        ),
        "taxa_performance_pct": clean_percentage(
            _primeiro_valor(linha, "taxa_performance_bruta", "taxa_performance")
        ),
        "aplicacao_minima_bruta": _primeiro_valor(linha, "aplicacao_minima_bruta", "aplicacao_minima"),
        "cotizacao_resgate_bruta": _primeiro_valor(linha, "cotizacao_resgate_bruta", "cotizacao_resgate"),
        "benchmark": linha.get("benchmark"),
        "gestor": linha.get("gestor"),
        "administrador": linha.get("administrador"),
        "custodiante": linha.get("custodiante"),
        "auditor": linha.get("auditor"),
        "data_inicio": linha.get("data_inicio"),
        "risco_pontuacao_xp": linha.get("risco_pontuacao_xp"),
        "dividend_yield": linha.get("dividend_yield"),
        "valor_patrimonial_bruto": linha.get("valor_patrimonial"),
        "quantidade_cotistas_bruto": linha.get("quantidade_cotistas"),
        "url": linha.get("url"),
        "source": linha.get("source"),
        "access_timestamp": linha.get("access_timestamp"),
        "extraction_method": linha.get("extraction_method"),
        "status_confirmacao": status_confirmacao,
        "objetivo": linha.get("objetivo"),
        "rating_morningstar": linha.get("rating_morningstar"),
    }

    extras_retorno_risco = {
        chave: valor for chave, valor in linha.items()
        if valor not in (None, "")
        and any(chave == p or chave.startswith(p) for p in PREFIXOS_RETORNO_RISCO)
    }

    return {**campos_fixos, **extras_retorno_risco}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/raw/universo_kinea_raw.csv")
    parser.add_argument("--output", default="data/processed/universo_kinea.csv")
    args = parser.parse_args()

    input_csv = Path(args.input)
    output_csv = Path(args.output)

    with open(input_csv, encoding="utf-8") as f:
        linhas_brutas = list(csv.DictReader(f))

    linhas_tratadas = [transformar_linha(l) for l in linhas_brutas]

    # checagem simples de chave duplicada antes de salvar (join-safety)
    chaves = [l["fund_key"] for l in linhas_tratadas]
    duplicadas = {k for k in chaves if chaves.count(k) > 1}
    if duplicadas:
        print(f"AVISO: fund_key duplicada encontrada: {duplicadas}")

    # Campos de saída: os fixos de sempre + qualquer campo de retorno/risco
    # que tenha aparecido nas linhas tratadas (varia por tipo de fundo -
    # fundo aberto e FII têm conjuntos diferentes, por isso não dá pra
    # fixar numa lista só).
    campos_saida = list(OUTPUT_FIELDS)
    for l in linhas_tratadas:
        for chave in l:
            if chave not in campos_saida:
                campos_saida.append(chave)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos_saida)
        writer.writeheader()
        writer.writerows(linhas_tratadas)

    print(f"{len(linhas_tratadas)} fundo(s) tratado(s). Saída: {output_csv}")
    print(f"Campos no arquivo de saída: {len(campos_saida)}")


if __name__ == "__main__":
    main()