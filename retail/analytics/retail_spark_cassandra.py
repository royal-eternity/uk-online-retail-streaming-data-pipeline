
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    from_json,
    round as spark_round,
    current_timestamp,
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    IntegerType,
    DoubleType,
)

KAFKA_SERVERS = "broker:29092"
KAFKA_TOPIC = "retail_transactions_full"
KEYSPACE = "spark_streams"
TABLE = "retail_transactions_v2"
CHECKPOINT = "/opt/spark-checkpoint/retail_cassandra_checkpoint"

schema = StructType([
    StructField("invoice", StringType(), True),
    StructField("stock_code", StringType(), True),
    StructField("description", StringType(), True),
    StructField("quantity", IntegerType(), True),
    StructField("invoice_date", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("customer_id", DoubleType(), True),
    StructField("country", StringType(), True),
])

spark = (
    SparkSession.builder
    .appName("UKRetailToCassandra")
    .config("spark.cassandra.connection.host", "cassandra")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

kafka = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_SERVERS)
    .option("subscribe", KAFKA_TOPIC)
    .option("startingOffsets", "earliest")
    .option("maxOffsetsPerTrigger", 10000)
    .load()
)

records = (
    kafka.selectExpr(
        "CAST(value AS STRING) AS json",
        "CAST(partition AS INT) AS kafka_partition",
        "CAST(offset AS BIGINT) AS kafka_offset",
    )
    .select(
        from_json(col("json"), schema).alias("r"),
        col("kafka_partition"),
        col("kafka_offset"),
    )
    .select("r.*", "kafka_partition", "kafka_offset")
    .filter(
        col("invoice").isNotNull()
        & col("stock_code").isNotNull()
        & col("invoice_date").isNotNull()
        & col("quantity").isNotNull()
        & col("price").isNotNull()
        & col("kafka_offset").isNotNull()
    )
    .withColumn(
        "revenue",
        spark_round(col("quantity") * col("price"), 2),
    )
    .withColumn("processed_at", current_timestamp())
)


def write_to_cassandra(batch_df, batch_id):
    if batch_df.isEmpty():
        print(f"Batch {batch_id}: no valid rows")
        return

    output = batch_df.select(
        "invoice",
        "stock_code",
        "invoice_date",
        "kafka_partition",
        "kafka_offset",
        "description",
        "quantity",
        "price",
        "customer_id",
        "country",
        "revenue",
        "processed_at",
    )

    (
        output.write
        .format("org.apache.spark.sql.cassandra")
        .mode("append")
        .options(keyspace=KEYSPACE, table=TABLE)
        .save()
    )

    print(f"Batch {batch_id}: Cassandra write completed")


query = (
    records.writeStream
    .foreachBatch(write_to_cassandra)
    .option("checkpointLocation", CHECKPOINT)
    .trigger(availableNow=True)
    .start()
)

query.awaitTermination()
print("UK_RETAIL_CASSANDRA_COMPLETE")
