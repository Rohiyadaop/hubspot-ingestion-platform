
# import dlt
# from app.hubspot_source import get_contacts


# def run_pipeline():
#     pipeline = dlt.pipeline(
#         pipeline_name="hubspot_ingestion",
#         destination=dlt.destinations.filesystem(
#             bucket_url="./data/parquet"
#         ),
#         dataset_name="hubspot_data",
#         pipelines_dir="./data/dlt_pipelines",
#     )

#     load_info = pipeline.run(
#         get_contacts(),
#         loader_file_format="parquet",
#     )

#     print("\nPipeline execution completed!")
#     print(load_info)


# if __name__ == "__main__":
#     run_pipeline()




import dlt
from app.hubspot_source import hubspot_source


def run_pipeline():
    pipeline = dlt.pipeline(
        pipeline_name="hubspot_ingestion",
        destination=dlt.destinations.filesystem(
            bucket_url="./data/parquet"
        ),
        dataset_name="hubspot_data",
        pipelines_dir="./data/dlt_pipelines",
    )

    load_info = pipeline.run(
        hubspot_source(),
        loader_file_format="parquet",
    )

    print("\nPipeline execution completed!")
    print(load_info)


if __name__ == "__main__":
    run_pipeline()
