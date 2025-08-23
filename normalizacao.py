import os
import json
import requests
import datetime
from docx import Document

# === CONFIG ===
FOLDER_PATH = "medico"

output_dir = os.path.join(os.path.dirname(__file__), "output")

# Texto alvo a ser removido (string1)
STRING1 = (
    " FASE 2️⃣\n"
    "Documentos necessários: \n"
    "✅Carteira de identidade frente e verso: anexo\n"
    "✅Carteira CRM frente/verso: declaração anexo\n"
    "✅Diploma medicina: certificado anexo\n"
    "✅Certidão de Casamento (se casado): anexo\n"
    "✅Comprovante de endereço: anexo\n"
    "✅PIS / Carteira de trabalho : PIS 12964420094 carteira anexo\n"
    "✅ Certificado de residência médica OU declaraçao de residência médica EM CURSO\n"
    "✅ Certificado de especialidade/pós graduação: anexo \n"
    "✅Certificados de cursos diversos (ACLS, ATLS, PALS ou qualquer outro): anexo\n"
    "✅Currículo atualizado: anexo\n"
    "Esses documentos devem ser entregues até 20/05/2021. Podem ser enviados escaneados ou digitalizados para o email OU para meu WhatsApp.\n"
    "medicals.apoio@gmail.com\n"
    "Qualquer dúvida entre em contato comigo\n"
    "☎️ 027 99937-6146 "
)

def read_docx(file_path):
    """Extracts text from a .docx file."""
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])



def main():
    # ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # master output file path
    master = os.path.join(output_dir, "all_texts.txt")

    # Clear/truncate the master output file before starting
    try:
        with open(master, "w", encoding="utf-8") as mf:
            mf.write("")
        print(f"Cleared master file: {master}")
    except Exception as e:
        print(f"Warning: could not clear master file {master}: {e}")

    # compute absolute folder path for source DOCX files
    source_dir = os.path.join(os.path.dirname(__file__), FOLDER_PATH)

    for filename in os.listdir(source_dir):
        if filename.lower().endswith(".docx"):
            file_path = os.path.join(source_dir, filename)
            print(f"\n--- Processing: {filename} ---")
            
            text = read_docx(file_path)

            if not text.strip():
                print("File is empty or contains no extractable text.")
                continue
            
            try:
                file_size = os.path.getsize(file_path)
            except OSError:
                file_size = None

            try:
                mtime_ts = os.path.getmtime(file_path)
                mtime = datetime.datetime.fromtimestamp(mtime_ts, datetime.UTC).isoformat() + "Z"
            except OSError:
                mtime = None

            extraction_time = datetime.datetime.now(datetime.UTC).isoformat() + "Z"
            word_count = len(text.split())

            with open(master, "a", encoding="utf-8") as mf:
                mf.write(f"---- {filename} ----\n")
                mf.write(text.rstrip() + "\n")
                mf.write(f"---------------------------------\n\n")


def normalizacao(
    input_file: str | None = None,
    output_file: str | None = None,
    target: str | None = None,
    fuzzy: bool = False,
) -> str:
    """Remove todas as ocorrências de `target` do arquivo de entrada e grava em `output_file`.

    Args:
        input_file: Caminho do arquivo de origem (default: output/all_texts.txt)
        output_file: Caminho do arquivo normalizado (default: output/normalizado.txt)
        target: Texto alvo para remoção (default: STRING1)

    Returns:
        Caminho do arquivo gerado.
    """
    if input_file is None:
        input_file = os.path.join(output_dir, "all_texts.txt")
    if output_file is None:
        output_file = os.path.join(output_dir, "normalizado.txt")
    if target is None:
        target = STRING1

    # Garante diretório
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = f.read()
    except FileNotFoundError:
        print(f"Arquivo de entrada não encontrado: {input_file}")
        return output_file

    if not fuzzy:
        occurrences = data.count(target)
        if occurrences:
            print(f"Removendo {occurrences} ocorrência(s) do texto alvo (exato).")
            data = data.replace(target, "")
        else:
            print("Nenhuma ocorrência exata do texto alvo encontrada.")
    else:
        print("Modo fuzzy ativado: tentando remover variantes do bloco alvo.")
        data = _remove_fuzzy_blocks(data, target)

    # Opcional: limpar múltiplas quebras de linha geradas pela remoção
    # Reduz 3+ quebras seguidas para 2
    import re
    data = re.sub(r"\n{3,}", "\n\n", data)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(data)

    print(f"Arquivo normalizado criado em: {output_file}")
    return output_file


# === Fuzzy helpers ===
import re
import unicodedata
from typing import Iterable


def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


STOPWORD_PATTERN = re.compile(r"\b(anexo|v)\b", re.IGNORECASE)
MULTI_NL = re.compile(r"\n{3,}")


def _normalize_for_compare(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = _strip_accents(s.lower())
    # remove variation selectors
    s = s.replace("️", "")  # common VS16 leftover
    # remove punctuation we don't care about
    s = re.sub(r"[,:.;()-]+", " ", s)
    # remove stopwords
    s = STOPWORD_PATTERN.sub(" ", s)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _token_set(s: str) -> set[str]:
    return set(_normalize_for_compare(s).split())


def _similar_tokens(a: str, b: str, threshold: float = 0.7) -> bool:
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    base = max(len(ta), len(tb))
    ratio = inter / base
    return ratio >= threshold


BLOCK_REGEX = re.compile(
    r"(?s)(FASE\s*2[^\n]*\n(?:.(?!\n----))*?(?=(?:\n\s*\n)|\n---- |\nFICHA|$))",
    re.IGNORECASE,
)


def _remove_fuzzy_blocks(text: str, target: str) -> str:
    norm_target = _normalize_for_compare(target)
    removals: list[tuple[int, int]] = []
    for m in BLOCK_REGEX.finditer(text):
        block = m.group(1)
        # quick filter: must contain several checkmarks
        if block.count("✅") < 4:
            continue
        norm_block = _normalize_for_compare(block)
        if norm_block == norm_target or _similar_tokens(block, target):
            removals.append((m.start(), m.end()))
    if not removals:
        print("Nenhuma variante compatível encontrada para remoção.")
        return text
    # merge overlaps
    merged: list[tuple[int, int]] = []
    for start, end in sorted(removals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][start], max(merged[-1][1], end))  # type: ignore
    # apply removals
    new_text_parts = []
    last = 0
    for start, end in merged:
        new_text_parts.append(text[last:start])
        last = end
    new_text_parts.append(text[last:])
    cleaned = "".join(new_text_parts)
    cleaned = MULTI_NL.sub("\n\n", cleaned)
    print(f"Removidos {len(removals)} bloco(s) variante(s).")
    return cleaned



if __name__ == "__main__":
    main()
    # Executa normalização após gerar o all_texts.txt
    normalizado_path = normalizacao(fuzzy=True)


