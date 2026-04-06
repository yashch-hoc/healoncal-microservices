# Healoncal: PostgreSQL (Supabase) → MySQL Migration Analysis

## Overview

Your `Healoncal_databse.sql` is a **PostgreSQL** schema (used by Supabase). This document summarizes what must change to run the same logical schema on **MySQL 8.0+**.

---

## 1. Schema Summary (Current)

| # | Table | Purpose |
|---|--------|---------|
| 1 | `healoncal_analysis_sessions` | Skin analysis sessions (user, status, metadata) |
| 2 | `healoncal_captured_images` | Captured images per session (angle, quality, URLs) |
| 3 | `healoncal_analysis_results` | Per-image analysis (biomarkers, scores, JSON) |
| 4 | `healoncal_combined_results` | Aggregated session results |
| 5 | `treatment_recommendations` | AI recommendations (Gemini 2.5 Flash) |
| 6 | `detected_skin_diseases` | Detected diseases per session/result |
| 7 | `disease_heatmaps` | Heatmap visualization data |

**Views:** `comprehensive_treatment_view`, `user_analysis_summary`, `disease_analytics_view`

---

## 2. PostgreSQL → MySQL Mapping

| PostgreSQL (Supabase) | MySQL 8.0 | Notes |
|----------------------|-----------|--------|
| `UUID` type | `CHAR(36)` | Store UUIDs as string; use `UUID()` for defaults |
| `uuid_generate_v4()` | `(UUID())` | Or application-generated UUIDs |
| `TIMESTAMPTZ` | `DATETIME(6)` or `TIMESTAMP(6)` | Prefer `DATETIME(6)` for clarity; MySQL stores in server TZ |
| `JSONB` | `JSON` | MySQL JSON is binary; query with `JSON_*` functions |
| `CREATE EXTENSION "uuid-ossp"` | *(remove)* | Not applicable |
| `NOW()` | `CURRENT_TIMESTAMP(6)` or `NOW(6)` | Same idea |
| `INTERVAL '6 months'` | `DATE_ADD(NOW(), INTERVAL 6 MONTH)` | In default expression |
| `public.` schema | *(omit or use DB name)* | MySQL “schema” = database |
| `DROP VIEW ... CASCADE` | `DROP VIEW IF EXISTS` | No CASCADE needed for views |
| `CHECK (col IN (...))` | `CHECK (col IN (...))` | Supported in MySQL 8.0.16+ |
| `json_agg(...) FILTER (WHERE ...)` | `JSON_ARRAYAGG(CASE WHEN ... THEN JSON_OBJECT(...) END)` | FILTER not in MySQL; CASE + JSON_ARRAYAGG (NULLs omitted) |
| `json_build_object(...)` | `JSON_OBJECT(...)` | Direct equivalent |
| `DATE_TRUNC('month', x)` | `DATE_FORMAT(x, '%Y-%m-01')` | Or `LAST_DAY(x) - INTERVAL (DAY(LAST_DAY(x))-1) DAY` |
| `COMMENT ON TABLE t IS '...'` | `COMMENT '...'` in `CREATE TABLE` | Or `ALTER TABLE t COMMENT '...'` |

---

## 3. Dependency Order (for CREATE/DROP)

**Drop order (views first, then tables):**

1. Views: `comprehensive_treatment_view`, `user_analysis_summary`, `disease_analytics_view`
2. `disease_heatmaps`
3. `detected_skin_diseases`
4. `treatment_recommendations`
5. `healoncal_combined_results`
6. `healoncal_analysis_results`
7. `healoncal_captured_images`
8. `healoncal_analysis_sessions`

**Create order:** Reverse of above (sessions first, then images, results, combined, treatment, diseases, heatmaps, then views).

---

## 4. Application Code Impact

- **Supabase client:** Replace with a **MySQL** client (e.g. `mysql-connector-python`, `PyMySQL`, or async like `aiomysql`). All Supabase-specific code (RLS, Realtime, Storage API) must be replaced or removed.
- **Queries:** If you use raw SQL, change:
  - `RETURNING *` → use `LAST_INSERT_ID()` / second query or MySQL’s limited `RETURNING` (8.0.21+).
  - JSON: `->`, `->>` → `JSON_EXTRACT()`, `JSON_UNQUOTE(JSON_EXTRACT())` or `->`, `->>` in MySQL 5.7+.
- **UUIDs:** Keep storing as string (e.g. `CHAR(36)`); app can keep generating UUIDs or use `UUID()` in MySQL.
- **Connection/config:** Point to MySQL host, port, database, user, password; remove Supabase URL/keys.

---

## 5. What Stays the Same (Conceptually)

- Table names and column names (no need to change).
- Foreign key relationships and cascade behavior.
- Indexes (same columns; syntax slightly different).
- CHECK constraints (MySQL 8.0.16+).
- View logic (same joins and aggregates; only SQL dialect changed as above).

---

## 6. Image Storage (AWS S3)

Images are stored in **AWS S3**, not in the database or Supabase Storage. The `healoncal_captured_images` table only stores references:

- **storage_bucket** – S3 bucket name (e.g. your bucket for skin scans)
- **storage_path** – S3 object key (path within the bucket)
- **image_url** / **cdn_url** – Full URL (e.g. S3 or CloudFront) for display/download

No schema change is required for S3; these columns are storage-agnostic.

---

## 7. Files to Add/Change

| Action | File / area |
|--------|-------------|
| **Use** | `Healoncal_database_mysql.sql` (MySQL schema created from your current file) |
| **Update** | Config: replace Supabase URL/keys with MySQL host, database, user, password |
| **Replace** | `app/services/supabase_client_service.py` (or equivalent) with a MySQL connection/service |
| **Update** | Any code that inserts/updates/selects (Supabase client → MySQL client; adjust JSON/returning if needed) |

---

## 8. Environment Variables (Docker MySQL on AWS EC2)

MySQL runs in **Docker on an EC2 instance**. Set these in `.env` or GCP Secret Manager:

```env
MYSQL_HOST=<ec2-public-or-private-ip-or-dns>
MYSQL_PORT=3306
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=your_database_name
```

**Connectivity:**  
- Expose port **3306** from the MySQL container (e.g. `docker run -p 3306:3306 ...` or in `docker-compose`).  
- On EC2: open **port 3306** in the security group for the app’s source (e.g. Cloud Run IP range or your app server).  
- If the app runs on the same EC2, use `127.0.0.1` or the EC2 private IP; if the app runs on GCP, use the EC2 **public IP** (or VPN/peering) and ensure MySQL is bound to `0.0.0.0` inside the container.

---

## 9. Recommended Next Steps

1. Create a MySQL 8.0 database and run `Healoncal_database_mysql.sql`.
2. Switch config to MySQL and implement a small MySQL service (connection pool, execute query, return rows).
3. Migrate `treatment_storage_service` and any other code that talks to Supabase to use the MySQL service (same table/column names, so mostly client API changes).
4. Run tests and, if needed, migrate existing data from Supabase (export CSV/JSON from Postgres, load into MySQL with same column names).

This analysis and the generated `Healoncal_database_mysql.sql` give you a complete, runnable MySQL schema that mirrors your current PostgreSQL design.
