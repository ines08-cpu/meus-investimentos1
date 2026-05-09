import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Dashboard de Património - Consolidado")

def clean_val(val):
    """Limpa e converte valores financeiros em texto para números reais."""
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def smart_read(file):
    """Lê o CSV saltando o 'lixo' inicial dos relatórios."""
    content = file.getvalue().decode('utf-8')
    sep = ';' if content.count(';') > content.count(',') else ','
    lines = content.split('\n')
    skip = 0
    for i, line in enumerate(lines[:25]):
        if any(x in line.lower() for x in ['descrição', 'ticker', 'ativo', 'montante', 'transação', 'type', 'tipo', 'comentário']):
            skip = i
            break
    df = pd.read_csv(io.StringIO(content), sep=sep, skiprows=skip)
    df.columns = [str(c).strip().lower() for c in df.columns] # Tudo em minúsculas para não falhar
    return df

def process_data(uploaded_files):
    all_assets_list = []
    xtb_manual = {}
    xtb_auto = {}
    metrics = {'dividendos': 0.0, 'juros': 0.0, 'depositos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            df = smart_read(file)
            
            # 1. OFFLINE (Aforro/PPR - Sempre atualizado)
            if "offline" in name:
                col_estado = next((c for c in df.columns if 'estado' in c), None)
                col_desc = next((c for c in df.columns if 'descrição' in c), None)
                col_ativo = next((c for c in df.columns if 'ativo' in c), 'ativo')
                col_val = next((c for c in df.columns if 'aplicado' in c), None)
                
                if col_estado and col_desc and col_val:
                    temp = df[df[col_estado].astype(str).str.contains('aberto', na=False, case=False)]
                    for _, row in temp.iterrows():
                        all_assets_list.append({'Ativo': row[col_desc], 'Cat': row.get(col_ativo, 'Offline'), 'Valor': clean_val(row[col_val]), 'Fonte': 'Offline'})

            # 2. XTB EXCEL ANTIGOS (Para sabermos as categorias/setores do que preenchias)
            elif "setorial" in name or "usd" in name or "ações" in name:
                t_col = next((c for c in df.columns if 'ticker' in c or 'unnamed: 1' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'euros' in c or 'valor' in c), None)
                
                if t_col and v_col:
                    cat_nome = 'ETF' if 'setorial' in name else 'Ação'
                    for _, row in df.dropna(subset=[t_col]).iterrows():
                        ticker = str(row[t_col]).strip()
                        if ticker.lower() not in ['ticker', 'total', 'nan', 'soma'] and ticker:
                            xtb_manual[ticker] = {'Cat': cat_nome, 'Valor': clean_val(row[v_col])}

            # 3. FREEDOM24 (Ofertas)
            elif "sheet" in name:
                t_col = next((c for c in df.columns if 'ticker' in c), None)
                v_col = next((c for c in df.columns if 'valor' in c or 'preço' in c), df.columns[-1])
                if t_col:
                    for _, row in df.iterrows():
                        if str(row[t_col]).lower() != 'nan':
                            all_assets_list.append({'Ativo': row[t_col], 'Cat': 'Ação (Oferta)', 'Valor': clean_val(row[v_col]), 'Fonte': 'Freedom24'})

            # 4. RENDIMENTOS FREEDOM24 (Transações em Numerário)
            elif "transacções" in name or "numerário" in name:
                t_col = next((c for c in df.columns if 'transação' in c or 'type' in c), None)
                v_col = next((c for c in df.columns if 'montante' in c or 'amount' in c), None)
                m_col = next((c for c in df.columns if 'moeda' in c or 'currency' in c), None)
                
                if t_col and v_col:
                    for _, row in df.iterrows():
                        desc = str(row[t_col]).lower()
                        valor = clean_val(row[v_col])
                        moeda = str(row[m_col]).upper() if m_col else 'EUR'
                        cambio = 0.92 if moeda == 'USD' else 1.0 # Aproximação USD -> EUR
                        
                        # Dividendos e Taxas F24 (Tudo o que indicaste)
                        if any(x in desc for x in ["dividend", "societári", "soietári", "taxas do agente"]):
                            metrics['dividendos'] += (valor * cambio)
                        
                        # Capital Injetado F24
                        if 'transferência bancária' in desc:
                            metrics['depositos'] += abs(valor * cambio)

            # 5. XTB CASH OPERATIONS (A Fonte da Verdade para a XTB)
            elif "cash" in name or "operations" in name:
                type_col = next((c for c in df.columns if 'type' in c or 'tipo' in c), None)
                val_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), None)
                com_col = next((c for c in df.columns if 'comment' in c or 'comentário' in c), None)
                
                if type_col and val_col:
                    for _, row in df.iterrows():
                        tipo = str(row[type_col]).lower()
                        valor = clean_val(row[val_col])
                        comentario = str(row.get(com_col, '')).strip()
                        
                        # Depositos e Levantamentos XTB
                        if 'deposit' in tipo or 'transfer' in tipo or 'depósito' in tipo:
                            metrics['depositos'] += abs(valor) # Adiciona
                        if 'withdrawal' in tipo or 'levantamento' in tipo:
                            metrics['depositos'] -= abs(valor) # Subtrai
                            
                        # Rendimentos XTB
                        if 'dividend' in tipo or 'dividendo' in tipo:
                            metrics['dividendos'] += valor
                        if 'interest' in tipo or 'juros' in tipo:
                            metrics['juros'] += valor
                            
                        # POSIÇÕES AUTOMÁTICAS: Compras e Vendas
                        if any(x in tipo for x in ['purchase', 'compra', 'sale', 'venda', 'open', 'close']):
                            # Em transações de compra, o valor é negativo (sai da conta). 
                            # O capital investido é o inverso disso.
                            investimento_liquido = -valor 
                            
                            # Tentar limpar o nome do Ticker (Ex: "OPEN BUY 10 AAPL.US" -> "AAPL.US")
                            ativo = comentario.replace('OPEN', '').replace('CLOSE', '').replace('BUY', '').replace('SELL', '').strip().split()[0]
                            if ativo not in xtb_auto: xtb_auto[ativo] = 0.0
                            xtb_auto[ativo] += investimento_liquido

        except Exception as e:
            continue

    # --- O GRANDE MERGE (Juntar Excel Antigo com Compras Novas da XTB) ---
    for ativo, val_investido in xtb_auto.items():
        if val_investido > 1: # Ignorar ações que já vendeste totalmente ou arredondamentos
            match_key = next((k for k in xtb_manual.keys() if k in ativo or ativo in k), None)
            
            if match_key:
                # Já tinhas no Excel antigo! Vamos usar o maior valor (se compraste mais, o val_investido será maior)
                val_final = max(xtb_manual[match_key]['Valor'], val_investido)
                cat = xtb_manual[match_key]['Cat']
                del xtb_manual[match_key] # Removemos para não duplicar
            else:
                # É UMA COMPRA NOVA! O teu Excel antigo não tinha isto.
                val_final = val_investido
                cat = "Novo Ativo (Auto)"
                
            all_assets_list.append({'Ativo': ativo, 'Cat': cat, 'Valor': val_final, 'Fonte': 'XTB'})
            
    # Adicionar os restantes do Excel que por acaso não tiveram match
    for ativo, data in xtb_manual.items():
        all_assets_list.append({'Ativo': ativo, 'Cat': data['Cat'], 'Valor': data['Valor'], 'Fonte': 'XTB'})

    return pd.DataFrame(all_assets_list), metrics


# --- UI INTERFACE ---
uploaded = st.sidebar.file_uploader("Arraste os seus Ficheiros CSV aqui", accept_multiple_files=True)

if uploaded:
    df_pos, m = process_data(uploaded)
    
    if not df_pos.empty:
        total_patrimonio = df_pos['Valor'].sum()
        
        st.subheader("Resumo Financeiro Consolidado")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Atual (Total)", f"€ {total_patrimonio:,.2f}")
        c2.metric("Capital Injetado (Líquido)", f"€ {m['depositos']:,.2f}")
        c3.metric("Dividendos Recebidos (Limpos)", f"€ {m['dividendos']:,.2f}")
        c4.metric("Juros Líquidos", f"€ {m['juros']:,.2f}")
        
        st.divider()
        col_a, col_b = st.columns([1, 1])
        with col_a:
            fig = px.pie(df_pos, values='Valor', names='Cat', hole=0.4, title="Distribuição do teu Dinheiro")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.subheader("Lista Completa de Ativos")
            st.dataframe(df_pos.sort_values('Valor', ascending=False), use_container_width=True, hide_index=True)
            
        # O VERDADEIRO GANHO
        lucro = (total_patrimonio - m['depositos']) + m['dividendos'] + m['juros']
        cor = "🟢" if lucro >= 0 else "🔴"
        st.success(f"{cor} **Balanço Global Estimado (Valorização + Rendimentos): € {lucro:,.2f}**")
    else:
        st.info("A processar dados... Confirme se os ficheiros 'Cash Operations' e 'Transações em Numerário' estão carregados.")
