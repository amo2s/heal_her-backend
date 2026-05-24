# use the official python 3.13 slim image for a fast enterprise build
FROM python:3.13-slim

# set the working directory inside the cloud container
WORKDIR /code

# install native linux build tools and compilers needed for c-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# copy all your local project files into the container
COPY . /code/

# install uv for ultra-fast dependency management
RUN pip install --no-cache-dir uv

# the advanced fix: tell uv to compile from source if it cant find a pre-built wheel
RUN uv pip install --system --compile-source guardrails-ai -e .

# expose hugging face's required internal port
EXPOSE 7860

# tell granian to route into the src/ folder to find your fastapi app
CMD ["granian", "--interface", "asgi", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]