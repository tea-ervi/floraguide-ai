from fastapi import FastAPI

app = FastAPI(title="FloraGuide AI API")

@app.get("/")
async def root():
    return {"message": "FloraGuide AI Backend is running!"}