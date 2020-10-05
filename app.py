# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
import dash_table
from dash.dependencies import Input, Output, State
import plotly.express as px
import pandas as pd
import pyarrow as pa
from pyarrow import plasma

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

def get_plasma(conn_str):
    try:
        return plasma.connect(conn_str, 1)
    except:
        return None

def connected_alert(pc, conn_str):
    if pc is not None:
        msg = 'Plasma connected!'
        color = 'success'
    else:
        msg = f'Plasma was not able to connect on {conn_str}'
        color = 'danger'
    return msg, color

def plasma_list_display_cols():
    cols = ['id_start', 'create_time', 'data_size', 'state']
    mapped_cols = [{'name': i, 'id': i} for i in cols]
    return mapped_cols

def get_plasma_list(client):
    plasma_items = [{
        'id_start': str(x)[9:18],
        'create_time':y['create_time'],
        'data_size': y['data_size'],
        'state': y['state'],
        'id': str(x),
        'oid': x} for x,y in client.list().items()]
    return pd.DataFrame(plasma_items).sort_values(['create_time', 'id'], ascending=False)


app.layout = dbc.Container(
    [
        dcc.Store(id='socket-val', data='/tmp/plasma'),
        dcc.Store(id='previous-id'),
        dcc.Store(id='current-id'),
        dcc.Store(id='num_listing_rows', data=0),
        html.H1("Plasma Dash!"),
        dbc.Row(
            dbc.Col(dbc.Alert(id='alert-connection', children='Connecting...', color='info'), md=12)
        ),
        dbc.Row(
            dbc.Col(
                dbc.Form([
                    dbc.FormGroup([
                        dbc.Label('Plasma Address', html_for='plasma-socket', className='mr-2'),
                        dbc.Input(id='plasma-socket', value='/tmp/plasma', type='text')
                    ], className='mr-3'),
                    dbc.Button('Connect to Plasma', id='plasma-connect', color='primary', n_clicks=0)
                ], inline=True)
            )
        ),
        dbc.Row(dbc.Col(html.H2('Tables in Plasma')), className='mt-md-2'),
        dbc.Row([
                dbc.Col([
                    dash_table.DataTable(
                        id='plasma-listing',
                        columns=plasma_list_display_cols(),
                        row_selectable='single',
                        selected_rows=[0],
                        page_size=10,
                    ),
                ]),
            ],
        ),
        dbc.Row([
            dbc.Col([
                html.H2('Selected Table'),
                dash_table.DataTable(
                    id='explore-table',
                    columns=[],
                    page_size=10)
            ])
        ]),
        dbc.Row([
            dbc.Col([
                html.H2('Visual Control'),
                dbc.FormGroup([
                    dbc.Label('X', html_for='x-col'),
                    dcc.Dropdown(id='x-col', options=[])
                ]),
                dbc.FormGroup([
                    dbc.Label('Y', html_for='y-col'),
                    dcc.Dropdown(id='y-col', options=[])
                ]),
                dbc.FormGroup([
                    dbc.Label('Color', html_for='color-col'),
                    dcc.Dropdown(id='color-col', options=[])
                ]),
            ], width=3),
            dbc.Col([
                html.H2('Visual Out'),
                dcc.Graph(id='explore-graph')
            ], width=9)
        ]),
        dcc.Interval(
            id='update-plasma-state',
            interval=1*3000,
            n_intervals=0
        ),
    ],
    fluid=True
)

@app.callback(
    [
        Output('socket-val', 'data'),
        Output('update-plasma-state', 'n_intervals'),
    ],
    [Input('plasma-connect', 'n_clicks')],
    [State('plasma-socket', 'value'), State('update-plasma-state', 'n_intervals')]
)
def update_connection_status(n_clicks, new_socket_val, n_intervals):
    return new_socket_val, n_intervals+1

@app.callback(
    [
        Output('plasma-listing', 'data'),
        Output('alert-connection', 'children'),
        Output('alert-connection', 'color'),
        Output('num_listing_rows', 'data'),
        Output('plasma-listing', 'selected_row_ids'),
        Output('plasma-listing', 'selected_rows'),
    ],
    [Input('update-plasma-state', 'n_intervals')],
    [State('socket-val', 'data'),
        State('current-id', 'data'),
        State('num_listing_rows', 'data'),
        State('plasma-listing', 'selected_row_ids'),
        State('plasma-listing', 'selected_rows'),]
)
def interval_update_plasma_state(n_intervals, socket_val, current_id, num_listing_rows, selected_row_ids, selected_rows):
    client = get_plasma(socket_val)
    m,c = connected_alert(client, socket_val)
    if client is not None:
        list_t = get_plasma_list(client)
        set_selected_row = current_id
        if num_listing_rows != list_t.shape[0] and list_t.shape[0]>0:
            selected_row_ids=[list_t.id.tolist()[0]]
            selected_rows=[0]
        return list_t.drop(columns=['oid']).to_dict('records'),m,c,list_t.shape[0],selected_row_ids,selected_rows
    else:
        return [],m,c,0,selected_row_ids,selected_rows

@app.callback(
    [Output('previous-id', 'data'), Output('current-id', 'data')],
    [
        Input('plasma-listing', 'selected_row_ids'),
        Input('plasma-listing', 'data'),
        Input('num_listing_rows', 'data')],
    [State('current-id', 'data')]
)
def interval_update_plasma_state(selected_row_ids, data, num_listing_rows, current_id):
    new_id = selected_row_ids[0] if selected_row_ids is not None else None
    if new_id is None or new_id == current_id:
        raise dash.exceptions.PreventUpdate
    return current_id, new_id

@app.callback(
    [
        Output('explore-table', 'data'),
        Output('explore-table', 'columns'),
        Output('x-col', 'options'),
        Output('y-col', 'options'),
        Output('color-col', 'options'),
        Output('x-col', 'value'),
        Output('y-col', 'value'),
        Output('color-col', 'value'),
    ],
    [Input('current-id', 'data')],
    [State('previous-id', 'data'), State('socket-val', 'data')]
)
def update_selected_id(selected_row_ids, previous_id, socket_val):
    if selected_row_ids is not None:
        if (previous_id is not None and selected_row_ids==previous_id):
            raise dash.exceptions.PreventUpdate
        
        client=get_plasma(socket_val)
        if client is not None:
            listing = get_plasma_list(client)
            selected_id = listing[listing.id == selected_row_ids].oid
            df = client.get(selected_id.tolist()[0]).to_pandas()
            colnames = [{'name': i, 'id':i} for i in df.columns]
            opt_dict = [{'label': i, 'value': i} for i in df.columns]
            return df.to_dict('records'), colnames, opt_dict, opt_dict, opt_dict, \
                    df.columns[0], df.columns[1], None
    return [], [], [], [], [], [], [], []

@app.callback(
    Output('explore-graph', 'figure'),
    [
        Input('current-id', 'data'),
        Input('x-col', 'value'),
        Input('y-col', 'value'),
        Input('color-col', 'value')],
    [State('socket-val', 'data')]
)
def update_explore_graph(selected_row_ids, x_col, y_col, color_col, socket_val):
    if selected_row_ids is not None:
        client=get_plasma(socket_val)
        if client is not None:
            listing = get_plasma_list(client)
            selected_id = listing[listing.id == selected_row_ids].oid
            df = client.get(selected_id.tolist()[0]).to_pandas()
            cols = df.columns
            return px.scatter(df, x=x_col or cols[0], y=y_col or cols[1], color=color_col)
    return {'data': []}
    

if __name__ == '__main__':
    app.run_server(debug=True)

