-- 03_regras_comparabilidade.sql
-- Finalidade: registrar, de forma explícita e consultável, os critérios de
-- comparabilidade usados para montar o universo competitivo de cada
-- categoria. Nenhum desses critérios deve viver "escondido" dentro de
-- código Python - eles devem poder ser lidos, questionados e alterados
-- aqui. Ainda não é a definição FINAL (depende de fechar o universo
-- Kinea e testar contra o universo real da categoria na Etapa 2b) -
-- é a proposta de regra por categoria, sujeita a ajuste quando os dados
-- publicamente disponíveis não permitirem aplicar um critério à risca.

DELETE FROM regras_comparabilidade;

INSERT INTO regras_comparabilidade
(categoria_padronizada, criterio_estrategia, criterio_publico_alvo, criterio_liquidez,
 criterio_tipo_ativo, criterio_nivel_risco, criterio_benchmark, justificativa)
VALUES
('Multimercado - Macro',
 'Mesma subclassificação XP (ex. "Macro Média Vol") ou classificação ANBIMA equivalente (Multimercado Macro)',
 'Mesmo público-alvo declarado (Investidor em Geral vs. Qualificado/Profissional - não misturar)',
 'Mesma faixa de cotização de resgate (ex. D+0/D+1 vs. fundos com carência maior)',
 'Fundo aberto multimercado',
 'Faixa de volatilidade/pontuação de risco XP comparável (não comparar Baixa Vol com Alta Vol)',
 'CDI (benchmark padrão da categoria na prateleira XP)',
 'Vol e liquidez são os fatores que mais distorcem comparação em multimercado macro - sem esse filtro, o "universo" mistura fundos com propostas de risco incompatíveis.'),

('Renda Fixa',
 'Mesma subestratégia (Crédito Privado vs. Duração Livre vs. Inflação/IPCA) - não comparar entre si',
 'Mesmo público-alvo declarado',
 'Faixa de cotização/resgate comparável',
 'Fundo aberto de renda fixa',
 'Faixa de risco de crédito comparável quando informação disponível',
 'CDI ou IPCA, dependendo da subestratégia (registrar qual)',
 '"Renda Fixa" é categoria ampla demais para comparação direta - subestratégia é o filtro que realmente define o grupo de pares.'),

('Ações',
 'Mesmo estilo declarado (ativo long-only vs. long-biased vs. setorial) quando identificável',
 'Mesmo público-alvo declarado',
 'Não é o filtro mais relevante nesta categoria (liquidez costuma ser padrão D+30/D+4, mas registrar se divergir)',
 'Fundo aberto de ações',
 'N/A direto - risco intrínseco à classe (comparar por volatilidade/beta se disponível)',
 'Ibovespa (padrão da categoria) - registrar se o fundo usar benchmark alternativo',
 'Fundos de ações com mandatos muito diferentes (ex. dividendos vs. small caps) não deveriam competir na mesma prateleira de comparação sem qualificação do estilo.'),

('Fundo Imobiliário (FII)',
 'Mesmo segmento (papel/recebíveis vs. tijolo vs. fundo de fundos vs. FIAGRO/FI-Infra - tratados como categorias próprias)',
 'Sem restrição na maior parte dos FIIs (público geral) - filtro pouco discriminante aqui',
 'Liquidez de mercado secundário (volume diário) como proxy, não cotização/carência (não se aplica a fundo negociado em bolsa)',
 'FII listado em bolsa',
 'Pontuação de risco XP quando disponível - setor de atuação como proxy adicional',
 'IFIX (benchmark padrão de FIIs na XP)',
 'FIIs de papel e de tijolo têm perfis de risco/retorno estruturalmente diferentes - comparar KNCR11 (papel) com KNRI11 (tijolo) sem qualificação seria comparação inválida.'),

('FIAGRO',
 'Mesma subestratégia (crédito agro vs. equity agro) quando identificável',
 'Sem restrição, tipicamente',
 'Liquidez de mercado secundário (volume diário)',
 'FIAGRO listado em bolsa',
 'Risco de crédito do lastro (CRA) como proxy quando disponível',
 'CDI ou IPCA, dependendo do lastro predominante',
 'Categoria ainda pequena na prateleira XP - universo pode ser naturalmente reduzido - documentar tamanho real na Etapa 2b antes de aplicar mais filtros.'),

('FI-Infra',
 'Mesma estrutura (debêntures incentivadas de infraestrutura)',
 'Sem restrição, tipicamente',
 'Liquidez de mercado secundário (volume diário)',
 'FI-Infra listado em bolsa',
 'Risco de crédito da carteira de debêntures como proxy quando disponível',
 'IPCA ou IMA-B (comum no segmento de debêntures incentivadas)',
 'Categoria recente e pequena - mesmo racional do FIAGRO: medir tamanho real do universo antes de aplicar filtros adicionais.'),

('Previdência',
 'Mesma subestratégia dentro de previdência (RF Crédito Privado vs. Multimercado vs. Data-Alvo)',
 'Mesmo público-alvo declarado',
 'N/A direto (previdência tem regras de portabilidade próprias, não cotização de fundo aberto)',
 'Fundo previdenciário (FIC/FIF de previdência)',
 'Faixa de risco comparável quando informação disponível',
 'CDI (mais comum) ou IPCA, dependendo da subestratégia',
 'Fundos de previdência não competem com fundos abertos equivalentes na mesma prateleira - tributação e portabilidade mudam a decisão do investidor, por isso tratamos como categoria própria mesmo quando a estratégia subjacente é parecida.');
