"""Gera dicionário/JSON/CSV a partir do arquivo `normalizado.txt`.

Formato de saída solicitado:
{
  "medico": {
       "filename": [list[str]],
       "textsnippet": [list[str]]
  }
}

O arquivo de entrada contém blocos delimitados por linhas no padrão:
---- <NOME DO ARQUIVO>.docx ----

Cada bloco até o próximo cabeçalho (ou EOF) é associado ao respectivo filename.
"""

from __future__ import annotations

import os
import json
import csv
from dataclasses import dataclass
from typing import Iterator


output_dir = os.path.join(os.path.dirname(__file__), "output")
normalizado_path = os.path.join(output_dir, "normalizado.txt")


@dataclass
class Snippet:
    filename: str
    text: str


HEADER_PREFIX = "---- "
HEADER_SUFFIX = " ----"


def _iter_snippets(path: str) -> Iterator[Snippet]:
    """Itera sobre cada snippet extraído do arquivo normalizado.

    Regras:
      - Cabeçalho exatamente em uma linha começando com '---- ' e terminando com ' ----' (pode conter qualquer texto entre eles)
      - Tudo até o próximo cabeçalho (exclusivo) pertence ao snippet atual.
    """
    current_name: str | None = None
    buffer: list[str] = []

    def flush():
        if current_name is not None:
            # Remove linhas em branco extras no fim
            while buffer and buffer[-1].strip() == "":
                buffer.pop()
            yield Snippet(current_name, "\n".join(buffer).rstrip())

    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\n")
            if line.startswith(HEADER_PREFIX) and line.endswith(HEADER_SUFFIX):
                # Encontramos novo cabeçalho: descarrega o anterior
                if current_name is not None:
                    yield from flush()
                # Extrai nome entre prefixo e sufixo
                current_name = line[len(HEADER_PREFIX):-len(HEADER_SUFFIX)].strip()
                buffer = []
            else:
                buffer.append(line)
    # EOF
    if current_name is not None:
        yield from flush()


def text_to_csv(normalizado: str | None = None) -> dict:
    """Cria o dicionário exigido e grava arquivos JSON e CSV.

    Args:
        normalizado: caminho do arquivo normalizado (default: output/normalizado.txt)
    Returns:
        dict conforme especificação.
    """

    if normalizado is None:
        normalizado = normalizado_path

    if not os.path.exists(normalizado):
        raise FileNotFoundError(f"Arquivo não encontrado: {normalizado}")

    filenames: list[str] = []
    texts: list[str] = []

    for snip in _iter_snippets(normalizado):
        filenames.append(snip.filename)
        texts.append(snip.text)

    resultado = {"medico": {"filename": filenames, "textsnippet": texts}}

    # Garante diretório de saída
    os.makedirs(output_dir, exist_ok=True)

    # Salva JSON
    json_path = os.path.join(output_dir, "snippets.json")
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(resultado, jf, ensure_ascii=False, indent=2)

    # Salva CSV
    csv_path = os.path.join(output_dir, "snippets.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as cf:
        writer = csv.writer(cf, delimiter=",", quotechar='"', quoting=csv.QUOTE_ALL)
        writer.writerow(["filename", "textsnippet"])
        for fn, txt in zip(filenames, texts):
            writer.writerow([fn, txt])

    return resultado


if __name__ == "__main__":
    data = text_to_csv()
    print(f"Gerados {len(data['medico']['filename'])} snippets. Arquivos: snippets.json e snippets.csv em {output_dir}")
