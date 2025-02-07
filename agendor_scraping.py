import dash
from dash import Dash, html, dcc, Input, Output, State
import pandas as pd
import requests
from datetime import datetime, timedelta
import plotly.express as px

API_KEY = '881078-ec5446d8-7fbd-4fac-806d-8a4d81eece36'
URL = "https://api.agendor.com.br/v3/deals"

headers = {
    "Authorization": f"Token {API_KEY}",
    "Content-Type": "application/json"
}

# Função para realizar o scraping
def fetch_data():
    next_url = URL
    params = {"per_page": 100}
    all_json_deals_data = []

    while next_url:
        response = requests.get(next_url, headers=headers, params=params)
        json_deal_data = response.json().get('data', [])
        all_json_deals_data.extend(json_deal_data)
        links = response.json().get('links', {})
        next_url = links.get('next', False)

    return all_json_deals_data

# Função para processar os dados
def process_data(deals):
    deal_by_stage = {
        'stage_detail': [], 'stage_name': [], 'stage_number': [], 'stage_status': [],
        'person': [], 'title': [], 'date_created': [], 'date_lost': [], 'date_won': [],
        'organization': [], 'description': []
    }

    for deal in deals:
        deal_by_stage['stage_detail'].append(deal['dealStage']['name'])
        deal_by_stage['stage_number'].append(int(deal['dealStage']['sequence']))
        deal_by_stage['stage_name'].append(deal['dealStage']['funnel']['name'])
        deal_by_stage['stage_status'].append(deal['dealStatus']['name'])
        if deal['person']:
            deal_by_stage['person'].append(deal.get('person', {}).get('id'))
        else:
            deal_by_stage['person'].append(None)
        if deal['organization']:
            deal_by_stage['organization'].append(deal.get('organization', {}).get('id'))
        else: 
            deal_by_stage['organization'].append(None)
        deal_by_stage['date_created'].append(deal['createdAt'])
        deal_by_stage['date_won'].append(deal['wonAt'])
        deal_by_stage['date_lost'].append(deal['lostAt'])
        deal_by_stage['title'].append(deal['title'])
        deal_by_stage['description'].append(deal['description'])

    df = pd.DataFrame(deal_by_stage)
    # Supondo que df já esteja carregado
    # Criar as colunas 'id' e 'type'
    df['id'] = df['person'].fillna(df['organization'])
    df['type'] = df['person'].apply(lambda x: 'person' if pd.notna(x) else 'organization')

    # Remover as colunas 'person' e 'organization'
    df = df.drop(columns=['person', 'organization'])

    # Remover números no início da coluna 'stage_name'
    df['stage_name'] = df['stage_name'].str.replace(r'^\d+\s*', '', regex=True)

    # Filtragem por data
    df['date_created'] = pd.to_datetime(df['date_created']).dt.date

    return df

def process_line_data(df):
    # Transformação da coluna 'stage_detail'
    df['stage_detail'] = df['stage_detail'].replace({
        'CONTATO': '1.1 LEADS',
        'TYPEFORM': '2.1 VALIDAÇÃO',
        'CONTRATO': '3.1 ATIVOS'
    })
    
    return df
    

def process_bar_data(df):
    df_filtered = df[(df['stage_name'] == 'AMBULANTE ESSENCIAL') | df['description'].str.contains("CA", na=False)]


    dt_filtered = df_filtered.loc[df_filtered.groupby('id')['date_created'].idxmax()]
    df_filtered = df.dropna(subset=['id'])

    dt_filtered = dt_filtered[~dt_filtered['stage_detail'].str.contains('1', na=False)]
    d = dt_filtered['stage_detail'].value_counts()

    df_bar = d.reset_index()
    df_bar.columns = ['stage_detail', 'count']
    
    return df_bar


# Buscar os dados **apenas uma vez** ao iniciar o servidor
deals = fetch_data()
df = process_data(deals)
df_line = process_line_data(df)
df_bar = process_bar_data(df)

# Link externo para CSS
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

# Criar o aplicativo Dash
app = Dash(__name__, external_stylesheets=external_stylesheets)
app.title = "Dashboard de Stage Detail"

# Valor inicial do filtro de data
default_start_date = datetime.today() - timedelta(days=60)
default_end_date = datetime.today()

# Layout do dashboard
app.layout = html.Div(children=[
    html.H1(children="Dashboard de Stage Detail", style={'text-align': 'center', 'color': '#003366'}),

    # Container para os filtros dinâmicos
    html.Div(id='date-filters-container', children=[
        html.Div([
            html.Label(f'Filtro 1', style={'color': '#003366'}),
            dcc.DatePickerRange(
                id={'type': 'date-filter', 'index': 0},
                min_date_allowed=df['date_created'].min(),
                max_date_allowed=df['date_created'].max(),
                start_date=default_start_date,
                end_date=default_end_date,
                display_format='DD/MM/YYYY',
                style={'margin-bottom': '10px'}
            )
        ], style={'border': '2px solid #003366', 'padding': '10px', 'border-radius': '5px'})
    ]),

    # Botão para adicionar filtros
    html.Button("Adicionar Filtro", id="add-filter-btn", n_clicks=0, style={'background-color': '#003366', 'color': 'white'}),

    # Gráfico
    dcc.Graph(id='line-chart'),

    # Gráfico de barras
    dcc.Graph(
        id='bar-chart',
        figure=px.bar(
            df_bar, x='stage_detail', y='count', text='count',
            title="Visão Geral por Stage Detail"
        ).update_traces(
            texttemplate='%{text}', textposition='outside'
        ).update_layout(
            uniformtext_minsize=8, uniformtext_mode='hide',
            plot_bgcolor='white', paper_bgcolor='rgba(0,0,0,0)',
            font={'color': '#003366'}
        )
    )
    
], style={'font-family': 'Arial, sans-serif', 'padding': '20px', 'backgroundColor': '#FFFFFF'})

# Callback para adicionar novos filtros dinamicamente
@app.callback(
    Output('date-filters-container', 'children'),
    Input('add-filter-btn', 'n_clicks'),
    State('date-filters-container', 'children')
)
def add_date_filter(n_clicks, children):
    if n_clicks > 0:
        new_filter_index = n_clicks + 1
        new_filter = html.Div([
            html.Label(f'Filtro {new_filter_index}', style={'color': '#003366'}),
            dcc.DatePickerRange(
                id={'type': 'date-filter', 'index': n_clicks},
                min_date_allowed=df['date_created'].min(),
                max_date_allowed=df['date_created'].max(),
                start_date=default_start_date,
                end_date=default_end_date,
                display_format='DD/MM/YYYY',
                style={'margin-bottom': '10px'}
            )
        ], style={'border': '2px solid #003366', 'padding': '10px', 'border-radius': '5px'})
        children.append(new_filter)
    return children

# Callback para atualizar o gráfico baseado nos filtros aplicados
@app.callback(
    Output('line-chart', 'figure'),
    [Input({'type': 'date-filter', 'index': dash.ALL}, 'start_date'),
     Input({'type': 'date-filter', 'index': dash.ALL}, 'end_date')]
)
def update_chart(start_dates, end_dates):
    fig = px.line(title="Evolução por Stage Detail")
    if not start_dates or not end_dates:
        return fig

    for i, (start_date, end_date) in enumerate(zip(start_dates, end_dates)):
        if start_date and end_date:
            start_date = datetime.fromisoformat(start_date).date()
            end_date = datetime.fromisoformat(end_date).date()
            filtered_df = df_line[(df_line['date_created'] >= start_date) & (df['date_created'] <= end_date)]
            filtered_df = filtered_df.loc[filtered_df.groupby('id')['date_created'].idxmax()]


            filtered_df = filtered_df.groupby('stage_detail').size().reset_index(name='total')
            
            fig.add_scatter(x=filtered_df['stage_detail'], y=filtered_df['total'], mode='lines+markers', name=f'Filtro {i + 1}')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font={'color': '#003366'})
    return fig




# Rodar o app
if __name__ == '__main__':
    app.run_server(debug=True)

    