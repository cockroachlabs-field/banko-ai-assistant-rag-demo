from flask import Flask, request, render_template, redirect, url_for, session
from langchain_community.llms import Ollama
from langchain_community.utilities import SQLDatabase 
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import create_sql_agent
from langchain_openai import ChatOpenAI
from config import API_KEY

app = Flask(__name__)
model_name = "GPT 3.5"
model = ChatOpenAI(model_name="gpt-3.5-turbo-1106",api_key=API_KEY)
app.secret_key = 'your_secret_key'  # Needed to use sessions

# Database Connection String

#DATABASE_URL="cockroachdb://david:Qx1u2iV_dYMDkFzisFPzAA@brave-ox-dj-2401.j77.aws-us-east-1.cockroachlabs.cloud:26257/defaultdb?sslmode=verify-full"
#db = SQLDatabase.from_uri(DATABASE_URL)
db = SQLDatabase.from_uri('cockroachdb://root@localhost:26257/defaultdb?sslmode=disable')


# Connect to the database & LLM Model
#model_name = "mistral"
#model = Ollama(model=model_name)
toolkit = SQLDatabaseToolkit(llm=model,db=db)
agent_executor = create_sql_agent(llm=model, toolkit=toolkit,verbose=True, handle_parsing_errors=True)

@app.route('/banko', methods=['GET', 'POST'])
def chat():
    session['chat'] = []
    if 'chat' not in session:
        session['chat'] = []
    if request.method == 'POST':
            render_template('index.html', chat=session['chat'])
            user_message = request.form.get('message')
            if user_message:
                session['chat'].append({'text': user_message, 'class': 'User'})
                prompt = user_message+". Account id is 2. Final Result should show balance. Think step by step."
                print(prompt)
                result = agent_executor.invoke({"input": prompt}, handle_parsing_errors=True)
                session['chat'].append({'text': result['output'], 'class': model_name })  # Mock response
                print(session['chat'])
    return render_template('index.html', chat=session['chat'])

@app.route('/home')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)
