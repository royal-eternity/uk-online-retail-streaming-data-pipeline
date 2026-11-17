"""Live streaming engine for the retail sales dashboard.

RETAIL_STREAM_MODE:
    auto       -> Try Kafka; use simulator if Kafka is unavailable.
    kafka      -> Kafka only; retry if unavailable.
    simulator  -> Built-in simulated stream only.

Environment variables:
    RETAIL_KAFKA_BOOTSTRAP   default localhost:9092
    RETAIL_KAFKA_TOPIC       default retail_transactions
    RETAIL_INVOICES_PER_SEC  default 2
"""

import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

BOOTSTRAP = os.getenv("RETAIL_KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.getenv("RETAIL_KAFKA_TOPIC", "retail_transactions")
MODE = os.getenv("RETAIL_STREAM_MODE", "auto").strip().lower()

try:
    INVOICES_PER_SEC = max(
        0.1, float(os.getenv("RETAIL_INVOICES_PER_SEC", "2"))
    )
except ValueError:
    INVOICES_PER_SEC = 2.0

# Expected layout:
# retail/analytics/Live_engine.py
# retail/output/full_streamed_parquet/
DATA_DIR = (
        Path(__file__).resolve().parents[1]
        / "output"
        / "full_streamed_parquet"
)

COLUMNS = [
    "invoice",
    "stock_code",
    "description",
    "quantity",
    "price",
    "customer_id",
    "country",
    "revenue",
    "event_time",
]

NON_PRODUCT = {
    "POST", "DOT", "M", "D", "S", "B", "C2", "CRUK",
    "BANK CHARGES", "AMAZONFEE", "PADS", "ADJUST",
    "ADJUST2", "TEST001", "TEST002",
}

QTYS = np.array([1, 2, 3, 4, 6, 8, 12, 24])
QTY_P = np.array([0.20, 0.15, 0.10, 0.10, 0.15, 0.10, 0.15, 0.05])

FALLBACK_PRODUCTS = [
    ("85123A", "WHITE HANGING HEART T-LIGHT HOLDER", 2.95),
    ("22423", "REGENCY CAKESTAND 3 TIER", 12.75),
    ("84879", "ASSORTED COLOUR BIRD ORNAMENT", 1.69),
    ("47566", "PARTY BUNTING", 4.95),
    ("21212", "PACK OF 72 RETROSPOT CAKE CASES", 0.55),
    ("22086", "PAPER CHAIN KIT 50'S CHRISTMAS", 2.55),
    ("85099B", "JUMBO BAG RED RETROSPOT", 2.08),
    ("23166", "MEDIUM CERAMIC TOP STORAGE JAR", 1.04),
    ("22197", "POPCORN HOLDER", 0.85),
    ("21977", "PACK OF 60 PINK PAISLEY CAKE CASES", 0.55),
    ("20725", "LUNCH BAG RED RETROSPOT", 1.65),
    ("22960", "JAM MAKING SET WITH JARS", 4.25),
]

ALIASES = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "event_time",
    "invoice_date": "event_time",
    "Price": "price",
    "Customer ID": "customer_id",
    "CustomerID": "customer_id",
    "Country": "country",
    "timestamp": "event_time",
}


class EventGenerator:
    """Generate demo invoice lines using a product/customer catalogue."""

    def __init__(self):
        self.rng = np.random.default_rng()
        self.invoice_no = 600000
        self._load_catalogue()

    def _load_catalogue(self):
        try:
            import pyarrow.dataset as ds

            if not DATA_DIR.exists():
                raise FileNotFoundError(
                    f"Parquet directory not found: {DATA_DIR}"
                )

            dataset = ds.dataset(str(DATA_DIR), format="parquet")
            available = set(dataset.schema.names)
            required = {
                "stock_code", "description", "price",
                "customer_id", "country",
            }
            missing = required - available

            if missing:
                raise ValueError(
                    f"Parquet dataset is missing columns: {sorted(missing)}"
                )

            raw = dataset.to_table(
                columns=[
                    "stock_code", "description", "price",
                    "customer_id", "country",
                ]
            ).to_pandas()

            raw["price"] = pd.to_numeric(raw["price"], errors="coerce")
            raw = raw.dropna(subset=["description", "price"]).copy()
            raw["stock_code"] = raw["stock_code"].fillna("").astype(str)
            raw["description"] = (
                raw["description"].fillna("").astype(str).str.strip()
            )
            raw = raw[
                raw["description"].ne("")
                & raw["price"].gt(0)
                & raw["price"].lt(500)
                & ~raw["stock_code"].isin(NON_PRODUCT)
                ].copy()

            products = (
                raw.groupby(
                    ["stock_code", "description"], as_index=False
                )
                .agg(price=("price", "median"), n=("price", "size"))
                .nlargest(800, "n")
                .reset_index(drop=True)
            )

            customers_raw = raw.dropna(subset=["customer_id"]).copy()
            customers_raw["customer_id"] = (
                customers_raw["customer_id"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
            )
            customers = (
                customers_raw.groupby(
                    ["customer_id", "country"], as_index=False
                )
                .size()
            )
            customers["country"] = customers["country"].fillna("Unknown")

            if products.empty or customers.empty:
                raise ValueError("No usable products or customers found.")

            self.p_code = products["stock_code"].to_numpy()
            self.p_desc = products["description"].to_numpy()
            self.p_price = products["price"].to_numpy(dtype=float)
            self.p_w = (
                    products["n"] / products["n"].sum()
            ).to_numpy(dtype=float)

            self.c_id = customers["customer_id"].to_numpy()
            self.c_country = customers["country"].astype(str).to_numpy()
            self.c_w = (
                    customers["size"] / customers["size"].sum()
            ).to_numpy(dtype=float)

            print(f"Loaded {len(products)} products from {DATA_DIR}")

        except Exception as exc:
            print(f"Catalogue loading warning: {exc}")
            print("Using the built-in fallback product catalogue.")

            self.p_code = np.array([p[0] for p in FALLBACK_PRODUCTS])
            self.p_desc = np.array([p[1] for p in FALLBACK_PRODUCTS])
            self.p_price = np.array([p[2] for p in FALLBACK_PRODUCTS])
            self.p_w = np.ones(len(FALLBACK_PRODUCTS)) / len(FALLBACK_PRODUCTS)

            self.c_id = np.array([str(12347 + i) for i in range(300)])
            countries = [
                            "United Kingdom"
                        ] * 8 + ["Germany", "France", "EIRE"]
            self.c_country = np.array(
                [countries[i % len(countries)] for i in range(300)]
            )
            self.c_w = np.ones(len(self.c_id)) / len(self.c_id)

    def invoice(self, ts=None):
        """Create one invoice containing one or more product lines."""
        ts = ts or datetime.now()
        self.invoice_no += 1

        customer_index = self.rng.choice(len(self.c_id), p=self.c_w)
        cancelled = self.rng.random() < 0.02

        n_lines = min(
            int(self.rng.geometric(0.22)),
            12,
            len(self.p_code),
        )
        n_lines = max(1, n_lines)

        indices = self.rng.choice(
            len(self.p_code),
            size=n_lines,
            replace=False,
            p=self.p_w,
        )

        invoice_id = (
            f"C{self.invoice_no}" if cancelled else str(self.invoice_no)
        )
        rows = []

        for index in indices:
            quantity = int(self.rng.choice(QTYS, p=QTY_P))
            if cancelled:
                quantity = -quantity

            price = float(self.p_price[index])
            rows.append({
                "invoice": invoice_id,
                "stock_code": str(self.p_code[index]),
                "description": str(self.p_desc[index]),
                "quantity": quantity,
                "price": round(price, 2),
                "customer_id": str(self.c_id[customer_index]),
                "country": str(self.c_country[customer_index]),
                "revenue": round(quantity * price, 2),
                "event_time": ts,
            })

        return rows


class LiveEngine:
    """Thread-safe buffer holding the most recent stream events."""

    def __init__(self, maxlen=60000):
        self.events = deque(maxlen=maxlen)
        self.lock = threading.Lock()
        self.countries = set()
        self.total = 0
        self.started = datetime.now()
        self.source = "Starting"
        self.status = "Starting stream..."

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="live-engine",
        )
        self.thread.start()

    def snapshot(self):
        """Return a safe DataFrame copy of the buffered events."""
        with self.lock:
            rows = list(self.events)

        if not rows:
            return pd.DataFrame(columns=COLUMNS)

        df = pd.DataFrame(rows, columns=COLUMNS)
        df["event_time"] = pd.to_datetime(
            df["event_time"], errors="coerce"
        )
        return (
            df.dropna(subset=["event_time"])
            .sort_values("event_time", kind="stable")
            .reset_index(drop=True)
        )

    def _ingest(self, rows):
        """Add normalized event rows to the shared buffer."""
        if not rows:
            return

        valid_rows = [
            row for row in rows
            if isinstance(row, dict)
        ]
        if not valid_rows:
            return

        with self.lock:
            self.events.extend(valid_rows)
            self.total += len(valid_rows)
            self.countries.update(
                str(row.get("country", "Unknown"))
                for row in valid_rows
            )

    def _run(self):
        mode = MODE
        if mode not in {"auto", "kafka", "simulator"}:
            self.status = f"Invalid mode '{mode}'; using auto mode."
            mode = "auto"

        if mode != "simulator":
            connected = self._run_kafka()

            # A successful Kafka consumer runs until it exits.
            if connected:
                return

            if mode == "kafka":
                while True:
                    time.sleep(5)
                    if self._run_kafka():
                        return

        self._run_simulator()

    def _normalise(self, msg):
        """Normalize Kafka records to the dashboard's column names."""
        data = {ALIASES.get(key, key): value for key, value in msg.items()}
        now = datetime.now()

        try:
            timestamp = pd.to_datetime(
                data.get("event_time"), errors="raise"
            ).to_pydatetime()
            if abs((now - timestamp).total_seconds()) > 3600:
                timestamp = now
        except Exception:
            timestamp = now

        try:
            quantity = float(data.get("quantity") or 0)
        except (TypeError, ValueError):
            quantity = 0.0

        try:
            price = float(data.get("price") or 0)
        except (TypeError, ValueError):
            price = 0.0

        try:
            revenue = float(data.get("revenue"))
        except (TypeError, ValueError):
            revenue = quantity * price

        customer_id = str(data.get("customer_id") or "")
        if customer_id.endswith(".0"):
            customer_id = customer_id[:-2]

        return {
            "invoice": str(data.get("invoice") or ""),
            "stock_code": str(data.get("stock_code") or ""),
            "description": str(
                data.get("description") or "Unknown"
            ).strip(),
            "quantity": quantity,
            "price": price,
            "customer_id": customer_id,
            "country": str(data.get("country") or "Unknown"),
            "revenue": revenue,
            "event_time": timestamp,
        }

    def _run_kafka(self):
        """Consume Kafka messages. Return False if connection fails."""
        try:
            from kafka import KafkaConsumer

            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=BOOTSTRAP.split(","),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                group_id="retail-live-dashboard",
                value_deserializer=lambda value: json.loads(
                    value.decode("utf-8")
                ),
                api_version_auto_timeout_ms=4000,
                consumer_timeout_ms=1000,
            )
        except Exception as exc:
            self.source = "Kafka"
            self.status = (
                f"Kafka unavailable at {BOOTSTRAP} "
                f"({type(exc).__name__})"
            )
            return False

        self.source = "Kafka"
        self.status = f"Connected to {BOOTSTRAP}; topic '{TOPIC}'"

        while True:
            try:
                batches = consumer.poll(timeout_ms=1000)

                for records in batches.values():
                    rows = []
                    for record in records:
                        value = record.value
                        items = value if isinstance(value, list) else [value]
                        for item in items:
                            if isinstance(item, dict):
                                rows.append(self._normalise(item))
                    self._ingest(rows)

            except Exception as exc:
                self.status = (
                    f"Kafka read error: {type(exc).__name__}; retrying"
                )
                time.sleep(2)

    def _run_simulator(self):
        """Seed recent demo events, then continue generating events."""
        self.source = "Simulator"
        self.status = "Loading product catalogue..."

        generator = EventGenerator()
        self.status = (
            "Simulated live stream using the available product catalogue"
        )

        # Seed approximately five minutes of data.
        timestamp = datetime.now() - timedelta(minutes=5)
        end_time = datetime.now()

        while timestamp < end_time:
            self._ingest(generator.invoice(timestamp))
            delay = float(
                generator.rng.exponential(1 / INVOICES_PER_SEC)
            )
            timestamp += timedelta(seconds=max(delay, 0.01))

        while True:
            self._ingest(generator.invoice())
            time.sleep(
                max(
                    float(generator.rng.exponential(1 / INVOICES_PER_SEC)),
                    0.01,
                )
            )