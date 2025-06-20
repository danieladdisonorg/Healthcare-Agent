# Healthcare AI Agent

A comprehensive healthcare management system that provides a REST API for accessing ICU patient data and medical appointments. The system leverages AWS Bedrock for AI-powered clinical assistance and real-time alert generation for critical patient conditions.

## Overview

The Healthcare AI Agent is designed to streamline healthcare operations by providing:
- Real-time ICU patient monitoring and data management
- Intelligent appointment scheduling and tracking
- AI-powered clinical decision support through chat interface
- Automated alert system for critical patient conditions
- Scalable data ingestion via Apache Kafka

## Architecture

The system utilizes a microservices architecture with the following components:
- **FastAPI REST API**: Provides endpoints for data access and AI interactions
- **Apache Kafka Integration**: Real-time data streaming via Confluent Cloud
- **AWS Bedrock**: AI/ML services for chat assistance and data generation
- **Avro Schema**: Structured data serialization for reliable message processing

## Project Structure

```
healthcare_agent/
├── Dockerfile                          # Container configuration
├── README.md                          # Project documentation
├── .gitignore                         # Git ignore rules
└── src/
    ├── agent.py                       # Core agent logic and Kafka consumer
    ├── main.py                        # FastAPI application and API endpoints
    ├── dummy_data_producer.py         # Test data generator
    ├── healthcare_record.avsc         # Avro schema definition
    ├── requirements.txt               # Python dependencies
    └── .env.example                   # Environment configuration template
```

## Prerequisites

- Python 3.8 or higher
- Docker (optional, for containerized deployment)
- AWS Account with Bedrock access
- Confluent Cloud Kafka cluster
- Valid AWS credentials configured

## Installation & Setup

### 1. Environment Setup

Clone the repository and navigate to the source directory:

```bash
cd src
```

Create and activate a Python virtual environment:

```bash
python -m venv venv
```

**Windows:**
```bash
.\venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the `src` directory with the following configuration:

```env
# Confluent Cloud Kafka Configuration
BOOTSTRAP_SERVERS="pkc-xxxx.region.provider.confluent.cloud:9092"
SCHEMA_REGISTRY_URL="https://sr-xxxx.region.provider.confluent.cloud"
SCHEMA_REGISTRY_API_KEY="YOUR_SR_API_KEY"
SCHEMA_REGISTRY_API_SECRET="YOUR_SR_API_SECRET"
CLUSTER_API_KEY="YOUR_CLUSTER_API_KEY"
CLUSTER_API_SECRET="YOUR_CLUSTER_API_SECRET"

# AWS Bedrock Configuration
BEDROCK_MODEL_ID="anthropic.claude-sonnet-4-20250514-v1:0"
AWS_DEFAULT_REGION="us-east-1"
AWS_ACCESS_KEY_ID="YOUR_AWS_ACCESS_KEY"
AWS_SECRET_ACCESS_KEY="YOUR_AWS_SECRET_KEY"
```

> **Note**: Ensure your AWS credentials have appropriate permissions for Bedrock service access.

## Deployment

### Local Development

1. **Start the Data Producer** (Terminal 1):
   ```bash
   python dummy_data_producer.py
   ```

2. **Start the Healthcare Agent** (Terminal 2):
   ```bash
   uvicorn main:app --reload --port 8000
   ```

The API will be available at `http://localhost:8000` with interactive documentation at `http://localhost:8000/docs`.

### Docker Deployment

Build the Docker image:

```bash
docker build -t healthcare-agent .
```

Run the containerized application:

```bash
docker run -p 8000:8000 --env-file ./src/.env healthcare-agent
```

## API Reference

### Patient Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/icu/patients` | GET | Retrieve all ICU patient data |
| `/icu/patients/{patient_id}` | GET | Get specific patient information |

### Appointment Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/appointments/{doctor_id}` | GET | Get doctor's upcoming appointments |

### Alert System

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/alerts` | GET | Retrieve critical patient alerts |

### AI Chat Interface

| Endpoint | Method | Description | Request Body |
|----------|--------|-------------|--------------|
| `/chat` | POST | AI-powered clinical assistance | `{"session_id": "string", "query": "string"}` |

### Example API Usage

**Chat with AI Assistant:**
```json
POST /chat
{
  "session_id": "session_001",
  "query": "What is the current status of patient P123?"
}
```

**Get Patient Data:**
```bash
curl -X GET "http://localhost:8000/icu/patients/P123"
```

## Data Schema

Healthcare events follow the Avro schema defined in `healthcare_record.avsc`, supporting:
- ICU patient updates with vital signs and medical status
- Appointment scheduling with doctor and patient details
- Structured data validation and serialization

## Monitoring & Alerts

The system automatically generates alerts for:
- Critical vital sign thresholds
- Abnormal patient conditions
- System health and connectivity issues

Alerts are timestamped and stored for historical analysis and reporting.

## Security Considerations

- All API endpoints should be secured with appropriate authentication in production
- Environment variables contain sensitive credentials and should be properly managed
- AWS IAM roles and policies should follow the principle of least privilege
- Network security groups should restrict access to necessary ports only

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## Support

For technical support or questions:
- Review the API documentation at `/docs` endpoint
- Check system logs for error details
- Verify environment configuration and credentials

## License

This project is licensed under the [MIT License](./LICENSE)