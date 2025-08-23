import json
import os
import re
import re
from typing import Dict, List

FLAGS = re.IGNORECASE | re.UNICODE | re.MULTILINE

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

def extract_estado_civil(text: str) -> Dict[str, Dict[str, List[str]]]:
    # Normaliza NBSP e espaços múltiplos
    norm = text.replace("\xa0", " ")
    norm = re.sub(r"[ \t]+", " ", norm)

    pat_estado = re.compile(
        r"^(?:-\s*)?estado\s*civil\s*:\s*([^\r\n]+?)\s*$",
        FLAGS
    )

    encontrados = [m.group(1).strip() for m in pat_estado.finditer(norm)]
    encontrados = _dedup(encontrados)

    return {"estado_civil": encontrados}


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
        extracao = extract_estado_civil(cadastro_texto)
        resultados.append({
            'indice_bloco': idx,
            'nome': bloco.get('nome'),
            'cpf': bloco.get('cpf'),
            'resultado_regex': extracao['estado_civil']
        })

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump({'teste_regex': resultados}, f, ensure_ascii=False, indent=2)

    print(f'Resultados gravados em: {out_json}')


if __name__ == '__main__':
    main()
