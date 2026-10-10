
import requests
import dlt

BASE_URL = "http://127.0.0.1:8000"


def fetch_resource(resource_name):
    after = None

    while True:
        params = {"limit": 100}
        if after:
            params["after"] = after

        response = requests.get(
            f"{BASE_URL}/{resource_name}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        for record in payload["results"]:
            yield record

        next_page = payload.get("paging", {}).get("next")
        if not next_page:
            break

        after = next_page["after"]


@dlt.source(name="hubspot")
def hubspot_source():
    @dlt.resource(name="contacts", write_disposition="append")
    def contacts():
        yield from fetch_resource("contacts")

    @dlt.resource(name="companies", write_disposition="append")
    def companies():
        yield from fetch_resource("companies")

    @dlt.resource(name="deals", write_disposition="append")
    def deals():
        yield from fetch_resource("deals")

    @dlt.resource(name="tickets", write_disposition="append")
    def tickets():
        yield from fetch_resource("tickets")

    @dlt.resource(name="line_items", write_disposition="append")
    def line_items():
        yield from fetch_resource("line_items")

    @dlt.resource(name="engagements", write_disposition="append")
    def engagements():
        yield from fetch_resource("engagements")

    @dlt.resource(name="pipelines", write_disposition="append")
    def pipelines():
        yield from fetch_resource("pipelines")

    @dlt.resource(name="owners", write_disposition="append")
    def owners():
        yield from fetch_resource("owners")

    return (
        contacts,
        companies,
        deals,
        tickets,
        line_items,
        engagements,
        pipelines,
        owners,
    )
