import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
resp = client.chat.completions.create(model="deepseek-chat", messages=[{"role": "user", "content": "Introduce yourself in one sentence."}])
print(resp.choices[0].message.content)