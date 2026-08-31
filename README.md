# Case BI Kinea — Inteligência Competitiva na Prateleira XP

**Candidata:** Juliana Manso Murakami
**Processo seletivo:** Business Intelligence — Kinea Investimentos

## O case

Como os 17 fundos públicos da Kinea estão posicionados na prateleira pública da XP, em 4 dimensões — **Produto**, **Liquidez e custos**, **Retorno e risco** e **Conteúdo e diferenciação** — e quais ações de Comercial/Marketing priorizar nos próximos 90 dias?

XP tratada simultaneamente como **cliente** (canal a otimizar) e **distribuidora** (concorrência aparece na mesma prateleira).

## Resultado em uma frase

Dos 68 pares fundo × dimensão avaliados, **39 estão bem posicionados (57%)**, **17 em desvantagem** (concentrados em taxa de administração acima da mediana dos concorrentes diretos), **5 mal comunicados** (a ficha pública não reflete um resultado real que o fundo já tem) e **7 em limitação de categoria/plataforma** (nem Kinea nem concorrente têm o dado — não conta como desvantagem competitiva).

Três fundos foram priorizados para aprofundamento por combinarem maior desvio numérico com maior ambiguidade sobre a causa: **KNIP11** (maior desvio negativo de retorno do portfólio, exige investigação antes de qualquer ação comercial), **KDIF11** (retorno 5,75 p.p. acima da mediana dos pares, mas ficha pública quebrada — tabela de rentabilidade zerada), **KNHY11** (taxa 63% acima da mediana, mas retorno mais resiliente que os pares — taxa fácil de justificar, falta comunicar isso).

## Estrutura do repositório

```
├── app.py                        # Dashboard Streamlit (5 abas)
├── requirements.txt
├── notebooks/
│   ├── coleta_fundos_kinea.ipynb       # Etapa 1-2: coleta dos 17 fundos Kinea na XP
│   ├── universo_competitivo.ipynb      # Etapa 2b-6: universo competitivo via CVM
│   └── aprofundamento_3_fundos.ipynb   # Etapa 7: aprofundamento KNIP11/KDIF11/KNHY11
├── src/
│   ├── transformation/
│   │   ├── build_universe.py           # raw → processed (universo Kinea)
│   │   ├── build_competitive_universe.py  # universo competitivo via 4 fontes CVM
│   │   ├── enrich_fii_cnpj.py          # CNPJ dos 7 FIIs (ausente na ficha XP)
│   │   ├── standardize.py              # normalização, build_fund_key
│   │   └── patrimonio_liquido.py       # PL comparável dos 17 fundos
│   ├── quality/
│   │   └── validate_universe.py        # checagens de qualidade, não corrige sozinho
│   └── collection/
│       ├── xp_fund_scraper.py          # scraper (curl_cffi, impersonate=chrome)
│       └── cvm_download.py             # download CVM Dados Abertos
├── sql/
│   ├── 01_schema.sql
│   ├── 02_universo_kinea_analise.sql
│   ├── 03_regras_comparabilidade.sql   # regras de comparabilidade por categoria
│   └── run_sql_queries.py              # roda o SQL contra os dados reais via DuckDB
├── data/
│   ├── raw/                            # dado bruto, como coletado (html + csv)
│   └── processed/                      # dado tratado — sem sufixo de versão, sempre o atual
└── docs/
    ├── metodologia.md                  # definições, regras de comparabilidade, limitações
    ├── dicionario_dados.md             # schema de cada CSV
    ├── fontes.md                       # log de fontes com URL e data de acesso
    ├── log_ia.md                       # uso de IA — diagnóstico vs. decisão da candidata
    └── memo_executivo.docx             # memo executivo (2 páginas)
```

## Como rodar

```bash
pip install -r requirements.txt --break-system-packages

# Pipeline — ordem obrigatória (cada etapa depende da anterior)
python src/transformation/build_universe.py \
    --input data/raw/universo_kinea_raw.csv \
    --output data/processed/universo_kinea.csv

python src/transformation/enrich_fii_cnpj.py
python src/quality/validate_universe.py \
    --input data/processed/universo_kinea.csv \
    --output data/processed/quality_report_universo_kinea.md

python src/transformation/build_competitive_universe.py

# SQL contra os dados reais (prova de que não é SQL decorativo)
python sql/run_sql_queries.py

# Dashboard
streamlit run app.py
```

Nenhum número no dashboard, no memo ou nos slides é hardcoded — tudo é recalculado a partir de `data/raw/` a cada execução do pipeline.

## Os 5 entregáveis

| Entregável | Onde está |
|---|---|
| Memo executivo (2 páginas) | `docs/memo_executivo.docx` |
| Apresentação (10 slides) | enviada em anexo separado |
| Dashboard navegável | `app.py` (Streamlit) |
| Repositório reprodutível | este repositório |
| Governança (dicionário, fontes, log de IA) | `docs/dicionario_dados.md`, `docs/fontes.md`, `docs/log_ia.md` |

## Metodologia — pontos-chave

- **Concorrência agrupada por similaridade real de estratégia**, não por classe ANBIMA/CVM genérica (ex.: KDIF11 compete com fundos de debênture incentivada de infraestrutura, não com todo o universo "Renda Fixa Duração Livre Crédito Livre" de ~3.146 fundos).
- **Regras de classificação do scorecard:** desvantagem em Liquidez/custos a partir de +30% acima da mediana; em Retorno/risco a partir de -2 p.p. abaixo da mediana (maior tolerância, reflete variância natural de retorno). "Mal comunicado" só quando há assimetria real (concorrente tem o dado, Kinea não) — quando os dois lados não têm, é "limitação de categoria/plataforma".
- **Hierarquia de chave de fundo:** CNPJ > ticker > nome padronizado. Nunca join só por nome.
- **robots.txt:** `conteudos.xpi.com.br` é scrapeável (só restringe `/wp-admin/` e `.pdf`); `maisretorno.com` bloqueia acesso automatizado — usado só como referência manual, nunca raspado.

Detalhes completos, incluindo limitações conhecidas (vitrine comercial da XP sem endpoint público reproduzível, fundos de colocação privada sem ficha pública) em `docs/metodologia.md`.

## Uso de IA

Todo apoio de IA (Claude), modelo Sonnet 5, está documentado em `docs/log_ia.md`, em primeira pessoa, separando o que foi diagnosticado pela IA do que foi decidido, executado e validado pela candidata em meu próprio ambiente.
