from fastapi import FastAPI
from src.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="MaxsorLabs Support Decision API")


@app.get("/health")
def health():
    return {"status": "ok"}
