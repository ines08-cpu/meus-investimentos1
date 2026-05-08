import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor de Portfólio Inteligente")

def process_data(uploaded_files):
    all_assets = []
    totals = {'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        content = file.getvalue().decode('utf-8')
        
        try:
            # 1. OFFLINE (Aforro/PPR) - Pula 1 linha
            if "offline" in name:
                df = pd.read_csv(io.StringIO(content), skiprows=1)
                temp = df[df['ESTADO'].str.contains('Aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': float(row['APLICADO']), 'Fonte': 'Offline'})

            # 2. XTB ETFs (Análise Setorial) - Pula 1 linha
            elif "analise setorial" in name:
                df = pd.read_csv(io.StringIO(content), skiprows=1)
                temp = df.dropna(subset=['Ticker'])
                for _, row in temp.iterrows():
                    if str(row['Ticker']) not in ['Ticker', 'Total', 'nan']:
                        all_assets.append({'Ativo': row['Ticker'], 'Cat': row['Setor'], 'Valor': float(row['€ investido']), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD - Pula 2 linhas (Tabela começa na linha 3)
            elif "ações usd" in name:
                df = pd.read_csv(io.StringIO(content), skiprows=2)
                df.columns = [c.strip() for c in df.columns]
                temp = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['Tickers'], 'Cat': 'Ação', 'Valor': float(row['Em Euros']), 'Fonte': 'XTB'})

            # 4. FREEDOM24 (Ações de Oferta) - Sem pular linhas
            elif "sheet" in name:
                df = pd.read_csv(io.StringIO(content))
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': float(row['Valor']), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS (Juros e Dividendos)
            if "juros de capital" in name:
                df = pd.read_csv(io.StringIO(content), skiprows=1)
                totals['juros'] += pd.to_numeric(df['Juros liquidos'], errors='coerce').sum()

            if "dividendos" in name:
                df = pd.read_csv(io.StringIO(content), skiprows=2) # Pula as linhas de título do Excel
                df.columns = [c.strip() for c in df.columns]
                totals['dividendos'] += pd.to_numeric(df['Ganhos reais'], errors='coerce').sum()

            if "transacções" in name: # Freedom24
                df = pd.read_csv(io.StringIO(content))
                divs = df[df['Transação'].str.contains('Dividendos', na=False, case=False)]
                totals['dividendos'] += pd.to_numeric(divs['Montante'], errors='coerce').sum()

        except Exception as e:
            st.sidebar.error(f"Erro ao processar {file.name}")
            continue

    return pd.DataFrame(all_assets), totals

# --- INTERFACE ---
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_final, rendimentos = process_data(files)
    if not df_final.empty:
        total = df_final['Valor'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {total:,.2f}")
        c2.metric("Dividendos XTB/F24", f"€ {rendimentos['dividendos']:,.2f}")
        c3.metric("Juros XTB Líquidos", f"€ {rendimentos['juros']:,.2f}")
        
        st.divider()
        col_l, col_r = st.columns([1, 1])
        with col_l:
            fig = px.pie(df_final, values='Valor', names='Cat', hole=0.4, title="Distribuição de Ativos")
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.subheader("Lista Detalhada")
            st.dataframe(df_final.sort_values('Valor', ascending=False), use_container_width=True)
    else:
        st.warning("Ficheiros detetados. Por favor, garante que os nomes dos ficheiros contêm as palavras: 'offline', 'setorial', 'ações usd', 'sheet', 'dividendos', 'juros' ou 'transacções'.")
