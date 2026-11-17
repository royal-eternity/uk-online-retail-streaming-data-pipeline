
import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType

logging.basicConfig(level=logging.INFO)

KAFKA_SERVER = "broker:29092"
CASSANDRA_HOST = "cassandra"

schema = StructType([
    StructField("id", StringType(), True),
    StructField("first_name", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("gender", StringType(), True),
    StructField("address", StringType(), True),
    StructField("post_code", StringType(), True),
    StructField("email", StringType(), True),
    StructField("username", StringType(), True),
    StructField("dob", StringType(), True),
    StructField("registered_date", StringType(), True),
    StructField("phone", StringType(), True),
    StructField("picture", StringType(), True),
])

def main():
    spark = (
        SparkSession.builder
        .appName("SparkDataStreaming")
        .config("spark.cassandra.connection.host", CASSANDRA_HOST)
        .config("spark.cassandra.connection.port", "9042")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    users = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_SERVER)
        .option("subscribe", "users_created")
        .option("startingOffsets", "earliest")
        .load()
        .selectExpr("CAST(value AS STRING) AS json_value")
        .select(from_json(col("json_value"), schema).alias("data"))
        .select("data.*")
    )

    query = (
        users.writeStream
        .format("org.apache.spark.sql.cassandra")
        .option("checkpointLocation", "/tmp/checkpoint-users")
        .option("keyspace", "spark_streams")
        .option("table", "created_users")
        .start()
    )

    logging.info("Streaming users from Kafka to Cassandra...")
    query.awaitTermination()

    
if __name__ == "__main__":
    main()
