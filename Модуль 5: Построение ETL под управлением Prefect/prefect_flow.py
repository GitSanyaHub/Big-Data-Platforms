# импорт модулей
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

from onetl.connection import SparkHDFS
from onetl.file import FileDFReader
from onetl.db import DBWriter
from onetl.file.format import CSV
from onetl.connection import Hive

from prefect import flow, task



# функция инициализации сессии
@task
def create_session():
    spark = SparkSession.builder \
        .master("yarn") \
        .appName("spark-with-yarn") \
        .config("spark.sql.warehouse.dir", "/user/hive/warehouse") \
        .config("spark.hive.metastore.uris", "thrift://tmpl-dn-01:9083") \
        .enableHiveSupport() \
        .getOrCreate()
    return spark


# функция чтения данных
@task
def extract_data(
    spark,
    host="tmpl-nn",
    port=9000,
    cluster_name="test",
    source_path="/input",
    files=None,
    delimiter=",",
    header=True
):
    files = files or ["data-20241101-structure-20180828.csv"]

    hdfs = SparkHDFS(host=host, port=port, spark=spark, cluster=cluster_name)
    hdfs.check()

    reader = FileDFReader(
        connection=hdfs,
        format=CSV(delimiter=delimiter, header=header),
        source_path=source_path
    )

    return reader.run(files)


# функция трансформации данных
@task
def transform_data(
    df,
    input_col="registration date",
    new_col="reg_year",
    substring_start=0,
    substring_length=4,
    num_partitions=90
):
    df = df.withColumn(new_col, F.col(input_col).substr(substring_start, substring_length))
    return df.repartition(num_partitions, new_col)


# функция загрузки данных
@task
def load_data(
    df,
    spark,
    cluster="test",
    table="test.regs",
    if_exists="replace_entire_table",
    partition_col="reg_year"
):
    hive = Hive(spark=spark, cluster=cluster)
    writer = DBWriter(
        connection=hive,
        table=table,
        options={
            "if_exists": if_exists,
            "partitionBy": partition_col
        }
    )
    writer.run(df)


# главная функция
@flow
def process_data():
    spark = create_session()
    edata = extract_data(spark)
    tdata = transform_data(edata)
    load_data(tdata, spark)

    spark.stop()



if __name__ == '__main__':
    process_data()