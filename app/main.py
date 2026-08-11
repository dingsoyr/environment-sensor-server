from fastapi import FastAPI

app = FastAPI(title="Environment Sensor Server")


@app.get("/health")
def health():
    return {"status": "ok"}