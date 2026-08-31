# Case Kinea BI — Inteligência Competitiva na Prateleira XP

Projeto de Business Intelligence para o processo seletivo Kinea: mapeamento dos fundos Kinea na prateleira pública da XP, comparação com o universo competitivo e recomendações comerciais para os próximos 90 dias.

## Status atual
🔵 **Etapa 2 em andamento** — universo Kinea identificado (13 fundos, ficha completa em 2 deles); universo competitivo ainda não populado. Ver `docs/metodologia.md` para detalhes e limitações.

## Objetivo
Responder: *na prateleira pública da XP, em quais dimensões os fundos Kinea estão bem posicionados, em desvantagem ou mal comunicados — e quais ações Comercial/Marketing deveriam priorizar nos próximos 90 dias?*

## Estrutura do projeto
```
case-kinea-bi/
├── README.md                    # este arquivo
├── requirements.txt
├── .gitignore
├── config/
│   └── kinea_fund_urls.csv      # lista de URLs a coletar (editável, sem hardcode no scraper)
├── data/
│   ├── raw/                     # dado bruto, tal como coletado (+ HTML salvo por src/ingestion)
│   ├── staging/                 # (reservado para tratamento intermediário futuro)
│   └── processed/               # base tratada + relatórios de qualidade
├── src/
│   ├── ingestion/
│   │   └── xp_fund_scraper.py   # coleta ficha de fundo individual (requests + BeautifulSoup)
│   ├── transformation/
│   │   ├── standardize.py       # funções de limpeza/padronização + chave robusta
│   │   └── build_universe.py    # raw -> processed
│   ├── quality/
│   │   └── validate_universe.py # checagens de qualidade + relatório
│   └── analysis/                # (reservado para Etapa 2b/3)
├── sql/
│   ├── 01_schema.sql
│   ├── 02_universo_kinea_analise.sql
│   ├── 03_regras_comparabilidade.sql
│   └── run_sql_queries.py       # executa o SQL de fato, contra os dados reais (DuckDB)
├── notebooks/                   # (reservado)
├── dashboard/                   # (reservado — Streamlit, etapa posterior)
├── docs/
│   ├── metodologia.md
│   ├── dicionario_dados.md
│   ├── fontes.md
│   └── log_ia.md
└── prompts/                     # (reservado — registro de prompts relevantes)
```

**Por que essa estrutura:** `raw/staging/processed` separa dado bruto (auditável) de dado tratado (consumível), seguindo o padrão comum de pipelines de dados. `src/` é dividido por responsabilidade (ingestion → transformation → quality → analysis) para que cada etapa possa ser testada e rodada isoladamente — importante para o teste ao vivo, onde pode ser pedido para alterar só uma parte do pipeline sem reescrever tudo. `sql/` fica no nível raiz (não dentro de `src/`) porque o case pede explicitamente uma camada SQL visível e avaliável separadamente.

## Notebooks vs. scripts .py
O projeto tem notebooks (para rodar interativamente, célula a célula) e scripts `.py` equivalentes (mesma lógica, para reprodutibilidade/automação sem precisar abrir notebook). Cada notebook cobre uma fonte de dado / responsabilidade:

| Notebook | Camada do case | Fonte |
|---|---|---|
| `notebooks/coleta_fundos_kinea.ipynb` | Visão completa (parte 1) — mapear fundos Kinea | XP (`conteudos.xpi.com.br`) |
| `notebooks/universo_competitivo.ipynb` | Visão completa (parte 2) — mapear universos competitivos | CVM (`dados.cvm.gov.br`) |

## Como executar

```bash
pip install -r requirements.txt

# 1) (Opcional) Completar a coleta dos fundos Kinea pendentes na XP
python src/ingestion/xp_fund_scraper.py --only-pending --debug
# (ou usar notebooks/coleta_fundos_kinea.ipynb, célula a célula)

# 2) Tratar/padronizar o dado bruto -> base processada
python src/transformation/build_universe.py

# 3) Rodar checagens de qualidade
python src/quality/validate_universe.py

# 4) Baixar o cadastro completo de fundos da CVM (universo competitivo)
python src/ingestion/cvm_download.py

# 5) Descobrir a classe ANBIMA real de cada fundo Kinea e montar o
#    universo competitivo (todos os concorrentes por categoria)
python src/analysis/build_competitive_universe.py

# 6) Rodar as consultas SQL contra os dados reais
python sql/run_sql_queries.py
```

Todos os caminhos são relativos à raiz do projeto (sem caminho absoluto). Todos os parâmetros importantes (arquivo de entrada, saída, filtro `--only-pending`) são configuráveis via linha de comando — pensado para o teste ao vivo (trocar fonte, refazer consulta, adicionar fundo).

## Dependências
Ver `requirements.txt`. Principais: `requests`, `beautifulsoup4`, `pandas`, `duckdb`, `sqlparse`.

## Fluxo de arquivos brutos (importante para não duplicar dados)
- `data/raw/universo_kinea_raw_manual_original.csv` — os 2 fundos coletados manualmente na Etapa 1 (fonte fixa, não sobrescrever).
- `data/raw/universo_kinea_raw_scraped.csv` — os demais fundos coletados pelo `notebooks/coleta_fundos_kinea.ipynb` (regenerado a cada execução do notebook).
- `data/raw/universo_kinea_raw.csv` — os dois acima **combinados** (arquivo derivado; a última célula do notebook o recria do zero a cada execução — não editar à mão, não faz sentido rodar a célula de merge mais de uma vez sobre o resultado dela mesma).

## Fontes
Ver `docs/fontes.md` para a tabela completa (URL, data de acesso, uso). Resumo: Expert XP (`conteudos.xpi.com.br`) como fonte primária das fichas de fundo; CVM Dados Abertos planejado como fonte do universo competitivo completo (Etapa 2b/3).

## Limitações conhecidas (ver `docs/metodologia.md` para detalhes)
- Lista de fundos Kinea obtida via busca — validação final requer navegação manual controlada da vitrine XP (`xpi.com.br/investimentos/fundos-de-investimento/lista/`), que é client-side e não tem forma pública/reproduzível de acesso sem JS conhecida até o momento.
- 11 dos 13 fundos identificados ainda não têm ficha completa extraída (scraper pronto, pendente de execução em ambiente com rede).
- Universo competitivo: regra definida (`sql/03_regras_comparabilidade.sql`), mas ainda não populado com concorrentes reais.

## Sobre dados grandes / não versionados
`data/raw/html/` (HTML bruto salvo pelo scraper) pode crescer bastante — está no `.gitignore`. Se for necessário versionar para reprodutibilidade total, considerar Git LFS ou compactar em `.zip` e documentar o hash/data da coleta no commit.

## Uso de IA
Ver `docs/log_ia.md`.

---

## Como reproduzir do zero

Ordem de execução (Python 3.9, `/usr/bin/python3`):

```bash
# 1. Coleta dos fundos Kinea na XP (gera data/raw/ e data/processed/universo_kinea.csv)
#    -> rode o notebook notebooks/coleta_fundos_kinea.ipynb de cima a baixo

# 2. Baixar as bases cadastrais da CVM
python src/ingestion/cvm_download.py

# 3. Universo competitivo + PL comparável dos 17 fundos
#    -> rode o notebook notebooks/universo_competitivo.ipynb de cima a baixo
#    (ou, por linha de comando, só o universo competitivo:)
python src/analysis/build_competitive_universe.py --project-root .
```

### Saídas em `data/processed/`
| Arquivo | Conteúdo |
|---|---|
| `universo_kinea.csv` | Ficha bruta dos 17 fundos Kinea (coleta XP) |
| `universo_kinea_completo.csv` | Os 17 + PL (CVM) + percentil na categoria |
| `fundos_concorrentes.csv` | Concorrentes por fundo Kinea, com PL |
| `universo_competitivo_resumo.csv` | 1 linha por fundo Kinea: classe + tamanho do universo |

### Organização
- `data/raw/` — dados brutos (coleta manual, scraping, downloads CVM)
- `data/processed/` — saídas tratadas; **cada arquivo é sempre a versão atual** (sem sufixos `_v2`/`_atualizado`)
- `src/` — lógica reutilizável (fonte de verdade); notebooks só orquestram
- `docs/` — governança: metodologia, fontes, dicionário de dados, log de IA
