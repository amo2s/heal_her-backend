# Use a slim Python 3.13 image to meet project requirements
FROM python:3.13-slim

# Copy the pre-compiled uv binaries directly from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /code

# Configure uv to build the virtual environment locally inside /code
ENV UV_PROJECT_ENVIRONMENT="/code/.venv"
# Prepend the virtual environment to the system PATH
ENV PATH="/code/.venv/bin:$PATH"

# Copy dependency manifests first to leverage Docker layer caching
COPY pyproject.toml uv.lock ./

# Synchronize dependencies using uv
RUN uv sync --frozen --no-dev

# Copy the rest of the application source code
COPY . /code

# Create the standard non-root user required by Hugging Face Spaces (ID 1000)
RUN useradd -m -u 1000 user

# Grant the new user ownership of the application directory and the virtual environment
RUN chown -R user:user /code

# Switch to the required user context
USER user
ENV HOME=/home/user

# Initialize the Granian server on the required Hugging Face port
# Note: Ensure your FastAPI instance is named 'app' inside 'main.py'
CMD ["granian", "--interface", "asgi", "main:app", "--host", "0.0.0.0", "--port", "7860"]