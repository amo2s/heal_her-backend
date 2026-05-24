# Use the official python 3.12 slim image
FROM python:3.12-slim

# Set the working directory inside the cloud container
WORKDIR /code

# Install git so the container can pull the package directly from GitHub
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy all your local project files into the container
COPY . /code/

# Upgrade pip to ensure the latest source-installation logic is used
RUN pip install --no-cache-dir --upgrade pip

# Install the dependencies directly from your updated pyproject.toml blueprint
RUN pip install --no-cache-dir -e .

# Expose hugging face's required internal port
EXPOSE 7860

# Tell granian to route into the src/ folder to find your fastapi app
CMD ["granian", "--interface", "asgi", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]