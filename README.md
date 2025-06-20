# Healthcare AI Agent

This agent provides a REST API for accessing ICU patient data and upcoming medical appointments. It integrates with AWS Bedrock to offer AI-powered chat assistance for doctors and generates alerts for critical patient conditions.

Data is ingested from a Confluent Kafka topic (`healthcare_events`) populated by a dummy data producer, which also uses AWS Bedrock for generating realistic data.

## Project Structure

```
healthcare_agent/
├── Dockerfile
├── README.md
├── .gitignore
└── source_code/
    ├── agent.py             # Core agent logic, Kafka consumer, Bedrock integration
    ├── main.py              # FastAPI application, API endpoints
    ├── dummy_data_producer.py # Generates and sends dummy data to Kafka
    ├── healthcare_record.avsc # Avro schema for Kafka messages
    ├── requirements.txt     # Python dependencies
    └── .env.example         # Example environment variables file
```

## Setup

1.  **Clone the repository (if applicable) or ensure you have the `healthcare_agent` directory.**

2.  **Navigate to the agent's source code directory:**
    ```bash
    cd source_code
    ```

3.  **Create a virtual environment and activate it:**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    # source venv/bin/activate
    ```

4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Configure Environment Variables:**
    Create a `.env` file in the `source_code` directory by copying `.env.example` (if provided) or creating it manually. Populate it with your Confluent Cloud credentials and AWS Bedrock settings:
    ```env
    # Confluent Cloud Kafka Configuration
    BOOTSTRAP_SERVERS="pkc-xxxx.region.provider.confluent.cloud:9092"
    SCHEMA_REGISTRY_URL="https://sr-xxxx.region.provider.confluent.cloud"
    SCHEMA_REGISTRY_API_KEY="YOUR_SR_API_KEY"
    SCHEMA_REGISTRY_API_SECRET="YOUR_SR_API_SECRET"
    CLUSTER_API_KEY="YOUR_CLUSTER_API_KEY"
    CLUSTER_API_SECRET="YOUR_CLUSTER_API_SECRET"

    # AWS Bedrock Configuration
    BEDROCK_MODEL_ID="anthropic.claude-sonnet-4-20250514-v1:0" # Or your preferred model
    AWS_DEFAULT_REGION="us-east-1" # Your AWS region
    # Ensure your AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) are configured 
    # in your environment or via an IAM role if running in AWS.
    ```

## Running the Agent

1.  **Start the Dummy Data Producer (in a separate terminal):**
    Navigate to the `source_code` directory and run:
    ```bash
    python dummy_data_producer.py
    ```
    This script will start generating dummy ICU patient updates and appointment schedules and send them to the `healthcare_events` Kafka topic every minute.

2.  **Start the Healthcare AI Agent (FastAPI application):**
    In another terminal, navigate to the `source_code` directory and run:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The agent will start, connect to Kafka, and begin consuming messages. The API will be available at `http://localhost:8000`.

## API Endpoints

Once the agent is running, you can access the following endpoints (view interactive documentation at `http://localhost:8000/docs`):

*   **GET `/icu/patients`**: Retrieve all current ICU patient data.
*   **GET `/icu/patients/{patient_id}`**: Retrieve data for a specific ICU patient.
*   **GET `/appointments/{doctor_id}`**: Retrieve upcoming appointments for a specific doctor.
*   **GET `/alerts`**: Retrieve any generated alerts for critical patient conditions.
*   **POST `/chat`**: Interact with the AI chat assistant. Requires a JSON body:
    ```json
    {
      "session_id": "some_unique_session_id",
      "query": "What is the status of patient P123?"
    }
    ```

## Docker

A `Dockerfile` is provided to containerize the agent. 

1.  **Build the Docker image:**
    From the `healthcare_agent` directory (where the Dockerfile is located):
    ```bash
    docker build -t healthcare-agent .
    ```

2.  **Run the Docker container:**
    You'll need to pass the environment variables to the container. One way is using an env file:
    ```bash
    docker run -p 8000:8000 --env-file ./source_code/.env healthcare-agent
    ```
    Ensure your `.env` file is correctly populated before running.

## Avro Schema

The Kafka messages on the `healthcare_events` topic adhere to the Avro schema defined in `source_code/healthcare_record.avsc`.
