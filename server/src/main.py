import sys
from pathlib import Path
from pydantic import BaseModel

src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fundMandate import query_agent


app = FastAPI(
    title="FundAgent API",
    description="API for Compass Master application",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):

    content: str


class QueryResponse(BaseModel):

    response: str
    status: str


@app.get("/")
async def root():
    return {"message": "Agent Platform API is running!"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Agent Platform API"}

@app.post("/chat")
async def chat(request: QueryRequest) -> QueryResponse:

    result = query_agent(request.content)
    return QueryResponse(
        response=result["response"],
        status=result["status"]
    )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=8000,
        reload=False,
    )


