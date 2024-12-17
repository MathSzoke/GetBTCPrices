from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

app = FastAPI()

# Carregar o modelo LLaMA 2
MODEL_NAME = "meta-llama/Llama-2-7b-chat-hf"  # Modelo hospedado no Hugging Face
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, device_map="auto", torch_dtype=torch.float16)

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
