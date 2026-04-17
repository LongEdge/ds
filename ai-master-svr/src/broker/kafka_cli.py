from kafka import KafkaProducer
import json

BROKER = "<PRIVATE_HOST>:9002"
TOPIC = "<REDACTED_TOPIC>"


def send_message(msgs):
    producer = KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        retries=3,
    )
    for msg in msgs:
        producer.send(TOPIC, msg)
    producer.flush()
    producer.close()


if __name__ == "__main__":
    send_message([{'name': f'item-{i}', 'age': 18, 'gender': 1} for i in range(100)])
