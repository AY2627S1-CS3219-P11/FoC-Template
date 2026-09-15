import csv
import os
from contextlib import asynccontextmanager
import psycopg2
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)

def seed_database_from_csv():
    csv_path = "./data/csv/supplier-seed-data.csv"
    if not os.path.exists(csv_path):
        print(f"Seed CSV not found at {csv_path}, skipping seeding")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM suppliers;")
        count = cursor.fetchone()[0]
        if count > 0:
            print("Database already contains supplier records, skipping seeding")
            return

        with open(csv_path, mode="r", encoding="cp1252") as f:
            reader = csv.DictReader(f)
            for row in reader:
                building = row.get("Building", "")
                floor = row.get("Floor", "")
                location_str = f"{building}, Floor {floor}" if floor else building
                start = row.get("StartingTime", "")
                close = row.get("ClosingTime", "")
                hours_str = f"{start} - {close}"

                cursor.execute(
                    """
                    INSERT INTO suppliers (name, category, description, operating_hours, location,
                                           latitude, longitude, image_url, is_active, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s);
                    """,
                    (
                        row.get("Name"),
                        row.get("Type"),
                        row.get("Location Description"),
                        hours_str,
                        location_str,
                        float(row.get("Latitude")) if row.get("Latitude") else None,
                        float(row.get("Longitude")) if row.get("Longitude") else None,
                        row.get("ImageURL"),
                        "admin"
                    )
                )
            conn.commit()
            print("Successfully seeded database from CSV file")
    except Exception as e:
        conn.rollback()
        print(f"Error during database seeding: {e}")
    finally:
        cursor.close()
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_database_from_csv()
    yield

app = FastAPI(title="Supplier Service", lifespan=lifespan)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "supplier-service"}

@app.get("/suppliers")
def get_active_suppliers():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT id, name, category, description, operating_hours, location, 
                   latitude, longitude, image_url 
            FROM suppliers 
            WHERE is_active = TRUE;
            """
        )
        rows = cursor.fetchall()
        suppliers = []
        for row in rows:
            suppliers.append({
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "description": row[3],
                "operating_hours": row[4],
                "location": row[5],
                "latitude": float(row[6]) if row[6] is not None else None,
                "longitude": float(row[7]) if row[7] is not None else None,
                "image_url": row[8]
            })
        return {"suppliers": suppliers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()