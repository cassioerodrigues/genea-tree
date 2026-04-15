from fastapi import FastAPI

app = FastAPI(title="Genea Tree API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
