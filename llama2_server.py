from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
import os
import logging

# Configuração do logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        logger.info(f"Mensagem recebida: {input.message}")
        inputs = tokenizer(input.message, return_tensors="pt")
        outputs = model.generate(**inputs, max_length=150)
        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        logger.info(f"Resposta gerada pelo modelo: {response}")
        return {"response": response}
    except Exception as e:
        logger.error(f"Erro ao gerar resposta: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar a solicitação.")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
