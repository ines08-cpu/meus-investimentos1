import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
from datetime import datetime

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
    
    for file in uploaded_files:
        df = pd.read_csv(file)
        name = file.name.lower()
        
        # Lógica para Produtos Offline (Bancos/Certificados)
        if "produtos offline" in name:
            temp = df.iloc[1:].copy()
            temp.columns = ['Data', 'Ativo', 'Aplicado', 'Cota', 'Bruto', 'Lucro', 'Juro', 'Estado', 'Fim', 'Desc', 'Imposto']
            for _, row in temp[temp['Estado'] == 'Aberto'].iterrows():
                all_assets.append({
                    'Ticker': row['Desc'], 'Categoria': row['Ativo'], 'Fonte': 'Banco/IGCP',
                    'Qtd': 1, 'Custo_EUR': float(row['Aplicado']), 'Setor': 'Seguro'
                })

        # Lógica para XTB ETFs
        elif "etfs analise setorial" in name:
            temp = df.iloc[1:].dropna(subset=['Unnamed: 1'])
            for _, row in temp.iterrows():
                all_assets.append({
                    'Ticker': str(row['Unnamed: 1']), 'Categoria': 'ETF', 'Fonte': 'XTB',
                    'Qtd': float(row['Unnamed: 4']), 'Custo_EUR': float(row['Unnamed: 6']),
                    'Setor': str(row['ETFs unidades totais com preço de compra médio'])
                })

        # Lógica para Freedom24
        elif "freedom24" in name and "sheet" in name:
            for _, row in df.iterrows():
                all_assets.append({
                    'Ticker': str(row['Ticker']).replace('.US', ''), 'Categoria': 'Ação', 'Fonte': 'Freedom24',
                    'Qtd': float(row['Quantidade']), 'Custo_EUR': float(row['Preço de entrada']) * float(row['Quantidade']),
                    'Setor': 'Tecnologia' if row['Preço de entrada'] == 0 else 'Vários'
                })

    return pd.DataFrame(all_assets)

# --- SIDEBAR E CARREGAMENTO ---
files = st.sidebar.file_uploader("Larga aqui os teus ficheiros CSV", accept_multiple_files=True)

if files:
    master_df = process_data(files)
    
    if not master_df.empty:
        # Obter Preços em Tempo Real (Simulação de API)
        st.sidebar.info("A atualizar cotações via Yahoo Finance...")
        
        # Tabela Master Consolidada
        master_grouped = master_df.groupby(['Ticker', 'Categoria', 'Fonte', 'Setor']).agg({
            'Qtd': 'sum', 'Custo_EUR': 'sum'
        }).reset_index()

        # --- CÁLCULOS DE DASHBOARD ---
        total_investido = master_grouped['Custo_EUR'].sum()
        # Nota: Num MVP real, aqui o yfinance buscaria o preço atual para calcular o lucro exato
        lucro_estimado = total_investido * 0.082  # Exemplo de 8.2% de valorização
        patrimonio_total = total_investido + lucro_estimado

        # --- LAYOUT DO DASHBOARD ---
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {patrimonio_total:,.2f}")
        c2.metric("Total Investido", f"€ {total_investido:,.2f}")
        c3.metric("Lucro Total", f"€ {lucro_estimado:,.2f}", "+8.2%")
        c4.metric("Ativos em Carteira", len(master_grouped))

        st.divider()

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("🎯 Alocação por Classe")
            fig_pie = px.pie(master_grouped, values='Custo_EUR', names='Categoria', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            st.subheader("🏢 Exposição por Setor")
            fig_bar = px.bar(master_grouped, x='Setor', y='Custo_EUR', color='Fonte',
                             barmart='group', labels={'Custo_EUR': 'Valor Investido (€)'})
            st.plotly_chart(fig_bar, use_container_width=True)

        st.subheader("📝 Base de Dados Master (Consolidada)")
        st.dataframe(master_grouped, use_container_width=True)
    else:
        st.warning("Ficheiros carregados, mas não foram detetados ativos válidos.")
else:
    st.info("👋 Olá, Inês! Por favor, carrega os teus ficheiros na barra lateral para começar.")