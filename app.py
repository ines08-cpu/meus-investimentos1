import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor de Portfólio - Inês")

def clean_value(val):
    if pd.isna(val): return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s:
        s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try:
        return float(s)
    except:
        return 0.0

def smart_read(file):
    content = file.getvalue().decode('utf-8')
    sep = ';' if content.count(';') > content.count(',') else ','
    lines = content.split('\n')
    skip = 0
    # Procura a linha que contém palavras-chave de colunas
    for i, line in enumerate(lines[:15]):
        if any(x in line for x in ['DESCRIÇÃO', 'Ticker', 'Tickers', 'ATIVO', 'APLICADO', 'Em Euros']):
            skip = i
            break
    df = pd.read_csv(io.StringIO(content), sep=sep, skiprows=skip)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def process_data(uploaded_files):
    all_assets = []
    totals = {'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            df = smart_read(file)
            
            # 1. OFFLINE (Aforro/PPR)
            if "offline" in name and 'APLICADO' in df.columns:
                temp = df[df['ESTADO'].str.contains('Aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': clean_value(row['APLICADO']), 'Fonte': 'Offline'})

            # 2. XTB ETFs (Análise Setorial)
            elif "analise setorial" in name:
                t_col = next((c for c in df.columns if 'Ticker' in c or 'Unnamed' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'Unnamed' in c), None)
                if t_col and v_col:
                    temp = df.dropna(subset=[t_col])
                    for _, row in temp.iterrows():
                        if str(row[t_col]) not in ['Ticker', 'Total', 'nan', 'ETFs', 'Soma']:
                            all_assets.append({'Ativo': row[t_col], 'Cat': 'ETF', 'Valor': clean_value(row[v_col]), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD (Ajustado)
            elif "ações usd" in name:
                # Procura a coluna do Ticker e do Valor em Euros
                t_col = next((c for c in df.columns if 'Ticker' in c), None)
                v_col = next((c for c in df.columns if 'Euros' in c or 'Valor' in c), None)
                if t_col and v_col:
                    temp = df[df[t_col].notna() & (~df[t_col].astype(str).str.contains('Total|Soma', case=False))]
                    for _, row in temp.iterrows():
                        all_assets.append({'Ativo': row[t_col], 'Cat': 'Ação', 'Valor': clean_value(row[v_col]), 'Fonte': 'XTB'})

            # 4. FREEDOM24
            elif "sheet" in name and 'Ticker' in df.columns:
                v_col = 'Valor' if 'Valor' in df.columns else df.columns[-1]
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': clean_value(row[v_col]), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS
            if "juros" in name and any('Juros' in c for c in df.columns):
                j_col = next(c for c in df.columns if 'Juros' in c)
                totals['juros'] += df[j_col].apply(clean_value).sum()

            if "dividendo" in name:
                d_col = next((c for c in df.columns if 'Ganhos' in c or 'Dividendo' in c), None)
                if d_col:
                    totals['dividendos'] += df[d_col].apply(clean_value).sum()

        except: continue
    return pd.DataFrame(all_assets), totals

# --- UI ---
uploaded = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if uploaded:
    df_res, rends = process_data(uploaded)
    if not df_res.empty:
        total_p = df_res['Valor'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {total_p:,.2f}")
        c2.metric("Dividendos", f"€ {rends['dividendos']:,.2f}")
        c3.metric("Juros Líquidos", f"€ {rends['juros']:,.2f}")
        
        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.4, title="Distribuição por Ativo"), use_container_width=True)
        with col2:
            st.subheader("Lista de Ativos")
            st.dataframe(df_res.sort_values('Valor', ascending=False)[['Ativo', 'Valor', 'Fonte']], use_container_width=True)
    else:
        st.error("Ainda não conseguimos ler os dados. Tente carregar um ficheiro de cada vez para testar.")
