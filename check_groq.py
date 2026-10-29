import json
import urllib.request
import urllib.error

from rex.rag.llm import LLMClient

client = LLMClient.from_env()

if client is None:
    print("No API key configured.")
else:
    try:
        print(client([
            {"role": "user", "content": "Reply with exactly: API works"}
        ]))
    except Exception as error:
        print(type(error).__name__ + ":", error)

