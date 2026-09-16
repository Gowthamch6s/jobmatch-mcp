FROM python:3.11-slim

WORKDIR /app

# System deps for httpx/sqlite are already in the slim image's stdlib.
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY README.md ./

RUN pip install --no-cache-dir -e .

# Runs over stdio by default -- the MCP host (Claude Desktop, Cursor, etc.)
# spawns this container/process and communicates over stdin/stdout, so no
# port is published. ADZUNA_APP_ID/ADZUNA_APP_KEY are supplied at `docker
# run -e` time by the host config, never baked into the image.
ENV JOBMATCH_DB_PATH=/data/jobmatch.db
VOLUME ["/data"]

ENTRYPOINT ["jobmatch-mcp"]
