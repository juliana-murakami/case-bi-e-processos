"""
run_sql_queries.py

Finalidade
----------
Carrega data/processed/universo_kinea_completo.csv e
data/processed/fundos_concorrentes.csv num banco DuckDB em memória, aplica
sql/01_schema.sql e executa as consultas de sql/02_universo_kinea_analise.sql,
imprimindo os resultados. Existe para provar que o SQL do projeto roda de
fato contra os dados reais - não é SQL decorativo.

Como executar
--------------
    pip3 install duckdb pandas sqlparse --break-system-packages
    python3 sql/run_sql_queries.py
"""
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _executar_arquivo_sql(con: duckdb.DuckDBPyConnection, path: Path) -> None:
    """Executa um .sql com múltiplos statements. Usa sqlparse se
    disponível (respeita ';' dentro de strings); caso contrário cai para
    split ingênuo - por isso os .sql do projeto evitam ';' dentro de
    valores de texto (ver nota em 03_regras_comparabilidade.sql)."""
    sql_text = path.read_text(encoding="utf-8")
    try:
        import sqlparse
        statements = [s.strip() for s in sqlparse.split(sql_text) if s.strip()]
    except ImportError:
        statements = [s.strip() for s in sql_text.split(";") if s.strip()]
    for stmt in statements:
        if stmt.lstrip().startswith("--"):
            continue
        con.execute(stmt)


def carregar_schema_e_dados(con: duckdb.DuckDBPyConnection) -> None:
    _executar_arquivo_sql(con, ROOT / "sql" / "01_schema.sql")

    df_kinea = pd.read_csv(ROOT / "data" / "processed" / "universo_kinea_completo.csv")
    con.execute("DELETE FROM fundos_kinea")
    con.register("df_kinea", df_kinea)
    con.execute("INSERT INTO fundos_kinea SELECT * FROM df_kinea")

    df_concorrentes = pd.read_csv(ROOT / "data" / "processed" / "fundos_concorrentes.csv")
    con.execute("DELETE FROM fundos_concorrentes")
    con.register("df_concorrentes", df_concorrentes)
    con.execute("INSERT INTO fundos_concorrentes SELECT * FROM df_concorrentes")


def extrair_queries(sql_path: Path) -> list:
    """Remove comentários de linha (--) e separa por ';', descartando
    blocos vazios (ex: queries comentadas em bloco)."""
    conteudo = sql_path.read_text(encoding="utf-8")
    blocos = conteudo.split(";")
    queries = []
    for bloco in blocos:
        linhas_uteis = [l for l in bloco.splitlines() if not l.strip().startswith("--")]
        q = "\n".join(linhas_uteis).strip()
        if q and re.search(r"\bSELECT\b", q, re.IGNORECASE):
            queries.append(q)
    return queries


def main():
    con = duckdb.connect(":memory:")
    carregar_schema_e_dados(con)
    _executar_arquivo_sql(con, ROOT / "sql" / "03_regras_comparabilidade.sql")

    print("=== Regras de comparabilidade cadastradas ===")
    print(con.execute(
        "SELECT categoria_padronizada, criterio_benchmark FROM regras_comparabilidade"
    ).fetchdf().to_string(index=False))

    queries = extrair_queries(ROOT / "sql" / "02_universo_kinea_analise.sql")
    for i, q in enumerate(queries, 1):
        print(f"\n=== Query {i} ===")
        print(con.execute(q).fetchdf().to_string(index=False))


if __name__ == "__main__":
    main()
