from __future__ import print_function
from datetime import datetime
from flask.helpers import url_for
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect
from markupsafe import escape
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import os

load_dotenv() 

def handle_article(title, author, raw_notes):  
    title = title.title()  
    author = author.title()
    
    now = datetime.now()  
    day = str(now.day) if now.day > 9 else "0"+ str(now.day)
    month = str(now.month) if now.month > 9 else "0"+ str(now.month)
    date = f"{day}/{month}/{now.year}"

    notes_groups = raw_notes.split("***")                
    notes = []

    for note in notes_groups:
        commentary = ""
        if "--" in note:
            note, commentary = note.split("--")
        notes.append([title, author, "artigo", note.strip(), commentary.strip(), date])

    return notes

def handle_kindle_file(title, author, file):

    meses = {
        "janeiro": "01",
        "fevereiro": "02",
        "março": "03",
        "abril": "04",
        "maio": "05",
        "junho": "06",
        "julho": "07",
        "agosto": "08",
        "setembro": "09",
        "outubro": "10",
        "novembro": "11", 
        "dezembro": "12"
    }

    anotacoes = [x for x in file.split("==========\r\n") if x]
    
    total_notas = []
    total_destaques = []
    total = []
    for k, a in enumerate(anotacoes):        
        linhas = a.split('\r\n')                
        obra = linhas[0]
        cabecalho = linhas[1]
              
        is_nota = cabecalho.find("nota") > -1
        is_destaque = not is_nota        

        if cabecalho.find('|') > 0: 
            inicio_cabecalho, fim_cabelhaco = cabecalho.split('|')            
            posicoes = [x for x in inicio_cabecalho.split(' ') if x][-1]
            if is_destaque:
                posicao_inicial, posicao_final = map(int, posicoes.split('-'))
            else:
                posicao_inicial = int(posicoes) 
                posicao_final = int(posicoes)
            
            data_completa = ' '.join(fim_cabelhaco.split(' ')[2:])                    
            data_removendo_extremidades = data_completa.split()[1:-1]
            data_dia_mes_ano = data_removendo_extremidades[::2]
            data_dia_mes_ano[1] = meses[data_dia_mes_ano[1]]
            data_dia_mes_ano[0] = data_dia_mes_ano[0] if len(data_dia_mes_ano[0]) > 1 else "0"+ data_dia_mes_ano[0]
            date = "/".join(data_dia_mes_ano)

        txt = " ".join(linhas[2:]).strip()

        data = {
            'posicao_inicial': posicao_inicial,
            'posicao_final': posicao_final,
            'data': date,
            'txt': txt
        }        
        if is_nota:
            total_notas.append(data)
        elif is_destaque:
            total_destaques.append([data, 0, k])    

    for i in range(len(total_destaques)):
        for j in range(i + 1, len(total_destaques)):
            if total_destaques[i][0]["posicao_inicial"] == total_destaques[j][0]["posicao_inicial"] and total_destaques[i][0]["posicao_final"] == total_destaques[j][0]["posicao_final"]:
                total_destaques[j][1] = 1                
    for destaque in total_destaques:
        if destaque[1]:
            total_destaques.remove(destaque)
    
    for destaque in total_destaques:
        data = [title, author, "livro", destaque[0]["txt"], "", destaque[0]['data']]        
        for nota in total_notas:            
            if nota["posicao_inicial"] == destaque[0]["posicao_final"]:                
                data[-2] = nota['txt']                                                                                         
        total.append(data)     
    return total

def initialize_google_api():                 
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']   
    creds = None    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)        
        with open('token.json', 'w') as token:            
            token.write(creds.to_json())

    service = build('sheets', 'v4', credentials=creds)    
    sheet = service.spreadsheets()

    return sheet


def read_sheet():
    sheet = initialize_google_api()
    RANGE_NAME = 'Main!A2:G'
    result = sheet.values().get(spreadsheetId=os.getenv("SPREADSHEET_ID"),
                                range=RANGE_NAME).execute()
    values = result.get('values', [])
    return values

def write_sheet(values):
    sheet = initialize_google_api()    
    body = {
        'values': values
    }    
    result = sheet.values().append(spreadsheetId=os.getenv("SPREADSHEET_ID"), range="Main",
        body=body, valueInputOption='USER_ENTERED').execute()    
    print(result)


app = Flask(__name__)

@app.route("/")
def index():
    values = read_sheet()        
    return render_template("index.html", values=values)

@app.route("/book/", methods=["GET", "POST"])
def book():
    if request.method == "GET":
        return render_template("add_book.html")
    else:                
        file_storaged = request.files["notes_file"]          
        file = file_storaged.read()                

        separated_comments = handle_kindle_file(request.form["titulo"], request.form["autor"], file.decode('utf-8'))
        
        write_sheet(separated_comments)        
        return redirect(url_for('index'))
@app.route("/article/", methods=["GET", "POST"])
def article():
    if request.method == "GET":
        return render_template("add_article.html")
    else:                
        notas = handle_article(request.form["titulo"], request.form["autor"], request.form["notas"])        
        write_sheet(notas)
        return redirect(url_for('index'))