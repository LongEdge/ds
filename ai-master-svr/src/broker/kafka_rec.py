from kafka import KafkaConsumer
import time

BROKER = "<PRIVATE_HOST>:9002"
TOPIC = "<REDACTED_TOPIC>"


def receive_message():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BROKER,
        enable_auto_commit=True,
        auto_offset_reset="latest",
        max_poll_records=2000,
    )

    print(f"Listening on topic={TOPIC}")
    try:
        while True:
            msgs = consumer.poll(timeout_ms=1000)
            if not msgs:
                print("No new messages")
            else:
                record_lists = []
                for tp, records in msgs.items():
                    for record in records:
                        record_lists.append(record.value.decode())
                print("len:", len(record_lists))
            time.sleep(1)
    except KeyboardInterrupt:
        consumer.close()


if __name__ == "__main__":
    receive_message()
