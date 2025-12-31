from fastapi import FastAPI

app = FastAPI(
    title="AI Logbook API",
    description="AI-powered logbook application",
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


@app.get("/health")
def health_check():
    return {"status": "healthy"}
