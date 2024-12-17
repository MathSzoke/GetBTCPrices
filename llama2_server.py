from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch
import os

app = FastAPI()

# Carregar o modelo LLaMA 2
MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"
HF_TOKEN = os.getenv("HF_TOKEN")  # Pegue o token da variável de ambiente

# Baixar o modelo usando o token
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)

# Pipeline de geração de texto
generator = pipeline("text-generation", model=model, tokenizer=tokenizer, device=0)


class ChatRequest(BaseModel):
    message: str


@app.post("/generate")
def generate_text(request: ChatRequest):
    try:
        result = generator(request.message, max_length=100, num_return_sequences=1)
        return {"response": result[0]["generated_text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
