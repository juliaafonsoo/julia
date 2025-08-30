#!/usr/bin/env python3
"""
Script unificado para processamento de documentos médicos.

Este script combina as funcionalidades de:
- normalizacao.py: Extração e normalização de textos DOCX
- contacts.py: Extração de contatos e endereços 
- extraimedico.py: Extração de informações pessoais e profissionais

Uso:
    python processador_medico_unificado.py
"""

import os
import re
import json
import datetime
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Dict, Optional
from docx import Document

# =============================================================================
# CONFIGURAÇÕES GLOBAIS
# =============================================================================

FOLDER_PATH = "medico"
output_dir = os.path.join(os.path.dirname(__file__), "output")

# Delimitador usado entre textos no arquivo normalizado
DELIMITADOR = "---------------------------------\n\n"

# Texto alvo a ser removido durante normalização (FASE 2)
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

# Placeholders para dados não encontrados
PLACEHOLDER_CADASTRO = "CADASTRO nao detectado"
PLACEHOLDER_FORMACAO = "FORMACAO PROFISSIONAL nao detectada"
PLACEHOLDER_RECEBIMENTO = "RECEBIMENTO nao detectado"
PLACEHOLDER_CPF = "CPF nao detectado"
PLACEHOLDER_CNS = "CNS nao detectado"
PLACEHOLDER_MAE = "MAE nao detectada"
PLACEHOLDER_PAI = "PAI nao detectado"
PLACEHOLDER_DT_NASC = "DATA_NASCIMENTO nao detectada"
PLACEHOLDER_NOME = "NOME nao detectado"

# Flags regex comuns
FLAGS = re.IGNORECASE | re.UNICODE | re.MULTILINE

# =============================================================================
# REGEX PATTERNS E CONSTANTES
# =============================================================================

# Padrões para extração de dados
CPF_CANDIDATO_RE = re.compile(r"[\d.\-]{11,18}")
QUINZE_DIGITOS_RE = re.compile(r"\d{15}")
FORMACAO_RE = re.compile(r"FORMA[ÇC][AÃ]O PROFISSIONAL", re.IGNORECASE)
RECEBIMENTO_RE = re.compile(r"RECEBIMENTO", re.IGNORECASE)

# Regex para telefones brasileiros
PHONE_RX = re.compile(
    r"""
    (?:(?:\+?55)\s*)?                # opcional DDI
    (?:\(?\d{2}\)?\s*)?              # opcional DDD
    (?:                              # número local
        \d{5}[-\s]?\d{4}             # 5+4 (celular)
        | \d{4}[-\s]?\d{4}           # 4+4 (fixo)
        | \d{8,9}                    # 8 ou 9 dígitos colados
    )
    """,
    re.VERBOSE,
)

# Padrões para datas
DATA_REGEXES = [
    re.compile(r"\b(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{2,4})\b"),
    re.compile(r"\b(\d{1,2})[\-/\.](\d{1,2})(\d{4})\b"),
    re.compile(r"\b(\d{2})(\d{2})(\d{4})\b"),
]

# Padrões para normalização fuzzy
STOPWORD_PATTERN = re.compile(r"\b(anexo|v)\b", re.IGNORECASE)
MULTI_NL = re.compile(r"\n{3,}")
BLOCK_REGEX = re.compile(
    r"(?s)(FASE\s*2[^\n]*\n(?:.(?!\n----))*?(?=(?:\n\s*\n)|\n---- |\nFICHA|$))",
    re.IGNORECASE,
)

# =============================================================================
# FUNÇÕES UTILITÁRIAS
# =============================================================================

def _norm_space(s: str) -> str:
    """Normaliza espaços em branco."""
    return re.sub(r"\s+", " ", s, flags=re.UNICODE).strip().strip(" ;.-")

def _strip_accents(s: str) -> str:
    """Remove acentos preservando demais caracteres."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")

def _dedup(seq: Iterable[str]) -> List[str]:
    """Remove duplicatas preservando ordem."""
    seen: set[str] = set()
    out: List[str] = []
    for x in seq:
        if not x:
            continue
        val = x.strip()
        if not val:
            continue
        k = val.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(val)
    return out

def _extrair_valor_pos_label(line: str) -> Optional[str]:
    """Extrai valor após ':' em uma linha."""
    parts = line.split(":", 1)
    if len(parts) == 2:
        valor = parts[1].strip()
        return valor or None
    return None

def _normalizar_data(d: int, m: int, y: int) -> Optional[str]:
    """Normaliza data para formato ISO (YYYY-MM-DD)."""
    try:
        if y < 100:  # ano 2 dígitos
            y = 1900 + y if y >= 30 else 2000 + y
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return None

# =============================================================================
# MÓDULO 1: EXTRAÇÃO E NORMALIZAÇÃO DE TEXTOS DOCX
# =============================================================================

def read_docx(file_path: str) -> str:
    """Extrai texto de um arquivo .docx."""
    doc = Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])

def extrair_todos_textos() -> str:
    """Extrai texto de todos os arquivos DOCX na pasta e salva em all_texts.txt."""
    # Garante que o diretório de saída existe
    os.makedirs(output_dir, exist_ok=True)

    # Arquivo de saída principal
    master = os.path.join(output_dir, "all_texts.txt")

    # Limpa o arquivo antes de começar
    try:
        with open(master, "w", encoding="utf-8") as mf:
            mf.write("")
        print(f"Arquivo principal limpo: {master}")
    except Exception as e:
        print(f"Aviso: não foi possível limpar {master}: {e}")

    # Diretório dos arquivos DOCX
    source_dir = os.path.join(os.path.dirname(__file__), FOLDER_PATH)

    for filename in os.listdir(source_dir):
        if filename.lower().endswith(".docx"):
            file_path = os.path.join(source_dir, filename)
            print(f"\n--- Processando: {filename} ---")
            
            text = read_docx(file_path)

            if not text.strip():
                print("Arquivo vazio ou sem texto extraível.")
                continue

            with open(master, "a", encoding="utf-8") as mf:
                mf.write(f"---- {filename} ----\n")
                mf.write(text.rstrip() + "\n")
                mf.write(f"---------------------------------\n\n")

    print(f"Textos extraídos salvos em: {master}")
    return master

def _normalize_for_compare(s: str) -> str:
    """Normaliza string para comparação fuzzy."""
    s = unicodedata.normalize("NFKC", s)
    s = _strip_accents(s.lower())
    s = s.replace("️", "")  # remove variation selectors
    s = re.sub(r"[,:.;()-]+", " ", s)
    s = STOPWORD_PATTERN.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _token_set(s: str) -> set[str]:
    """Converte string em conjunto de tokens."""
    return set(_normalize_for_compare(s).split())

def _similar_tokens(a: str, b: str, threshold: float = 0.7) -> bool:
    """Verifica se duas strings são similares baseado em tokens."""
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return False
    inter = len(ta & tb)
    base = max(len(ta), len(tb))
    ratio = inter / base
    return ratio >= threshold

def _remove_fuzzy_blocks(text: str, target: str) -> str:
    """Remove blocos similares ao target usando matching fuzzy."""
    norm_target = _normalize_for_compare(target)
    removals: list[tuple[int, int]] = []
    
    for m in BLOCK_REGEX.finditer(text):
        block = m.group(1)
        if block.count("✅") < 4:
            continue
        norm_block = _normalize_for_compare(block)
        if norm_block == norm_target or _similar_tokens(block, target):
            removals.append((m.start(), m.end()))
    
    if not removals:
        print("Nenhuma variante compatível encontrada para remoção.")
        return text
    
    # Merge overlaps
    merged: list[tuple[int, int]] = []
    for start, end in sorted(removals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    
    # Apply removals
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

def normalizar_textos(
    input_file: str | None = None,
    output_file: str | None = None,
    target: str | None = None,
    fuzzy: bool = False,
) -> str:
    """Remove ocorrências do texto alvo e normaliza o arquivo."""
    if input_file is None:
        input_file = os.path.join(output_dir, "all_texts.txt")
    if output_file is None:
        output_file = os.path.join(output_dir, "normalizado.txt")
    if target is None:
        target = STRING1

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

    # Limpar múltiplas quebras de linha
    data = re.sub(r"\n{3,}", "\n\n", data)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(data)

    print(f"Arquivo normalizado criado em: {output_file}")
    return output_file

# =============================================================================
# MÓDULO 2: EXTRAÇÃO DE CONTATOS E ENDEREÇOS
# =============================================================================

def extract_address_email_contacts(text: str) -> Dict[str, List[str]]:
    """
    Extrai informações de contato de um texto.
    
    Retorna:
        Dict com listas para: endereco, crm, email, telefone, telefone_emergencia,
        tipo_contato_emergencia, carga_horaria_semanal
    """
    res = {
        "endereco": [],
        "crm": [],
        "email": [],
        "telefone": [],
        "telefone_emergencia": [],
        "tipo_contato_emergencia": [],
        "carga_horaria_semanal": [],
    }

    # ENDEREÇO
    endereco_pat = re.compile(
        r"""
        ^\s*[-–•]?\s*
        Endere[cç]o                 # 'Endereço' (com/sem acento)
        (?:\s+completo)?            # 'completo' opcional
        (?:\s+com\s+CEP)?           # 'com CEP' opcional
        \s*[:\-]\s*
        (.+?)                       # conteúdo do endereço
        \s*(?=^\s*CEP\b|$)          # para quando 'CEP' está na próxima linha
        """,
        re.IGNORECASE | re.MULTILINE | re.VERBOSE | re.DOTALL,
    )
    for m in endereco_pat.finditer(text):
        addr = _norm_space(m.group(1))
        addr = re.sub(r"\s*[;,.]?\s*CEP\b.*$", "", addr, flags=re.IGNORECASE)
        if addr:
            res["endereco"].append(addr)

    # CRM-ES
    for m in re.finditer(r"CRM-ES\s*[:\-]?\s*([\d\.]+)", text, re.IGNORECASE):
        res["crm"].append(m.group(1))

    # E-MAIL
    for m in re.finditer(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE):
        res["email"].append(m.group(0))

    # TELEFONE (não-emergência)
    tel_line_pat = re.compile(r"(?im)^\s*[-–•]*\s*(?:Tel\.?|TEL)\s*:?.*$")
    telefones = []
    for line in tel_line_pat.finditer(text):
        line_text = line.group(0)
        if re.search(r"contato\s+de\s+urg[êe]ncia", line_text, flags=re.IGNORECASE):
            continue
        for m in PHONE_RX.finditer(line_text):
            telefones.append(_norm_space(m.group(0)))
    if telefones:
        res["telefone"] = telefones

    # TELEFONE DE EMERGÊNCIA + TIPO/NOME
    emerg_line_pat = re.compile(
        r"(?im)^\s*[-–•]*\s*(?:CONTATO\s+DE\s+URG[ÊE]NCIA|Em\s+caso\s+de\s+necessidade,\s*ligar\s+para|Tel\.?\s*do\s+contato\s+de\s+urg[êe]ncia)\s*:?.*$"
    )
    telefones_emerg, tipos_emerg = [], []
    for line in emerg_line_pat.finditer(text):
        line_text = line.group(0)

        # telefones
        for m in PHONE_RX.finditer(line_text):
            telefones_emerg.append(_norm_space(m.group(0)))

        # tipos: textos entre parênteses que contenham letras
        paren_texts = re.findall(r"\(([^)]+)\)", line_text)
        added_from_paren = False
        for t in paren_texts:
            if re.search(r"[A-Za-zÀ-ÿ]", t):
                tipos_emerg.append(_norm_space(t))
                added_from_paren = True

        # se não houver parenteses "textuais", usa o trecho textual antes do 1º dígito
        if not added_from_paren:
            after_colon = re.split(r":", line_text, maxsplit=1)
            tail = after_colon[1] if len(after_colon) > 1 else after_colon[0]
            cut = re.split(r"\d", tail, maxsplit=1)[0]
            candidate = _norm_space(cut).strip(" :;.,-–•(").strip()
            if re.search(r"[A-Za-zÀ-ÿ]", candidate):
                tipos_emerg.append(candidate)

    if telefones_emerg:
        res["telefone_emergencia"] = telefones_emerg
    if tipos_emerg:
        res["tipo_contato_emergencia"] = tipos_emerg

    # CARGA HORÁRIA SEMANAL
    for m in re.finditer(r"Carga\s+hor[aá]ria\s+semanal\s*[:\-]\s*(.+)", text, re.IGNORECASE):
        val = _norm_space(m.group(1))
        if val:
            res["carga_horaria_semanal"].append(val)

    return res

# =============================================================================
# MÓDULO 3: EXTRAÇÃO DE INFORMAÇÕES PESSOAIS E PROFISSIONAIS
# =============================================================================

def extrai_secao(bloco: str) -> Dict[str, str]:
    """Extrai seções 'cadastro', 'formacao' e 'recebimento' de um bloco de texto."""
    cadastro = ""
    formacao = None
    recebimento = None

    m_form = FORMACAO_RE.search(bloco)
    m_receb = RECEBIMENTO_RE.search(bloco)

    if m_form and (not m_receb or m_form.start() < m_receb.start()):
        cadastro = bloco[:m_form.start()].strip()
        if m_receb and m_receb.start() > m_form.start():
            formacao = bloco[m_form.start():m_receb.start()].strip()
            recebimento = bloco[m_receb.start():].strip()
        else:
            formacao = bloco[m_form.start():].strip()
    else:
        if m_receb:
            cadastro = bloco[:m_receb.start()].strip()
            recebimento = bloco[m_receb.start():].strip()
        else:
            cadastro = bloco.strip()

    if not cadastro:
        cadastro = bloco.strip() or PLACEHOLDER_CADASTRO
    if formacao is None:
        formacao = PLACEHOLDER_FORMACAO
    if recebimento is None:
        recebimento = PLACEHOLDER_RECEBIMENTO

    return {
        "cadastro": cadastro,
        "formacao": formacao,
        "recebimento": recebimento,
    }

def _normalizar_cpf_fragmento(fragmento: str) -> Optional[str]:
    """Normaliza fragmento de CPF para 11 dígitos."""
    digits = re.sub(r"\D", "", fragmento)
    if len(digits) == 11:
        return digits
    return None

def _extrair_cpf_de_linha(linha: str) -> List[str]:
    """Extrai CPFs válidos de uma linha."""
    candidatos = []
    for frag in CPF_CANDIDATO_RE.findall(linha):
        cpf_norm = _normalizar_cpf_fragmento(frag)
        if cpf_norm:
            candidatos.append(cpf_norm)
    return candidatos

def _encontrar_cpf_em_bloco(bloco: str) -> Optional[str]:
    """Encontra o primeiro CPF válido no bloco."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if "cpf" not in lower:
            continue
        if "pix" in lower:
            continue
        cpfs = _extrair_cpf_de_linha(line)
        if cpfs:
            return cpfs[0]
    return None

def _encontrar_cns_em_bloco(bloco: str) -> Optional[str]:
    """Encontra CNS (15 dígitos) no bloco."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if 'cns' not in lower:
            continue
        
        # Procurar 15 dígitos contíguos
        m = QUINZE_DIGITOS_RE.search(line.replace(" ", ""))
        if m:
            return m.group(0)
        
        # Se não houver contíguo, tentar reconstruir
        somente_digitos = re.sub(r"\D", "", line)
        if len(somente_digitos) >= 15:
            for i in range(0, len(somente_digitos) - 14):
                candidato = somente_digitos[i:i+15]
                return candidato
    return None

def _encontrar_nome_mae(bloco: str) -> Optional[str]:
    """Encontra nome da mãe no bloco."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "nome da mae" in lowered:
            return _extrair_valor_pos_label(line)
    return None

def _encontrar_nome_pai(bloco: str) -> Optional[str]:
    """Encontra nome do pai no bloco."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "nome do pai" in lowered or "nome da pai" in lowered:
            return _extrair_valor_pos_label(line)
    return None

def _encontrar_data_nascimento(bloco: str) -> Optional[str]:
    """Encontra e normaliza data de nascimento no bloco."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "data de nascimento" not in lowered:
            continue
        
        after = _extrair_valor_pos_label(line) or line
        
        for rx in DATA_REGEXES:
            m = rx.search(after)
            if not m:
                continue
            groups = m.groups()
            if len(groups) == 3:
                try:
                    d = int(groups[0])
                    mth = int(groups[1])
                    y = int(groups[2])
                except ValueError:
                    continue
                iso = _normalizar_data(d, mth, y)
                if iso:
                    return iso
        
        # Fallback: extrair dígitos e tentar heurística
        digits = re.sub(r"\D", "", after)
        if len(digits) >= 6:
            if len(digits) >= 8:
                try:
                    d = int(digits[0:2])
                    mth = int(digits[2:4])
                    y = int(digits[4:8])
                    iso = _normalizar_data(d, mth, y)
                    if iso:
                        return iso
                except ValueError:
                    pass
            elif len(digits) == 6:
                try:
                    d = int(digits[0:2])
                    mth = int(digits[2:4])
                    y = int(digits[4:6])
                    iso = _normalizar_data(d, mth, y)
                    if iso:
                        return iso
                except ValueError:
                    pass
        return None
    return None

def _encontrar_nome_profissional(bloco: str) -> Optional[str]:
    """Encontra nome do profissional no bloco."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "nome" not in lowered:
            continue
        if "mae" in lowered or "pai" in lowered:
            continue
        
        parts = line.split(":", 1)
        if len(parts) == 2:
            valor = parts[1].strip()
            if valor:
                return valor
        
        # Fallback
        m = re.search(r"nome\s+(.+)$", lowered, re.IGNORECASE)
        if m:
            candidato = raw_line[m.start(1):].strip()
            if candidato:
                return candidato
    return None

def extrair_informacoes_rg_ci(texto: str) -> Dict[str, List[str]]:
    """Extrai informações de RG e CI do texto."""
    resultado: Dict[str, List[str]] = {
        "rg": [], "uf_ci": [], "orgao_emissor_ci": [], 
        "data_emissao_ci": [], "endereco_nascimento": []
    }
    if not texto:
        return resultado

    # RG
    rg_patterns = [
        r'Número\s+identidade:\s*([0-9.]+)',
        r'RG\s*\([^)]*\):\s*([0-9.]+)-\w{1,3}',
        r'RG\s*\([^)]*\):\s*([0-9.]+)'
    ]
    for pat in rg_patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultado["rg"] = [m.group(1).replace('.', '')]
            break

    # UF CI
    uf_patterns = [
        r'UF\s*CI:\s*(\w{2})',
        r'RG\s*\([^)]*\):\s*[0-9.]+-(\w{2})',
        r'-\s*(\w{2})\s*/\s*\w+\s*/',
        r'-\s*(\w{2})\s*,\s*ÓRGÃO'
    ]
    for pat in uf_patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultado["uf_ci"] = [m.group(1).upper()]
            break

    # Órgão emissor CI
    orgao_patterns = [
        r'Órgão\s+emissor\s+CI:\s*([A-ZÀ-Ú]{2,10})',
        r'/\s*([A-ZÀ-Ú]{2,10})\s*/\s*\d{2}/\d{2}/\d{4}',
        r'ÓRGÃO\s+EMISSOR\s+([A-ZÀ-Ú]{2,10})',
        r'\b\w{2}\s*/\s*([A-ZÀ-Ú]{2,10})\s*/'
    ]
    for pat in orgao_patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultado["orgao_emissor_ci"] = [m.group(1).upper()]
            break

    # Data emissão CI
    data_patterns = [
        r'Data\s+de\s+emissão\s+CI:\s*(\d{2}/\d{2}/\d{4})',
        r'/\s*\w+\s*/\s*(\d{2}/\d{2}/\d{4})',
        r'DATA\s+EMISS[ÃA]O\s+(\d{2}/\d{2}/\d{4})'
    ]
    for pat in data_patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            resultado["data_emissao_ci"] = [m.group(1)]
            break

    # Município / UF nascimento
    municipio = None
    uf_nasc = None
    municipio_patterns = [
        r'Município\s+de\s+nascimento:\s*([^\n-]+)',
        r'MUNIC[IÍ]PIO\s+DE\s+NASCIMENTO:\s*([^\n]+)'
    ]
    for pat in municipio_patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            municipio = m.group(1).strip().rstrip(' .;')
            break
    
    uf_nasc_patterns = [
        r'UF\s*DE\s+NASCIMENTO:\s*(\w{2})',
        r'UF\s+de\s+nascimento:\s*(\w{2})',
        r'UF:\s*(\w{2})\b'
    ]
    for pat in uf_nasc_patterns:
        m = re.search(pat, texto, re.IGNORECASE)
        if m:
            uf_nasc = m.group(1).upper()
            break
    
    if municipio and uf_nasc:
        resultado["endereco_nascimento"] = [f"{municipio} - {uf_nasc}"]
    elif municipio:
        resultado["endereco_nascimento"] = [municipio]
    
    return resultado

def extract_estado_civil(text: str) -> List[str]:
    """Extrai estado civil do texto."""
    norm = text.replace("\xa0", " ")
    norm = re.sub(r"[ \t]+", " ", norm)

    pat_estado = re.compile(
        r"^(?:-\s*)?estado\s*civil\s*:\s*([^\r\n]+?)\s*$",
        FLAGS
    )
    encontrados = [m.group(1).strip() for m in pat_estado.finditer(norm)]
    estado_civil = _dedup(encontrados)

    return estado_civil

@dataclass
class BlocoAudit:
    """Classe para auditoria de blocos processados."""
    cpf: str
    nome: Optional[str] = None

# =============================================================================
# FUNÇÃO PRINCIPAL DE PROCESSAMENTO
# =============================================================================

def processar_documentos_medicos(caminho_normalizado: Optional[str] = None) -> Dict[str, Dict]:
    """
    Função principal que processa todos os documentos médicos.
    
    Returns:
        Dict com todos os dados extraídos organizados por médico.
    """
    if caminho_normalizado is None:
        caminho_normalizado = os.path.join(output_dir, "normalizado.txt")

    resultado: Dict[str, Dict] = {"medico": {"blocos": []}}
    cns_nao_detectados: List[Dict] = []
    mae_nao_detectados: List[Dict] = []
    pai_nao_detectados: List[Dict] = []
    dt_nasc_nao_detectados: List[Dict] = []
    vistos: set[str] = set()

    try:
        with open(caminho_normalizado, "r", encoding="utf-8") as f:
            conteudo = f.read()
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {caminho_normalizado}")
        return resultado

    # Separa blocos pelos delimitadores
    blocos = [b.strip() for b in conteudo.split(DELIMITADOR) if b.strip()]

    for bloco in blocos:
        # Extrai seções do bloco
        secoes = extrai_secao(bloco)
        cadastro_txt = secoes.get("cadastro", "")

        # Extrai informações básicas
        cpf = _encontrar_cpf_em_bloco(cadastro_txt) or PLACEHOLDER_CPF
        if cpf != PLACEHOLDER_CPF and cpf not in vistos:
            vistos.add(cpf)

        nome = _encontrar_nome_profissional(cadastro_txt) or PLACEHOLDER_NOME
        cns = _encontrar_cns_em_bloco(cadastro_txt) or PLACEHOLDER_CNS
        
        if cns == PLACEHOLDER_CNS:
            cns_nao_detectados.append({"nome": nome, "cpf": cpf})

        # Extrai informações familiares
        nome_mae = _encontrar_nome_mae(cadastro_txt)
        if not nome_mae:
            mae_nao_detectados.append({"cpf": cpf})
            nome_mae = PLACEHOLDER_MAE
            
        nome_pai = _encontrar_nome_pai(cadastro_txt)
        if not nome_pai:
            pai_nao_detectados.append({"cpf": cpf})
            nome_pai = PLACEHOLDER_PAI

        # Data de nascimento
        data_nasc = _encontrar_data_nascimento(cadastro_txt)
        if not data_nasc:
            dt_nasc_nao_detectados.append({"cpf": cpf})
            data_nasc = PLACEHOLDER_DT_NASC

        # Extrai informações complementares
        rg_ci = extrair_informacoes_rg_ci(cadastro_txt) if cadastro_txt else {
            "rg": [], "uf_ci": [], "orgao_emissor_ci": [], 
            "data_emissao_ci": [], "endereco_nascimento": []
        }
        
        estado_civil = extract_estado_civil(cadastro_txt)
        
        contatos = extract_address_email_contacts(cadastro_txt) if cadastro_txt else {
            "endereco": [], "crm": [], "email": [], "telefone": [], 
            "telefone_emergencia": [], "tipo_contato_emergencia": [], 
            "carga_horaria_semanal": []
        }

        # Monta dicionário do bloco
        bloco_dict = {
            "nome": nome,
            "cpf": cpf,
            "cns": cns,
            "nome_mae": nome_mae,
            "nome_pai": nome_pai,
            "data_nascimento": data_nasc,
            "cadastro": secoes["cadastro"],
            "formacao": secoes["formacao"],
            "recebimento": secoes["recebimento"],
            "rg": rg_ci["rg"],
            "uf_ci": rg_ci["uf_ci"],
            "orgao_emissor_ci": rg_ci["orgao_emissor_ci"],
            "data_emissao_ci": rg_ci["data_emissao_ci"],
            "endereco_nascimento": rg_ci["endereco_nascimento"],
            "estado_civil": estado_civil,
            "endereco": contatos["endereco"],
            "crm": contatos["crm"],
            "email": contatos["email"],
            "telefone": contatos["telefone"],
            "telefone_emergencia": contatos["telefone_emergencia"],
            "tipo_contato_emergencia": contatos["tipo_contato_emergencia"],
            "carga_horaria_semanal": contatos["carga_horaria_semanal"],
        }
        resultado["medico"]["blocos"].append(bloco_dict)

    # Adiciona registros de auditoria
    resultado["medico"]["cns_nao_identificados"] = cns_nao_detectados
    resultado["medico"]["mae_nao_identificados"] = mae_nao_detectados
    resultado["medico"]["pai_nao_identificados"] = pai_nao_detectados
    resultado["medico"]["data_nascimento_nao_identificados"] = dt_nasc_nao_detectados

    return resultado

# =============================================================================
# FUNÇÃO PRINCIPAL DE EXECUÇÃO
# =============================================================================

def main():
    """Função principal que executa todo o pipeline de processamento."""
    print("=== PROCESSADOR MÉDICO UNIFICADO ===")
    print("Iniciando processamento completo...")
    
    try:
        # Etapa 1: Extração de textos dos arquivos DOCX
        print("\n1. Extraindo textos de arquivos DOCX...")
        extrair_todos_textos()
        
        # Etapa 2: Normalização dos textos
        print("\n2. Normalizando textos...")
        normalizado_path = normalizar_textos(fuzzy=True)
        
        # Etapa 3: Processamento e extração de dados
        print("\n3. Processando e extraindo dados...")
        dados = processar_documentos_medicos(normalizado_path)
        
        # Etapa 4: Salvamento dos resultados
        print("\n4. Salvando resultados...")
        cpfs_json_path = os.path.join(output_dir, "cpfs_blocos.json")
        
        with open(cpfs_json_path, "w", encoding="utf-8") as jf:
            json.dump(dados, jf, ensure_ascii=False, indent=2)
        
        print(f"Dados processados salvos em: {cpfs_json_path}")
        
        # Estatísticas finais
        total_blocos = len(dados["medico"]["blocos"])
        cns_nao_detectados = len(dados["medico"]["cns_nao_identificados"])
        mae_nao_detectadas = len(dados["medico"]["mae_nao_identificados"])
        pai_nao_detectados = len(dados["medico"]["pai_nao_identificados"])
        dt_nasc_nao_detectadas = len(dados["medico"]["data_nascimento_nao_identificados"])
        
        print(f"\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Total de blocos processados: {total_blocos}")
        print(f"CNS não detectados: {cns_nao_detectados}")
        print(f"Nomes de mãe não detectados: {mae_nao_detectadas}")
        print(f"Nomes de pai não detectados: {pai_nao_detectados}")
        print(f"Datas de nascimento não detectadas: {dt_nasc_nao_detectadas}")
        
        # Tentativa de gerar Excel (se disponível)
        try:
            import sys
            import importlib.util
            
            # Verifica se o módulo export_excel existe
            spec = importlib.util.find_spec("export_excel")
            if spec is not None:
                from export_excel import json_to_excel
                excel_out = os.path.join(output_dir, "cpfs_blocos.xlsx")
                json_to_excel(cpfs_json_path, excel_out)
                print(f"Arquivo Excel gerado: {excel_out}")
            else:
                print("Módulo export_excel não encontrado. Pulando geração de Excel.")
        except ImportError:
            print("Módulo export_excel não disponível. Pulando geração de Excel.")
        except Exception as e:
            print(f"Falha ao gerar Excel: {e}")
            
        print("\n=== PROCESSAMENTO CONCLUÍDO ===")
        
    except Exception as e:
        print(f"Erro durante o processamento: {e}")
        raise

if __name__ == "__main__":
    main()
