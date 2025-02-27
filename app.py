import dash
from dash import Dash, html, dcc, Input, Output, State, dash_table
import pandas as pd
import requests
import os
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

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
def process_data(deals, filter_by_status='Em andamento'):
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

    df['stage_name'] = df['stage_name'].str.replace(r'^\d+\s*', '', regex=True)

    # Filtragem por data
    df['date_created'] = pd.to_datetime(df['date_created']).dt.date
    df['date_won'] = pd.to_datetime(df['date_won']).dt.date
    df['date_lost'] = pd.to_datetime(df['date_lost']).dt.date
    
    if filter_by_status:
        df = df[df['stage_status'] == 'Em andamento']
    
    return df
    

def process_line_data(df):
    df = df.copy()
    
    # Transformação da coluna 'stage_detail'
    df['stage_detail'] = df['stage_detail'].replace({
        'CONTATO': '1.1 LEADS',
        'TYPEFORM': '2.1 VALIDAÇÃO',
        'CONTRATO': '3.1 ATIVOS'
    })
    
    # Remover as linhas onde 'stage_detail' começa com "5 " ou "6 "
    df = df[~df['stage_detail'].str.startswith(('5', '6'))]
    
    return df
    

def process_bar_data(df):
    df = df.copy()
    
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
df_line['date_created'] = pd.to_datetime(df_line['date_created']).dt.date
df_bar = process_bar_data(df)

# Função de processamento da linha de dados
def process_line_data(df):
    df = df.copy()
    df['stage_detail'] = df['stage_detail'].replace({
        'CONTATO': '1.1 LEADS',
        'TYPEFORM': '2.1 VALIDAÇÃO',
        'CONTRATO': '3.1 ATIVOS'
    })
    df = df[~df['stage_detail'].str.startswith(('5', '6'))]
    return df

def sort_stage_detail(stage_detail):
    """Ordena os valores de 'stage_detail' assumindo o formato numérico 'X.Y'"""
    try:
        parts = stage_detail.split(' ')[0].split('.')  # Pega apenas a parte numérica antes do espaço
        parts = [int(p) if p.isdigit() else 0 for p in parts]  # Converte para inteiro, tratando casos inesperados
        return tuple(parts)  # Retorna como tupla para ordenação correta
    except Exception as e:
        print(f"Erro ao tentar ordenar stage_detail '{stage_detail}': {e}")
        return (float('inf'),)  # Empurra valores problemáticos para o final da ordenação
        
# Link externo para CSS
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

# Criar o aplicativo Dash
app = Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server  # Esta linha é crucial para o deploy com Gunicorn
app.title = "Essencial - Dashbard"

# Valor inicial do filtro de data
default_start_date = datetime.today() - timedelta(days=60)
default_end_date = datetime.today()

# Ajuste para data de início dos leads
leads_start_date = (default_start_date + timedelta(days=30)).date()  # Converter para tipo 'date'

# Filtrando os dados para considerar apenas 'LEADS' no 'stage_detail'
leads_df = df_line[df_line['stage_detail'] == '1.1 LEADS']

# Convertendo 'date_created' para tipo 'date' para comparações
leads_df['date_created'] = pd.to_datetime(leads_df['date_created']).dt.date

# Filtrando pela data
leads_df = leads_df[leads_df['date_created'] >= leads_start_date]


# Contando a quantidade de leads por data
leads_count = leads_df.groupby('date_created').size().reset_index(name='total_leads')

df_stage_counts = df.loc[df.groupby('id')['date_created'].idxmax()]

stage_counts = df_stage_counts['stage_name'].value_counts().reset_index()
stage_counts.columns = ['Stage Name', 'Client Count']


# Layout do dashboard
app.layout = html.Div(children=[
    # Cabeçalho com título e logo
    html.Div([
        html.Img(src='../assets/essencial_logo.jpg', style={'height': '80px', 'margin-right': '20px'}),
        html.H1("Essencial", style={'color': '#003366', 'margin': '0'})
    ], style={'display': 'flex', 'align-items': 'center', 'justify-content': 'center', 'padding': '20px'}),
    
    # Dropdown estilizado e centralizado
    html.Div([
        dcc.Dropdown(
            id='stage-detail-filter',
            options=[{'label': 'Geral', 'value': 'Geral'}] + 
                    [{'label': stage, 'value': stage} for stage in sorted(df_line['stage_name'].unique()) 
                     if stage != "AMBULANTE ESSENCIAL"],
            value='Geral',
            clearable=False,
            style={
                'width': '80%', 'padding': '12px', 'borderRadius': '10px',
                'backgroundColor': '#f5f5f5', 'border': '1px solid #ccc',
                'fontSize': '20px', 'textAlign': 'center', 'margin-top': '5px'
            }
        )
    ], style={'display': 'flex', 'justify-content': 'center', 'margin-top': '20px', 'margin-bottom': '20px'}),
    
    html.Div([
        html.H3("Contagem de Cliente por Estágio", style={'color': '#003366', 'textAlign': 'center', 'margin-bottom': '20px'}),
        dash_table.DataTable(
            id='client-stage-table',  # Adicionamos um ID para o callback
            columns=[
                {'name': 'Nome do Estágio', 'id': 'Stage Name'},
                {'name': 'Quantidade de Clientes', 'id': 'Client Count'}
            ],
            data=stage_counts.to_dict('records'),
            style_table={'margin': 'auto', 'width': '60%', 'borderRadius': '10px', 'overflow': 'hidden'},
            style_header={
                'backgroundColor': '#003366', 'color': 'white', 'fontWeight': 'bold', 'textAlign': 'center',
                'border': '1px solid white'
            },
            style_data={
                'backgroundColor': '#f9f9f9', 'color': '#003366', 'textAlign': 'center', 'border': '1px solid #ddd'
            },
            style_data_conditional=[
                {'if': {'row_index': 'odd'}, 'backgroundColor': '#e6f2ff'}
            ],
            page_size=10
        )
    ], style={'margin-bottom': '40px'}),

    # Container para os filtros dinâmicos
    html.Div(id='date-filters-container', children=[
        html.Div([
            html.Label(f'Filtro 1', style={'color': '#003366'}),
            dcc.DatePickerRange(
                id={'type': 'date-filter', 'index': 0},
                min_date_allowed=df_line['date_created'].min(),
                max_date_allowed=df_line['date_created'].max(),
                start_date=default_start_date,
                end_date=default_end_date,
                display_format='DD/MM/YYYY',
                style={'marginBottom': '10px'}
            )
        ], style={'border': '2px solid #003366', 'padding': '10px', 'borderRadius': '5px'})
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
    ),
    
    # 📌 **Novo Gráfico**: Barras por Stage Name (Clientes Ganhos)
    html.Div(id='chart-won-container'),
    
    html.Div(id='chart-lost-container'),
    
    dcc.Graph(id='lost-reason-chart'),
    
    # Gráfico de evolução Leads (sem callback, independente)
    dcc.Graph(
        id='evolucao-leads',
        figure=px.line(
            leads_count, 
            x='date_created', 
            y='total_leads', 
            title="Evolução de Leads", 
            markers=True
        ).update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)', 
            font={'color': '#003366'}
        ),
        style={'display': 'block'}
    ),
    
], style={'font-family': 'Arial, sans-serif', 'padding': '20px', 'backgroundColor': '#FFFFFF'})


@app.callback(
    Output('date-filters-container', 'children'),
    [Input('add-filter-btn', 'n_clicks'),
     Input({'type': 'remove-filter-btn', 'index': dash.ALL}, 'n_clicks')],
    State('date-filters-container', 'children')
)
def update_filters(n_clicks, remove_clicks, children):
    ctx = dash.callback_context

    if not children:
        children = []

    # 🔍 Verifica se um botão "Remover" foi acionado
    if ctx.triggered and 'remove-filter-btn' in ctx.triggered[0]['prop_id']:
        try:
            triggered_id = eval(ctx.triggered[0]['prop_id'].replace(".n_clicks", ""))
            index_to_remove = triggered_id.get("index", None)

            if index_to_remove is not None:
                # 🔥 Remove elementos filtrando pelo ID diretamente
                children = [child for child in children if 
                            not (isinstance(child, dict) and 'props' in child and 
                                 any('id' in c['props'] and c['props']['id'].get('index') == index_to_remove
                                     for c in child['props'].get('children', [])))]
                return children
        except Exception as e:
            print(f"Erro ao remover filtro: {e}", flush=True)

    # Se for o botão de adicionar filtro
    if n_clicks > 0:
        new_filter_index = n_clicks + 1
        new_filter = html.Div([
            html.Label(f'Filtro {new_filter_index}', style={'color': '#003366'}),
            dcc.DatePickerRange(
                id={'type': 'date-filter', 'index': new_filter_index},
                min_date_allowed=df_line['date_created'].min(),
                max_date_allowed=df_line['date_created'].max(),
                start_date=default_start_date,
                end_date=default_end_date,
                display_format='DD/MM/YYYY',
                style={'marginRight': '10px'}
            ),
            html.Button("Remover", id={'type': 'remove-filter-btn', 'index': new_filter_index},
                        n_clicks=0, style={'background-color': 'red', 'color': 'white', 'margin-left': '10px'})
        ], style={'border': '2px solid #003366', 'padding': '10px', 'border-radius': '5px', 'margin-bottom': '10px'})
        children.append(new_filter)

    return children


# Criamos um DataFrame auxiliar para mapear stage_name e stage_detail
df_stage_mapping = df_line[['stage_name', 'stage_detail']].drop_duplicates(subset=['stage_detail'])

# Filtramos apenas os detalhes ordenados e fazemos um merge para manter a relação com stage_name
df_stage_mapping = df_stage_mapping.sort_values(by='stage_detail', key=lambda x: x.map(sort_stage_detail))

@app.callback(
    Output('line-chart', 'figure'),
    [Input({'type': 'date-filter', 'index': dash.ALL}, 'start_date'),
    Input({'type': 'date-filter', 'index': dash.ALL}, 'end_date'),
    Input('stage-detail-filter', 'value'),
])
def update_chart(start_dates, end_dates, selected_stage_name):
    fig = go.Figure()
    if not start_dates or not end_dates:
        return fig

    for i, (start_date, end_date) in enumerate(zip(start_dates, end_dates)):
        if start_date and end_date:
            start_date = datetime.fromisoformat(start_date).date()
            end_date = datetime.fromisoformat(end_date).date()
            filtered_df = df_line[(df_line['date_created'] >= start_date) & (df_line['date_created'] <= end_date)]
            
            if selected_stage_name != 'Geral':
                filtered_df = filtered_df[filtered_df['stage_name'] == selected_stage_name]
                full_df = df_stage_mapping[df_stage_mapping['stage_name'] == selected_stage_name]
                full_df = full_df[['stage_detail']]
            else:
                full_df = df_stage_mapping[['stage_detail']]
            
            filtered_df = filtered_df.loc[filtered_df.groupby('id')['date_created'].idxmax()]

            # Agrupar os dados por 'stage_detail'
            filtered_df = filtered_df.groupby('stage_detail').size().reset_index(name='total')

            # Adicionar valores ausentes para garantir alinhamento com o eixo X fixo
            filtered_df = full_df.merge(filtered_df, on='stage_detail', how='left').fillna(0)

            # Adicionar linha ao gráfico
            fig.add_scatter(
                x=filtered_df['stage_detail'],
                y=filtered_df['total'],
                mode='lines+markers',
                name=f'Filtro {i + 1}'
            )

    # Configurar layout
    fig.update_layout(
        title="Evolução por Stage Detail",
        xaxis_title="Stage Detail",
        yaxis_title="Total",
        xaxis=dict(categoryorder='array', categoryarray=full_df['stage_detail']),  # Fixar a ordem do eixo X
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)', 
        font={'color': '#003366'},
        showlegend=True
    )

    return fig

@app.callback(
    Output('client-stage-table', 'data'), # Atualiza a tabela
    [Input('stage-detail-filter', 'value')]
)
def update_data_table(selected_stage_name):
    global df_stage_counts
    df_stage_counts_temp = df_stage_counts.copy()
    
    # Se for "Geral", mostrar todos os estágios
    if selected_stage_name == 'Geral':
        stage_counts = df_stage_counts_temp['stage_name'].value_counts().reset_index()
        stage_counts.columns = ['Stage Name', 'Client Count']
    else: 
        df_stage_counts_temp = df_stage_counts_temp[df_stage_counts_temp['stage_name'] == selected_stage_name]
                                
        stage_counts = (df_stage_counts_temp['stage_detail']
                        .value_counts()
                        .reset_index()
                        .sort_values(by='stage_detail', key=lambda x: x.map(sort_stage_detail)))
        stage_counts.columns = ['Stage Name', 'Client Count']
        
    return stage_counts.to_dict('records')  # Retorna os dados no formato correto

@app.callback(
    Output('bar-chart', 'figure'),
    Input('stage-detail-filter', 'value')
)
def update_bar_chart(selected_stage_name):
    # Filtrar os dados conforme a seleção do dropdown
    if selected_stage_name == 'Geral':
        filtered_df = df_bar.copy()  # Mantém todos os dados
    else:
        filtered_df = (
            df[df['stage_name'] == selected_stage_name]  # Filtra pelo stage_name
            .loc[lambda df_: df_.groupby('id')['date_created'].idxmax()]  # Mantém o último registro por ID
            .dropna(subset=['id'])  # Remove linhas com id nulo
            ['stage_detail'].value_counts()  # Conta os valores de stage_detail
            .reset_index(name='count')  # Define o nome correto da coluna gerada
        )

    # Criar o gráfico atualizado
    fig = px.bar(
        filtered_df, x='stage_detail', y='count', text='count',
        title="Visão Geral por Stage Detail"
    ).update_traces(
        texttemplate='%{text}', textposition='outside'
    ).update_layout(
        uniformtext_minsize=8, uniformtext_mode='hide',
        plot_bgcolor='white', paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
        categoryorder='array', 
        categoryarray=sorted(filtered_df['stage_detail'], key=sort_stage_detail)
        ),# Ordenação personalizada,
        xaxis_title="Estágio no Funil",
        yaxis_title="Quantidade de Clientes",
        font={'color': '#003366'}

    )

    return fig


@app.callback(
    Output('chart-won-container', 'children'),
    [
        Input({'type': 'date-filter', 'index': dash.ALL}, 'start_date'),
        Input({'type': 'date-filter', 'index': dash.ALL}, 'end_date'),
        Input('stage-detail-filter', 'value')

    ]
)
def update_chart(start_dates, end_dates, selected_stage_name):
    
    if selected_stage_name != 'Geral':
        return None
    
    if not start_dates or not end_dates:
        return html.Div("Nenhum dado disponível", style={'textAlign': 'center', 'color': '#003366'})
    
    df = process_data(deals, filter_by_status=False)

    for start_date, end_date in zip(start_dates, end_dates):
        if start_date and end_date:
            start_date = datetime.fromisoformat(start_date).date()
            end_date = datetime.fromisoformat(end_date).date()

            # 🔍 Filtrar os dados dentro do período e com status "Ganho"
            filtered_df = df[(df['date_won'] >= start_date) & 
                             (df['date_won'] <= end_date) & 
                             (df['stage_status'] == 'Ganho')]

            # 📊 Contar clientes por stage_name
            grouped_df = filtered_df.groupby('stage_name').size().reset_index(name='total')

            # 🔵 Gráfico de Pizza (Proporção)
            pie_chart = px.pie(
                grouped_df, 
                names='stage_name', 
                values='total', 
                hole=0.4,  
                title="Distribuição Percentual dos Clientes Ganhos"
            ).update_traces(
                textposition='inside',
                textinfo='percent',  # Mostra o percentual e o nome da categoria
                insidetextorientation='radial'  # Ajusta o texto dentro da fatia
            )

            # 🔴 Gráfico de Barras (Quantidade)
            bar_chart = px.bar(
                grouped_df, 
                x='stage_name', 
                y='total', 
                text='total',
                title="Quantidade de Clientes Ganhos",
                color='stage_name', 
                labels={'total': 'Clientes'},
            ).update_traces(
                texttemplate='%{text}', 
                textposition='outside'
            ).update_layout(
                yaxis=dict(range=[0, grouped_df['total'].max() * 1.2])  # Adiciona 20% de espaço extra no topo
            )

            # Layout lado a lado
            return html.Div([
                dcc.Graph(figure=pie_chart, style={'width': '48%', 'display': 'inline-block'}),
                dcc.Graph(figure=bar_chart, style={'width': '48%', 'display': 'inline-block'}),
            ])

    
    return html.Div("Nenhum dado disponível", style={'textAlign': 'center', 'color': '#003366'})

@app.callback(
    Output('chart-lost-container', 'children'),
    [
        Input({'type': 'date-filter', 'index': dash.ALL}, 'start_date'),
        Input({'type': 'date-filter', 'index': dash.ALL}, 'end_date'),
        Input('stage-detail-filter', 'value')
        
    ]
)
def update_chart(start_dates, end_dates, selected_stage_name):
    if selected_stage_name != 'Geral':
        return None
    
    if not start_dates or not end_dates:
        return html.Div("Nenhum dado disponível", style={'textAlign': 'center', 'color': '#003366'})
    
    df = process_data(deals, filter_by_status=False)

    for start_date, end_date in zip(start_dates, end_dates):
        if start_date and end_date:
            start_date = datetime.fromisoformat(start_date).date()
            end_date = datetime.fromisoformat(end_date).date()

            # 🔍 Filtrar os dados dentro do período e com status "Perdido"
            filtered_df = df[(df['date_lost'] >= start_date) & 
                             (df['date_lost'] <= end_date) & 
                             (df['stage_status'] == 'Perdido')]

            # 📊 Contar clientes por stage_name
            grouped_df = filtered_df.groupby('stage_name').size().reset_index(name='total')

            # 🔵 Gráfico de Pizza (Proporção)
            pie_chart = px.pie(
                grouped_df, 
                names='stage_name', 
                values='total', 
                hole=0.4,  
                title="Distribuição Percentual dos Clientes Perdidos"
            ).update_traces(
                textposition='inside',
                textinfo='percent',  # Mostra o percentual e o nome da categoria
                insidetextorientation='radial'  # Ajusta o texto dentro da fatia
            )

            # 🔴 Gráfico de Barras (Quantidade)
            bar_chart = px.bar(
                grouped_df, 
                x='stage_name', 
                y='total', 
                text='total',
                title="Quantidade de Clientes Perdidos",
                color='stage_name', 
                labels={'total': 'Clientes'},
            ).update_traces(
                texttemplate='%{text}', 
                textposition='outside'
            ).update_layout(
                yaxis=dict(range=[0, grouped_df['total'].max() * 1.2])  # Adiciona 20% de espaço extra no topo
            )

            # Layout lado a lado
            return html.Div([
                dcc.Graph(figure=pie_chart, style={'width': '48%', 'display': 'inline-block'}),
                dcc.Graph(figure=bar_chart, style={'width': '48%', 'display': 'inline-block'}),
            ])

    return html.Div("Nenhum dado disponível", style={'textAlign': 'center', 'color': '#003366'})

@app.callback(
    Output('lost-reason-chart', 'figure'),
    [Input({'type': 'date-filter', 'index': dash.ALL}, 'start_date'),
     Input({'type': 'date-filter', 'index': dash.ALL}, 'end_date'),
     Input('stage-detail-filter', 'value')]  # Filtro do stage_name
)
def update_loss_reason_chart(start_dates, end_dates, selected_stage_name):
    fig = go.Figure()
    df = process_data(deals, filter_by_status=None)

    if not start_dates or not end_dates:
        return fig  # Retorna gráfico vazio se não houver datas selecionadas

    for i, (start_date, end_date) in enumerate(zip(start_dates, end_dates)):
        if start_date and end_date:
            start_date = datetime.fromisoformat(start_date).date()
            end_date = datetime.fromisoformat(end_date).date()

            # Filtra os clientes perdidos no intervalo de datas
            filtered_df = df[(df['date_lost'] >= start_date) & 
                             (df['date_lost'] <= end_date) & 
                             (df['stage_status'] == 'Perdido')]

            # Substitui valores vazios de 'loss_reason' por "Outro"
            filtered_df['loss_reason'] = filtered_df['loss_reason'].fillna("Outro")

            # Se um stage_name for selecionado, filtra por ele
            if selected_stage_name != 'Geral':
                filtered_df = filtered_df[filtered_df['stage_name'] == selected_stage_name]

            # Conta os motivos de perda e ordena do maior para o menor
            loss_reason_counts = (filtered_df.groupby('loss_reason')
                                  .size()
                                  .reset_index(name='total'))

            # Soma total das perdas
            total_losses = loss_reason_counts['total'].sum()

            # Adiciona a barra "Total" com uma cor diferente
            loss_reason_counts = pd.concat([
                loss_reason_counts, 
                pd.DataFrame({'loss_reason': ['Total'], 'total': [total_losses]})
            ]).sort_values(by='total', ascending=False)

            # Criar gráfico de barras com labels acima das barras
            fig.add_trace(go.Bar(
                x=loss_reason_counts['loss_reason'],
                y=loss_reason_counts['total'],
                text=loss_reason_counts['total'],  # Adiciona os valores
                textposition='outside',  # Posiciona o texto acima das barras
                marker_color=['#ff7f0e'] + ['#1f77b4'] * (len(loss_reason_counts) - 1),  # Azul padrão, última barra laranja
                name=f'Filtro {i + 1}'
            )).update_layout(
                yaxis=dict(range=[0, loss_reason_counts['total'].max() * 1.2])
            )

    # Configuração do layout
    fig.update_layout(
        title="Motivos de Perda",
        xaxis_title="Motivo de Perda",
        yaxis_title="Total de Clientes Perdidos",
        barmode='group',
        uniformtext_minsize=8,  # Tamanho mínimo dos textos
        uniformtext_mode='hide',  # Esconde textos sobrepostos
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)', 
        font={'color': '#003366'},
        showlegend=True
    )

    return fig


@app.callback(
    Output('evolucao-leads', 'style'),  # Altera a visibilidade do gráfico
    Input('stage-detail-filter', 'value')  # Monitora o dropdown
)
def toggle_graph_visibility(selected_stage):
    if selected_stage == "Geral":
        return {'display': 'block'}  # Mostra o gráfico
    return {'display': 'none'}  # Esconde o gráfico

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=False, host='0.0.0.0', port=port)

    