from fastapi import FastAPI, HTTPException
from transformers import AutoTokenizer, AutoModelForCausalLM
import os

app = FastAPI()

# Carregar o modelo LLaMA 2
MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"
HF_TOKEN = os.getenv("HF_TOKEN")

# Carregar modelo e tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, use_auth_token=HF_TOKEN)


@app.post("/generate")
async def generate(message: dict):
    try:
        input_text = message.get("message", "")
        inputs = tokenizer(input_text, return_tensors="pt")
        outputs = model.generate(**inputs, max_length=150)
        response_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))