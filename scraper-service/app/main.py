from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.retrievers.oracle import handle_oracle_query
from app.retrievers.reddit import handle_reddit_query


app = FastAPI(
    title="InfoByte Scraper Service",
    version="1.0.0"
)


class RedditRequest(BaseModel):
    query: str
    intent: str = "discussion_social"


class OracleRequest(BaseModel):
    query: str


@app.get("/")
def root():
    return {
        "service": "InfoByte Scraper Service",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/scrape/reddit")
def scrape_reddit(payload: RedditRequest):
    try:
        return handle_reddit_query(
            payload.query,
            payload.intent
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/scrape/oracle")
def scrape_oracle(payload: OracleRequest):
    try:
        return handle_oracle_query(payload.query)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )