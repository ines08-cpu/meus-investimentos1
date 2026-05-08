import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor de Portfólio - Inês")

def clean_value(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def smart_read(file):
    content = file.getvalue().decode('utf-8')
    sep = ';' if content.count(';') > content.count(',') else ','
    lines = content.split('\n')
    skip = 0
    # Procura a linha do cabeçalho
    for i, line in enumerate(lines[:20]):
        if any(x in line for x in ['DESCRIÇÃO', 'Ticker', 'Tickers', 'ATIVO', 'APLICADO', 'Em Euros', 'Type', 'Montante', 'Juros']):
            skip = i
            break
    df = pd.read_csv(io.StringIO(content), sep=sep, skiprows=skip)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def process_data(uploaded_files):
    all_assets = []
    totals = {'juros': 0.0, 'dividendos': 0.0, 'depositos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            df = smart_read(file)
            
            # 1. OFFLINE
            if "offline" in name:
                temp = df[df['ESTADO'].str.contains('Aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': clean_value(row['APLICADO']), 'Fonte': 'Offline'})

            # 2. XTB ETFs (Analise Setorial)
            elif "setorial" in name:
                t_col = next((c for c in df.columns if 'Ticker' in c or 'Unnamed: 1' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'Unnamed: 6' in c), None)
                if t_col and v_col:
                    temp = df.dropna(subset=[t_col])
                    for _, row in temp.iterrows():
                        if str(row[t_col]) not in ['Ticker', 'Total', 'nan', 'ETFs']:
                            all_assets.append({'Ativo': row[t_col], 'Cat': 'ETF', 'Valor': clean_value(row[v_col]), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD (Ajustado para o teu ficheiro)
            elif "usd" in name or "ações" in name:
                t_col = next((c for c in df.columns if 'Ticker' in c), None)
                v_col = next((c for c in df.columns if 'Euros' in c or 'Valor' in c), None)
                if t_col and v_col:
                    temp = df[df[t_col].notna() & (~df[t_col].astype(str).str.contains('Total|Soma', case=False))]
                    for _, row in temp.iterrows():
                        all_assets.append({'Ativo': row[t_col], 'Cat': 'Ação', 'Valor': clean_value(row[v_col]), 'Fonte': 'XTB'})

            # 4. FREEDOM24 (Ações Oferta)
            elif "sheet" in name:
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': clean_value(row['Valor']), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS E CASH FLOW
            # Juros (XTB)
            if "juros" in name or "capital" in name:
                j_col = next((c for c in df.columns if 'Juros' in c), None)
                if j_col: totals['juros'] += df[j_col].apply(clean_value).sum()

            # Dividendos (XTB e Freedom)
            if "dividendos" in name:
                d_col = next((c for c in df.columns if 'Ganhos' in c or 'Dividendo' in c), None)
                if d_col: totals['dividendos'] += df[d_col].apply(clean_value).sum()
            
            if "transacções" in name or "numerário" in name:
                if 'Montante' in df.columns:
                    divs = df[df['Transação'].str.contains('Dividendo', na=False, case=False)]
                    totals['dividendos'] += divs['Montante'].apply(clean_value).sum()

            # Cash Operations (Histórico XTB)
            if "cash" in name or "operations" in name:
                if 'Type' in df.columns and 'Amount' in df.columns:
                    totals['depositos'] += abs(df[df['Type'].str.contains('Deposit|Transfer', na=False, case=False)]['Amount'].apply(clean_value).sum())
                    # Também pode haver juros aqui
                    juros_extra = df[df['Type'].str.contains('Interest', na=False, case=False)]['Amount'].apply(clean_value).sum()
                    totals['juros'] += juros_extra

        except: continue
    return pd.DataFrame(all_assets), totals

# --- UI ---
uploaded = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if uploaded:
    df_res, rends = process_data(uploaded)
    if not df_res.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {df_res['Valor'].sum():,.2f}")
        c2.metric("Dividendos", f"€ {rends['dividendos']:,.2f}")
        c3.metric("Juros Líquidos", f"€ {rends['juros']:,.2f}")
        c4.metric("Capital Injetado", f"€ {rends['depositos']:,.2f}")
        
        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.4, title="Alocação"), use_container_width=True)
        with col2:
            st.subheader("Lista Detalhada")
            st.dataframe(df_res.sort_values('Valor', ascending=False)[['Ativo', 'Valor', 'Fonte']], use_container_width=True)
