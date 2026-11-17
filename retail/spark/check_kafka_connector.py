from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("RetailKafkaConnectorCheck").getOrCreate()

try:
    print("SPARK_VERSION:", spark.version)
    print("KAFKA_SOURCE_AVAILABLE:",
          spark._jvm.org.apache.spark.sql.SparkSession.active()
          .read().format("kafka").toString())
    print("CONNECTOR_CHECK: Spark session started")
finally:
    spark.stop()
