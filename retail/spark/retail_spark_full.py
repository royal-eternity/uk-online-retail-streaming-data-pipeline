
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, round as spark_round
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, DoubleType
)

spark = (
    SparkSession.builder
    .appName("RetailKafkaFullStreaming")
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
    .option("subscribe", "retail_transactions_full")
    .option("startingOffsets", "earliest")
    .option("maxOffsetsPerTrigger", 10000)
    .load()
)

records = (
    messages.selectExpr("CAST(value AS STRING) AS json")
    .select(from_json(col("json"), schema).alias("r"))
    .select("r.*")
    .filter(col("invoice").isNotNull())
    .withColumn("revenue", spark_round(col("quantity") * col("price"), 2))
)

query = (
    records.writeStream
    .format("parquet")
    .option("path", "/tmp/retail_full_output")
    .option("checkpointLocation", "/tmp/retail_full_checkpoint")
    .outputMode("append")
    .trigger(availableNow=True)
    .start()
)

query.awaitTermination()
print("FULL_STREAMING_COMPLETE")
