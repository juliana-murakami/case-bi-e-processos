"""
validate_universe.py

Finalidade
----------
Roda checagens de qualidade sobre data/processed/universo_kinea.csv e
produz um relatório em Markdown. Não corrige os dados automaticamente -
reporta para decisão humana (conforme princípio do projeto de não
esconder inconsistências).

Como executar
--------------
    python src/quality/validate_universe.py \
        --input data/processed/universo_kinea.csv \
        --output data/processed/quality_report_universo_kinea.md
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.transformation.standardize import is_valid_cnpj_format

CATEGORIAS_ESPERADAS = {
    "Multimercado", "Multimercado - Macro", "Renda Fixa", "Ações",
    "Previdência", "Fundo Imobiliário (FII)", "FIAGRO", "FI-Infra",
    "Private Equity (FIP)",
}


def carregar(input_csv: Path) -> list:
    with open(input_csv, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def checar_duplicidade_chave(linhas: list) -> list:
    chaves = [l["fund_key"] for l in linhas]
    contagem = Counter(chaves)
    return [k for k, n in contagem.items() if n > 1]


def checar_duplicidade_nome(linhas: list) -> list:
    nomes = [l["nome_padronizado"] for l in linhas]
    contagem = Counter(nomes)
    return [n for n, c in contagem.items() if c > 1]


def checar_cnpj_invalido(linhas: list) -> list:
    return [
        l["nome_padronizado"] for l in linhas
        if l.get("cnpj") and not is_valid_cnpj_format(l["cnpj"])
    ]


def checar_sem_categoria(linhas: list) -> list:
    return [l["nome_padronizado"] for l in linhas if not l.get("categoria_padronizada")]


def checar_sem_url(linhas: list) -> list:
    return [l["nome_padronizado"] for l in linhas if not l.get("url")]


def checar_categoria_inesperada(linhas: list) -> list:
    """Sinaliza categorias que não caíram em nenhum vocabulário controlado
    exato - não é necessariamente erro (pode ser categoria nova e válida),
    mas exige revisão humana antes de entrar em groupby/análise."""
    inesperadas = []
    for l in linhas:
        cat = l.get("categoria_padronizada") or ""
        if cat and not any(cat.startswith(esperada) for esperada in CATEGORIAS_ESPERADAS):
            inesperadas.append((l["nome_padronizado"], cat))
    return inesperadas


def checar_campos_pendentes(linhas: list) -> list:
    return [
        l["nome_padronizado"] for l in linhas
        if l.get("status_confirmacao") == "identificado_pendente"
    ]


def checar_cnpj_ausente_fii(linhas: list) -> list:
    """FIIs não expõem CNPJ na ficha pública da XP (limitação estrutural
    documentada em docs/metodologia.md) - sinaliza para lembrar que precisa
    de fonte complementar (CVM/B3) se o CNPJ for necessário adiante."""
    return [
        l["nome_padronizado"] for l in linhas
        if l.get("tipo_pagina") == "fii" and not l.get("cnpj")
    ]


def gerar_relatorio(linhas: list) -> str:
    total = len(linhas)
    dup_chave = checar_duplicidade_chave(linhas)
    dup_nome = checar_duplicidade_nome(linhas)
    cnpj_invalido = checar_cnpj_invalido(linhas)
    sem_categoria = checar_sem_categoria(linhas)
    sem_url = checar_sem_url(linhas)
    cat_inesperada = checar_categoria_inesperada(linhas)
    pendentes = checar_campos_pendentes(linhas)
    fii_sem_cnpj = checar_cnpj_ausente_fii(linhas)

    linhas_md = [
        "# Relatório de Qualidade — Universo Kinea",
        "",
        f"Total de fundos na base: **{total}**",
        "",
        "| Checagem | Resultado |",
        "|---|---|",
        f"| Chaves (`fund_key`) duplicadas | {len(dup_chave)} {'⚠️' if dup_chave else '✅'} |",
        f"| Nomes padronizados duplicados | {len(dup_nome)} {'⚠️' if dup_nome else '✅'} |",
        f"| CNPJ em formato inválido | {len(cnpj_invalido)} {'⚠️' if cnpj_invalido else '✅'} |",
        f"| Fundos sem categoria | {len(sem_categoria)} {'⚠️' if sem_categoria else '✅'} |",
        f"| Fundos sem URL de origem | {len(sem_url)} {'⚠️' if sem_url else '✅'} |",
        f"| Categorias fora do vocabulário controlado | {len(cat_inesperada)} {'ℹ️' if cat_inesperada else '✅'} |",
        f"| Fundos com coleta pendente (ficha incompleta) | {len(pendentes)} {'ℹ️' if pendentes else '✅'} |",
        f"| FIIs sem CNPJ (limitação estrutural da ficha XP) | {len(fii_sem_cnpj)} {'ℹ️' if fii_sem_cnpj else '✅'} |",
        "",
    ]

    if dup_chave:
        linhas_md += ["## Chaves duplicadas", *[f"- {k}" for k in dup_chave], ""]
    if cnpj_invalido:
        linhas_md += ["## CNPJ inválido", *[f"- {n}" for n in cnpj_invalido], ""]
    if sem_categoria:
        linhas_md += ["## Sem categoria", *[f"- {n}" for n in sem_categoria], ""]
    if cat_inesperada:
        linhas_md += ["## Categorias fora do vocabulário controlado (revisar)",
                       *[f"- {n}: `{c}`" for n, c in cat_inesperada], ""]
    if pendentes:
        linhas_md += ["## Fundos com ficha pendente (executar scraper local)",
                       *[f"- {n}" for n in pendentes], ""]
    if fii_sem_cnpj:
        linhas_md += ["## FIIs sem CNPJ na ficha pública (buscar em CVM/B3 se necessário)",
                       *[f"- {n}" for n in fii_sem_cnpj], ""]

    return "\n".join(linhas_md)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/processed/universo_kinea.csv")
    parser.add_argument("--output", default="data/processed/quality_report_universo_kinea.md")
    args = parser.parse_args()

    linhas = carregar(Path(args.input))
    relatorio = gerar_relatorio(linhas)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(relatorio, encoding="utf-8")

    print(relatorio)
    print(f"\nRelatório salvo em: {output_path}")


if __name__ == "__main__":
    main()
