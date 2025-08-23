import re
from typing import List, Dict

# --- regex util para telefones (várias formas brasileiras) ---
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

def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s, flags=re.UNICODE).strip().strip(" ;.-")

def extract_address_email_contacts(text: str) -> Dict[str, List[str]]:
    """
    Retorna listas por campo (podem ser vazias):
      endereco, crm, email, telefone, telefone_emergencia,
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

    # ENDEREÇO: após "Endereço", até antes de "CEP" (mesma linha ou linha seguinte)
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
        # remove ' ; CEP ...' caso CEP venha na mesma linha
        addr = re.sub(r"\s*[;,.]?\s*CEP\b.*$", "", addr, flags=re.IGNORECASE)
        if addr:
            res["endereco"].append(addr)

    # CRM-ES: aceita com ou sem ponto
    for m in re.finditer(r"CRM-ES\s*[:\-]?\s*([\d\.]+)", text, re.IGNORECASE):
        res["crm"].append(m.group(1))

    # E-MAIL: genérico e case-insensitive
    for m in re.finditer(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE):
        res["email"].append(m.group(0))

    # TELEFONE (não-emergência): apenas linhas iniciadas por Tel/TEL
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

        # tipos: 1) textos entre parênteses que contenham letras (ex.: "(MARIDO)")
        paren_texts = re.findall(r"\(([^)]+)\)", line_text)
        added_from_paren = False
        for t in paren_texts:
            if re.search(r"[A-Za-zÀ-ÿ]", t):
                tipos_emerg.append(_norm_space(t))
                added_from_paren = True

        # 2) se não houver parenteses "textuais", usa o trecho textual antes do 1º dígito
        if not added_from_paren:
            after_colon = re.split(r":", line_text, maxsplit=1)
            tail = after_colon[1] if len(after_colon) > 1 else after_colon[0]
            cut = re.split(r"\d", tail, maxsplit=1)[0]  # até o 1º dígito
            candidate = _norm_space(cut).strip(" :;.,-–•(").strip()
            if re.search(r"[A-Za-zÀ-ÿ]", candidate):
                tipos_emerg.append(candidate)

    if telefones_emerg:
        res["telefone_emergencia"] = telefones_emerg
    if tipos_emerg:
        res["tipo_contato_emergencia"] = tipos_emerg

    # CARGA HORÁRIA SEMANAL (se vier vazia, não adiciona)
    for m in re.finditer(r"Carga\s+hor[aá]ria\s+semanal\s*[:\-]\s*(.+)", text, re.IGNORECASE):
        val = _norm_space(m.group(1))
        if val:
            res["carga_horaria_semanal"].append(val)

    return res


# ---------------- EXEMPLO DE USO ----------------
# 'blocos' deve ser uma lista de strings, cada uma contendo um layout.
blocos = [
    """- Endereço com CEP: Rua Jequié, nº 1 - Bairro Jardim Atlântico - Serra/ES; CEP 29175-261
- CRM-ES: 18.238
- E-mail: deborah_bento@hotmail.com
- Carga horária semanal: """,
    """ENDEREÇO COMPLETO: RUA ENSEADA CARIOCA,101, ITAPARICA, VILA VELHA-ES
CEP: 29.102-312
EMAIL:  
TEL: 28 99909 8583
CONTATO DE URGÊNCIA: 27 99758 7424""",
    """ENDEREÇO COMPLETO:RUA ASTROGILDO ROMÃO DOS ANJOS
CEP: 29090580
CRM-ES: 21659
EMAIL: Victoribeiros07@Gmail.com
TEL: 27 997675592
CONTATO DE URGÊNCIA: 998112617 (JOSÉ CARLOS)""",
    """ENDEREÇO COMPLETO: RUA CHAFIC MURAD, 43. BENTO FERREIRA, VITORIA - ES. APTO 803
CEP: 29050660
CRM-ES: 21790
EMAIL: ESGALAVOTTI@GMAIL.COM
TEL: 27 99926-5006
CONTATO DE URGÊNCIA: 27 997252185 (MARIDO)""",
    """ENDEREÇO COMPLETO: Rua Carijós 180, Apto 304, Jardim da Penha, Vitória - ES
CEP: 29060-700
CRM-ES: 21.576
EMAIL:  
TEL: (27) 99821-3918 
CONTATO DE URGÊNCIA: Uéliton (27) 98151-6794""",
    """- Endereço completo: RUA DESEMBARGADOR AUGUSTO BOTELHO 688 PRAIA DA COSTA VV-ES
- CEP: 29101110
- CRM-ES: 21811
- E-mail: ELKJAER.LOURENCO.MED@GMAIL.COM
- Tel: 27997413701
- Possui carro próprio  ( X  ) SIM    (      ) NÃO 
- Modelo: FIESTA PRATA
- Placa:  ODO9J25
- Em caso de necessidade, ligar para: 27995283029
- Tel. do contato de urgência: 27992411027""",
    """- Endereço completo: Av. Francisco Generoso da Fonseca, 951, Apto 203, Jardim da Penha, Vitória-ES
- CEP: 29060-140
- CRM-ES: 21072
- E-mail: alexandrebonela@gmail.com 
- Tel: (28) 99996-9102
- Possui carro/moto próprio  ( x ) SIM    (      ) NÃO 
- Modelo: Honda PXC
- Placa: RQO9A46
- Em caso de necessidade, ligar para: (28) 99996-1065 (Reni – Mãe)
- Tel. do contato de urgência: (27) 99626-3132 (Ana Clara – Namorada)""",
]

# JSON de saída: para cada campo, uma lista com o resultado do respectivo bloco (ou []).
saida = {
    "endereco": [],
    "crm": [],
    "email": [],
    "telefone": [],
    "telefone_emergencia": [],
    "tipo_contato_emergencia": [],
    "carga_horaria_semanal": [],
}

for bloco in blocos:
    extra = extract_address_email_contacts(bloco)
    for k in saida:
        # append da lista (possivelmente vazia) daquele campo para este bloco
        saida[k].append(extra.get(k, []))

print(saida)  # descomente para ver o resultado
