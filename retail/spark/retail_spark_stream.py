import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType
)

spark = (
    SparkSession.builder
    .appName("RetailKafkaStreaming")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")

schema = StructType([
    StructField("invoice", StringType()),
    StructField("stock_code", StringType()),
    StructField("description", StringType()),
    StructField("quantity", IntegerType()),
    StructField("invoice_date", StringType()),
    StructField("price", DoubleType()),
    StructField("customer_id", DoubleType()),
    StructField("country", StringType())
])

messages = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "broker:29092")
    .option("subscribe", "retail_transactions")
    .option("startingOffsets", "earliest")
    .option("maxOffsetsPerTrigger", 100)
    .load()
)

records = (
    messages.selectExpr("CAST(value AS STRING) AS json")
    .select(from_json(col("json"), schema).alias("r"))
    .select("r.*")
    .filter(col("invoice").isNotNull())
    .withColumn("revenue", col("quantity") * col("price"))
)

query = (
    records.writeStream
    .format("parquet")
    .option("path", "/tmp/retail_stream_output")
    .option("checkpointLocation", "/tmp/retail_stream_checkpoint")
    .outputMode("append")
    .trigger(availableNow=True)
    .start()
)

query.awaitTermination()
print("STREAMING_COMPLETE")