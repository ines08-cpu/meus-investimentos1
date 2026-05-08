iimport streamlit as st
import pandas as pd
import plotly.express as px
import io

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Gestor de Portfólio Inteligente")

def smart_read(file):
    """Lê o CSV tentando detetar o separador e a linha do cabeçalho."""
    content = file.getvalue().decode('utf-8')
    # Tenta detetar se o separador é ; ou ,
    sep = ';' if content.count(';') > content.count(',') else ','
    
    # Tenta encontrar a linha onde estão os dados reais
    lines = content.split('\n')
    skip = 0
    for i, line in enumerate(lines[:10]):
        if any(x in line for x in ['DESCRIÇÃO', 'Ticker', 'Tickers', 'Data', 'Montante', 'ATIVO']):
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
            
            # 1. OFFLINE
            if "offline" in name and 'APLICADO' in df.columns:
                temp = df[df['ESTADO'].str.contains('Aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row['DESCRIÇÃO'], 'Cat': row['ATIVO'], 'Valor': float(str(row['APLICADO']).replace(',','.')), 'Fonte': 'Offline'})

            # 2. XTB ETFs
            elif "analise setorial" in name and ('Ticker' in df.columns or 'Unnamed: 1' in df.columns):
                t_col = 'Ticker' if 'Ticker' in df.columns else 'Unnamed: 1'
                v_col = '€ investido' if '€ investido' in df.columns else 'Unnamed: 6'
                temp = df.dropna(subset=[t_col])
                for _, row in temp.iterrows():
                    if str(row[t_col]) not in ['Ticker', 'Total', 'nan']:
                        val = str(row[v_col]).replace(' ', '').replace(',','.')
                        all_assets.append({'Ativo': row[t_col], 'Cat': 'ETF', 'Valor': float(val), 'Fonte': 'XTB'})

            # 3. XTB AÇÕES USD
            elif "ações usd" in name and 'Tickers' in df.columns:
                temp = df[df['Tickers'].notna() & (df['Tickers'] != 'Total')]
                for _, row in temp.iterrows():
                    val = str(row['Em Euros']).replace(' ', '').replace(',','.')
                    all_assets.append({'Ativo': row['Tickers'], 'Cat': 'Ação', 'Valor': float(val), 'Fonte': 'XTB'})

            # 4. FREEDOM24
            elif "sheet" in name and 'Ticker' in df.columns:
                for _, row in df.iterrows():
                    val = str(row['Valor']).replace(' ', '').replace(',','.')
                    all_assets.append({'Ativo': row['Ticker'], 'Cat': 'Ação (Oferta)', 'Valor': float(val), 'Fonte': 'Freedom24'})

            # 5. RENDIMENTOS
            if "juros de capital" in name and 'Juros liquidos' in df.columns:
                totals['juros'] += pd.to_numeric(df['Juros liquidos'].astype(str).str.replace(',','.'), errors='coerce').sum()

            if "dividendos" in name and 'Ganhos reais' in df.columns:
                totals['dividendos'] += pd.to_numeric(df['Ganhos reais'].astype(str).str.replace(',','.'), errors='coerce').sum()

        except Exception as e:
            continue

    return pd.DataFrame(all_assets), totals

files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_final, rends = process_data(files)
    if not df_final.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {df_final['Valor'].sum():,.2f}")
        c2.metric("Dividendos", f"€ {rends['dividendos']:,.2f}")
        c3.metric("Juros Líquidos", f"€ {rends['juros']:,.2f}")
        
        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.pie(df_final, values='Valor', names='Cat', hole=0.4, title="Distribuição"), use_container_width=True)
        with col2:
            st.dataframe(df_final.sort_values('Valor', ascending=False), use_container_width=True)
    else:
        st.error("Erro: Verifica se os CSVs têm os nomes certos (ex: 'offline', 'setorial', 'ações usd').")
