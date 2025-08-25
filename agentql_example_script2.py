import json
import requests
url = "https://api.agentql.com/v1/query-document"
headers = {
    "X-API-Key": "QTBBVz_3nq_S5E3DOkrSxRo_2WeI1WsZdKNhdguCBt5HPjZig-rsew",
}
form_body = {
  "body": json.dumps({
    "query": 
        medico {
            nome[]
            cpf[]
            cns[]
            nome_pai[]
            nome_mae[]
            data_nascimento[]
            endereco_nascimento[]
            rg[]
            email[]
        }
,
    "params": { "mode": "fast"}
  })
}
with open("medicopdf/Cópia de FASE 1️⃣.pdf", "rb") as f:
  file_object = {"file": ("file_name", f.read())}
response = requests.post(url, headers=headers, files=file_object, data=form_body)
data = response.json()