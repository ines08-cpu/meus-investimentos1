import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor de Portfólio Inteligente")

def clean_df(df):
    # Remove colunas e linhas totalmente vazias
    df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)
    # Limpa nomes de colunas (remove espaços e garante que são strings)
    df.columns = [str(c).strip() for c in df.columns]
    return df

def process_data(uploaded_files):
    all_assets = []
    totals = {'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            # Lemos o ficheiro ignorando as primeiras linhas de lixo (títulos do Excel)
            content = file.getvalue().decode('utf-8')
            df = pd.read_csv(io.StringIO(content), skiprows=0)
            
            # Tentar encontrar a linha do cabeçalho se a primeira não for válida
            if not any(x in str(df.columns) for x in ['ATIVO', 'Ticker', 'Tickers', 'Data', 'Montante']):
                for i in range(1, 6):
                    df = pd.read_csv(io.StringIO(content), skiprows=i)
                    df = clean_df(df)
                    if any(x in str(df.columns) for x in ['ATIVO', 'Ticker', 'Tickers', 'Data', 'Montante']):
                        break
            else:
                df = clean_df(df)

            # 1. OFFLINE (Aforro/PPR)
            if "offline" in name and 'APLICADO' in df.columns:
                temp = df[df['ESTADO'].str.contains('Aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': float(row['APLICADO']), 'Fonte': 'Offline'})

            # 2. XTB ETFs (Análise Setorial)
            elif "analise setorial" in name:
                col_ticker = 'Ticker' if 'Ticker' in df.columns else 'Unnamed: 1'
                col_valor = '€ investido' if '€ investido' in df.columns else 'Unnamed: 6'
                if col_ticker in df.columns:
                    temp = df.dropna(subset=[col_ticker])
                    for _, row in temp.iterrows():
                        if str(row[col_ticker]) not in ['Ticker', 'nan', 'Total']:
                            val = str(row[col_valor]).replace(',', '')
                            all_assets.append({'Ativo': row[col_ticker], 'Cat': 'ETF', 'Valor': float(val), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD
            elif "ações usd" in name and 'Tickers' in df.columns:
                temp = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['Tickers'], 'Cat': 'Ação', 'Valor': float(row['Em Euros']), 'Fonte': 'XTB'})

            # 4. FREEDOM24 (Ações de Oferta)
            elif "sheet" in name and 'Ticker' in df.columns:
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': float(row['Valor']), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS
            if "dividendo" in name:
                col = 'Ganhos reais' if 'Ganhos reais' in df.columns else 'Dividendo'
                if col in df.columns:
                    totals['dividendos'] += pd.to_numeric(df[col], errors='coerce').sum()

            if "juros de capital" in name and 'Juros liquidos' in df.columns:
                totals['juros'] += pd.to_numeric(df['Juros liquidos'], errors='coerce').sum()
            
            if "transacções" in name and 'Montante' in df.columns:
                divs_f24 = df[df['Transação'].str.contains('Dividendos', na=False, case=False)]
                totals['dividendos'] += pd.to_numeric(divs_f24['Montante'], errors='coerce').sum()

        except Exception as e:
            continue

    return pd.DataFrame(all_assets), totals

# --- UI ---
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_final, rendimentos = process_data(files)
    if not df_final.empty:
        total = df_final['Valor'].sum()
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {total:,.2f}")
        c2.metric("Dividendos", f"€ {rendimentos['dividendos']:,.2f}")
        c3.metric("Juros Líquidos", f"€ {rendimentos['juros']:,.2f}")
        
        st.divider()
        col_l, col_r = st.columns([1, 1])
        with col_l:
            fig = px.pie(df_final, values='Valor', names='Cat', hole=0.4, title="Alocação de Ativos")
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.subheader("Lista de Ativos")
            st.dataframe(df_final.sort_values('Valor', ascending=False), use_container_width=True)
    else:
        st.warning("Ficheiros detetados, mas as colunas não coincidem. Verifica os nomes dos ficheiros.")
