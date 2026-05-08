import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf

# Configuração da Página
st.set_page_config(page_title="Dashboard de Investimentos - Inês", layout="wide")

# --- ESTILOS CUSTOMIZADOS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Gestor de Portfólio Inteligente")
st.sidebar.header("📁 Upload de Dados")

# --- FUNÇÕES DE PROCESSAMENTO ---
def process_data(uploaded_files):
    all_assets = []
    cash_flow = {'depositos': 0.0, 'juros': 0.0, 'dividendos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        
        try:
            # 1. Produtos Offline (Bancos/Certificados)
            if "offline" in name:
                df = pd.read_csv(file, skiprows=1)
                temp = df[df['ESTADO'] == 'Aberto'].copy()
                for _, row in temp.iterrows():
                    all_assets.append({
                        'Ticker': str(row['DESCRIÇÃO']), 'Categoria': str(row['ATIVO']), 'Fonte': 'Bancos/IGCP',
                        'Valor_EUR': float(row['APLICADO']), 'Setor': 'Seguro'
                    })

            # 2. XTB ETFs (Análise Setorial)
            elif "analise setorial" in name:
                df = pd.read_csv(file, skiprows=1).dropna(subset=['Unnamed: 1'])
                for _, row in df.iterrows():
                    all_assets.append({
                        'Ticker': str(row['Unnamed: 1']), 'Categoria': 'ETF', 'Fonte': 'XTB',
                        'Valor_EUR': float(row['Unnamed: 6']), 'Setor': str(row['ETFs unidades totais com preço de compra médio'])
                    })

            # 3. XTB Ações USD
            elif "ações usd" in name:
                df = pd.read_csv(file, skiprows=3)
                df = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')]
                for _, row in df.iterrows():
                    all_assets.append({
                        'Ticker': str(row['Tickers']), 'Categoria': 'Ação', 'Fonte': 'XTB',
                        'Valor_EUR': float(row['Em Euros']), 'Setor': 'Tecnologia'
                    })

            # 4. Freedom24 (Ações Oferta)
            elif "freedom24" in name and "sheet" in name:
                df = pd.read_csv(file)
                for _, row in df.iterrows():
                    all_assets.append({
                        'Ticker': str(row['Ticker']).replace('.US', ''), 'Categoria': 'Ação (Oferta)', 'Fonte': 'Freedom24',
                        'Valor_EUR': float(row['Valor']), 'Setor': 'Vários'
                    })

            # 5. Dividendos e Juros (Processamento de Fluxo)
            if "dividendos" in name:
                df = pd.read_csv(file)
                col = 'Ganhos reais' if 'Ganhos reais' in df.columns else 'Dividendo'
                cash_flow['dividendos'] += pd.to_numeric(df[col], errors='coerce').sum()
            
            if "juros de capital" in name:
                df = pd.read_csv(file, skiprows=1)
                cash_flow['juros'] += pd.to_numeric(df['Juros liquidos'], errors='coerce').sum()

            if "cash operations" in name:
                df = pd.read_csv(file, skiprows=4)
                if 'Type' in df.columns:
                    deps = df[df['Type'].str.contains('Deposit|Transfer', case=False, na=False)]['Amount'].sum()
                    cash_flow['depositos'] += abs(float(deps))

        except Exception as e:
            st.sidebar.error(f"Erro ao ler {file.name}")
            continue

    return pd.DataFrame(all_assets), cash_flow

# --- INTERFACE ---
uploaded_files = st.sidebar.file_uploader("Arraste os seus ficheiros CSV aqui", accept_multiple_files=True)

if uploaded_files:
    master_df, flows = process_data(uploaded_files)
    
    if not master_df.empty:
        total_patrimonio = master_df['Valor_EUR'].sum()
        
        # Cartões de Métricas
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total_patrimonio:,.2f}")
        c2.metric("Dividendos Recebidos", f"€ {flows['dividendos']:,.2f}")
        c3.metric("Juros XTB", f"€ {flows['juros']:,.2f}")
        c4.metric("Nº de Ativos", len(master_df))

        st.divider()

        col_l, col_r = st.columns(2)
        with col_l:
            st.subheader("🎯 Alocação por Classe")
            fig_pie = px.pie(master_df, values='Valor_EUR', names='Categoria', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_r:
            st.subheader("🏢 Valor por Setor")
            fig_bar = px.bar(master_df, x='Setor', y='Valor_EUR', color='Fonte', barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("📑 Tabela Consolidada")
        st.dataframe(master_df.sort_values(by='Valor_EUR', ascending=False), use_container_width=True)
    else:
        st.warning("Ficheiros carregados, mas não foram detetados dados compatíveis.")
else:
    st.info("👋 Olá, Inês! Carregue os seus ficheiros CSV na barra lateral para gerar o dashboard.")
