import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

# Configuração Base
st.set_page_config(page_title="Portfolio Tracker Pro - Inês", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { border: 1px solid #e0e0e0; padding: 20px; border-radius: 8px; background: white; }
    </style>
    """, unsafe_allow_header=True)

st.title("🚀 Dashboard de Investimentos Consolidado")
st.sidebar.header("📥 Painel de Controlo")

def process_all_files(uploaded_files):
    assets = []
    cash_flow = {'depositos': 0.0, 'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        # Tentar ler CSV (ajustar separador se necessário)
        try:
            df = pd.read_csv(file)
        except:
            continue

        # 1. PRODUTOS OFFLINE (Aforro, PPR)
        if "offline" in name:
            df_off = pd.read_csv(file, skiprows=1)
            for _, row in df_off[df_off['ESTADO'] == 'Aberto'].iterrows():
                assets.append({
                    'Ativo': row['DESCRIÇÃO'], 'Tipo': row['ATIVO'], 'Fonte': 'Bancos/IGCP',
                    'Valor': float(row['APLICADO']), 'Setor': 'Seguro'
                })

        # 2. XTB - ANALISE SETORIAL (ETFs)
        elif "analise setorial" in name:
            df_xtb = pd.read_csv(file, skiprows=1).dropna(subset=['Unnamed: 1'])
            for _, row in df_xtb.iterrows():
                assets.append({
                    'Ativo': str(row['Unnamed: 1']), 'Tipo': 'ETF', 'Fonte': 'XTB',
                    'Valor': float(row['Unnamed: 6']), 'Setor': str(row['ETFs unidades totais com preço de compra médio'])
                })

        # 3. XTB - AÇÕES USD
        elif "ações usd" in name:
            df_usd = pd.read_csv(file, skiprows=3)
            df_usd = df_usd[df_usd['Tickers'].notna() & (df_usd['Tickers'] != 'Total')]
            for _, row in df_usd.iterrows():
                assets.append({
                    'Ativo': row['Tickers'], 'Tipo': 'Ação', 'Fonte': 'XTB',
                    'Valor': float(row['Em Euros']), 'Setor': 'Tecnologia/Outros'
                })

        # 4. FREEDOM24 - CARTEIRA (Ações Oferta)
        elif "freedom24" in name and "sheet" in name:
            for _, row in df.iterrows():
                assets.append({
                    'Ativo': str(row['Ticker']).replace('.US', ''), 'Tipo': 'Ação (Oferta)', 'Fonte': 'Freedom24',
                    'Valor': float(row['Valor']), 'Setor': 'Vários'
                })

        # 5. DIVIDENDOS E JUROS (XTB & Freedom)
        if "dividendos" in name or "transacções em numerário" in name:
            col_valor = 'Ganhos reais' if 'Ganhos reais' in df.columns else 'Montante'
            val = df[col_valor].dropna().astype(float).sum()
            cash_flow['dividendos'] += val

        if "juros de capital" in name or "cash operations" in name:
            # Captura juros líquidos da XTB
            if 'Juros liquidos' in df.columns:
                cash_flow['juros'] += df['Juros liquidos'].dropna().sum()
            elif 'Type' in df.columns: # Caso do Histórico Cash Operations
                juros = df[df['Type'].str.contains('interest', case=False, na=False)]['Amount'].sum()
                cash_flow['juros'] += juros
                
            # Captura Depósitos para o cálculo de esforço
            if 'Depósito' in df.columns:
                cash_flow['depositos'] += df['Depósito'].dropna().sum()
            elif 'Type' in df.columns:
                deps = df[df['Type'].str.contains('Deposit|Transferência', case=False, na=False)]['Amount'].sum()
                cash_flow['depositos'] += abs(deps)

    return pd.DataFrame(assets), cash_flow

# UI de Upload
uploaded = st.sidebar.file_uploader("Carrega os teus CSVs", accept_multiple_files=True)

if uploaded:
    df_final, flows = process_all_files(uploaded)
    
    if not df_final.empty:
        total_atual = df_final['Valor'].sum()
        
        # Dashboard Principal
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total_atual:,.2f}")
        c2.metric("Capital Injetado", f"€ {flows['depositos']:,.2f}")
        c3.metric("Dividendos Totais", f"€ {flows['dividendos']:,.2f}")
        c4.metric("Juros de Conta", f"€ {flows['juros']:,.2f}")

        st.divider()

        l_col, r_col = st.columns(2)
        with l_col:
            st.subheader("📊 Distribuição por Classe")
            fig = px.pie(df_final, values='Valor', names='Tipo', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

        with r_col:
            st.subheader("🌍 Exposição Setorial")
            fig2 = px.bar(df_final, x='Setor', y='Valor', color='Fonte')
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("📋 Detalhe da Master Table")
        st.dataframe(df_final.sort_values(by='Valor', ascending=False), use_container_width=True)
    else:
        st.info("A aguardar ficheiros válidos...")
