import os
import threading
import json
from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer
import os
import threading
import json
from datetime import datetime # Added for timestamping alerts
from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer
from dotenv import load_dotenv

from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

# Load environment variables from .env file
load_dotenv()

# AWS Bedrock Model ID and Region
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1") # Ensure this is set in .env or environment

class HealthcareAgent:
    def __init__(self):
        # Initialize LLM and chain
        try:
            self.llm = ChatBedrock(
                model_id=BEDROCK_MODEL_ID,
                region_name=AWS_REGION,
                model_kwargs={"temperature": 0.7, "max_tokens_to_sample": 1024} # Adjusted max_tokens
            )
            # Prompt template for chat, including history and current input with context
            self.chat_prompt_template = ChatPromptTemplate.from_messages([
                MessagesPlaceholder(variable_name="history"),
                HumanMessage(content="{input}") 
            ])
            self.chain = self.chat_prompt_template | self.llm | StrOutputParser()
            print(f"Successfully initialized Bedrock LLM with model: {BEDROCK_MODEL_ID} in region {AWS_REGION}")
        except Exception as e:
            print(f"Error initializing Bedrock LLM: {e}. Ensure AWS credentials and region are set.")
            self.llm = None
            self.chain = None

        self.kafka_topic = "healthcare_events" # Topic for n8n to produce to
        self.consumer = self._create_kafka_consumer()
        self.running = False
        self.consumer_thread = threading.Thread(target=self._consume_loop)

        # In-memory data stores (to be populated by the consumer)
        self.icu_patients = {}
        self.appointments = {}
        self.alerts = []  # For storing generated alerts
        self.conversation_histories = {}  # {session_id: [BaseMessage]}

    def _create_kafka_consumer(self):
        """Creates and configures the Kafka DeserializingConsumer."""
        schema_registry_conf = {
            'url': os.getenv("SCHEMA_REGISTRY_URL"),
            'basic.auth.user.info': os.getenv("SCHEMA_REGISTRY_API_KEY") + ':' + os.getenv("SCHEMA_REGISTRY_API_SECRET")
        }
        schema_registry_client = SchemaRegistryClient(schema_registry_conf)
        avro_deserializer = AvroDeserializer(schema_registry_client)

        consumer_conf = {
            'bootstrap.servers': os.getenv("BOOTSTRAP_SERVERS"),
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': os.getenv("CLUSTER_API_KEY"),
            'sasl.password': os.getenv("CLUSTER_API_SECRET"),
            'group.id': 'healthcare_agent_consumer_group',
            'auto.offset.reset': 'earliest',
            'key.deserializer': StringDeserializer('utf_8'),
            'value.deserializer': avro_deserializer
        }
        return DeserializingConsumer(consumer_conf)

    def _consume_loop(self):
        """The main loop for consuming and processing messages from Kafka."""
        self.consumer.subscribe([self.kafka_topic])
        print(f"Consumer subscribed to topic: {self.kafka_topic}")

        while self.running:
            try:
                msg = self.consumer.poll(1.0) # Poll for new messages
                if msg is None:
                    continue
                if msg.error():
                    print(f"Consumer error: {msg.error()}")
                    continue

                record = msg.value()
                print(f"Successfully consumed record: {record}")
                self._process_record(record)

            except Exception as e:
                print(f"An error occurred in the consumer loop: {e}")

        self.consumer.close()
        print("Kafka consumer closed.")

    def _process_record(self, record: dict):
        """Processes a single record from Kafka, updates data stores, and checks for alerts."""
        record_type = record.get('record_type')
        if record_type == 'ICU_PATIENT_UPDATE':
            patient_id = record.get('patient_id')
            icu_details_data = record.get('icu_details')
            if patient_id and icu_details_data:
                self.icu_patients[patient_id] = icu_details_data
                print(f"Updated ICU data for patient {patient_id}: {icu_details_data}")
                # Use current time for alert timestamp if not present in record
                alert_timestamp = record.get('timestamp', int(datetime.now().timestamp() * 1000))
                self._check_for_alerts(patient_id, icu_details_data, alert_timestamp)
        
        elif record_type == 'APPOINTMENT_SCHEDULE':
            details = record.get('appointment_details')
            if details:
                doctor_id = details.get('doctor_id')
                if doctor_id not in self.appointments:
                    self.appointments[doctor_id] = []
                self.appointments[doctor_id].append(details)
                print(f"Added new appointment for Dr. {doctor_id}")

    def _check_for_alerts(self, patient_id: str, icu_details: dict, timestamp: int):
        """Checks ICU data for critical conditions and generates alerts."""
        alerts_generated_this_cycle = []
        
        # Define critical thresholds (these are examples, adjust as needed)
        CRITICAL_HEART_RATE_LOW = 50
        CRITICAL_HEART_RATE_HIGH = 130
        CRITICAL_TEMP_HIGH = 39.0
        # Add more conditions: blood_pressure, respiratory_rate, etc.

        heart_rate = icu_details.get('heart_rate')
        if heart_rate is not None:
            if heart_rate < CRITICAL_HEART_RATE_LOW:
                alerts_generated_this_cycle.append({
                    "alert_id": f"alert_{patient_id}_hr_low_{timestamp}",
                    "patient_id": patient_id,
                    "condition": "Low Heart Rate",
                    "value": heart_rate,
                    "severity": "critical",
                    "timestamp": timestamp,
                    "message": f"Patient {patient_id} has critically low heart rate: {heart_rate} bpm."
                })
            elif heart_rate > CRITICAL_HEART_RATE_HIGH:
                alerts_generated_this_cycle.append({
                    "alert_id": f"alert_{patient_id}_hr_high_{timestamp}",
                    "patient_id": patient_id,
                    "condition": "High Heart Rate",
                    "value": heart_rate,
                    "severity": "critical",
                    "timestamp": timestamp,
                    "message": f"Patient {patient_id} has critically high heart rate: {heart_rate} bpm."
                })

        temp = icu_details.get('temperature_celsius')
        if temp is not None and temp > CRITICAL_TEMP_HIGH:
            alerts_generated_this_cycle.append({
                "alert_id": f"alert_{patient_id}_temp_high_{timestamp}",
                "patient_id": patient_id,
                "condition": "High Temperature",
                "value": temp,
                "severity": "warning",
                "timestamp": timestamp,
                "message": f"Patient {patient_id} has high temperature: {temp}°C."
            })
        
        for new_alert in alerts_generated_this_cycle:
            # Simple de-duplication: remove any existing alert for the same patient and condition before adding new one.
            self.alerts = [a for a in self.alerts if not (a['patient_id'] == new_alert['patient_id'] and a['condition'] == new_alert['condition'])]
            self.alerts.append(new_alert)
            print(f"Generated alert: {new_alert['message']}")

    def start_consumer(self):
        """Starts the Kafka consumer in a separate thread."""
        if not self.running:
            self.running = True
            self.consumer_thread.start()
            print("Kafka consumer thread started.")

    def stop_consumer(self):
        """Stops the Kafka consumer thread gracefully."""
        if self.running:
            self.running = False
            self.consumer_thread.join()
            print("Kafka consumer thread stopped.")

    def get_alerts(self) -> list:
        """Returns the list of currently active alerts. Can be expanded to filter old alerts."""
        # Example: Filter alerts older than 1 hour (3600000 ms)
        # current_time_ms = int(datetime.now().timestamp() * 1000)
        # recent_alerts = [a for a in self.alerts if (current_time_ms - a.get('timestamp', 0)) < 3600000]
        # return recent_alerts
        return self.alerts

    async def handle_chat(self, query: str, session_id: str = "default_session") -> str:
        """Handles a chat query using Bedrock LLM and maintains conversation history."""
        if not self.chain:
            return "AI service is not available at the moment. Please check configuration."

        if session_id not in self.conversation_histories:
            self.conversation_histories[session_id] = []

        # Prepare context for the LLM
        context_parts = ["You are a helpful Healthcare AI assistant for doctors. Your knowledge includes current ICU patient data and doctor appointments."]
        
        context_parts.append("Current ICU Patients Data (summarized for brevity):")
        if self.icu_patients:
            for patient_id, details in list(self.icu_patients.items())[:5]: # Limit context size
                context_parts.append(f"  - Patient {patient_id}: Vital signs - HR: {details.get('heart_rate')}, BP: {details.get('blood_pressure')}, Temp: {details.get('temperature_celsius')}°C. Notes: {details.get('notes', 'N/A')[:50]}...")
        else:
            context_parts.append("  No ICU patient data currently available.")
        
        context_parts.append("Upcoming Appointments Data (summarized for brevity):")
        if self.appointments:
            for doctor_id, appts in list(self.appointments.items())[:3]: # Limit context size
                context_parts.append(f"  - Dr. {doctor_id}:")
                for appt_detail in appts[:2]: # Limit context size
                    appt_time_dt = datetime.fromtimestamp(appt_detail.get('appointment_time') / 1000)
                    context_parts.append(f"    - Patient {appt_detail.get('patient_id', 'N/A')} on {appt_time_dt.strftime('%Y-%m-%d %H:%M')} for {appt_detail.get('reason', 'N/A')[:50]}...")
        else:
            context_parts.append("  No appointment data currently available.")
        
        final_context = "\n".join(context_parts)
        llm_input_text = f"{final_context}\n\nDoctor's query: {query}"

        history_messages = self.conversation_histories[session_id]
        
        try:
            # Use ainvoke for async FastAPI endpoint
            response = await self.chain.ainvoke({"input": llm_input_text, "history": history_messages})
            
            # Update history
            self.conversation_histories[session_id].append(HumanMessage(content=query))
            self.conversation_histories[session_id].append(AIMessage(content=response))
            # Limit history size
            if len(self.conversation_histories[session_id]) > 10: # Keep last 5 interactions (10 messages)
                self.conversation_histories[session_id] = self.conversation_histories[session_id][-10:]

            return response
        except Exception as e:
            print(f"Error during Bedrock LLM call for session {session_id}: {e}")
            # Consider logging the full error for debugging
            return "I encountered an error trying to process your request with the AI model. Please try again or check the logs."

# To run this agent independently for testing:
if __name__ == '__main__':
    agent = HealthcareAgent()
    agent.start_consumer()

    try:
        # Keep the main thread alive
        while True:
            pass
    except KeyboardInterrupt:
        print("Shutting down agent...")
        agent.stop_consumer()
