# InfoByte

**InfoByte** is an intent-aware, cross-source information retrieval and
synthesis platform designed to retrieve relevant information from
specialized sources instead of relying entirely on a general-purpose
language model for factual retrieval.

A user submits a query, which is classified into an appropriate intent
category. Based on the predicted intent, InfoByte dynamically routes the
query to relevant sources such as Wikipedia, Stack Overflow, Reddit,
Oracle Forums, and other domain-specific sources. The retrieved
information is aggregated and provided as context for AI-based
synthesis, forming a routing-oriented **Retrieval-Augmented Generation
(RAG)** pipeline.

The objective of InfoByte is to combine the reliability and domain
specificity of external information sources with the synthesis
capabilities of generative AI.

## Key Features

-   Intent-aware query routing using a custom-trained classifiergit add Report/InfoByte_Internship_Report.pdf
-   Multi-source retrieval based on the detected query domain
-   RAG-based architecture that grounds synthesis in retrieved
    information
-   Retrieval from specialized sources including Wikipedia, Stack
    Overflow, Reddit, and Oracle Forums
-   Playwright-based browser automation for dynamically rendered sources
-   Gemini-powered synthesis of retrieved cross-source information
-   User confirmation and intent override before retrieval
-   Intent confidence score visualization
-   Query and correction logging for future classifier improvement
-   Containerized backend deployment using Docker

## Architecture Overview

InfoByte follows the following high-level pipeline:

**User Query → Intent Classification → Intent Confirmation → Source
Routing → Information Retrieval → Content Aggregation → AI Synthesis →
Final Response**

The classifier determines the domain of an incoming query and enables
the retrieval layer to select sources suited to that type of
information. Instead of asking a language model to generate an answer
entirely from its internal knowledge, InfoByte first retrieves external
information and supplies the collected context to the synthesis stage.

This makes InfoByte a specialized RAG system in which retrieval is
dynamically controlled by query intent and source-specific routing
logic.

## Technology Stack

### Backend

-   Python
-   FastAPI
-   Uvicorn
-   ONNX Runtime
-   Playwright
-   BeautifulSoup
-   Supabase

### Machine Learning

-   Transformer-based text classification
-   ONNX model inference
-   INT8 model quantization
-   Scikit-learn and NLP preprocessing utilities

### Frontend

-   React
-   TypeScript
-   Vite
-   TanStack Router

### External Services and Sources

-   Google Gemini API
-   Wikipedia
-   Stack Overflow
-   Reddit
-   Oracle Forums
-   Additional intent-specific sources

### Deployment

-   Docker
-   Render --- Backend
-   Vercel --- Frontend

## Running InfoByte Locally

### 1. Clone the Repository

``` bash
git clone <YOUR_REPOSITORY_URL>
cd InfoByte-v3
```

### 2. Set Up the Backend

Create and activate a virtual environment:

``` bash
python3 -m venv venv
source venv/bin/activate
```

Install the required dependencies:

``` bash
pip install -r requirements.txt
```

Install Chromium for Playwright-based retrievers:

``` bash
playwright install chromium
```

Configure the required environment variables in the backend `.env` file,
including the API keys and service credentials used by the project.

Start the backend:

``` bash
cd backend
uvicorn app.main:app --reload
```

The backend runs locally at `http://127.0.0.1:8000`.

### 3. Start the Frontend

Open another terminal:

``` bash
cd frontend-web
npm install
npm run dev
```

The terminal will display the local frontend URL, typically
`http://localhost:8080`.

## Running with Docker

The backend can also be built and executed as a Docker container. Use
the Dockerfile and environment configuration included in the repository
to build and run the service according to your local or deployment
environment.

## Project Report

A detailed **InfoByte project and architecture report** is included in
this repository. It documents the motivation behind the project, system
architecture, intent-classification pipeline, source-routing mechanism,
retrieval workflow, RAG architecture, implementation details, deployment
strategy, testing, current limitations, and future enhancements.

Refer to the report for a comprehensive technical explanation of the
system and its design decisions.

## Current Deployment Considerations

Some retrieval pipelines use Playwright and headless Chromium for
browser-based extraction. These operations require more memory than
direct API or lightweight HTTP-based retrieval. Deployment environments
with strict memory limits may therefore require a higher-memory instance
or separation of browser-based retrieval into an independent service.

## Project Status

InfoByte is an actively developed project focused on source-aware
information retrieval, intelligent query routing, and grounded
AI-assisted synthesis.
