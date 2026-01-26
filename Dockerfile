# Use Python 3.10
FROM python:3.10

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

# --- THE FIX IS HERE ---
# Give the user permission to write to the static_ffmpeg folder so it can create its lock file
RUN chown -R user:user /usr/local/lib/python3.10/site-packages/static_ffmpeg

# Switch to the new user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Start the app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]