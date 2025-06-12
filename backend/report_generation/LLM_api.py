from langchain_openai import ChatOpenAI

import os

# import the .env file
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print(f"OPENAI_API_KEY retrieved: {OPENAI_API_KEY[:4]}...{OPENAI_API_KEY[-4:]}")

# initiate the model
llm = ChatOpenAI(temperature=0.5, model='gpt-4o-mini', api_key=OPENAI_API_KEY)

# call this function for every message added to the chatbot
def get_llm_response(prompt):
    
    print(f"Prompt passed to LLM: {prompt[:25]}")

    answer = ""

    # stream the response
    for response in llm.stream(prompt):
        answer += response.content
        
    print(f"LLM response received: {answer[:25]}")
        
    return answer

if __name__ == "__main__" and os.getenv("DOCTOR_CHECK") == "true":
    try:
        result = get_llm_response("Hello")
        print("LLM responded successfully")
    except Exception as e:
        print(f"LLM failed: {e}")
        exit(1)