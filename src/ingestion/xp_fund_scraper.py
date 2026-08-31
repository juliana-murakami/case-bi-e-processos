"""
xp_fund_scraper.py

Finalidade
----------
Coleta a ficha pública de um fundo individual em conteudos.xpi.com.br
(subdomínio de conteúdo/research da XP - Expert XP). Essas páginas são
renderizadas no servidor (HTML estático), diferente da vitrine principal
(www.xpi.com.br/investimentos/fundos-de-investimento/lista/), que é uma
aplicação Next.js client-side e NÃO expõe os dados de fundos no HTML bruto
(confirmado por teste em 15/08/2026 - ver docs/metodologia.md).

Como executar
--------------
    python src/ingestion/xp_fund_scraper.py \
        --input config/kinea_fund_urls.csv \
        --raw-dir data/raw \
        --output data/raw/universo_kinea_raw.csv

Requisitos
----------
    pip install requests beautifulsoup4 pandas --break-system-packages

Nota de transparência (IMPORTANTE)
-----------------------------------
A lógica de extração foi escrita com base na ESTRUTURA DE TEXTO observada
em leitura direta de página (conteúdo já convertido para markdown/texto,
não o HTML bruto). A extração usa uma estratégia de "proximidade de
rótulo" (label -> próximo valor) que é resiliente a mudanças de classe
CSS, mas NÃO foi validada contra o HTML bruto real antes da primeira
execução em lote (ambiente de desenvolvimento sem acesso de rede a
xpi.com.br - ver docs/log_ia.md).
Antes de rodar em lote, valide com --debug em 1-2 URLs e confira se os
campos batem com o que aparece no navegador. Ajuste SELECTORS/LABELS se
necessário - esse é o ponto de ajuste esperado no "teste ao vivo".

Nota de transparência 2 (23/08/2026) - Risco e Retorno
--------------------------------------------------------
Adicionada extração das tabelas "Risco e Retorno" (fundo_aberto e
previdencia) e "Rentabilidade" (fii). Estrutura confirmada via fetch
direto de 3 páginas reais (Sparta Debêntures = fundo_aberto, SPX Seahawk
Icatu Prev = previdencia, Devant DEVA11 = fii) em 23/08/2026 - ver
extrair_risco_retorno() e extrair_rentabilidade_fii(). MESMA RESSALVA
acima se aplica: validado contra conteúdo convertido, não contra o HTML
bruto real. Rode --debug antes do lote.
"""
import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as curl_requests
    _TEM_CURL_CFFI = True
except ImportError:
    _TEM_CURL_CFFI = False

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20
REQUEST_DELAY_SECONDS = 2.0  # gentileza com o servidor - nao sobrecarregar

# NOTA (achado real de execução, 15/08/2026): a primeira versão deste
# script usava um User-Agent que se identificava como bot
# ("KineaBICaseBot/1.0") e a XP retornou HTTP 403 em 100% das requisições.
# Trocando para um User-Agent de navegador comum (abaixo) resolveu.
# Isso não contorna login/CAPTCHA - a página continua pública e sem
# autenticação; só evita que a requisição seja descartada por um filtro
# de bot genérico antes de chegar ao conteúdo. Documentado também em
# docs/metodologia.md.

# Rótulos que aparecem nas fichas de fundo aberto e de FII na XP.
# Mapeia rótulo->nome de campo padronizado. Ajustável sem tocar no parser.
LABELS_FUNDO_ABERTO = {
    "CNPJ": "cnpj",
    "Aplicação Mínima": "aplicacao_minima",
    "Taxa de Administração (ao ano)": "taxa_administracao",
    "Taxa Máxima de Administração (ao ano)": "taxa_administracao_maxima",
    "Taxa de Performance": "taxa_performance",
    "Cotização de Resgate": "cotizacao_resgate",
    "Liquidação de Resgate": "liquidacao_resgate",
    "Cotização de Aplicação": "cotizacao_aplicacao",
    "Público Alvo": "publico_alvo",
    "Benchmark": "benchmark",
    "Classificação XP": "classificacao_xp",
    "Classificação CVM": "classificacao_cvm",
    "Gestor": "gestor",
    "Administrador": "administrador",
    "Custodiante": "custodiante",
    "Auditor": "auditor",
    "Risco": "risco_pontuacao_xp",
    "Data de Início": "data_inicio",
    "Rating Morningstar": "rating_morningstar",
    "Objetivo": "objetivo",
    "Política de Gestão": "politica_gestao",
    "Tributação": "tributacao",
    "Movimentação Mínima": "movimentacao_minima",
    "Saldo mínimo de permanência": "saldo_minimo_permanencia",
}

LABELS_FII = {
    "Segmento": "segmento",
    "Taxa de administração": "taxa_administracao",
    "Público Alvo": "publico_alvo",
    "Dividendo Yield": "dividend_yield",
    "Último Dividendo": "ultimo_dividendo",
    "Valor Patrimonial": "valor_patrimonial",
    "Cotas Emitidas": "cotas_emitidas",
    "Quantidade de Cotistas": "quantidade_cotistas",
    "Participação no IFIX": "participacao_ifix",
}


@dataclass
class FundoColetado:
    nome_referencia: str
    url: str
    tipo_pagina: str
    access_timestamp: str
    extraction_method: str
    source: str = "conteudos.xpi.com.br (Expert XP)"
    http_status: Optional[int] = None
    titulo_pagina: Optional[str] = None
    campos: dict = field(default_factory=dict)
    erro: Optional[str] = None


# Alguns rótulos aparecem MAIS DE UMA VEZ na página (ex: "Risco" aparece
# como legenda "Risco (0-100)" perto do topo, e de novo na seção "Mais
# Informações" com o valor numérico real). Para esses, exigimos que o
# valor pareça um número - senão continuamos procurando a próxima ocorrência.
CAMPOS_SO_NUMERICOS = {"risco_pontuacao_xp"}


def _parece_numerico(texto: str) -> bool:
    return bool(re.fullmatch(r"\d+([.,]\d+)?", texto.strip()))


def _label_value_map(soup: BeautifulSoup, labels: dict) -> dict:
    """Estratégia de proximidade de rótulo: para cada rótulo conhecido,
    procura o texto exato em qualquer elemento e pega o texto do próximo
    elemento irmão/descendente não vazio como valor. Resiliente a mudança
    de classes CSS, mas depende dos rótulos continuarem os mesmos.
    Para campos em CAMPOS_SO_NUMERICOS, pula ocorrências do rótulo cujo
    valor seguinte não parece um número (ex: legenda "Risco (0-100)")."""
    resultado = {}
    all_texts = [t for t in soup.stripped_strings]
    for i, texto in enumerate(all_texts):
        for label, campo in labels.items():
            if texto.strip() != label or campo in resultado:
                continue
            for j in range(i + 1, min(i + 4, len(all_texts))):
                candidato = all_texts[j].strip()
                if not candidato or candidato == label:
                    continue
                if campo in CAMPOS_SO_NUMERICOS and not _parece_numerico(candidato):
                    continue
                resultado[campo] = candidato
                break
    return resultado


# --- Extração de tabelas de Retorno e Risco (Risco e Retorno / Rentabilidade) ---
# Rótulos de coluna e linha exatamente como aparecem na página (normalizados
# para snake_case no dicionário de saída). Ausência de dado na página vem
# como "-" e deve virar None, não string. Estrutura confirmada em 23/08/2026
# via fetch direto (Sparta = fundo_aberto, SPX Seahawk Icatu Prev =
# previdencia, Devant DEVA11 = fii) - ver nota de transparência no topo.

COLUNAS_RISCO_RETORNO = {
    "No Ano": "no_ano", "12 Meses": "12m", "24 Meses": "24m",
    "36 Meses": "36m", "Desde o Início": "desde_inicio",
}
LINHAS_RISCO_RETORNO = {
    "Rentabilidade": "rentabilidade", "Volatilidade": "volatilidade",
    "Índice de Sharpe": "sharpe",
}

COLUNAS_RENTABILIDADE_FII = {
    "Dia": "dia", "Semana": "semana", "Mês": "mes",
    "3 Meses": "3m", "6 Meses": "6m", "No ano": "no_ano",
}
LINHAS_RENTABILIDADE_FII = {
    "Fundo": "fundo", "IBOV": "ibov", "CDI": "cdi",
}


def _texto_ou_none(valor: str):
    valor = valor.strip()
    return None if valor in ("", "-") else valor


def _extrair_tabela_apos_heading(soup: BeautifulSoup, heading_texto: str):
    """Ancora no texto do heading (H2/H3/H4), não em classe CSS - mesma
    filosofia de resiliência do _label_value_map. Retorna a <table> do
    BeautifulSoup ou None se o heading/tabela não existir na página."""
    heading = soup.find(
        lambda tag: tag.name in ("h2", "h3", "h4")
        and tag.get_text(strip=True) == heading_texto
    )
    if heading is None:
        return None
    return heading.find_next("table")


def _parse_matriz_tabela(tabela, mapa_linhas: dict, mapa_colunas: dict, prefixo: str) -> dict:
    """Espera uma tabela com 1a linha = cabeçalho de colunas e 1a célula
    de cada linha seguinte = rótulo de linha. Gera campos tipo
    '{prefixo}_{linha}_{coluna}', ex: 'rr_sharpe_12m'."""
    if tabela is None:
        return {}

    linhas_html = tabela.find_all("tr")
    if not linhas_html:
        return {}

    cabecalho = [c.get_text(strip=True) for c in linhas_html[0].find_all(["td", "th"])]
    # a primeira célula do cabeçalho costuma vir vazia (canto superior esquerdo)
    indices_coluna = {}
    for i, texto_col in enumerate(cabecalho):
        if texto_col in mapa_colunas:
            indices_coluna[i] = mapa_colunas[texto_col]

    resultado = {}
    for tr in linhas_html[1:]:
        celulas = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not celulas:
            continue
        rotulo_linha = celulas[0]
        if rotulo_linha not in mapa_linhas:
            continue
        chave_linha = mapa_linhas[rotulo_linha]
        for i, valor in enumerate(celulas):
            if i in indices_coluna:
                campo = f"{prefixo}_{chave_linha}_{indices_coluna[i]}"
                resultado[campo] = _texto_ou_none(valor)
    return resultado


def extrair_risco_retorno(soup: BeautifulSoup) -> dict:
    """Para fundo_aberto e previdencia: tabela 'Risco e Retorno' com
    Rentabilidade/Volatilidade/Sharpe x No Ano/12M/24M/36M/Desde o Início.
    Gera campos: rr_rentabilidade_no_ano, rr_volatilidade_12m,
    rr_sharpe_desde_inicio, etc."""
    tabela = _extrair_tabela_apos_heading(soup, "Risco e Retorno")
    return _parse_matriz_tabela(tabela, LINHAS_RISCO_RETORNO, COLUNAS_RISCO_RETORNO, prefixo="rr")


def extrair_rentabilidade_fii(soup: BeautifulSoup) -> dict:
    """Para FII: tabela 'Rentabilidade' com Fundo/IBOV/CDI x
    Dia/Semana/Mês/3M/6M/No ano. Gera campos: rent_fundo_no_ano,
    rent_ibov_3m, rent_cdi_dia, etc."""
    tabela = _extrair_tabela_apos_heading(soup, "Rentabilidade")
    return _parse_matriz_tabela(tabela, LINHAS_RENTABILIDADE_FII, COLUNAS_RENTABILIDADE_FII, prefixo="rent")


def fetch_fund_page(url: str, timeout: int = REQUEST_TIMEOUT) -> requests.Response:
    """Usa curl_cffi (impersonando Chrome) quando disponível - a XP retorna
    HTTP 403 para requests puro (bloqueio por fingerprint de TLS, não só
    User-Agent; confirmado empiricamente em 15/08/2026). Faz fallback para
    requests puro só se curl_cffi não estiver instalado."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://conteudos.xpi.com.br/",
    }
    if _TEM_CURL_CFFI:
        return curl_requests.get(url, headers=headers, impersonate="chrome", timeout=timeout)
    session = requests.Session()
    return session.get(url, headers=headers, timeout=timeout)


def parse_fund_page(html: str, tipo_pagina: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    labels = LABELS_FII if tipo_pagina == "fii" else LABELS_FUNDO_ABERTO
    campos = _label_value_map(soup, labels)

    # Retorno e risco - estrutura difere por tipo de página
    if tipo_pagina == "fii":
        campos.update(extrair_rentabilidade_fii(soup))
    else:
        campos.update(extrair_risco_retorno(soup))

    titulo = soup.find("title")
    titulo_texto = titulo.get_text(strip=True) if titulo else None

    return {"titulo_pagina": titulo_texto, "campos": campos}


def coletar_fundo(nome_referencia: str, url: str, tipo_pagina: str, raw_dir: Path) -> FundoColetado:
    timestamp = datetime.now(timezone.utc).isoformat()
    registro = FundoColetado(
        nome_referencia=nome_referencia,
        url=url,
        tipo_pagina=tipo_pagina,
        access_timestamp=timestamp,
        extraction_method="requests_bs4_local",
    )
    try:
        resp = fetch_fund_page(url)
        registro.http_status = resp.status_code
        if resp.status_code != 200:
            registro.erro = f"HTTP {resp.status_code}"
            return registro

        # salva HTML bruto para auditoria/reprodutibilidade (data lineage)
        raw_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", nome_referencia.lower()).strip("-")
        raw_path = raw_dir / f"{slug}.html"
        raw_path.write_text(resp.text, encoding="utf-8")

        parsed = parse_fund_page(resp.text, tipo_pagina)
        registro.titulo_pagina = parsed["titulo_pagina"]
        registro.campos = parsed["campos"]
    except requests.RequestException as exc:
        registro.erro = str(exc)
    return registro


def carregar_lista_urls(input_csv: Path) -> list:
    with open(input_csv, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def salvar_resultados(registros: list, output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    # achata campos dinâmicos em colunas, preservando lineage
    todas_chaves_campos = sorted({k for r in registros for k in r.campos.keys()})
    fieldnames = [
        "nome_referencia", "url", "tipo_pagina", "source", "access_timestamp",
        "extraction_method", "http_status", "titulo_pagina", "erro",
    ] + todas_chaves_campos

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in registros:
            row = asdict(r)
            campos = row.pop("campos")
            row.update(campos)
            writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="config/kinea_fund_urls.csv")
    parser.add_argument("--raw-dir", default="data/raw/html")
    parser.add_argument("--output", default="data/raw/universo_kinea_raw.csv")
    parser.add_argument("--only-pending", action="store_true",
                         help="Coleta somente linhas com status_confirmacao=identificado_pendente")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    input_csv = Path(args.input)
    raw_dir = Path(args.raw_dir)
    output_csv = Path(args.output)

    linhas = carregar_lista_urls(input_csv)
    if args.only_pending:
        linhas = [l for l in linhas if l.get("status_confirmacao") == "identificado_pendente"]

    if not linhas:
        print("Nenhuma URL para coletar (verifique --only-pending e o CSV de entrada).")
        sys.exit(0)

    registros = []
    for linha in linhas:
        print(f"Coletando: {linha['nome_referencia']} ...")
        registro = coletar_fundo(
            nome_referencia=linha["nome_referencia"],
            url=linha["url"],
            tipo_pagina=linha["tipo_pagina"],
            raw_dir=raw_dir,
        )
        if args.debug:
            print(json.dumps(asdict(registro), indent=2, ensure_ascii=False))
        registros.append(registro)
        time.sleep(REQUEST_DELAY_SECONDS)

    salvar_resultados(registros, output_csv)
    print(f"\n{len(registros)} fundo(s) processado(s). Saída: {output_csv}")
    erros = [r for r in registros if r.erro]
    if erros:
        print(f"AVISO: {len(erros)} fundo(s) com erro de coleta - ver coluna 'erro' no output.")


if __name__ == "__main__":
    main()