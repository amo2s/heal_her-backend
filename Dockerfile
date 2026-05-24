# Use the official python 3.13 slim image for a fast enterprise build
FROM python:3.13-slim

# Set the working directory inside the cloud container
WORKDIR /code

# Install native Linux build tools and compilers needed for C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy all your local project files into the container
COPY . /code/

# Install uv for ultra-fast dependency management
RUN pip install --no-cache-dir uv

# THE CORRECTED FIX: Force uv to compile guardrails-ai from source code
RUN uv pip install --system --no-binary guardrails-ai -e .

# Expose hugging face's required internal port
EXPOSE 7860

# Tell granian to route into the src/ folder to find your fastapi app
CMD ["granian", "--interface", "asgi", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]