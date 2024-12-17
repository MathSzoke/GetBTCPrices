from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM

app = FastAPI()

MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct"
HF_TOKEN = os.getenv("HF_TOKEN")

# Carregar modelo e tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, token=HF_TOKEN)
model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, token=HF_TOKEN)


class InputMessage(BaseModel):
    message: str


@app.post("/generate")
async def generate_response(input: InputMessage):
    try:
        inputs = tokenizer(input.message, return_tensors="pt")
        outputs = model.generate(**inputs, max_length=150)
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no modelo: {e}")


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
