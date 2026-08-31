# Metodologia

## Data-base
Coleta realizada em **15/08/2026**. Todos os campos têm `access_timestamp` registrado por fundo — não existe "data-base única" implícita, cada dado carrega sua própria data de coleta (ver `docs/dicionario_dados.md`).

## Definição de "prateleira pública XP"
Identificamos **duas superfícies públicas distintas** na XP, relevantes para reprodutibilidade:

1. **`conteudos.xpi.com.br`** (Expert XP) — portal de research/conteúdo. Cada fundo tem página própria, **renderizada no servidor (HTML estático)**. Confirmado por teste direto: página acessível via HTTP simples, sem necessidade de JavaScript.
2. **`www.xpi.com.br/investimentos/fundos-de-investimento/lista/`** — a vitrine/prateleira comercial filtrável. Testamos via fetch direto em 15/08/2026: **o HTML retornado contém apenas o shell da aplicação (menu, rodapé) — nenhum dado de fundo está presente no HTML bruto.** É uma aplicação Next.js que carrega o conteúdo via chamadas client-side após o carregamento da página. **Não localizamos endpoint JSON público, nem dado embutido (`__NEXT_DATA__` ou similar) no HTML estático.** Não tentamos inspecionar chamadas de rede da própria página nem endpoints não documentados — isso seria contornar mecanismo de acesso, o que o case proíbe explicitamente.

**Conclusão adotada:** usamos (1) como fonte primária para a ficha de cada fundo (reproduzível via `requests` simples). Para (2) — a enumeração completa da vitrine — **não existe forma pública e reproduzível conhecida sem JavaScript**. Essa limitação é aceita e documentada, conforme instruído: a lista de fundos Kinea foi construída via busca (`site:conteudos.xpi.com.br kinea`), o que é necessariamente uma coleta **parcial e não garantidamente exaustiva**. A validação final do universo completo depende de navegação manual controlada da vitrine (2), registrada como tal — nunca apresentada como automatizada.

## Definição do universo Kinea
Um fundo é considerado parte do "universo Kinea" nesta análise se:
- Tem página própria confirmada em `conteudos.xpi.com.br` (fonte primária), **ou**
- É identificado manualmente na vitrine filtrável por gestora "Kinea" (fonte complementar, registrada como coleta manual).

Fundos institucionais/exclusivos/feeder sob gestão da Kinea (a gestora administra ~450+ fundos no total, segundo fontes de mercado) **estão fora de escopo** — o case pede a prateleira pública de varejo, não o total sob gestão.

## Definição do universo competitivo
Regra hierárquica (não escolha por fama/preferência):

```
categoria XP (rótulo mostrado na ficha do fundo)
   → subestratégia/segmento (ex. Macro Média Vol; FII papel vs. tijolo)
   → filtros de comparabilidade (ver sql/03_regras_comparabilidade.sql)
   → universo competitivo final
```

Cada categoria tem critérios próprios (estratégia, público-alvo, liquidez, tipo de ativo, nível de risco, benchmark) — **documentados em SQL, não escondidos em código Python** (`sql/03_regras_comparabilidade.sql`). Os critérios foram propostos com base no que é *publicamente observável* em cada template de ficha da XP — não presumem dado que não está disponível.

**Importante:** por ora só temos o lado Kinea do universo. O lado "concorrentes" (tabela `fundos_concorrentes`) ainda não foi populado — depende de decidir a fonte (navegação manual da vitrine por categoria, e/ou CVM Dados Abertos, que é uma base pública completa mas não teria a mesma UX/rotulagem "como o assessor vê" que o case pede). Essa decisão fica para a Etapa 2b, após o universo Kinea estar fechado.

## Estrutura de ficha por tipo de produto
Fundos abertos e FIIs usam **templates de ficha diferentes** na XP — isso não é uma falha de comunicação específica da Kinea, é estrutural da plataforma:

| Campo | Fundo aberto | FII listado |
|---|---|---|
| CNPJ | Visível | Ausente |
| Classificação XP/CVM | Visível | Ausente (só "segmento") |
| Taxa de performance | Visível | Ausente na ficha pública |
| Aplicação mínima / cotização | Visível | N/A (compra via bolsa) |
| Volatilidade/Sharpe/Drawdown | Visível | Ausente |
| Dividend Yield | N/A | Visível |

Isso é tratado como campo estruturalmente ausente por categoria de produto na análise de completude de conteúdo — não como lacuna do gestor.

## Identificação e chave de fundo
Prioridade: **CNPJ > ticker > nome padronizado** (`src/transformation/standardize.py::build_fund_key`). Nunca fazemos join só por nome. Ver `docs/dicionario_dados.md` para o formato exato da chave.

## Limitações conhecidas (estado atual)
- Universo Kinea fechado em 17 fundos (13 via busca + 4 confirmados em validação manual da vitrine XP — ver docs/log_ia.md). Lista tratada como razoavelmente completa, mas a vitrine comercial filtrável não tem endpoint público reproduzível (ver seção "Definição de prateleira pública XP" acima), então uma expansão futura da prateleira exigiria nova validação manual.
- CNPJ de FIIs não vem na ficha pública da XP — enriquecido via `src/transformation/enrich_fii_cnpj.py`, cruzando nome/ticker contra o cadastro CVM (ver docs/dicionario_dados.md para o mapeamento).
- Universo competitivo e PL comparável dos 17 fundos: fechados (ver docs/fontes.md e docs/log_ia.md para as 4 fontes CVM usadas e as correções aplicadas durante a validação).

## Notas adicionais (achados durante a validação)

### KDIF11 não é juridicamente um FII
Kinea Infra FII (KDIF11) é rotulado como "FII" pela XP e pelo mercado, mas
seu registro na CVM (RCVM175, verificado por CNPJ) o classifica como Renda
Fixa Duração Livre Crédito Livre — não consta no cadastro de FIIs da CVM.

É um Fundo de Infraestrutura (também chamado Fundo de Debêntures
Incentivadas): investe em debêntures de empresas de infraestrutura
(geração/transmissão de energia, transporte e afins), com benchmark em
juros reais (IPCA+) e distribuição mensal de dividendos isentos de Imposto
de Renda aos cotistas — semelhante ao FII na experiência do investidor
(renda isenta, ticker "11", negociação em bolsa), mas juridicamente uma
estrutura distinta (Lei 12.431), não um FII (Lei 8.668/ICVM 472).

Por isso seu universo competitivo nesta análise é composto por fundos de
Renda Fixa Duração Livre Crédito Livre (n=3.146), não por outros FIIs —
decisão correta e intencional, não uma falha de categorização. A
similaridade com FII é comercial/tributária, não regulatória.

### Previdência e sub-tipos de FII têm completude diferente
- **Previdência (Kinea Alpes Prev):** único fundo com `tipo_pagina = "previdencia"`
  na prateleira. A ficha pública não tem os campos "Objetivo" (proposta em texto
  corrido) nem "Classificação XP" — só "Classificação CVM". Confirmado
  visualmente na página (24/08/2026), não é falha de extração.
- **KNCA11 (FIAGRO) e KDIF11 (FI-Infra):** dos 7 fundos rotulados "FII" pela XP,
  são os únicos 2 sem "Quantidade de Cotistas" e "Valor Patrimonial" na ficha
  pública — os outros 5 (FII "Multicategoria" de verdade) têm ambos. Coerente
  com o achado já documentado de que esses 2 também não constam no cadastro de
  FIIs da CVM (ver nota sobre KDIF11 acima) — reforça que, apesar do mesmo
  ticker "11" e linguagem comercial de "FII", a XP trata esses produtos de
  forma estruturalmente diferente também na própria ficha pública.

### KNCA11 — concorrentes diretos sem ficha pública na XP

Do universo de 5 concorrentes diretos do KNCA11 identificados na base CVM
(RCVM175/FIAGRO), 2 são fundos de colocação privada e não possuem ficha
pública em conteudos.xpi.com.br nem em plataformas de research de varejo
alternativas:

- **Koppert FI Nas Cadeias Produtivas do Agronegócio RL** (CNPJ
  47.669.421/0001-73) — 3 cotistas institucionais, PL R$ 220,78 mi
  (fonte: maisretorno.com, consultado via resultado de busca em
  29/08/2026; fetch direto bloqueado por robots.txt do site).
- **Hedge I Fiagro RL** (primeira cota 31/03/2023) — 7 cotistas, PL
  R$ 2,75 mi, sem adaptação à RCVM 175 registrada (mesma fonte/data/
  restrição de acesso acima).

Ambos são fundos fechados de colocação privada (poucos cotistas
institucionais, sem ticker de negociação em bolsa identificado), não
distribuídos no varejo — por isso a ausência de ficha não é uma falha de
coleta, é uma característica do produto. Não foi feito scraping dessas
páginas: o maisretorno bloqueia acesso automatizado via robots.txt
(retorna erro ROBOTS_DISALLOWED), o que violaria a instrução do case de
não contornar mecanismos de acesso. Consequência: a comparação de
"Conteúdo e diferenciação" do KNCA11 considera apenas 3 dos 5 concorrentes
diretos (RURA11, VCRA11, Canaã CRA Cocal); a comparação numérica de
taxa/PL via CVM (`fundos_concorrentes.csv`) continua com os 5. 

## Grupos de comparação por similaridade de estratégia (Liquidez/custos e Retorno/risco, 17 fundos)

Para os 14 fundos fora do aprofundamento, a comparação de Liquidez e custos e
Retorno e risco contra concorrente direto usa **grupos definidos por
similaridade de estratégia real**, não pela classe ANBIMA/CVM genérica —
mesmo critério já aplicado ao KDIF11 no aprofundamento (classe CVM
"Renda Fixa Duração Livre Crédito Livre" é ampla demais; a estratégia real
dele é debênture incentivada de infraestrutura).

| Grupo | Fundos Kinea | Concorrentes (XP, scraper) |
|---|---|---|
| Infra Debênture | KDIF11, Incentivado | Sparta Deb. Incentivadas, Itaú Deb. Incentivadas, SulAmérica Infra |
| RF Crédito Genérico | Andes, Oportunidade, IPCA Dinâmico II, Dakar | Sparta Top FIC FI RF CP LP, JGP Corporate FIC FIF RF CP LP Feeder III |
| Multimercados Macro | Chronos, Atlas II, Apolo | SPX Nimitz Feeder FIC FIM, Ibiuna Hedge STH FIC FIM |
| Ações Livre | Gama | Constellation Institucional FIC FIA, Selection Ações FIC FIA |
| FIAGRO | KNCA11 | Itaú Asset Rural (RURA11), Vectis Datagro (VCRA11), Canaã CRA Cocal |
| FII Tijolo Diversificado | KNRI11 | VBI Prime Properties (PVBI11), Vinci Logística (VILG11) |
| FII Papel/Recebíveis | KNCR11, KNIP11 | XP Crédito Imobiliário (XPCI11), Capitania Securities II (CPTS11) |
| FII Fundo de Fundos | KFOF11 | XP Selection FOF (XPSF11), Hedge Top FOFII 3 (HFOF11) |
| FII Multicategoria (CVM, sem scraping XP) | KNCR11, KNIP11, KNRI11, KFOF11 (Liquidez/custos) | Universo amplo FII-Multicategoria via CVM (mesmo cálculo do KNHY11 no aprofundamento, n=580 válidos) |

Os 3 fundos priorizados no aprofundamento (Alpes Prev, KDIF11, KNHY11) mantêm
seus concorrentes próprios, já documentados.

## Achado: concorrentes diretos do KNCA11 sem ficha pública na XP

Do universo de 5 concorrentes diretos do KNCA11 identificados na base CVM
(RCVM175/FIAGRO), 2 são fundos de colocação privada e não possuem ficha
pública em conteudos.xpi.com.br nem em plataformas de research de varejo
alternativas:

- **Koppert FI Nas Cadeias Produtivas do Agronegócio RL** (CNPJ
  47.669.421/0001-73) — 3 cotistas institucionais, PL R$ 220,78 mi.
- **Hedge I Fiagro RL** (primeira cota 31/03/2023) — 7 cotistas, PL
  R$ 2,75 mi, sem adaptação à RCVM 175 registrada.

Fonte de ambos: maisretorno.com, consultado via resultado de busca em
29/08/2026 — **fetch direto bloqueado por robots.txt do site** (erro
`ROBOTS_DISALLOWED`). Confirmamos que esse bloqueio é uma política
declarada (Disallow explícito), diferente do bloqueio técnico de
impressão digital de TLS da própria XP (cujo robots.txt real foi
verificado e só restringe `/wp-admin/` e arquivos `.pdf` — nenhum caminho
de fundo é bloqueado). Por isso não foi feito scraping do maisretorno:
contornar um robots.txt declarado violaria a instrução do case de não
contornar mecanismos de acesso.

Ambos os fundos são de colocação privada (poucos cotistas institucionais,
sem ticker de negociação em bolsa), não distribuídos no varejo — a
ausência de ficha pública não é falha de coleta, é característica do
produto. Comparação de "Conteúdo e diferenciação" do KNCA11 considera
apenas os 3 concorrentes com ficha pública confirmada (RURA11, VCRA11,
Canaã CRA Cocal); a comparação numérica de taxa/PL via CVM
(`fundos_concorrentes.csv`) mantém os 5.

## Achado: Rentabilidade "No Ano" zerada em toda a categoria FIAGRO na XP

O KNCA11 e os 2 concorrentes diretos com ficha pública (RURA11, VCRA11)
mostram 0% na janela "Rentabilidade No Ano" na ficha da XP — o mesmo padrão
já documentado para o KDIF11 (tabela de Rentabilidade zerada), mas aqui
afeta **tanto a Kinea quanto os concorrentes**, não é assimetria. Hipótese
mais provável: FIAGRO é categoria regulatória recente (Lei 14.130/2021) e
a XP pode não ter 12 meses completos de cota pra calcular a janela "No Ano"
em nenhum fundo da categoria ainda. Tratado como **limitação de
categoria/plataforma**, não como achado de "mal comunicado" específico da
Kinea — regra aplicada de forma consistente no scorecard de posicionamento
(ver seção seguinte).

## Regra de classificação do scorecard de posicionamento (17 fundos × 4 dimensões)

Critérios fechados e testados contra casos reais antes de aplicar em lote:

- **Liquidez e custos:** `desvantagem` se taxa Kinea > 30% acima da mediana
  do grupo de concorrentes; `bem posicionado` caso contrário (com dado
  válido).
- **Retorno e risco:** `desvantagem` se retorno Kinea < -2 p.p. vs. mediana
  do grupo; `bem posicionado` caso contrário (com dado válido).
- **Ausência de dado (qualquer dimensão):** `mal comunicado` **somente se**
  o concorrente direto tem o dado e a Kinea não (assimetria real,
  comprovável mesma fonte/mesmo canal). Se o concorrente também não tem o
  dado, é `limitação de categoria/plataforma` — não conta contra o
  posicionamento competitivo da Kinea. Essa distinção foi testada contra
  dois casos reais antes de virar regra: KNCA11 (Kinea E concorrentes
  zerados → limitação de categoria) vs. KDIF11 e Alpes Prev (Kinea vazio,
  concorrentes/pares preenchidos → mal comunicado de fato).

**Validação adicional do "mal comunicado" em Produto (Alpes Prev e KDIF11):**
confirmado por inspeção direta do HTML da ficha real da XP, não só por
inferência via dado CVM — evita misturar fonte CVM (concorrente) com fonte
XP (Kinea) na mesma comparação, o que teria sido metodologicamente
inválido (comparação teria que ser sempre XP vs. XP, mesmo canal).
- Alpes Prev: confirmado que o template de Previdência da XP mostra o campo
  "Público" (ex.: SPX Seahawk Icatu Previdência exibe "Investidor não
  qualificado"), mas a ficha do Alpes Prev não mostra o campo.
  `conteudos.xpi.com.br/previdencia-privada/spx-seahawk-icatu-previdencia-ficfi-multimercado-credito-privado/`,
  consultado 30/08/2026.
- KDIF11: evidência ainda mais direta — os outros FIIs da própria Kinea
  (KNRI11, KNIP11, KFOF11, KNHY11) mostram `publico_alvo = "Não Há
  Restrição"` na ficha; só o KDIF11 vem vazio. Mesma casa, mesmo canal,
  mesmo template — comparação Kinea-vs-Kinea, a mais direta possível.

## Critérios de classificação do scorecard de posicionamento

Cada fundo recebe status por dimensão (`bem posicionado`, `desvantagem`,
`mal comunicado`, `limitação de categoria/plataforma`):

- **Liquidez e custos:** `desvantagem` se a taxa de administração está
 **+30% acima** da mediana dos concorrentes diretos (limiar mais alto
  que o padrão de mercado para evitar ruído em amostras pequenas — ver
  `n_concorrentes` em `dimensao_liquidez_custos.csv`).
- **Retorno e risco:** `desvantagem` se o retorno está **-2 p.p. abaixo**
  da mediana dos concorrentes diretos (tolerância maior que a de taxas,
  refletindo variância natural de retorno).
- **Mal comunicado:** aplica-se só quando o concorrente direto tem o
  dado publicamente e a Kinea não (assimetria real). Quando nenhum dos
  dois lados tem o dado, é `limitação de categoria/plataforma`, não
  desvantagem competitiva — a ausência não é atribuída à Kinea nesse caso.
- Fundos sem concorrentes diretos com dado comparável na dimensão
  recebem `limitação de categoria/plataforma` por padrão nessa dimensão
  (não `desvantagem` nem `bem posicionado` por ausência de evidência).  

  ## Achado: taxa do KNHY11 recalculada com concorrentes diretos de CRI/Recebíveis

A comparação de Liquidez e custos do KNHY11 inicialmente usou o universo
amplo de FII-Multicategoria via CVM (n=580, mediana 0,43% a.a.) — mesma
base usada para os outros FII-Multicategoria genéricos (KNCR11, KNIP11,
KNRI11, KFOF11). Isso gerou um desvio de +272,1%, mas misturava tijolo,
papel e fundo de fundos numa mediana só, sem refletir a estratégia real do
KNHY11 (CRI/High Yield).

Corrigido para o mesmo princípio de similaridade real de estratégia já
usado no KDIF11: filtramos os concorrentes por nome (CRI, Recebíveis, High
Yield, Crédito) dentro da base CVM, chegando a 38 concorrentes diretos
identificados, 37 com taxa válida após o mesmo filtro de sanidade de
0-0,25%/mês. Mediana recalculada: 0,98% a.a. — taxa Kinea (1,60%) fica
**+63,3%** acima, não +272,1%. O status no scorecard (`desvantagem`, acima
do limiar de 30%) não muda, mas o número é mais defensável: compara o
KNHY11 com pares de estratégia parecida, não com o mercado de FII inteiro.

## Achado: Conteúdo e diferenciação do KDIF11 — clareza e narrativa, não só completude

A dimensão "Conteúdo e diferenciação" tem 3 componentes (clareza da
proposta, completude das informações, narrativa competitiva), e a análise
inicial só cobria completude. Revisão qualitativa dos 3 fundos do
aprofundamento, usando **conteúdo editorial próprio na ficha** ("Relatórios"
com recomendação/tese, quando existe) como proxy conjunta de clareza e
narrativa — as duas colapsam na mesma evidência nessa fonte, já que o
único texto livre disponível é justamente esse relatório:

- **KDIF11**: sem seção de Relatórios/Análise Research na própria ficha.
  Segmento aparece como "Outros" (confirmado direto na ficha, 30/08/2026)
  — mesmo padrão de rótulo genérico já documentado em `categoria_padronizada`.
  Comparável ao KNIP11 (mesma casa, mesmo template FII), que tem 2
  relatórios publicados — não aos concorrentes de infra (Sparta, Itaú,
  SulAmérica), que são `fundo_aberto` e não têm essa seção estruturalmente
  (confirmado: a ficha do Sparta só tem "Documentos", PDFs regulatórios,
  sem conteúdo editorial).
- **KNHY11**: mesma ausência de Relatórios/Análise Research. Segmento
  genérico ("Títulos e Valores Mobiliários"), mas esse rótulo é padrão de
  toda a categoria de papel/recebíveis (XPCI11 usa o mesmo), não é
  assimetria.
- **KNIP11**: único dos 3 com conteúdo editorial ativo — 2 relatórios
  publicados pela XP ("Baixo risco de crédito e proteção contra a
  inflação", "Atualização de Tese"), o mais recente com recomendação de
  compra reiterada (04/06/2025).

Correção de um erro anterior: o achado de completude do KDIF11 havia sido
associado a concorrentes errados (Devant/VGIP11, que são na verdade
concorrentes diretos do KNHY11, não do KDIF11). Corrigido para usar a
comparação correta: os outros 5 FIIs da própria Kinea no mesmo template
(KNCR11, KNIP11, KNRI11, KNHY11, KFOF11), que expõem quantidade_cotistas e
valor_patrimonial normalmente — só o KDIF11 não.