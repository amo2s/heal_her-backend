# use the official python 3.12 slim image for rock-solid enterprise stability
FROM python:3.12-slim

# set the working directory inside the cloud container
WORKDIR /code

# copy all your local project files into the container
COPY . /code/

# install uv for ultra-fast dependency management
RUN pip install --no-cache-dir uv

# install your project dependencies system-wide (this will now instantly find guardrails-ai!)
RUN uv pip install --system -e .

# expose hugging face's required internal port
EXPOSE 7860

# tell granian to route into the src/ folder to find your fastapi app
CMD ["granian", "--interface", "asgi", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]