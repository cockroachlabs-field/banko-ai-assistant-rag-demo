from openai import OpenAI
from config import API_KEY

client = OpenAI(api_key=API_KEY)

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "user", "content": "Write a haiku about recursion in programming."}
    ]
)

print(response.choices[0].message.content)