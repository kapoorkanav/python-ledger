from fastapi import FastAPI
from app.routers import accounts
from app.routers import transfers
app=FastAPI()

app.include_router(accounts.router)
app.include_router(transfers.router)

@app.get("/")
def read_root():
    return {"message": "hello, this is my ledger API"}

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/hello/{name}")
def hello(name: str):
    return {"message": f"hello, {name}"}