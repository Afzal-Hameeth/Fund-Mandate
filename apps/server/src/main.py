import sys
from pathlib import Path
from parsing_sourcing_routes import router

src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=8000,
        reload=False,
    )


