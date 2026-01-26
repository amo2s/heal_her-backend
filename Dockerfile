# Use Python 3.9
FROM python:3.9

# Set the working directory
WORKDIR /code

# Copy the requirements file
COPY ./requirements.txt /code/requirements.txt

# Install the dependencies
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of your backend code
COPY . /code

# Create a new user (Required by Hugging Face)
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Start the app (Assumes your main file is main.py)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]