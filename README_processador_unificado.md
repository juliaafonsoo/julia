# Processador Médico Unificado

Este script unifica as funcionalidades dos módulos `normalizacao.py`, `contacts.py` e `extraimedico.py` em um único arquivo para processamento completo de documentos médicos.

## Funcionalidades

O script executa automaticamente as seguintes etapas:

1. **Extração de Textos**: Lê todos os arquivos `.docx` da pasta `medico/` e extrai o texto
2. **Normalização**: Remove blocos indesejados (como listas de documentos) e limpa o texto
3. **Processamento**: Extrai informações estruturadas de cada documento
4. **Exportação**: Salva os resultados em formato JSON

## Dados Extraídos

Para cada documento médico, o script extrai:

### Informações Pessoais
- Nome completo
- CPF
- CNS (Cartão Nacional de Saúde)
- Nome da mãe
- Nome do pai
- Data de nascimento
- Estado civil

### Informações de Identificação
- RG
- UF do CI
- Órgão emissor do CI
- Data de emissão do CI
- Endereço/cidade de nascimento

### Informações de Contato
- Endereço completo
- CRM-ES
- E-mail
- Telefone
- Telefone de emergência
- Tipo/nome do contato de emergência
- Carga horária semanal

### Seções do Documento
- Cadastro (seção principal)
- Formação profissional
- Recebimento

## Uso

### Execução Simples
```bash
python3 processador_medico_unificado.py
```

### Estrutura de Pastas Esperada
```
projeto/
├── processador_medico_unificado.py
├── medico/                    # Pasta com arquivos .docx
│   ├── documento1.docx
│   ├── documento2.docx
│   └── ...
└── output/                    # Pasta criada automaticamente
    ├── all_texts.txt         # Textos extraídos concatenados
    ├── normalizado.txt       # Textos após normalização
    └── cpfs_blocos.json      # Resultado final em JSON
```

## Saída

O script gera um arquivo JSON (`output/cpfs_blocos.json`) com a seguinte estrutura:

```json
{
  "medico": {
    "blocos": [
      {
        "nome": "João Silva",
        "cpf": "12345678901",
        "cns": "123456789012345",
        "nome_mae": "Maria Silva",
        "nome_pai": "José Silva",
        "data_nascimento": "1990-01-15",
        "endereco": ["Rua das Flores, 123"],
        "crm": ["12345"],
        "email": ["joao@email.com"],
        "telefone": ["27 99999-9999"],
        "telefone_emergencia": ["27 88888-8888"],
        "tipo_contato_emergencia": ["ESPOSA"],
        "estado_civil": ["CASADO"],
        "rg": ["1234567"],
        "uf_ci": ["ES"],
        "orgao_emissor_ci": ["DETRAN"],
        "data_emissao_ci": ["01/01/2010"],
        "endereco_nascimento": ["Vitória - ES"],
        "carga_horaria_semanal": ["40 horas"],
        "cadastro": "...",
        "formacao": "...",
        "recebimento": "..."
      }
    ],
    "cns_nao_identificados": [...],
    "mae_nao_identificados": [...],
    "pai_nao_identificados": [...],
    "data_nascimento_nao_identificados": [...]
  }
}
```

## Configuração

### Personalizando Caminhos
Você pode modificar as constantes no início do arquivo:

```python
FOLDER_PATH = "medico"  # Pasta com arquivos DOCX
output_dir = os.path.join(os.path.dirname(__file__), "output")  # Pasta de saída
```

### Texto Alvo para Remoção
Para modificar o texto que deve ser removido durante a normalização, edite a constante `STRING1`.

### Modo Fuzzy
O script usa por padrão o modo "fuzzy" para remoção de blocos similares. Para usar remoção exata, modifique a chamada:

```python
normalizado_path = normalizar_textos(fuzzy=False)
```

## Dependências

- `python-docx`: Para leitura de arquivos .docx
- `typing`: Para tipagem (incluído no Python 3.5+)
- `dataclasses`: Para estruturas de dados (incluído no Python 3.7+)

### Instalação de Dependências
```bash
pip install python-docx
```

## Tratamento de Erros

O script inclui tratamento robusto de erros:

- Arquivos DOCX corrompidos ou ilegíveis são ignorados
- Campos não encontrados recebem placeholders descritivos
- Relatório de auditoria para campos não detectados

## Auditoria

O script gera automaticamente listas de auditoria para:
- CNS não identificados
- Nomes de mãe não identificados  
- Nomes de pai não identificados
- Datas de nascimento não identificadas

## Estatísticas

Ao final da execução, o script exibe:
- Total de blocos processados
- Quantidade de cada tipo de dado não detectado
- Localização dos arquivos gerados

## Logs

O script fornece logs detalhados durante a execução:
- Progresso da extração de cada arquivo
- Resultados da normalização
- Estatísticas finais
- Erros e avisos

## Exemplo de Execução

```
=== PROCESSADOR MÉDICO UNIFICADO ===
Iniciando processamento completo...

1. Extraindo textos de arquivos DOCX...
--- Processando: documento1.docx ---
--- Processando: documento2.docx ---
Textos extraídos salvos em: ./output/all_texts.txt

2. Normalizando textos...
Removidos 3 bloco(s) variante(s).
Arquivo normalizado criado em: ./output/normalizado.txt

3. Processando e extraindo dados...

4. Salvando resultados...
Dados processados salvos em: ./output/cpfs_blocos.json

=== ESTATÍSTICAS FINAIS ===
Total de blocos processados: 97
CNS não detectados: 29
Nomes de mãe não detectados: 0
Nomes de pai não detectados: 0
Datas de nascimento não detectadas: 0

=== PROCESSAMENTO CONCLUÍDO ===
```
