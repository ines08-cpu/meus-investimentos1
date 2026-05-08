import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor de Portfólio - Inês")

def clean_value(val):
    """Limpa strings de valores (remove €, $, espaços) e converte para float."""
    if pd.isna(val): return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    # Se houver pontos e vírgulas (ex: 1.250,50), removemos o ponto e trocamos a vírgula
    if ',' in s and '.' in s:
        s = s.replace('.', '')
    s = s.replace(',', '.')
    # Remover qualquer caractere que não seja número, ponto ou sinal de menos
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
    for i, line in enumerate(lines[:10]):
        if any(x in line for x in ['DESCRIÇÃO', 'Ticker', 'Tickers', 'Data', 'Montante', 'ATIVO', 'APLICADO']):
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
                t_col = next((c for c in df.columns if 'Ticker' in c or 'Unnamed: 1' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'Unnamed: 6' in c), None)
                if t_col and v_col:
                    temp = df.dropna(subset=[t_col])
                    for _, row in temp.iterrows():
                        if str(row[t_col]) not in ['Ticker', 'Total', 'nan', 'ETFs']:
                            all_assets.append({'Ativo': row[t_col], 'Cat': 'ETF', 'Valor': clean_value(row[v_col]), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD
            elif "ações usd" in name and 'Tickers' in df.columns:
                temp = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['Tickers'], 'Cat': 'Ação', 'Valor': clean_value(row['Em Euros']), 'Fonte': 'XTB'})

            # 4. FREEDOM24
            elif "sheet" in name and 'Ticker' in df.columns:
                v_col = 'Valor' if 'Valor' in df.columns else 'Preço de entrada'
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': clean_value(row[v_col]), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS
            if "juros de capital" in name and 'Juros liquidos' in df.columns:
                totals['juros'] += df['Juros liquidos'].apply(clean_value).sum()

            if "dividendos" in name and 'Ganhos reais' in df.columns:
                totals['dividendos'] += df['Ganhos reais'].apply(clean_value).sum()

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
            st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.4, title="Distribuição Real"), use_container_width=True)
        with col2:
            st.subheader("Lista Detalhada")
            st.dataframe(df_res.sort_values('Valor', ascending=False), use_container_width=True)
    else:
        st.error("Dados lidos como zero. Verifica se os CSVs são os corretos.")
