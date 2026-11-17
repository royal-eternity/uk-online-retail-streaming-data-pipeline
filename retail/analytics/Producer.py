"""
Publishes a continuous stream of retail transactions to Kafka.

    python producer.py

Use this when you want a real Kafka -> dashboard pipeline.
(If you already have your own producer / Spark job writing to a topic,
 just point RETAIL_KAFKA_TOPIC at it and skip this file.)
"""
import json
import time

from kafka import KafkaProducer

from live_engine import BOOTSTRAP, INVOICES_PER_SEC, TOPIC, EventGenerator


def main() -> None:
    gen = EventGenerator()
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP.split(","),
        value_serializer=lambda v: json.dumps(
            v, default=lambda o: o.isoformat()
        ).encode("utf-8"),
    )
    print(f"Streaming to Kafka {BOOTSTRAP} topic '{TOPIC}' (Ctrl+C to stop)")

    sent = 0
    try:
        while True:
            for event in gen.invoice():
                producer.send(TOPIC, event)
                sent += 1
            if sent % 200 < 8:
                print(f"{sent:,} events sent")
            time.sleep(float(gen.rng.exponential(1 / INVOICES_PER_SEC)))
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush()
        producer.close()


if __name__ == "__main__":
    main()