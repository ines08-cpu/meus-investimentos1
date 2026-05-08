import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor do Portfólio Inteligente da Inês")

def try_read_csv(file):
    # Tenta ler o ficheiro e encontrar onde começa a tabela real
    try:
        # Lê as primeiras 10 linhas para encontrar o cabeçalho
        df_test = pd.read_csv(file, nrows=10, header=None)
        header_row = 0
        for i, row in df_test.iterrows():
            row_str = row.astype(str).values
            if any(x in row_str for x in ['Ticker', 'TICKER', 'Tickers', 'ATIVO', 'DESCRIÇÃO', 'Data', 'DATA']):
                header_row = i
                break
        file.seek(0)
        return pd.read_csv(file, skiprows=header_row)
    except:
        return None

def process_data(uploaded_files):
    all_assets = []
    totals = {'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        df = try_read_csv(file)
        if df is None: continue
        
        # Limpar colunas vazias e nomes
        df.columns = [str(c).strip() for c in df.columns]
        
        try:
            # 1. OFFLINE (Aforro/PPR)
            if "offline" in name:
                temp = df[df['ESTADO'].str.contains('Aberto', na=False, case=False)].copy()
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': float(row['APLICADO']), 'Fonte': 'Offline'})

            # 2. XTB ETFs
            elif "analise setorial" in name:
                col_ticker = 'Ticker' if 'Ticker' in df.columns else 'Unnamed: 1'
                col_valor = '€ investido' if '€ investido' in df.columns else 'Unnamed: 6'
                temp = df.dropna(subset=[col_ticker])
                for _, row in temp.iterrows():
                    if str(row[col_ticker]) not in ['Ticker', 'nan', 'Total']:
                        val = str(row[col_valor]).replace(',', '')
                        all_assets.append({'Ativo': row[col_ticker], 'Cat': 'ETF', 'Valor': float(val), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD
            elif "ações usd" in name:
                temp = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')].copy()
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['Tickers'], 'Cat': 'Ação', 'Valor': float(row['Em Euros']), 'Fonte': 'XTB'})

            # 4. FREEDOM24
            elif "sheet" in name:
                for _, row in df.iterrows():
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': float(row['Valor']), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS
            if "dividendo" in name:
                col = 'Ganhos reais' if 'Ganhos reais' in df.columns else 'Dividendo'
                totals['dividendos'] += pd.to_numeric(df[col], errors='coerce').sum()

            if "juros de capital" in name:
                totals['juros'] += pd.to_numeric(df['Juros liquidos'], errors='coerce').sum()
            
            if "transacções" in name: # Dividendos Freedom24
                divs_f24 = df[df['Transação'].str.contains('Dividendos', na=False, case=False)]
                totals['dividendos'] += pd.to_numeric(divs_f24['Montante'], errors='coerce').sum()

        except Exception as e:
            continue

    return pd.DataFrame(all_assets), totals

files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_final, rendimentos = process_data(files)
    if not df_final.empty:
        # Layout de métricas
        c1, c2, c3 = st.columns(3)
        total = df_final['Valor'].sum()
        c1.metric("Património Total", f"€ {total:,.2f}")
        c2.metric("Dividendos Acumulados", f"€ {rendimentos['dividendos']:,.2f}")
        c3.metric("Juros Líquidos XTB", f"€ {rendimentos['juros']:,.2f}")
        
        st.divider()
        col_l, col_r = st.columns([1, 1])
        with col_l:
            fig = px.pie(df_final, values='Valor', names='Cat', hole=0.4, title="Onde está o teu dinheiro")
            st.plotly_chart(fig, use_container_width=True)
        with col_r:
            st.subheader("Top Ativos")
            st.dataframe(df_final.sort_values('Valor', ascending=False)[['Ativo', 'Valor', 'Fonte']], use_container_width=True)
    else:
        st.error("Erro na leitura. Confirma se os ficheiros são os CSVs originais.")
