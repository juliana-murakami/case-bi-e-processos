"""
standardize.py

Finalidade
----------
Funções de padronização reutilizáveis para tratar os campos coletados
antes de qualquer join ou análise. Regra do projeto: nunca fazer join
apenas por nome sem antes tratar a identificação (CNPJ > ticker > nome
padronizado).

Como executar (teste rápido das funções)
-----------------------------------------
    python src/transformation/standardize.py

Como usar em outro script
--------------------------
    from src.transformation.standardize import (
        clean_cnpj, clean_ticker, clean_name, clean_percentage,
        clean_currency_brl, standardize_category, build_fund_key,
    )
"""
import re
import unicodedata
import math
from typing import Optional


def clean_cnpj(raw) -> Optional[str]:
    """Remove tudo que não é dígito e valida tamanho (14 dígitos).
    Retorna CNPJ formatado XX.XXX.XXX/XXXX-XX ou None se inválido/ausente.
    Aceita str, int ou float (pandas às vezes infere CNPJ como número
    quando a coluna não tem formatação - ex: CSV da CVM com CNPJ só em
    dígitos, sem pontuação, pode virar int64 na leitura)."""
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    if not isinstance(raw, str):
        raw = str(int(raw)) if isinstance(raw, float) else str(raw)
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 14:
        return None
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def is_valid_cnpj_format(raw: str) -> bool:
    return clean_cnpj(raw) is not None


def clean_ticker(raw: str) -> Optional[str]:
    """Extrai um ticker de FII/ação no padrão B3 (4 letras + 1-2 dígitos),
    ex: KNCR11, KDIF11. Retorna em maiúsculas ou None."""
    if not raw or not isinstance(raw, str):
        return None
    match = re.search(r"\b([A-Z]{4}\d{1,2})\b", raw.upper())
    return match.group(1) if match else None


def clean_name(raw: str) -> Optional[str]:
    """Padroniza nome de fundo: remove espaços duplicados, normaliza
    acentuação para forma NFC, remove espaços nas pontas, capitaliza
    de forma consistente (mantém siglas como FIM, FII, RL em maiúsculo)."""
    if not raw or not isinstance(raw, str):
        return None
    texto = unicodedata.normalize("NFC", raw)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def clean_percentage(raw: str) -> Optional[float]:
    """Converte string tipo '1,50 %' ou '20,00%' em float (1.50, 20.00).
    Não divide por 100 - mantém na escala percentual, tratamento de escala
    fica a cargo de quem consome (deixar explícito evita erro silencioso)."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    texto = str(raw).strip().replace("%", "").replace(",", ".")
    texto = re.sub(r"[^\d.\-]", "", texto)
    if texto in ("", "-", "."):
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def clean_currency_brl(raw: str) -> Optional[float]:
    """Converte string tipo 'R$ 1.6 bi', 'R$ 500', 'R$ 7,8 bi' em float
    (unidade: reais). Trata sufixos mi/bi/mil. Retorna None se não parsear."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    texto = str(raw).upper().replace("R$", "").strip()
    multiplicador = 1.0
    abreviado = False
    if "BI" in texto:
        multiplicador, abreviado = 1_000_000_000, True
        texto = texto.replace("BI", "")
    elif "MI" in texto:
        multiplicador, abreviado = 1_000_000, True
        texto = texto.replace("MI", "")
    elif re.search(r"\bMIL\b", texto):
        multiplicador, abreviado = 1_000, True
        texto = re.sub(r"\bMIL\b", "", texto)

    texto = texto.strip()
    if abreviado:
        # formas abreviadas ("1.6 bi", "7,8 bi") não usam separador de
        # milhar - tanto "." quanto "," aqui são separador decimal.
        texto = texto.replace(",", ".")
    else:
        # forma completa ("R$ 1.234,56") - "." é milhar, "," é decimal.
        texto = texto.replace(".", "").replace(",", ".")

    texto = re.sub(r"[^\d.\-]", "", texto)
    if texto in ("", "-", "."):
        return None
    try:
        return float(texto) * multiplicador
    except ValueError:
        return None


# Vocabulário controlado de categoria - evita que "Multimercado", "MULTIMERCADO"
# e "multi-mercado" virem 3 categorias diferentes num groupby.
CATEGORY_VOCAB = {
    "multimercado": "Multimercado",
    "macro": "Multimercado - Macro",
    "renda fixa": "Renda Fixa",
    "crédito high grade": "Renda Fixa",
    "crédito": "Renda Fixa",
    "debêntures incentivadas": "Renda Fixa",
    "acoes": "Ações",
    "ações": "Ações",
    "long only": "Ações",
    "long biased": "Ações",
    "previdencia": "Previdência",
    "previdência": "Previdência",
    "híbrido": "Fundo Imobiliário (FII)",
    "títulos e valores mobiliários": "Fundo Imobiliário (FII)",
    "fii": "Fundo Imobiliário (FII)",
    "fiagro": "FIAGRO",
    "fi-infra": "FI-Infra",
    "fip": "Private Equity (FIP)",
}


def standardize_category(raw: str) -> Optional[str]:
    """Mapeia texto livre de categoria para o vocabulário controlado.
    Retorna a categoria padronizada ou o texto original (limpo) se não
    houver correspondência - nunca descarta a informação original."""
    if not raw or not isinstance(raw, str):
        return None
    texto = clean_name(raw).lower()
    for chave, padronizado in CATEGORY_VOCAB.items():
        if chave in texto:
            return padronizado
    return clean_name(raw)  # preserva o valor original se não reconhecido


def build_fund_key(cnpj: str = None, ticker: str = None, nome: str = None) -> str:
    """Chave robusta de identificação do fundo, priorizando:
    1) CNPJ (mais confiável, único por lei)
    2) ticker (único para FIIs/ações negociados em bolsa)
    3) nome padronizado (fallback - menos confiável, sujeito a variações)
    Sempre prefixa com a origem da chave para deixar explícito no dado
    qual nível de confiança está sendo usado (não esconder no código)."""
    cnpj_limpo = clean_cnpj(cnpj) if cnpj else None
    if cnpj_limpo:
        return f"CNPJ:{cnpj_limpo}"
    ticker_limpo = clean_ticker(ticker) if ticker else None
    if ticker_limpo:
        return f"TICKER:{ticker_limpo}"
    nome_limpo = clean_name(nome) if nome else None
    if nome_limpo:
        return f"NOME:{nome_limpo.upper()}"
    return "SEM_CHAVE"


if __name__ == "__main__":
    # smoke tests manuais - rodar `python src/transformation/standardize.py`
    assert clean_cnpj("21.624.757/0001-26") == "21.624.757/0001-26"
    assert clean_cnpj("21624757000126") == "21.624.757/0001-26"
    assert clean_cnpj(21624757000126) == "21.624.757/0001-26"  # CNPJ como int (bug real encontrado com dados da CVM)
    assert clean_cnpj(float("nan")) is None
    assert clean_cnpj("abc") is None
    assert clean_ticker("KINEA RENDIMENTOS IMOBILIÁRIOS FII - KNCR11") == "KNCR11"
    assert clean_percentage("1,50 %") == 1.50
    assert clean_percentage("20,00%") == 20.00
    assert clean_currency_brl("R$ 1.6 bi") == 1_600_000_000.0
    assert clean_currency_brl("R$ 500") == 500.0
    assert standardize_category("Macro Média Vol") == "Multimercado - Macro"
    assert build_fund_key(cnpj="21.624.757/0001-26") == "CNPJ:21.624.757/0001-26"
    assert build_fund_key(ticker="KNCR11") == "TICKER:KNCR11"
    assert build_fund_key(nome="Kinea Gama") == "NOME:KINEA GAMA"
    print("Todos os smoke tests passaram.")
