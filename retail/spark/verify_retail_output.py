from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("VerifyRetailOutput").getOrCreate()

df = spark.read.parquet("/tmp/retail_stream_output")

print("TOTAL_RECORDS:", df.count())
df.select("invoice", "quantity", "price", "revenue").show(10, truncate=False)

spark.stop()