# etsyshop — dashboard + trendscanner runner image
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir -e ".[dashboard,images]"

# Credentials are provided at runtime via env (.env / -e flags); never baked in.
ENV ETSYSHOP_LOG_LEVEL=INFO
EXPOSE 8000

# Default: serve the dashboard. Override CMD to run `trendscan <sources.json>`
# or any `etsyshop ...` subcommand.
CMD ["etsyshop", "dashboard", "--host", "0.0.0.0", "--port", "8000"]
