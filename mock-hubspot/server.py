
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(
    title="Mock HubSpot API",
    description="Local mock CRM API for the HubSpot ingestion project",
    version="1.0.0",
)

# Sample CRM data
CONTACTS = [
    {
        "id": "101",
        "firstname": "Rohit",
        "lastname": "Yadav",
        "email": "rohit@example.com",
        "company": "Tech Solutions",
        "updated_at": "2026-10-09T10:00:00Z",
    },
    {
        "id": "102",
        "firstname": "Aman",
        "lastname": "Sharma",
        "email": "aman@example.com",
        "company": "Data Systems",
        "updated_at": "2026-10-09T11:00:00Z",
    },
    {
        "id": "103",
        "firstname": "Priya",
        "lastname": "Verma",
        "email": "priya@example.com",
        "company": "Tech Solutions",
        "updated_at": "2026-10-09T12:00:00Z",
    },
]

COMPANIES = [
    {
        "id": "201",
        "name": "Tech Solutions",
        "domain": "techsolutions.example",
        "updated_at": "2026-10-09T10:00:00Z",
    },
    {
        "id": "202",
        "name": "Data Systems",
        "domain": "datasystems.example",
        "updated_at": "2026-10-09T11:00:00Z",
    },
]

DEALS = [
    {
        "id": "301",
        "dealname": "Website Development",
        "amount": 500000,
        "company_id": "201",
        "pipeline_id": "401",
        "updated_at": "2026-10-09T10:00:00Z",
    },
    {
        "id": "302",
        "dealname": "Data Platform",
        "amount": 800000,
        "company_id": "202",
        "pipeline_id": "401",
        "updated_at": "2026-10-09T11:00:00Z",
    },
]

TICKETS = [
    {
        "id": "501",
        "subject": "Login issue",
        "status": "open",
        "updated_at": "2026-10-09T10:00:00Z",
    },
    {
        "id": "502",
        "subject": "Payment question",
        "status": "closed",
        "updated_at": "2026-10-09T11:00:00Z",
    },
]

PIPELINES = [
    {
        "id": "401",
        "label": "Sales Pipeline",
        "updated_at": "2026-10-09T10:00:00Z",
    }
]

OWNERS = [
    {
        "id": "601",
        "email": "sales@example.com",
        "firstName": "Sales",
        "lastName": "Manager",
        "updated_at": "2026-10-09T10:00:00Z",
    }
]

LINE_ITEMS = [
    {
        "id": "701",
        "name": "Website Package",
        "quantity": 1,
        "price": 500000,
        "deal_id": "301",
        "updated_at": "2026-10-09T10:00:00Z",
    }
]

ENGAGEMENTS = [
    {
        "id": "801",
        "type": "CALL",
        "subject": "Initial sales call",
        "deal_id": "301",
        "updated_at": "2026-10-09T10:00:00Z",
    }
]


@app.get("/")
def root():
    return {
        "message": "Mock HubSpot API is running",
        "resources": [
            "contacts",
            "companies",
            "deals",
            "tickets",
            "line_items",
            "engagements",
            "pipelines",
            "owners",
        ],
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def paginate(records, limit: int, after: str | None):
    """Return records with simple ID-based pagination."""
    start = 0

    if after is not None:
        positions = {
            str(record["id"]): index
            for index, record in enumerate(records)
        }

        if after not in positions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid pagination cursor: {after}",
            )

        start = positions[after] + 1

    page = records[start : start + limit]
    next_after = str(page[-1]["id"]) if page else None

    has_more = start + limit < len(records)

    return {
        "results": page,
        "paging": {
            "next": {"after": next_after} if has_more else None
        },
        "total": len(records),
    }


def create_list_endpoint(records):
    def endpoint(
        limit: int = Query(default=2, ge=1, le=100),
        after: str | None = Query(default=None),
    ):
        return paginate(records, limit, after)

    return endpoint


# Register all CRM resource endpoints.
for resource_name, records in [
    ("contacts", CONTACTS),
    ("companies", COMPANIES),
    ("deals", DEALS),
    ("tickets", TICKETS),
    ("line_items", LINE_ITEMS),
    ("engagements", ENGAGEMENTS),
    ("pipelines", PIPELINES),
    ("owners", OWNERS),
]:
    app.add_api_route(
        f"/{resource_name}",
        create_list_endpoint(records),
        methods=["GET"],
        name=f"list_{resource_name}",
    )
