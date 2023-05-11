# main.py

import uvicorn
from fastapi import FastAPI

app = FastAPI()

if __name__ == "__main__":
    uvicorn.run("nfvcl:app", host="0.0.0.0", port=5002)