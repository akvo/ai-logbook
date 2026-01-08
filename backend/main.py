from fastapi import FastAPI

from routers import farmers, records, extract, webhook

app = FastAPI(
    title="AI Logbook API",
    description="AI-powered logbook application for Myanmar GAP farmer records",
    version="1.0.0",
    ignore_trailing_slash=True,
    contact={
        "name": "Akvo Support",
    },
    license_info={
        "name": "GNU General Public License v3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.en.html",
    },
    redoc_url="/api/redoc",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Include routers
app.include_router(farmers.router)
app.include_router(records.router)
app.include_router(extract.router)
app.include_router(webhook.router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
