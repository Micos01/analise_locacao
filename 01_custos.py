import os
import fitz  # PyMuPDF
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÕES ---
# Coloque aqui a pasta "Mãe". O script vai olhar tudo que tem dentro dela.
DIRETORIO_RAIZ = os.getenv("DIRETORIO_RAIZ")  

CUSTO_MEDIO_POR_IMAGEM_USD = 0.0645       # Estimativa Claude 3.5 Sonnet
TAXA_DOLAR = 6.00                         # Cotação

def calcular_custo_recursivo():
    if not os.path.exists(DIRETORIO_RAIZ):
        print(f"❌ Diretório não encontrado: {DIRETORIO_RAIZ}")
        return

    print(f"🔍 Iniciando varredura recursiva em: {DIRETORIO_RAIZ}...\n")
    
    total_docs = 0
    total_paginas_reais = 0
    total_fotos_ia = 0
    
    relatorio = []

    # Cabeçalho da Tabela
    print(f"{'ARQUIVO (Nome)':<50} | {'PÁGS':<6} | {'FOTOS':<6} | {'CUSTO (R$)':<10}")
    print("-" * 85)

    # --- O SEGREDO ESTÁ AQUI: os.walk ---
    # Ele navega por todas as pastas, subpastas e arquivos a partir da raiz
    for root, dirs, files in os.walk(DIRETORIO_RAIZ):
        for arquivo in files:
            if arquivo.lower().endswith('.pdf'):
                
                # Monta o caminho completo (Ex: C:\pasta\subpasta\arquivo.pdf)
                caminho_completo = os.path.join(root, arquivo)
                
                try:
                    doc = fitz.open(caminho_completo)
                    num_paginas = len(doc)
                    
                    # --- LÓGICA DE ECONOMIA ---
                    # > 6 págs = 5 fotos (2 início + 3 fim)
                    # <= 6 págs = todas as fotos
                    if num_paginas > 6:
                        fotos_necessarias = 5
                    else:
                        fotos_necessarias = num_paginas
                    
                    custo_usd = fotos_necessarias * CUSTO_MEDIO_POR_IMAGEM_USD
                    custo_brl = custo_usd * TAXA_DOLAR
                    
                    # Adiciona aos totais
                    total_docs += 1
                    total_paginas_reais += num_paginas
                    total_fotos_ia += fotos_necessarias
                    
                    # Exibe no console (trunca nome se for muito longo para não quebrar a tabela)
                    nome_exibicao = arquivo[:45] + "..." if len(arquivo) > 45 else arquivo
                    print(f"{nome_exibicao:<50} | {num_paginas:<6} | {fotos_necessarias:<6} | R$ {custo_brl:.2f}")
                    
                    # Salva dados completos para o Excel (incluindo o caminho da subpasta)
                    relatorio.append({
                        "Caminho_Completo": caminho_completo,
                        "Pasta_Origem": root,
                        "Nome_Arquivo": arquivo,
                        "Paginas_Reais": num_paginas,
                        "Fotos_IA_Processadas": fotos_necessarias,
                        "Custo_Est_USD": round(custo_usd, 4),
                        "Custo_Est_BRL": round(custo_brl, 2)
                    })
                    
                    doc.close()
                    
                except Exception as e:
                    print(f"❌ Erro ao ler {arquivo}: {e}")

    # --- TOTAIS FINAIS ---
    if total_docs == 0:
        print("\n⚠️ Nenhum PDF encontrado neste diretório ou subdiretórios.")
        return

    custo_total_usd = total_fotos_ia * CUSTO_MEDIO_POR_IMAGEM_USD
    custo_total_brl = custo_total_usd * TAXA_DOLAR

    print("-" * 85)
    print("\n💰 RESUMO DO ORÇAMENTO (VARREDURA COMPLETA):")
    print(f"   📂 Diretório Raiz:           {DIRETORIO_RAIZ}")
    print(f"   📑 Total de Documentos:      {total_docs}")
    print(f"   📄 Páginas Totais (PDFs):    {total_paginas_reais}")
    print(f"   📸 Fotos enviadas p/ IA:     {total_fotos_ia} (Economia de {total_paginas_reais - total_fotos_ia} págs)")
    print("   -------------------------------------------------")
    print(f"   💵 Custo Total (USD):        US$ {custo_total_usd:.2f}")
    print(f"   🇧🇷 Custo Total (BRL):        R$  {custo_total_brl:.2f}")
    print("   -------------------------------------------------")

    # Exportar para Excel
    if relatorio:
        df = pd.DataFrame(relatorio)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        caminho_excel = f"Orcamento_Recursivo_{timestamp}.xlsx"
        
        # Ordenar por custo (do mais caro para o mais barato) para facilitar análise
        df = df.sort_values(by="Custo_Est_BRL", ascending=False)
        
        df.to_excel(caminho_excel, index=False)
        print(f"\n✅ Planilha detalhada salva em: {caminho_excel}")

if __name__ == "__main__":
    calcular_custo_recursivo()