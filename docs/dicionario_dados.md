# Dicionário de Dados — `data/processed/universo_kinea.csv`

| Campo | Definição | Tipo | Fonte | Tratamento |
|---|---|---|---|---|
| `fund_key` | Chave robusta de identificação: `CNPJ:xxx` (prioridade 1) → `TICKER:xxx` (prioridade 2) → `NOME:xxx` (fallback) | string | Derivado | `standardize.build_fund_key()` |
| `nome_padronizado` | Nome do fundo, espaços normalizados, acentuação NFC | string | Ficha XP | `standardize.clean_name()` |
| `cnpj` | CNPJ no formato XX.XXX.XXX/XXXX-XX, ou vazio se ausente/inválido | string | Ficha XP (fundo aberto) | `standardize.clean_cnpj()` |
| `ticker` | Código de negociação B3 (ex. KNCR11), quando aplicável | string | Ficha XP / nome do fundo | `standardize.clean_ticker()` |
| `tipo_pagina` | `fundo_aberto` \| `fii` \| `previdencia` — determina qual template de ficha foi usado na coleta | string | Classificação manual na coleta | — |
| `categoria_padronizada` | Categoria mapeada para vocabulário controlado (`standardize.CATEGORY_VOCAB`); preserva texto original se não houver correspondência exata | string | Derivado de `categoria_bruta` | `standardize.standardize_category()` |
| `categoria_bruta` | Categoria/classificação exatamente como aparece na fonte (XP e/ou CVM) | string | Ficha XP | Nenhum (preservado como coletado) |
| `publico_alvo` | Público-alvo declarado (ex. "Investidor em Geral", "Não Há Restrição") | string | Ficha XP | `standardize.clean_name()` |
| `taxa_administracao_pct` | Taxa de administração ao ano, em pontos percentuais (1.50 = 1,50%) | float | Ficha XP | `standardize.clean_percentage()` |
| `taxa_performance_pct` | Taxa de performance, em pontos percentuais | float | Ficha XP (só fundo aberto) | `standardize.clean_percentage()` |
| `aplicacao_minima_bruta` | Valor mínimo de aplicação, como texto (ex. "R$ 500") — não convertido a float nesta etapa | string | Ficha XP (só fundo aberto) | Nenhum |
| `cotizacao_resgate_bruta` | Prazo de cotização de resgate, como texto (ex. "D+0 (Dias Úteis)") | string | Ficha XP (só fundo aberto) | Nenhum |
| `url` | URL de origem do dado | string | — | — |
| `source` | Nome da fonte (ex. "conteudos.xpi.com.br (Expert XP)") | string | — | — |
| `access_timestamp` | Data/hora UTC da coleta (ISO 8601) | string | — | — |
| `extraction_method` | Como o dado foi obtido: `leitura_direta_pagina` (coleta manual assistida por IA, 2 fundos da Etapa 1 — ver docs/log_ia.md) \| `curl_cffi_notebook_local` (scraper automatizado, 15 fundos) \| `web_search_snippet` (identificado via busca, ficha ainda não extraída) | string | — | — |
| `status_confirmacao` | `ficha_coletada` (todos os campos relevantes extraídos) \| `identificado_pendente` (fundo confirmado, ficha ainda não detalhada) | string | — | — |


## `universo_kinea_completo.csv`

Todas as colunas de `universo_kinea.csv` (ficha bruta da XP), mais:

| Campo | Descrição |
|---|---|
| `status_pl` | `encontrado` / `nao_encontrado` / `ambiguo`. |
| `patrimonio_liquido_cvm` | PL do fundo, em R$, da CVM. Fundos abertos/previdência/FIAGRO: nível de fundo. FIIs: `Patrimonio_Liquido` do Informe Mensal Complemento, competência 2026-07. |
| `fonte_pl` | Qual arquivo CVM originou o PL. |
| `classe_anbima_cvm` | Classe/segmento usado como universo de comparação. |
| `n_concorrentes_com_pl` | Tamanho do universo de comparação (concorrentes não-Kinea com PL na classe). |
| `percentil_pl` | Percentil do PL do fundo Kinea no universo (0–100). |
| `pl_sobre_mediana_universo` | PL do fundo Kinea / mediana de PL do universo. |

**Limitação:** PL dos 10 fundos abertos/previdência é a nível de FUNDO (join por `ID_Registro_Fundo`), não de subclasse; sem data-base explícita nessa fonte. FIIs e FIAGRO têm `Data_Referencia` (2026-07).

**Validação cruzada:** para os 4 FIIs com PL na ficha XP (KNRI11, KNIP11, KFOF11, KNHY11), o PL via CVM bateu com diferença ≤2%.

## `scorecard_posicionamento.csv`

Matriz de 17 fundos × 4 dimensões do case (`aba Scorecard`).

| Campo | Definição | Tipo |
|---|---|---|
| `nome_padronizado` | Nome do fundo | string |
| `categoria_padronizada` | Categoria (vocabulário controlado) | string |
| `status_liquidez` | `bem posicionado` \| `desvantagem` \| `mal comunicado` \| `limitação de categoria/plataforma` | string |
| `status_retorno` | Idem, para Retorno e risco | string |
| `status_produto` | Idem, para Produto | string |
| `status_conteudo` | Idem, para Conteúdo e diferenciação | string |
| `n_bem_posicionado` | Contagem de dimensões "bem posicionado" (0–4) | int |
| `n_desvantagem` | Contagem de dimensões "desvantagem" (0–4) | int |
| `n_mal_comunicado` | Contagem de dimensões "mal comunicado" (0–4) | int |

Critérios de classificação: ver `metodologia.md`.

## `dimensao_liquidez_custos.csv` / `dimensao_retorno_risco_17.csv`

Detalhe por fundo (17 fundos, exceto os 3 aprofundados que usam arquivo próprio) que sustenta o `status_liquidez` / `status_retorno` do scorecard. Concorrentes agrupados por similaridade real de estratégia, não por classe ANBIMA genérica (ver `grupo`/`fonte`).

| Campo | Definição | Tipo |
|---|---|---|
| `nome_padronizado` / `fundo_kinea` | Nome do fundo | string |
| `metrica` | (só retorno_risco) Nome da métrica, ex. "Rentabilidade (No Ano)" | string |
| `taxa_kinea_pct` / `valor_kinea` | Valor do fundo Kinea | float |
| `mediana_concorrentes_pct` / `mediana_concorrentes` | Mediana do grupo de concorrentes diretos | float |
| `n_concorrentes` | Nº de concorrentes diretos usados na mediana | int |
| `desvio_relativo_pct` / `desvio_vs_mediana` | Desvio percentual (liquidez) ou em p.p. (retorno) vs. mediana | float |
| `grupo` | (só retorno_risco) Grupo de concorrentes por similaridade de estratégia | string |
| `fonte` | Origem do dado / grupo de comparação usado | string |

## `dimensao_produto.csv` / `visao_consolidada.csv`

Detalhe por fundo que sustenta `status_produto` e `status_conteudo` do scorecard.

| Campo | Definição | Tipo |
|---|---|---|
| `nome_padronizado` | Nome do fundo | string |
| `categoria_padronizada` / `categoria_generica_xp` | Categoria e flag se é genérica ("Outros" etc.) | string / bool |
| `publico_alvo_kinea` | Público-alvo declarado do fundo Kinea | string |
| `n_concorrentes_com_publico_alvo` | Nº de concorrentes com público-alvo comparável | int |
| `posicionamento_publico_alvo` | Comparação textual (mais/menos restritivo, não comparável) | string |
| `aplicacao_minima_kinea` | Aplicação mínima do fundo Kinea | string |
| `disponibilidade` | Canal de aplicação/resgate (B3 vs. distribuidora) | string |
| `completude_conteudo_pct` | % de campos preenchidos na ficha (100 = ficha completa) | float |
| `campos_faltando` | Lista de campos ausentes na ficha, quando houver | string |
| `percentil_pl` / `pl_sobre_mediana_universo` | Porte relativo (ver `universo_kinea_completo.csv`) | float |

## `aprofundamento_liquidez_custos.csv` / `aprofundamento_retorno_risco.csv` / `aprofundamento_conteudo.csv`

Mesma lógica dos arquivos `dimensao_*`, só que para os 3 fundos priorizados (KNIP11, KDIF11, KNHY11), com concorrentes diretos identificados manualmente (`config/concorrentes_aprofundamento.csv`) em vez de agrupamento automático. Colunas equivalentes às de `dimensao_*`, mais:

| Campo | Definição | Tipo |
|---|---|---|
| `dimensao` | Nome da dimensão do case (redundante com o nome do arquivo, usado no filtro do app) | string |
| `observacao` | Texto livre com achado/ressalva metodológica (ex. fonte suplementar, exclusão de outliers) | string |
| `achado` / `evidencia` | (conteúdo) Frase-resumo do achado e evidência textual | string |

## `recomendacoes.csv`

| Campo | Definição | Tipo |
|---|---|---|
| `fundo_kinea` | Fundo relacionado | string |
| `titulo` | Título curto da recomendação | string |
| `problema_oportunidade` / `evidencia` / `acao_proposta` / `impacto_esperado` | Estrutura pedida pelo case | string |
| `tipo_evidencia_problema` / `tipo_evidencia_evidencia` / `tipo_evidencia_acao` / `tipo_evidencia_impacto` | `FATO` \| `INFERÊNCIA` \| `HIPÓTESE` | string |
| `responsavel_sugerido` | Área/responsável sugerido | string |
| `metrica_acompanhamento` | Métrica de acompanhamento | string |
| `dependencias` | Dependências para executar | string |
