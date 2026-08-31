-- 02_universo_kinea_analise.sql
-- Finalidade: consultas de apoio à decisão sobre o universo Kinea, contra os
-- dados finais do pipeline (universo_kinea_completo.csv + fundos_concorrentes.csv).
-- Testado com DuckDB: ver README.md > "Como executar o SQL".


-- 1) Fundos Kinea por categoria padronizada (visão geral da prateleira)
SELECT
    categoria_padronizada,
    COUNT(*) AS n_fundos,
    SUM(CASE WHEN status_confirmacao = 'ficha_coletada' THEN 1 ELSE 0 END) AS n_ficha_completa,
    SUM(CASE WHEN status_confirmacao = 'identificado_pendente' THEN 1 ELSE 0 END) AS n_pendente
FROM fundos_kinea
GROUP BY categoria_padronizada
ORDER BY n_fundos DESC;

-- 2) Fundos por tipo de página (fundo aberto vs FII vs previdência) -
--    relevante porque cada tipo tem um template de ficha diferente na XP
--    (ver docs/metodologia.md, seção "campos disponíveis vs ausentes").
SELECT
    tipo_pagina,
    COUNT(*) AS n_fundos,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fundos_kinea), 1) AS pct_do_universo
FROM fundos_kinea
GROUP BY tipo_pagina
ORDER BY n_fundos DESC;

-- 3) Cobertura de identificação robusta: quantos fundos têm CNPJ, ticker,
--    ou dependem só do nome (fallback menos confiável para join futuro).
SELECT
    CASE
        WHEN fund_key LIKE 'CNPJ:%'   THEN 'CNPJ'
        WHEN fund_key LIKE 'TICKER:%' THEN 'TICKER'
        ELSE 'NOME (fallback)'
    END AS tipo_chave,
    COUNT(*) AS n_fundos
FROM fundos_kinea
GROUP BY tipo_chave
ORDER BY n_fundos DESC;

-- 4) Fundos ainda sem taxa de administração coletada (gap de dado a
--    fechar antes da Etapa 3 - indicador crítico para a dimensão custos).
SELECT nome_padronizado, tipo_pagina, categoria_padronizada, url
FROM fundos_kinea
WHERE taxa_administracao_pct IS NULL
ORDER BY tipo_pagina, nome_padronizado;

-- 5) Tamanho do universo competitivo por categoria Kinea (fundos_concorrentes
--    já populada - join por referencia_fundo_kinea, excluindo o próprio
--    fundo Kinea autocasado dentro do seu universo).
SELECT
    k.categoria_padronizada,
    COUNT(DISTINCT k.fund_key) AS n_fundos_kinea,
    COUNT(DISTINCT CASE WHEN c.eh_fundo_kinea = FALSE THEN c.cnpj END) AS n_concorrentes_diretos
FROM fundos_kinea k
LEFT JOIN fundos_concorrentes c
    ON c.referencia_fundo_kinea = k.nome_padronizado
GROUP BY k.categoria_padronizada
ORDER BY n_concorrentes_diretos DESC;

-- 6) Fundos Kinea com PL abaixo da mediana do universo competitivo
--    (percentil_pl < 50) - indicador de porte relativo, relevante para
--    priorizar quais fundos precisam de atenção comercial por tamanho.
SELECT
    nome_padronizado,
    categoria_padronizada,
    status_pl,
    ROUND(patrimonio_liquido_cvm, 0) AS pl_cvm,
    ROUND(percentil_pl, 1) AS percentil_pl,
    n_concorrentes_com_pl
FROM fundos_kinea
WHERE status_pl = 'encontrado'
  AND percentil_pl < 50
ORDER BY percentil_pl ASC;

