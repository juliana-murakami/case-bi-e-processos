-- 01_schema.sql
-- Finalidade: criar as tabelas base do projeto (compatível com SQLite/DuckDB).
-- fundos_kinea é carregada a partir de data/processed/universo_kinea_completo.csv
-- (universo Kinea enriquecido: PL/percentil via CVM + retorno/risco via XP).
-- fundos_concorrentes é carregada a partir de data/processed/fundos_concorrentes.csv
-- (universo competitivo já fechado, join por CNPJ contra CVM Dados Abertos).


-- NOTA (30/08/2026): schema alinhado às 34 colunas REAIS de
-- data/processed/universo_kinea_completo.csv na entrega final. Uma versão
-- anterior deste arquivo tinha ~66 colunas (campos de retorno/risco por
-- tipo de página, objetivo, rating_morningstar) que build_universe.py é
-- capaz de gerar dinamicamente mas que não estão presentes no CSV
-- efetivamente commitado - isso fazia `INSERT INTO fundos_kinea SELECT *
-- FROM df_kinea` falhar (66 colunas no schema vs. 34 no dado real). Se o
-- pipeline for re-rodado do zero e o CSV final passar a ter mais colunas,
-- este schema precisa ser atualizado de novo para bater 1:1.
DROP TABLE IF EXISTS fundos_kinea;
CREATE TABLE fundos_kinea (
    fund_key                            TEXT PRIMARY KEY,  -- CNPJ:xxx | TICKER:xxx | NOME:xxx
    nome_padronizado                    TEXT NOT NULL,
    cnpj                                TEXT,
    ticker                              TEXT,
    tipo_pagina                         TEXT NOT NULL,      -- fundo_aberto | fii | previdencia
    categoria_padronizada               TEXT,
    categoria_bruta                     TEXT,
    publico_alvo                        TEXT,
    taxa_administracao_pct              REAL,
    taxa_performance_pct                REAL,
    aplicacao_minima_bruta              TEXT,
    cotizacao_resgate_bruta             TEXT,
    benchmark                           TEXT,
    gestor                              TEXT,
    administrador                       TEXT,
    custodiante                         TEXT,
    auditor                             TEXT,
    data_inicio                         TEXT,
    risco_pontuacao_xp                  REAL,
    dividend_yield                      TEXT,
    valor_patrimonial_bruto             TEXT,
    quantidade_cotistas_bruto           TEXT,
    url                                 TEXT NOT NULL,
    source                              TEXT NOT NULL,
    access_timestamp                    TEXT NOT NULL,
    extraction_method                   TEXT NOT NULL,
    status_confirmacao                  TEXT NOT NULL,
    -- Enriquecimento CVM (PL comparável e percentil dentro da categoria)
    status_pl                           TEXT,
    patrimonio_liquido_cvm              REAL,
    fonte_pl                            TEXT,
    classe_anbima_cvm                   TEXT,
    n_concorrentes_com_pl               INTEGER,
    percentil_pl                        REAL,
    pl_sobre_mediana_universo           REAL
);

-- Universo de concorrentes (populado, join por CNPJ contra CVM Dados Abertos).
-- 9 colunas - bate 1:1 com data/processed/fundos_concorrentes.csv real.
DROP TABLE IF EXISTS fundos_concorrentes;
CREATE TABLE fundos_concorrentes (
    fund_key                            TEXT,       -- não é PK: um fundo pode aparecer
                                                      -- mais de uma vez (casado contra
                                                      -- mais de uma referência Kinea antes
                                                      -- da deduplicação por classe)
    nome                                 TEXT NOT NULL,
    cnpj                                 TEXT,
    gestor                               TEXT,
    classe_anbima                        TEXT,
    patrimonio_liquido                   REAL,
    referencia_fundo_kinea               TEXT,       -- nome_padronizado do fundo Kinea
                                                      -- ao qual este concorrente foi
                                                      -- associado (join por categoria)
    eh_fundo_kinea                       BOOLEAN NOT NULL,  -- TRUE = é o próprio fundo
                                                      -- Kinea aparecendo dentro do seu
                                                      -- próprio universo; filtrar FALSE
                                                      -- para comparar só contra concorrentes
    source                               TEXT NOT NULL
);

-- Regras de comparabilidade aplicadas por categoria (documentadas, não
-- escondidas dentro do código - ver também docs/metodologia.md).
-- Sem mudança nesta revisão - não depende de colunas de fundo específicas.
DROP TABLE IF EXISTS regras_comparabilidade;
CREATE TABLE regras_comparabilidade (
    categoria_padronizada     TEXT PRIMARY KEY,
    criterio_estrategia       TEXT,
    criterio_publico_alvo     TEXT,
    criterio_liquidez         TEXT,
    criterio_tipo_ativo       TEXT,
    criterio_nivel_risco      TEXT,
    criterio_benchmark        TEXT,
    justificativa             TEXT
);