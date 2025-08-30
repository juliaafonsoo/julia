import json
import requests
import agentql
import os
from pathlib import Path


def process_pdf_files():
    url = "https://api.agentql.com/v1/query-document"
    headers = {
        "X-API-Key": "QTBBVz_3nq_S5E3DOkrSxRo_2WeI1WsZdKNhdguCBt5HPjZig-rsew",
    }
    
    query_template = {
        "query": """
            {
              medico[] {
                nome
                cpf
                cns
                nome_mae
                nome_pai
                data_nascimento
                rg
                uf_ci
                orgao_emissor_ci
                data_emissao_ci
                endereco_nascimento
                estado_civil
                endereco
                crm
                email
                telefone
                telefone_emergencia
                tipo_contato_emergencia
                carga_horaria_semanal
                formacao
                recebimento
              }
            }""",
    }
    
    # Estrutura para armazenar todos os resultados
    resultado = {
        "medico": {
            "blocos": []
        }
    }
    
    # Pasta com os PDFs
    pdf_folder = Path("medicopdf")
    output_folder = Path("output")
    
    # Criar pasta output se não existir
    output_folder.mkdir(exist_ok=True)
    
    # Buscar todos os arquivos PDF
    pdf_files = list(pdf_folder.glob("*.pdf"))
    
    print(f"Encontrados {len(pdf_files)} arquivos PDF para processar...")
    
    # Processar cada arquivo PDF
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"Processando arquivo {i}/{len(pdf_files)}: {pdf_file.name}")
        
        try:
            form_body = {
                "body": json.dumps(query_template)
            }
            
            with open(pdf_file, "rb") as f:
                file_object = {"file": (pdf_file.name, f.read())}
            
            response = requests.post(url, headers=headers, files=file_object, data=form_body)
            
            if response.status_code == 200:
                data = response.json()
                
                # Adicionar informações do arquivo ao resultado
                bloco_dict = {
                    "nome_arquivo": pdf_file.name,
                    "dados_extraidos": data
                }
                
                # Se há dados de médico extraídos, adicionar aos blocos
                if "data" in data and data["data"] and "medico" in data["data"]:
                    for medico_data in data["data"]["medico"]:
                        medico_bloco = {
                            "nome_arquivo": pdf_file.name,
                            "nome": medico_data.get("nome", ""),
                            "cpf": medico_data.get("cpf", ""),
                            "cns": medico_data.get("cns", ""),
                            "nome_mae": medico_data.get("nome_mae", ""),
                            "nome_pai": medico_data.get("nome_pai", ""),
                            "data_nascimento": medico_data.get("data_nascimento", ""),
                            "formacao": medico_data.get("formacao", ""),
                            "recebimento": medico_data.get("recebimento", ""),
                            "rg": medico_data.get("rg", ""),
                            "uf_ci": medico_data.get("uf_ci", ""),
                            "orgao_emissor_ci": medico_data.get("orgao_emissor_ci", ""),
                            "data_emissao_ci": medico_data.get("data_emissao_ci", ""),
                            "endereco_nascimento": medico_data.get("endereco_nascimento", ""),
                            "estado_civil": medico_data.get("estado_civil", ""),
                            "endereco": medico_data.get("endereco", ""),
                            "crm": medico_data.get("crm", ""),
                            "email": medico_data.get("email", ""),
                            "telefone": medico_data.get("telefone", ""),
                            "telefone_emergencia": medico_data.get("telefone_emergencia", ""),
                            "tipo_contato_emergencia": medico_data.get("tipo_contato_emergencia", ""),
                            "carga_horaria_semanal": medico_data.get("carga_horaria_semanal", "")
                        }
                        resultado["medico"]["blocos"].append(medico_bloco)
                else:
                    # Se não há dados estruturados, adicionar o resultado bruto
                    resultado["medico"]["blocos"].append(bloco_dict)
                
                print(f"✓ Arquivo {pdf_file.name} processado com sucesso")
            else:
                print(f"✗ Erro ao processar {pdf_file.name}: {response.status_code}")
                # Adicionar erro ao resultado
                erro_bloco = {
                    "nome_arquivo": pdf_file.name,
                    "erro": f"Status code: {response.status_code}",
                    "resposta": response.text
                }
                resultado["medico"]["blocos"].append(erro_bloco)
                
        except Exception as e:
            print(f"✗ Erro ao processar {pdf_file.name}: {str(e)}")
            # Adicionar erro ao resultado
            erro_bloco = {
                "nome_arquivo": pdf_file.name,
                "erro": str(e)
            }
            resultado["medico"]["blocos"].append(erro_bloco)
    
    # Salvar resultado no arquivo JSON
    output_file = output_folder / "pdf_blocos.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    
    print(f"\nProcessamento concluído! Resultados salvos em: {output_file}")
    print(f"Total de blocos processados: {len(resultado['medico']['blocos'])}")


if __name__ == "__main__":
    process_pdf_files()