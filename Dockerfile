# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY ./source_code/requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's source code from the host to the container at /app
COPY ./source_code /app/source_code

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV PYTHONPATH=/app

# Run main.py when the container launches
# The command will be to run uvicorn server for the FastAPI app defined in source_code/main.py
CMD ["uvicorn", "source_code.main:app", "--host", "0.0.0.0", "--port", "8000"]
