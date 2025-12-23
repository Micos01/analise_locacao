#  **Auditor Jurídico & Financeiro de Contratos (LCP 214/2025)**

Sistema de automação forense para auditoria em massa de contratos de locação imobiliária. O projeto utiliza Inteligência Artificial Generativa e Visão Computacional para extrair dados, validar assinaturas, calcular custas cartorárias e definir estratégias de registro com base na Reforma Tributária (Lei Complementar 214/2025).

##  **Objetivo do Projeto**

Analisar contratos de aluguel para determinar a necessidade de **Registro em Títulos e Documentos (RTD)**, visando:

1. **Segurança Jurídica:** Garantir a "Data Certa" (anterior a 16/01/2025) conforme Art. 487 da LCP 214\.
2. **Eficiência Financeira:** Evitar gastos desnecessários com registros de contratos que vencem antes do início da cobrança da CBS (2027).

##  **Lógica Estratégica (A "Regra de Ouro")**

O sistema classifica cada contrato e recomenda uma ação, baseada na seguinte matriz de decisão:

| Cenário do Contrato | Status da Assinatura | Vencimento | Ação Recomendada | Motivo |
|---|---|---|---|---|
| Já possui Fé Pública | Com Firma ou Digital (Gov.br) | Qualquer | ARQUIVAR (SEGURO) | Já possui Data Certa anterior à lei. Custo zero. |
| Risco Jurídico | Sem Firma / Não Assinado | Antes de 2027 | NÃO REGISTRAR | O contrato acaba antes do aumento de imposto. Economia de caixa. |
| Risco Financeiro | Sem Firma / Não Assinado | Após 2027 | REGISTRAR URGENTE | Contrato atravessa a vigência da CBS. Precisa de Data Certa para proteção fiscal. | baseada na seguinte matriz de decisão:

| Cenário do Contrato | Status da Assinatura | Vencimento | Ação Recomendada | Motivo |
| Já possui Fé Pública | Com Firma ou Digital (Gov.br) | Qualquer | ARQUIVAR (SEGURO) | Já possui Data Certa anterior à lei. Custo zero. |
| Risco Jurídico | Sem Firma / Não Assinado | Antes de 2027 | NÃO REGISTRAR | O contrato acaba antes do aumento de imposto. Economia de caixa. |
| Risco Financeiro | Sem Firma / Não Assinado | Após 2027 | REGISTRAR URGENTE | Contrato atravessa a vigência da CBS. Precisa de Data Certa para proteção fiscal. 



##  **Arquitetura do Pipeline**

O projeto segue o padrão **Data Lake (Raw Data)** para garantir integridade e permitir reprocessamentos sem custo adicional de extração.

### **Passo 1: Extração Bruta (01\_extrator\_custos\_llama.py)**

* **Entrada:** PDFs na pasta outputs/documentos.
* **Tecnologia:**
  * **LlamaParse:** OCR avançado para converter PDF em Markdown.
  * **Claude 3.5 Sonnet:** Analisa o texto, extrai valores, datas e identifica o tipo de assinatura.
* **Saída:** Arquivos JSON brutos salvos em outputs/dados\_brutos\_ia.

### **Passo 2: Processamento Inteligente (02\_processador\_gemini\_flash.py)**

* **Entrada:** JSONs brutos do Passo 1\.
* **Tecnologia:**
  * **Python (Pandas/Regex):** Limpeza de dados, sanitização de valores monetários (R$) e normalização de datas.
  * **Gemini 2.0 Flash:** (Opcional/Híbrido) Validação de raciocínio e geração de justificativas textuais.
* **Saída:** Relatório Excel (.xlsx) com formatação contábil, ordenado por prioridade de ação e custo.

##  **Como Usar**

### **1\. Pré-requisitos**

* Python 3.10+
* Conta na **OpenRouter** (para Claude/Gemini).
* Conta na **LlamaCloud** (para LlamaParse).

### **2\. Instalação**

Instale as dependências necessárias:

pip install openai pandas python-dotenv llama-parse fitz pymupdf xlsxwriter

### **3\. Configuração (.env)**

Crie um arquivo .env na raiz do projeto:

OPENROUTER\_API\_KEY=sk-or-v1-seu-token-aqui
LLAMA\_CLOUD\_API\_KEY=llx-seu-token-aqui

### **4\. Execução**

Etapa 1: Extração (Consome Créditos de API)
Lê os PDFs e baixa os dados brutos.
python 01\_extrator\_custos\_llama.py

Etapa 2: Análise e Relatório (Rápido/Baixo Custo)
Processa os dados baixados e gera o Excel final.
python 02\_processador\_gemini\_flash.py

## **📂 Estrutura de Pastas**

projeto/
│
├── 01_extrator_custos_llama.py    \# Script de Extração (LlamaParse \+ Claude)
├── 02\_processador\_gemini\_flash.py \# Script de Lógica de Negócio (Excel Final)
├── .env                           \# Chaves de API (Não comitar\!)
├── outputs/
│   ├── documentos/                \# Coloque seus PDFs aqui
│   ├── dados\_brutos\_ia/           \# JSONs gerados pela IA (Backup seguro)
│   ├── relatorios\_finais/         \# Excel pronto para diretoria
│   └── logs/                      \# Histórico de execução e erros
└── README.md

## **📊 Detalhes da Tabela de Custas**

O sistema possui integrada a **Tabela de Custas de Registro 2025**. Ele calcula automaticamente:

1. Extrai o valor do aluguel mensal.
2. Calcula a base anual (x12).
3. Enquadra na faixa correta da tabela progressiva.
4. Estima o custo exato do registro em cartório para tomada de decisão.

## **⚠️ Aviso Legal**

Esta ferramenta é um auxiliar para auditoria e tomada de decisão. A responsabilidade final sobre o registro ou não de documentos é do gestor, baseada nas recomendações jurídicas e contábeis da empresa.
