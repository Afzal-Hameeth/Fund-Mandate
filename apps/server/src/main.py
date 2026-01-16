import sys
from pathlib import Path

src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from parsing_sourcing_routes import router as parsing_router
from fundMandate import router as mandate_router
from risk_api import router as risk_router


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

app.include_router(parsing_router)
app.include_router(mandate_router)
app.include_router(risk_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host='0.0.0.0',
        port=8000,
        reload=False,
    )



