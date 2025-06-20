import os
import json
import time
import random
from datetime import datetime
from dotenv import load_dotenv
from confluent_kafka import avro
from confluent_kafka.avro import AvroProducer
from langchain_aws import ChatBedrock
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables
load_dotenv()

# --- Configuration ---
KAFKA_TOPIC = "healthcare_events"
SCHEMA_FILE_PATH = "healthcare_record.avsc"

# Confluent Cloud Config
bootstrap_servers = os.getenv("BOOTSTRAP_SERVERS")
schema_registry_url = os.getenv("SCHEMA_REGISTRY_URL")
sr_api_key = os.getenv("SCHEMA_REGISTRY_API_KEY")
sr_api_secret = os.getenv("SCHEMA_REGISTRY_API_SECRET")
cluster_api_key = os.getenv("CLUSTER_API_KEY")
cluster_api_secret = os.getenv("CLUSTER_API_SECRET")

print(f"DEBUG: Loaded SCHEMA_REGISTRY_URL = '{schema_registry_url}'") # Diagnostic print

# AWS Bedrock Config
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# --- Initialize LLM ---
llm = None
try:
    llm = ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        model_kwargs={"temperature": 0.8, "max_tokens_to_sample": 1500} # Increased tokens for JSON
    )
    print(f"Successfully initialized Bedrock LLM: {BEDROCK_MODEL_ID}")
except Exception as e:
    print(f"Error initializing Bedrock LLM: {e}. Producer will not run.")
    exit()

# --- Load Avro Schema ---
value_schema = None
try:
    value_schema = avro.load(SCHEMA_FILE_PATH)
    print(f"Successfully loaded Avro schema from {SCHEMA_FILE_PATH}")
except Exception as e:
    print(f"Error loading Avro schema: {e}. Producer will not run.")
    exit()

# --- Kafka Producer Config ---
producer_config = {
    'bootstrap.servers': bootstrap_servers,
    'schema.registry.url': schema_registry_url,
    'schema.registry.basic.auth.user.info': f'{sr_api_key}:{sr_api_secret}',
    'security.protocol': 'SASL_SSL',
    'sasl.mechanisms': 'PLAIN',
    'sasl.username': cluster_api_key,
    'sasl.password': cluster_api_secret,
}

avro_producer = AvroProducer(producer_config, default_value_schema=value_schema)

# --- LLM Prompt Templates for Data Generation ---

icu_update_prompt_template = PromptTemplate.from_template(
    """Generate a realistic JSON object for an ICU patient update. 
    The patient_id should be a string like 'P' followed by 3 digits (e.g., 'P123').
    The timestamp should be the current Unix timestamp in milliseconds.
    Follow this JSON structure strictly for the 'icu_details' part:
    {{ 'bed_number': 'string (e.g., B-105)', 'heart_rate': integer (50-180), 'blood_pressure': 'string (e.g., 120/80 mmHg)', 'respiratory_rate': integer (10-30), 'temperature_celsius': float (35.0-41.0), 'notes': 'string (brief, 5-15 words, or null)' }}
    
    The top-level JSON should be:
    {{ 'record_type': 'ICU_PATIENT_UPDATE', 'patient_id': 'PXXX', 'timestamp': {current_timestamp_ms}, 'icu_details': {{ ... }} }}
    
    Example for icu_details:
    {{ 'bed_number': 'B-201', 'heart_rate': 75, 'blood_pressure': '110/70 mmHg', 'respiratory_rate': 18, 'temperature_celsius': 37.2, 'notes': 'Patient stable and resting.' }}
    
    Provide only the JSON object as a string, no other text.
    Current timestamp (ms): {current_timestamp_ms}
    Random Patient ID: P{random_patient_id_suffix}
    JSON object:"""
)

appointment_schedule_prompt_template = PromptTemplate.from_template(
    """Generate a realistic JSON object for an upcoming doctor appointment.
    The patient_id should be a string like 'P' followed by 3 digits (e.g., 'P456').
    The doctor_id should be a string like 'D' followed by 3 digits (e.g., 'D789').
    The appointment_time should be a future Unix timestamp in milliseconds (e.g., within the next 1-7 days).
    The reason should be a brief medical reason for the appointment (5-10 words).
    Follow this JSON structure strictly for the 'appointment_details' part:
    {{ 'doctor_id': 'DXXX', 'appointment_time': {future_timestamp_ms}, 'reason': 'string' }}
    
    The top-level JSON should be:
    {{ 'record_type': 'APPOINTMENT_SCHEDULE', 'patient_id': 'PXXX', 'timestamp': {current_timestamp_ms}, 'appointment_details': {{ ... }} }}
    
    Example for appointment_details:
    {{ 'doctor_id': 'D007', 'appointment_time': {example_future_timestamp_ms}, 'reason': 'Follow-up consultation for recent lab results.' }}
    
    Provide only the JSON object as a string, no other text.
    Current timestamp (ms): {current_timestamp_ms}
    Future appointment timestamp (ms): {future_timestamp_ms}
    Random Patient ID: P{random_patient_id_suffix}
    Random Doctor ID: D{random_doctor_id_suffix}
    JSON object:"""
)

chain = llm | StrOutputParser()

# --- Helper Functions ---
def generate_llm_data(prompt_template, **kwargs):
    """Generates data using LLM based on the provided prompt template and arguments."""
    prompt = prompt_template.format(**kwargs)
    try:
        response_str = chain.invoke(prompt) # Using invoke for synchronous producer
        # The LLM might return the JSON string within triple backticks or with surrounding text.
        # Basic cleaning to extract JSON:
        if '```json' in response_str:
            response_str = response_str.split('```json')[1].split('```')[0].strip()
        elif '```' in response_str:
            response_str = response_str.split('```')[1].split('```')[0].strip()
        else:
            # Try to find the first '{' and last '}'
            first_brace = response_str.find('{')
            last_brace = response_str.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                response_str = response_str[first_brace:last_brace+1]
            else:
                print(f"LLM response doesn't look like valid JSON: {response_str}")
                return None
        
        return json.loads(response_str)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}")
        print(f"LLM Raw Response was: {response_str}")
        return None
    except Exception as e:
        print(f"Error during LLM data generation: {e}")
        return None

def delivery_report(err, msg):
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

# --- Main Production Loop ---
def main():
    if not llm or not value_schema:
        print("LLM or Schema not initialized. Exiting producer.")
        return

    print(f"Starting dummy data producer for topic '{KAFKA_TOPIC}'. Press Ctrl+C to stop.")
    try:
        while True:
            current_ts_ms = int(datetime.now().timestamp() * 1000)
            patient_id_suffix = str(random.randint(100, 999))
            record_to_produce = None

            if random.choice([True, False]): # 50/50 chance for ICU update or appointment
                print("\nGenerating ICU Patient Update...")
                record_to_produce = generate_llm_data(
                    icu_update_prompt_template,
                    current_timestamp_ms=current_ts_ms,
                    random_patient_id_suffix=patient_id_suffix
                )
            else:
                print("\nGenerating Appointment Schedule...")
                future_ts_ms = current_ts_ms + random.randint(1, 7) * 24 * 60 * 60 * 1000 # 1-7 days in future
                doctor_id_suffix = str(random.randint(100, 999))
                record_to_produce = generate_llm_data(
                    appointment_schedule_prompt_template,
                    current_timestamp_ms=current_ts_ms,
                    future_timestamp_ms=future_ts_ms,
                    example_future_timestamp_ms=current_ts_ms + 3 * 24 * 60 * 60 * 1000, # For example in prompt
                    random_patient_id_suffix=patient_id_suffix,
                    random_doctor_id_suffix=doctor_id_suffix
                )
            
            if record_to_produce:
                try:
                    # Basic validation (can be more thorough)
                    if 'record_type' not in record_to_produce or \
                       ('icu_details' not in record_to_produce and 'appointment_details' not in record_to_produce):
                        print(f"Generated data missing key fields: {record_to_produce}")
                        continue
                    
                    # Ensure patient_id is in the top level for appointment_details as per schema
                    if record_to_produce['record_type'] == 'APPOINTMENT_SCHEDULE' and 'patient_id' not in record_to_produce:
                        record_to_produce['patient_id'] = f"P{patient_id_suffix}" # Add if missing
                    
                    print(f"Producing record: {json.dumps(record_to_produce, indent=2)}")
                    avro_producer.produce(topic=KAFKA_TOPIC, value=record_to_produce, key=record_to_produce.get('patient_id', str(random.randint(0,1000000))) , callback=delivery_report)
                    avro_producer.poll(0) # Trigger delivery reports
                except Exception as e:
                    print(f"Error producing message: {e}")
                    print(f"Record was: {record_to_produce}")
            else:
                print("Failed to generate data from LLM for this cycle.")

            time.sleep(60) # Wait for 1 minute

    except KeyboardInterrupt:
        print("\nShutting down producer...")
    finally:
        avro_producer.flush()
        print("Producer flushed and shut down.")

if __name__ == "__main__":
    main()
