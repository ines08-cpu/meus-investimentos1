import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Investimentos Inês", layout="wide")

st.title("📊 Gestor de Portfólio Inteligente")
st.sidebar.header("📁 Upload de Ficheiros")

def process_data(uploaded_files):
    all_assets = []
    totals = {'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            # 1. OFFLINE (Aforro/PPR) - Procura a tabela a partir da linha 1
            if "offline" in name:
                df = pd.read_csv(file, skiprows=1)
                df.columns = [c.upper().strip() for c in df.columns]
                temp = df[df['ESTADO'].str.contains('Aberto', na=False)].copy()
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': float(row['APLICADO']), 'Fonte': 'Offline'})

            # 2. XTB ETFs - Procura a partir da linha 1
            elif "analise setorial" in name:
                df = pd.read_csv(file, skiprows=1)
                # O ticker está na coluna 'Ticker' ou 'Unnamed: 1'
                ticker_col = 'Ticker' if 'Ticker' in df.columns else 'Unnamed: 1'
                valor_col = '€ investido' if '€ investido' in df.columns else 'Unnamed: 6'
                temp = df.dropna(subset=[ticker_col])
                for _, row in temp.iterrows():
                    if str(row[ticker_col]) != 'Ticker':
                        all_assets.append({'Ativo': row[ticker_col], 'Cat': 'ETF', 'Valor': float(row[valor_col]), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD - Procura a partir da linha 3
            elif "ações usd" in name:
                df = pd.read_csv(file, skiprows=3)
                df = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')]
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Tickers'], 'Cat': 'Ação', 'Valor': float(row['Em Euros']), 'Fonte': 'XTB'})

            # 4. FREEDOM24 - Ações de Oferta
            elif "sheet" in name:
                df = pd.read_csv(file)
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': float(row['Valor']), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS (Dividendos e Juros)
            if "dividendo" in name or "transacções" in name:
                df = pd.read_csv(file, skiprows=2 if "dividendo" in name else 0)
                col = 'Ganhos reais' if 'Ganhos reais' in df.columns else 'Montante'
                totals['dividendos'] += pd.to_numeric(df[col], errors='coerce').sum()

            if "juros de capital" in name:
                df = pd.read_csv(file, skiprows=1)
                totals['juros'] += pd.to_numeric(df['Juros liquidos'], errors='coerce').sum()

        except Exception as e:
            st.sidebar.error(f"Erro no ficheiro {file.name}")
            
    return pd.DataFrame(all_assets), totals

files = st.sidebar.file_uploader("Larga aqui os teus CSVs", accept_multiple_files=True)

if files:
    df_final, rendimentos = process_data(files)
    if not df_final.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {df_final['Valor'].sum():,.2f}")
        c2.metric("Dividendos", f"€ {rendimentos['dividendos']:,.2f}")
        c3.metric("Juros XTB", f"€ {rendimentos['juros']:,.2f}")
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.pie(df_final, values='Valor', names='Cat', title="Distribuição por Ativo")
            st.plotly_chart(fig)
        with col2:
            st.dataframe(df_final.sort_values('Valor', ascending=False), use_container_width=True)
    else:
        st.warning("Ficheiros lidos, mas os nomes das colunas não batem certo. Verifica se os CSVs estão corretos.")
