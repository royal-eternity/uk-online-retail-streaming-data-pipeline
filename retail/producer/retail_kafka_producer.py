
import argparse
import json
import time
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer
from kafka.errors import KafkaError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PARQUET_DIR = PROJECT_ROOT / "retail" / "output" / "parquet"

DEFAULT_TOPIC = "retail_transactions_full"
DEFAULT_BOOTSTRAP = "localhost:9092"


def json_value(value):
    """Convert Pandas and NumPy values into JSON-compatible values."""
    if pd.isna(value):
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    if hasattr(value, "item"):
        return value.item()

    return value


def main():
    parser = argparse.ArgumentParser(
        description="Replay historical UK retail transactions into Kafka."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of records to send (default: 100).",
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=20,
        help="Target records per second (default: 20).",
    )

    parser.add_argument(
        "--bootstrap",
        default=DEFAULT_BOOTSTRAP,
        help="Kafka bootstrap server (default: localhost:9092).",
    )

    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"Kafka topic (default: {DEFAULT_TOPIC}).",
    )

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be greater than zero.")

    if args.rate <= 0:
        parser.error("--rate must be greater than zero.")

    files = sorted(PARQUET_DIR.glob("retail_*.parquet"))

    if not files:
        raise FileNotFoundError(
            f"No retail Parquet files found in {PARQUET_DIR}"
        )

    print("Starting UK Online Retail II Kafka Producer")
    print(f"Kafka server : {args.bootstrap}")
    print(f"Kafka topic  : {args.topic}")
    print(f"Record limit : {args.limit}")
    print(f"Target rate  : {args.rate} records/second")
    print(f"Parquet files: {len(files)}")

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        value_serializer=lambda value: json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8"),
        acks="all",
        retries=5,
        max_block_ms=30000,
    )

    sent = 0
    started = time.monotonic()
    next_send = started

    try:
        for file in files:
            print(f"\nReading: {file.name}")

            dataframe = pd.read_parquet(file)

            for record_data in dataframe.to_dict(orient="records"):
                if sent >= args.limit:
                    break

                record = {
                    key: json_value(value)
                    for key, value in record_data.items()
                }

                future = producer.send(
                    args.topic,
                    value=record,
                )

                future.get(timeout=30)
                sent += 1

                next_send += 1.0 / args.rate
                delay = next_send - time.monotonic()

                if delay > 0:
                    time.sleep(delay)

                if sent % 25 == 0 or sent == args.limit:
                    elapsed = time.monotonic() - started

                    print(
                        f"Sent {sent}/{args.limit} records "
                        f"in {elapsed:.1f} seconds",
                        flush=True,
                    )

            if sent >= args.limit:
                break

        producer.flush(timeout=30)

        elapsed = time.monotonic() - started

        print("\n========== PRODUCER SUMMARY ==========")
        print(f"Records sent : {sent}")
        print(f"Elapsed time : {elapsed:.2f} seconds")
        print(f"Kafka topic  : {args.topic}")
        print("Status       : SUCCESS")
        print("======================================")

    except Exception:
        print(
            f"Producer stopped after sending {sent} records.",
            flush=True,
        )
        raise

    finally:
        producer.close(timeout=10)


if __name__ == "__main__":
    main()
