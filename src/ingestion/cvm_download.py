"""
cvm_download.py

Finalidade
----------
Baixa o cadastro de fundos de investimento da CVM (Dados Abertos, fonte
pública, sem login, sem bot-block). Baixa AS DUAS fontes necessárias:

1. registro_fundo_classe.zip - fundos/classes JÁ ADAPTADOS à Resolução
   CVM 175 (estrutura de classes/subclasses). Os fundos Kinea têm
   "Subclasse I/II" no nome - ou seja, já adaptados - e por isso só
   aparecem AQUI, não no cadastro legado (a CVM avisa explicitamente que
   fundos adaptados somem do arquivo legado).
2. cad_fi.csv - cadastro legado (fundos NÃO adaptados). Cobre concorrentes
   que ainda não migraram para a RCVM175.

Fonte oficial
-------------
https://dados.cvm.gov.br/dataset/fi-cad
Índice de arquivos: https://dados.cvm.gov.br/dados/FI/CAD/DADOS/
Atualização: manhãs de terça a sábado, posição do dia útil anterior.

Como executar
--------------
    python src/ingestion/cvm_download.py
"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import requests

CVM_CAD_FI_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"
CVM_REGISTRO_ZIP_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"


def _baixar(url: str, output_path: Path, timeout: int = 120) -> None:
    print(f"Baixando {url} ...")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(resp.content)

    meta_path = output_path.with_suffix(output_path.suffix + ".meta.txt")
    meta_path.write_text(
        f"source_url: {url}\n"
        f"access_timestamp: {datetime.now(timezone.utc).isoformat()}\n"
        f"tamanho_bytes: {len(resp.content)}\n",
        encoding="utf-8",
    )
    print(f"Salvo em {output_path} ({len(resp.content):,} bytes)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-legado", default="data/raw/cvm_cad_fi.csv")
    parser.add_argument("--output-novo", default="data/raw/cvm_registro_fundo_classe.zip")
    args = parser.parse_args()

    _baixar(CVM_REGISTRO_ZIP_URL, Path(args.output_novo))
    _baixar(CVM_CAD_FI_URL, Path(args.output_legado))


if __name__ == "__main__":
    main()
