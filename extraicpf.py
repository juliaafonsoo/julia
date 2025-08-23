import os
import re
import json
import unicodedata
from typing import Dict, List

FOLDER_PATH = "medico"
output_dir = os.path.join(os.path.dirname(__file__), "output")

DELIMITADOR = "---------------------------------\n\n"  # delimitador exato entre textos

FLAGS = re.IGNORECASE | re.UNICODE | re.MULTILINE

CPF_CANDIDATO_RE = re.compile(r"[\d.\-]{11,18}")
QUINZE_DIGITOS_RE = re.compile(r"\d{15}")  # para localizar sequência exata de 15 dígitos

# Padrões para detectar as seções (aceitando variações com/sem acentos)
FORMACAO_RE = re.compile(r"FORMA[ÇC][AÃ]O PROFISSIONAL", re.IGNORECASE)
RECEBIMENTO_RE = re.compile(r"RECEBIMENTO", re.IGNORECASE)


def _normalizar_cpf_fragmento(fragmento: str) -> str | None:
    """Recebe um fragmento (ex: '123.456.789-09'), remove não dígitos.
    Retorna somente se tiver exatamente 11 dígitos."""
    digits = re.sub(r"\D", "", fragmento)
    if len(digits) == 11:
        return digits
    return None


def _extrair_cpf_de_linha(linha: str) -> list[str]:
    """Extrai possíveis CPFs de uma linha que já passou pelos filtros de conter 'cpf'
    e não conter 'pix'."""
    candidatos = []
    for frag in CPF_CANDIDATO_RE.findall(linha):
        cpf_norm = _normalizar_cpf_fragmento(frag)
        if cpf_norm:
            candidatos.append(cpf_norm)
    return candidatos


def _encontrar_cpf_em_bloco(bloco: str) -> str | None:
    """Varre o bloco inteiro e retorna o primeiro CPF encontrado segundo as regras:
       - linha contém 'cpf' (case-insensitive)
       - linha NÃO contém 'pix'
       - extrai o primeiro CPF válido dessa linha
    """
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
            return cpfs[0]  # primeiro CPF do bloco
    return None


def _encontrar_cns_em_bloco(bloco: str) -> str | None:
    """Procura em cada linha do bloco um CNS conforme regra:
       - a linha contém 'cns' (case-insensitive)
       - a própria linha deve conter ao menos uma sequência que, removendo não dígitos,
         resulte em exatamente 15 dígitos. Retorna a primeira encontrada.
       Retorna somente os dígitos (normalizado)."""
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if 'cns' not in lower:
            continue
        # Buscar todas as sequências de dígitos (permitindo espaços/pontuação intercalados)
        # Estratégia: pegar todos os agrupamentos que contenham dígitos e separadores e testar.
        # Mais simples: varrer todas as sequências puras de dígitos de tamanho >= 3 e também
        # tentar a linha inteira sem não-dígitos.
        # 1. Procurar diretamente padrões de 15 dígitos contíguos
        m = QUINZE_DIGITOS_RE.search(line.replace(" ", ""))
        if m:
            return m.group(0)
        # 2. Se não houver contíguo, reconstruir juntando dígitos e verificar blocos com separadores
        # Ex: "700 0010 8284 1506" -> retirando não dígitos vira 700001082841506
        somente_digitos = re.sub(r"\D", "", line)
        if len(somente_digitos) >= 15:
            # tentar localizar primeira janela de 15 dígitos dentro
            for i in range(0, len(somente_digitos) - 14):
                candidato = somente_digitos[i:i+15]
                # Heurística: exigir que candidato não faça parte de uma sequência maior de >15 adjacente
                # (mas se fizer, ainda assim o primeiro bloco de 15 é aceitável)
                return candidato
    return None


def _extrair_valor_pos_label(line: str) -> str | None:
    """Dado uma linha, retorna o texto após o primeiro ':' se houver, senão None."""
    parts = line.split(":", 1)
    if len(parts) == 2:
        valor = parts[1].strip()
        return valor or None
    return None


def _encontrar_nome_mae(bloco: str) -> str | None:
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "nome da mae" in lowered:
            return _extrair_valor_pos_label(line)
    return None


def _encontrar_nome_pai(bloco: str) -> str | None:
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "nome do pai" in lowered or "nome da pai" in lowered:  # tolerar erro de digitação
            return _extrair_valor_pos_label(line)
    return None


def _normalizar_data(d: int, m: int, y: int) -> str | None:
    try:
        if y < 100:  # ano 2 dígitos
            y = 1900 + y if y >= 30 else 2000 + y
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        # Não validar meses/dias com calendário estrito aqui (simplicidade)
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return None


DATA_REGEXES = [
    re.compile(r"\b(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{2,4})\b"),  # 02/10/1992 ou 01.09.86
    re.compile(r"\b(\d{1,2})[\-/\.](\d{1,2})(\d{4})\b"),             # 27/021996 (mês+ano colados)
    re.compile(r"\b(\d{2})(\d{2})(\d{4})\b"),                          # 02101992 sem separadores
]


def _encontrar_data_nascimento(bloco: str) -> str | None:
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "data de nascimento" not in lowered:
            continue
        # Obter somente a parte após ':' para limitar ruído
        after = _extrair_valor_pos_label(line) or line
        # Primeira correspondência que normalize corretamente
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
        # fallback: retirar dígitos e tentar heurística
        digits = re.sub(r"\D", "", after)
        if len(digits) >= 6:
            # Tentar DDMMAAAA ou DDMMAA
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
            elif len(digits) == 6:  # DDMMAA
                try:
                    d = int(digits[0:2])
                    mth = int(digits[2:4])
                    y = int(digits[4:6])
                    iso = _normalizar_data(d, mth, y)
                    if iso:
                        return iso
                except ValueError:
                    pass
        return None  # não inspecionar outras linhas se etiqueta encontrada
    return None


def _strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def _encontrar_nome_profissional(bloco: str) -> str | None:
    """Localiza a primeira linha que representa o nome do profissional.

    Regra:
      - linha contém 'nome' (case-insensitive)
      - linha NÃO contém 'mae'/'mãe' nem 'pai'
      - extrai substring após ': ' (dois pontos + espaço) até o fim da linha
    Retorna None se não encontrado.
    """
    for raw_line in bloco.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lowered = _strip_accents(line.lower())
        if "nome" not in lowered:
            continue
        if "mae" in lowered or "pai" in lowered:
            continue
        # tenta achar pattern ": "
        parts = line.split(":", 1)
        if len(parts) == 2:
            valor = parts[1].strip()
            if valor:
                return valor
        # fallback se não houver ':' claramente
        # Ex: "Nome  Fulano" -> pega depois da palavra nome
        m = re.search(r"nome\s+(.+)$", lowered, re.IGNORECASE)
        if m:
            candidato = raw_line[m.start(1):].strip()
            if candidato:
                return candidato
    return None


def extrai_secao(bloco: str) -> dict:
    """Extrai seções 'cadastro', 'formacao' e 'recebimento' de um bloco de texto.

    Regras de corte:
      - 'cadastro': do início até o início de 'FORMAÇÃO PROFISSIONAL'.
        Se 'FORMAÇÃO PROFISSIONAL' não existir mas existir 'RECEBIMENTO', então
        vai do início até 'RECEBIMENTO'. Caso nenhuma das marcas exista, é o bloco inteiro.
      - 'formacao': inicia em 'FORMAÇÃO PROFISSIONAL' e vai até 'RECEBIMENTO'. Se não houver
        'RECEBIMENTO', vai até o fim. Se não houver 'FORMAÇÃO PROFISSIONAL', marca como não detectado.
      - 'recebimento': inicia em 'RECEBIMENTO' até o fim. Se não houver, marca não detectado.

    Inclui as palavras-chaves (delimitadores) dentro das seções quando presentes.
    """
    cadastro = ""
    formacao = None
    recebimento = None

    m_form = FORMACAO_RE.search(bloco)
    m_receb = RECEBIMENTO_RE.search(bloco)

    # Calcular fatias com base nas combinações possíveis
    if m_form and (not m_receb or m_form.start() < m_receb.start()):
        # Cadastro antes da formação
        cadastro = bloco[:m_form.start()].strip()
        # Formação até recebimento (se houver)
        if m_receb and m_receb.start() > m_form.start():
            formacao = bloco[m_form.start():m_receb.start()].strip()
            recebimento = bloco[m_receb.start():].strip()
        else:
            formacao = bloco[m_form.start():].strip()
    else:
        # Não temos formação antes de recebimento ou formação ausente
        if m_receb:
            cadastro = bloco[:m_receb.start()].strip()
            recebimento = bloco[m_receb.start():].strip()
        else:
            # Nenhuma marca encontrada: tudo é cadastro
            cadastro = bloco.strip()

    # Placeholders para ausentes
    if not cadastro:
        cadastro = "CADASTRO nao detectado"
    if formacao is None:
        formacao = "FORMACAO PROFISSIONAL nao detectada"
    if recebimento is None:
        recebimento = "RECEBIMENTO nao detectado"

    return {
        "cadastro": cadastro,
        "formacao": formacao,
        "recebimento": recebimento,
    }


def extrair_informacoes_rg_ci(texto: str) -> dict:
    """Extrai RG / UF CI / órgão emissor / data emissão / endereço nascimento de um texto de cadastro.

    Formato de retorno (listas com no máximo 1 item):
    {
      'rg': [...], 'uf_ci': [...], 'orgao_emissor_ci': [...], 'data_emissao_ci': [...], 'endereco_nascimento': [...]
    }
    """
    resultado = {"rg": [], "uf_ci": [], "orgao_emissor_ci": [], "data_emissao_ci": [], "endereco_nascimento": []}
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

def _dedup(seq):
    seen = set()
    out = []
    for x in seq:
        if not x:
            continue
        k = x.strip().casefold()
        if k in seen:
            continue
        out.append(x.strip())
        seen.add(k)
    return out

def extract_estado_civil(text: str) -> str:
    # Normaliza NBSP e espaços múltiplos
    norm = text.replace("\xa0", " ")
    norm = re.sub(r"[ \t]+", " ", norm)

    pat_estado = re.compile(
        r"^(?:-\s*)?estado\s*civil\s*:\s*([^\r\n]+?)\s*$",
        FLAGS
    )
    encontrados = [m.group(1).strip() for m in pat_estado.finditer(norm)]
    estado_civil = _dedup(encontrados)

    return estado_civil

def extrair_cpfs_por_blocos(caminho: str | None = None) -> dict:
    """Lê normalizado.txt, separa pelos delimitadores e constrói
    {"medico": {"blocos": [{"nome": "...", "cpf": "...", "texto": "..."}]}}
    """
    if caminho is None:
        caminho = os.path.join(output_dir, "normalizado.txt")

    resultado = {"medico": {"blocos": []}}
    cns_nao_detectados: list[dict] = []  # manter registro dos blocos sem CNS
    mae_nao_detectados: list[dict] = []
    pai_nao_detectados: list[dict] = []
    dt_nasc_nao_detectados: list[dict] = []
    vistos: set[str] = set()

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read()
    except FileNotFoundError:
        print(f"Arquivo não encontrado: {caminho}")
        return resultado

    # Split preservando apenas blocos não vazios
    blocos = [b.strip() for b in conteudo.split(DELIMITADOR) if b.strip()]

    for bloco in blocos:
        cpf = _encontrar_cpf_em_bloco(bloco)
        if not cpf:
            cpf = "CPF nao detectado"
        else:
            if cpf not in vistos:
                vistos.add(cpf)
        cns = _encontrar_cns_em_bloco(bloco)
        if not cns:
            cns = "CNS nao detectado"
            cns_nao_detectados.append({"nome": _encontrar_nome_profissional(bloco) or "NOME nao detectado", "cpf": cpf})
        nome_mae = _encontrar_nome_mae(bloco)
        if not nome_mae:
            mae_nao_detectados.append({"cpf": cpf})
            nome_mae = "MAE nao detectada"
        nome_pai = _encontrar_nome_pai(bloco)
        if not nome_pai:
            pai_nao_detectados.append({"cpf": cpf})
            nome_pai = "PAI nao detectado"
        data_nasc = _encontrar_data_nascimento(bloco)
        if not data_nasc:
            dt_nasc_nao_detectados.append({"cpf": cpf})
            data_nasc = "DATA_NASCIMENTO nao detectada"
        nome = _encontrar_nome_profissional(bloco) or "NOME nao detectado"

        secoes = extrai_secao(bloco)
        rg_ci = extrair_informacoes_rg_ci(secoes["cadastro"]) if secoes.get("cadastro") else {"rg":[],"uf_ci":[],"orgao_emissor_ci":[],"data_emissao_ci":[],"endereco_nascimento":[]}
        estado_civil = extract_estado_civil(secoes["cadastro"])
        
        resultado["medico"]["blocos"].append({
            "nome": nome,
            "cpf": cpf,
            "cns": cns,
            "nome_mae": nome_mae,
            "nome_pai": nome_pai,
            "data_nascimento": data_nasc,
            "cadastro": secoes["cadastro"],
            "formacao": secoes["formacao"],
            "recebimento": secoes["recebimento"],
            # Campos RG/CI extraídos
            "rg": rg_ci["rg"],
            "uf_ci": rg_ci["uf_ci"],
            "orgao_emissor_ci": rg_ci["orgao_emissor_ci"],
            "data_emissao_ci": rg_ci["data_emissao_ci"],
            "endereco_nascimento": rg_ci["endereco_nascimento"],
            "estado_civil": estado_civil
        })

    # Acrescenta registro auxiliar (fora do schema principal solicitado) para auditoria
    resultado["medico"]["cns_nao_identificados"] = cns_nao_detectados
    resultado["medico"]["mae_nao_identificados"] = mae_nao_detectados
    resultado["medico"]["pai_nao_identificados"] = pai_nao_detectados
    resultado["medico"]["data_nascimento_nao_identificados"] = dt_nasc_nao_detectados

    return resultado


if __name__ == "__main__":
    normalizado_path = os.path.join(output_dir, "normalizado.txt")
    dados = extrair_cpfs_por_blocos(normalizado_path)

    # Grava JSON completo (com blocos)
    cpfs_json_path = os.path.join(output_dir, "cpfs_blocos.json")
    try:
        with open(cpfs_json_path, "w", encoding="utf-8") as jf:
            json.dump(dados, jf, ensure_ascii=False, indent=2)
        print(f"Dados (CPFs + blocos) gravados em: {cpfs_json_path}")
    except Exception as e:
        print(f"Falha ao gravar cpfs_blocos.json: {e}")

