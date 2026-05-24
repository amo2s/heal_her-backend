# use the official python 3.13 slim image for a fast enterprise build
FROM python:3.13-slim

# set the working directory inside the cloud container
WORKDIR /code

# copy all your local project files into the container
COPY . /code/

# install uv for ultra-fast dependency management
RUN pip install --no-cache-dir uv

# install your project dependencies system-wide with prerelease flexibility
# (if you use a requirements.txt file instead of pyproject.toml, change the line below to: RUN uv pip install --system --prerelease allow -r requirements.txt)
RUN uv pip install --system --prerelease allow -e .

# expose hugging face's required internal port
EXPOSE 7860

# THE FIX: tell granian to route into the src/ folder to find your fastapi app
CMD ["granian", "--interface", "asgi", "src.main:app", "--host", "0.0.0.0", "--port", "7860"]