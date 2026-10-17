# HubSpot Data Ingestion

## Kaise start karein

**Zaroorat:** Docker Desktop installed aur running hona chahiye.

1. Project folder mein `.env.example` ki copy banakar uska naam `.env` rakhein.
2. `.env` file mein `API_KEY`, `HMAC_SECRET`, aur `POSTGRES_PASSWORD` ke sample values ko apne values se badlein.
3. Project folder ke terminal mein ye command chalayein:

   ```sh
   docker compose --profile mock up --build
   ```

4. Service check karne ke liye browser mein `http://localhost:8080/health` kholein. API docs `http://localhost:8080/docs` par milenge.
5. Band karne ke liye terminal mein `Ctrl+C` dabayein, phir chalayein:

   ```sh
   docker compose --profile mock down
   ```

## Is project mein kya hota hai

- API ek ingestion job shuru karti hai.
- Job HubSpot se contacts, companies, deals aur doosra CRM data laati hai. Local start mein sample data dene ke liye mock HubSpot chalta hai.
- Har resource ka data Parquet files mein save hota hai. Job ki progress PostgreSQL mein save hoti hai, taaki service restart hone par kaam continue kiya ja sake.
- API se job ka status dekha, pause, resume, ya cancel kiya ja sakta hai.