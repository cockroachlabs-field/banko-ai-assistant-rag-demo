from flask import Flask, request, render_template, redirect, url_for, session
from openai import OpenAI
from config import API_KEY
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
import numpy as np
import json
from aws_bedrock import search_expenses, RAG_response

app = Flask(__name__)
client = OpenAI(api_key=API_KEY)
app.secret_key = 'your_secret_key'

# Database Connection String

#DATABASE_URL="cockroachdb://david:Qx1u2iV_dYMDkFzisFPzAA@brave-ox-dj-2401.j77.aws-us-east-1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full"
#db = SQLDatabase.from_uri(DATABASE_URL)
#db = SQLDatabase.from_uri('cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')

@app.route('/banko', methods=['GET', 'POST'])
def chat():
    session['chat'] = []
    if 'chat' not in session:
        session['chat'] = []  # Initialize chat history if it doesn't exist
    if request.method == 'POST':
        user_message = request.form.get('message')
        if user_message:
            session['chat'].append({'text': user_message, 'class': 'User'})
            prompt = user_message
            result = search_expenses(prompt)
            # Remove the description extraction and just pass the full results
            rag_response = RAG_response(user_message, result)
            print(rag_response)

            session['chat'].append({'text': rag_response, 'class': 'Assistant'})
    return render_template('index.html', chat=session['chat'])

@app.route('/home')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)
