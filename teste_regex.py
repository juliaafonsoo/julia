import json
import os
import re


def extrair_informacoes(texto: str):
    """Extrai campos de RG/CI e local de nascimento de um bloco de texto de cadastro.

    Retorna estrutura:
    {
        "blocos": {
            "rg": [..],
            "uf_ci": [..],
            "orgao_emissor_ci": [..],
            "data_emissao_ci": [..],
            "endereco_nascimento": [..]
        }
    }
    Cada lista conterá no máximo 1 item (primeira ocorrência encontrada) ou ficará vazia.
    """
    resultado = {
        "blocos": {
            "rg": [],
            "uf_ci": [],
            "orgao_emissor_ci": [],
            "data_emissao_ci": [],
            "endereco_nascimento": []
        }
    }

    if not texto:
        return resultado

    # --- RG ---
    rg_patterns = [
        r'Número\s+identidade:\s*([0-9.]+)',            # Número identidade: 3.022.766
        r'RG\s*\([^)]*\):\s*([0-9.]+)-\w{1,3}',       # RG (...): 4089393-ES
        r'RG\s*\([^)]*\):\s*([0-9.]+)'                # RG (...): 4.128.126
    ]
    for pattern in rg_patterns:
        m = re.search(pattern, texto, re.IGNORECASE)
        if m:
            rg_num = m.group(1).replace('.', '')
            resultado["blocos"]["rg"] = [rg_num]
            break

    # --- UF CI ---
    uf_patterns = [
        r'UF\s*CI:\s*(\w{2})',                         # UF CI: ES
        r'RG\s*\([^)]*\):\s*[0-9.]+-(\w{2})',        # 4089393-ES
        r'-\s*(\w{2})\s*/\s*\w+\s*/',               # -ES / SPTC /
        r'-\s*(\w{2})\s*,\s*ÓRGÃO'                    # -ES, ÓRGÃO
    ]
    for pattern in uf_patterns:
        m = re.search(pattern, texto, re.IGNORECASE)
        if m:
            resultado["blocos"]["uf_ci"] = [m.group(1).upper()]
            break

    # --- Órgão emissor CI ---
    orgao_patterns = [
        r'Órgão\s+emissor\s+CI:\s*([A-ZÀ-Ú]{2,10})',   # Órgão emissor CI: SPTC
        r'/\s*([A-ZÀ-Ú]{2,10})\s*/\s*\d{2}/\d{2}/\d{4}',  # / SPTC / 12/01/2016
        r'ÓRGÃO\s+EMISSOR\s+([A-ZÀ-Ú]{2,10})',          # ÓRGÃO EMISSOR SPTC
        r'\b\w{2}\s*/\s*([A-ZÀ-Ú]{2,10})\s*/'        # ES / SPTC /
    ]
    for pattern in orgao_patterns:
        m = re.search(pattern, texto, re.IGNORECASE)
        if m:
            resultado["blocos"]["orgao_emissor_ci"] = [m.group(1).upper()]
            break

    # --- Data de emissão CI ---
    data_patterns = [
        r'Data\s+de\s+emissão\s+CI:\s*(\d{2}/\d{2}/\d{4})',  # Data de emissão CI: 15/02/2007
        r'/\s*\w+\s*/\s*(\d{2}/\d{2}/\d{4})',                # / SPTC / 12/01/2016
        r'DATA\s+EMISS[ÃA]O\s+(\d{2}/\d{2}/\d{4})'             # DATA EMISSÃO 18/05/2016
    ]
    for pattern in data_patterns:
        m = re.search(pattern, texto, re.IGNORECASE)
        if m:
            resultado["blocos"]["data_emissao_ci"] = [m.group(1)]
            break

    # --- Município + UF nascimento ---
    municipio = None
    uf_nasc = None
    municipio_patterns = [
        r'Município\s+de\s+nascimento:\s*([^\n-]+)',
        r'MUNIC[IÍ]PIO\s+DE\s+NASCIMENTO:\s*([^\n]+)'
    ]
    for pattern in municipio_patterns:
        m = re.search(pattern, texto, re.IGNORECASE)
        if m:
            municipio = m.group(1).strip().rstrip(' .;')
            break

    uf_nasc_patterns = [
        r'UF\s*DE\s+NASCIMENTO:\s*(\w{2})',
        r'UF\s+de\s+nascimento:\s*(\w{2})',
        r'UF:\s*(\w{2})\b'  # fallback simples (cuidar para não capturar UF CI)
    ]
    for pattern in uf_nasc_patterns:
        m = re.search(pattern, texto, re.IGNORECASE)
        if m:
            uf_nasc = m.group(1).upper()
            break

    if municipio and uf_nasc:
        resultado["blocos"]["endereco_nascimento"] = [f"{municipio} - {uf_nasc}"]
    elif municipio:
        resultado["blocos"]["endereco_nascimento"] = [municipio]

    return resultado


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_json = os.path.join(base_dir, 'output', 'cpfs_blocos.json')
    out_json = os.path.join(base_dir, 'output', 'teste_regex.json')

    if not os.path.exists(input_json):
        raise SystemExit(f'Arquivo não encontrado: {input_json}')

    with open(input_json, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    blocos = dados.get('medico', {}).get('blocos', [])
    resultados = []

    for idx, bloco in enumerate(blocos):
        cadastro_texto = bloco.get('cadastro', '')
        extracao = extrair_informacoes(cadastro_texto)
        resultados.append({
            'indice_bloco': idx,
            'nome': bloco.get('nome'),
            'cpf': bloco.get('cpf'),
            'resultado_regex': extracao['blocos']
        })

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump({'teste_regex': resultados}, f, ensure_ascii=False, indent=2)

    print(f'Resultados gravados em: {out_json}')


if __name__ == '__main__':
    main()
