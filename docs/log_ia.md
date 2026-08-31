# Log de Uso de IA

Ferramenta: Claude (Anthropic), via chat com busca web, leitura de página (`web_fetch`) e execução de código em sandbox (sem acesso de rede a `xpi.com.br`).

## Etapa 1 — Mapeamento da prateleira XP
- **O que pedi pra IA:** buscar os fundos Kinea na XP; testar `web_fetch` em 2 páginas pra ver se o HTML era estático; testar acesso à vitrine filtrável.
- **O que validei:** o fetch direto confirmou que páginas individuais são HTML estático e a vitrine é client-side — registrei em `metodologia.md`/`fontes.md`.
- **Decisão minha:** tratei a lista inicial de 13 fundos como não definitiva e exigi validação manual antes de fechar o universo.

## Etapa 2 — Estrutura do projeto e automação da coleta
- **O que pedi pra IA:** montar a estrutura de pastas e escrever `xp_fund_scraper.py`, `standardize.py`, `build_universe.py`, `validate_universe.py`, queries SQL.
- **O que rodei e validei:** executei o código no sandbox (smoke tests, pipeline raw→processed, relatório de qualidade, queries via DuckDB). Encontrei um bug de parsing de CSV (vírgula decimal sem aspas) nessa execução e corrigi.
- **Limitação que identifiquei:** o scraper não pôde ser testado contra o site real da XP no sandbox (sem acesso de rede). A lógica foi escrita a partir do texto retornado por `web_fetch`, e eu sabia que precisava validar contra o HTML real antes de confiar nela.
- **O que não deleguei:** validação final do universo de 13 fundos (fiz manualmente na vitrine); critérios de comparabilidade por categoria (pedi pra IA não aplicar automaticamente sem eu checar contra os dados disponíveis).

## Etapa 2b — Coleta real (VS Code + notebook)
- **O que pedi pra IA:** ajuda na escrita inicial de `coleta_fundos_kinea.ipynb` e `xp_fund_scraper.py`.
- **Bugs que encontrei rodando de verdade, com a IA me ajudando a diagnosticar a partir dos erros que eu trouxe:**
  1. HTTP 403 com `requests` puro (bloqueio por fingerprint TLS) → troquei para `curl_cffi` (`impersonate="chrome"`).
  2. `risco_pontuacao_xp` capturando "(0-100)" em vez do valor → corrigi exigindo formato numérico.
  3. `TypeError` de sintaxe `str | None` (meu Python 3.9 não suporta) → troquei por `typing.Optional[str]`.
- **Execução real:** coletei os 11 fundos no meu ambiente local (o sandbox do Claude não tem acesso a `xpi.com.br`). Cada bug eu encontrei rodando, reportei pra IA com o erro real, e validei que a correção funcionou rodando de novo.

## Estado ao final da Etapa 2
Fechei 17 fundos (13 iniciais + 4 que achei na validação manual: Andes, Apolo, Dakar, Incentivado). Qualidade: 0 duplicidade de chave, 0 CNPJ inválido, 0 fundo sem categoria, 0 coleta pendente.

Fechei o universo competitivo dos 17, via 4 fontes CVM:

| Fonte CVM | Cobre | Fundos Kinea |
|---|---|---|
| `registro_classe.csv` (RCVM175) | Fundos abertos/previdência migrados | Chronos, Atlas II, Oportunidade, Gama, IPCA Dinâmico II, Alpes Prev, Andes, Apolo, Dakar, Incentivado (10) |
| `registro_classe.csv` (classe RF) | KDIF11, registrado como debênture, não FII | KDIF11 (1) |
| `inf_mensal_fii_geral` | FIIs "puros" | KNCR11, KNRI11, KNIP11, KFOF11, KNHY11 (5) |
| `inf_mensal_fiagro` | FIAGRO | KNCA11 (1) |

| Fundo Kinea | Classe/segmento real | Tamanho do universo |
|---|---|---|
| Chronos, Atlas II, Apolo | Multimercados Macro | 738 |
| Oportunidade, IPCA Dinâmico II, Andes, Dakar, Incentivado, KDIF11 | Renda Fixa Duração Livre Crédito Livre | 3.146 |
| Gama | Ações Livre | 2.023 |
| Alpes Prev | Previdência Multimercado Livre | 2.687 |
| KNCR11, KNRI11, KNIP11, KFOF11, KNHY11 | FII - Multicategoria | 659 |
| KNCA11 | FIAGRO | 8 |

**Limitação:** "Multicategoria" e "FIAGRO" são classes reais mas amplas (não separam papel/tijolo nem crédito/imobiliário) — a CVM não publica essa granularidade. Comparar percentil dentro desses universos exige cautela extra.

## Etapa 2b — Descoberta do universo via CVM Dados Abertos
- **Contexto:** tentei achar API pública por trás da vitrine XP (DevTools) — não encontrei nenhuma (só analytics e chamadas de login, que descartei por princípio). Optei pela CVM Dados Abertos (`cad_fi.csv`), download público sem login.
- **2 bugs que encontrei e corrigi (com dado sintético, antes do arquivo real de ~200MB):**
  1. Merge casando fundos sem CNPJ entre si (pandas trata `None` como igual em string) → separei antes do merge.
  2. `clean_cnpj` rejeitando CNPJ lido como número → corrigi pra aceitar `str`/`int`/`float`.
- **Limitação:** `cad_fi.csv` cobre fundos não migrados à Resolução CVM 175; fundos migrados podem precisar de `registro_fundo.csv`/`registro_classe.csv`.

## Etapa 3 — PL comparável dos 17 fundos + reorganização do código
- **Contexto:** a ficha XP só tinha PL de 4 FIIs; os concorrentes já tinham PL da CVM.
- **Achado:** os 17 fundos já apareciam em `fundos_concorrentes.csv` auto-casados — não precisei de fonte nova pra 12 deles.
- **Bug que encontrei e corrigi:** 5 FIIs vinham com PL vazio porque a extração só lia `inf_mensal_fii_geral` (sem PL); o campo estava em `inf_mensal_fii_complemento`.
- **Validação:** cross-check contra os 4 PLs que já tinha coletado na ficha XP, diferença ≤2%.
- **Reorganização que pedi pra IA:** consolidar a lógica das 4 fontes CVM em `build_competitive_universe.py::montar_universo_competitivo`, e a lógica de PL em `patrimonio_liquido.py`. Notebook passou a só orquestrar. Renomeei os CSVs sem sufixo de versão.
- **Limitação:** PL de fundos abertos é a nível de fundo (não subclasse), sem data-base explícita.

## Etapa 4 — Regressão: cartesiano de 59 linhas no PL dos FIIs
- **Sintoma que encontrei:** `universo_kinea_completo.csv` veio com 59 linhas em vez de 17 — percebi antes de aceitar o arquivo e reportei.
- **Causa (2 bugs, diagnosticados com apoio da IA a partir do arquivo real que quebrou):**
  1. A refatoração parou de chamar `enrich_fii_cnpj.py` → 7 FIIs sem CNPJ, filtrados fora do join, desapareciam.
  2. `.astype(str)` transformava `NaN` em string `"nan"` → os 7 FIIs sem CNPJ casavam entre si no merge (7×7=49 linhas fantasma).
- **Correção que apliquei:** `build_competitive_universe.py` voltou a chamar `enriquecer_cnpj_fii()`; `patrimonio_liquido.py` passou a usar `clean_cnpj` + concat por posição (não merge por chave), com `assert` de contagem de linhas.
- **Validei contra:** os arquivos reais que quebraram (fundos_concorrentes.csv de 21.568 linhas, universo_kinea.csv com CNPJ vazio nos FIIs).

## Etapa 5 — Regressão: cadastro legado sobrepondo classe correta dos FII
- **Sintoma que encontrei:** depois da Etapa 4, `montar_universo_competitivo` ainda só calculava universo pra 11 dos 17.
- **Causa que identifiquei com apoio da IA:** `cad_fi.csv` tem entradas de FII/FIAGRO com `classe_anbima` em branco; por entrar primeiro no concat, `drop_duplicates(keep="first")` mantinha a linha vazia em vez da classe correta.
- **Correção que apliquei:** descartar linhas com `classe_anbima` vazia antes de deduplicar por CNPJ.
- **Validei:** com dado sintético reproduzindo o padrão exato — confirmei 17/17.

## Etapa 6 — Correção de rótulo: categoria_padronizada do KDIF11 mostrava "Outros"
- **O que percebi:** na minha tabela de diagnóstico, KDIF11 tinha `categoria_padronizada = "Outros"` e `classe_anbima_cvm = "Renda Fixa Duração Livre Crédito Livre"` — inconsistente. Pedi pra IA investigar a causa.
- **Causa raiz (achada pela IA lendo o código, a partir da inconsistência que eu tinha identificado):** ficha XP sem `categoria_bruta`/`classificacao_xp` para o KDIF11; o fallback em `build_universe.py` pegou `segmento`, que valia literalmente "Outros" (bucket genérico do template, não classificação real).
- **Não era bug de cálculo:** `calcular_percentil()` sempre usou `classe_anbima_cvm`, não `categoria_padronizada`. O percentil (97,2) sempre esteve certo — só o rótulo estava errado.
- **Correção que apliquei:** em `montar_universo_kinea_completo()`, quando `categoria_padronizada` é vazio/nulo/"Outros", passa a usar `standardize_category(classe_anbima_cvm)`. Mantive `categoria_bruta` original intacto.
- **Validei no meu ambiente real:** bati num `FileNotFoundError` de path ao rodar — colei o traceback e corrigi a partir dele. Depois de corrigir o arquivo, o resultado ainda mostrava "Outros"; percebi que era porque não tinha reiniciado o kernel (módulo já importado em memória) — reiniciei e rodei de novo. Resultado final: `categoria_padronizada` = "Renda Fixa", `percentil_pl` inalterado (97,2). Efeito colateral esperado que notei: `taxa_vs_media_categoria_kinea` dos outros fundos de RF mudou levemente (o KDIF11 entrou no cálculo da média do grupo).

## Etapa 7 — Fechamento das 4 dimensões nos 17 fundos + scorecard de posicionamento
- **Contexto:** Produto, Liquidez e custos e Retorno e risco só existiam para os 3 fundos priorizados no aprofundamento; os outros 14 ficavam sem comparação com concorrente nessas dimensões.
- **O que foi feito com IA:** identificação de concorrentes reais por grupo de similaridade de estratégia (busca web, confirmação de URL antes de usar); extensão do scraper existente (`xp_fund_scraper.py`, sem modificação) para 14 concorrentes novos; construção das dimensões Produto e Liquidez/custos e Retorno/risco pros 17; construção do Scorecard de posicionamento final (17 × 4 dimensões).
- **Bug real encontrado e corrigido — duplicata silenciosa no config:** a célula que escreve `concorrentes_aprofundamento.csv` sempre concatenava a lista nova por cima da existente sem checar se já estava lá — cada re-execução duplicava os mesmos concorrentes. Isso inflou a mediana de taxa/retorno do grupo "RF Crédito Genérico" (Sparta Top aparecendo 5x) e do grupo FIAGRO, mascarando os números reais até a candidata notar o  `n_concorrentes` inconsistente entre execuções. Corrigido: (1) dedup pontual do config; (2) reescrita da célula de escrita do config para ser
idempotente (só adiciona linha nova por `(nome_referencia, url)` ainda não presente) — segura pra Run All repetido.