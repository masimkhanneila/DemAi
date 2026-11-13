
from fastapi import FastAPI

from routers.stations import router as stations_router
from routers.routes import router as routes_router
from routers.saved_routes import router as saved_routes_router


app = FastAPI(
    title="DemAI API",
    description="Eco-Friendly Route Recommendation REST API",
    version="1.0.0"
)


app.include_router(stations_router)
app.include_router(routes_router)
app.include_router(saved_routes_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "DemAI API is running"}
