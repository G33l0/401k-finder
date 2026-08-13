import csv
import logging
from app.database import get_connection

logger = logging.getLogger(__name__)

def parse_schedule_c(filepath, plan_id_mapping, conn=None):
    """
    Parse Schedule C CSV and insert service providers.
    Args:
        filepath: path to CSV file
        plan_id_mapping: dict mapping (ein, plan_number) -> plan.id
        conn: optional existing database connection (if None, opens its own)
    """
    owns_conn = False
    if conn is None:
        conn = get_connection()
        owns_conn = True
    cursor = conn.cursor()
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ein = row.get('SPONSOR_DFE_EIN') or row.get('SPONSOR_EIN') or row.get('EIN')
                plan_number = row.get('PLAN_NUMBER') or row.get('PLAN_NUM')
                provider_name = row.get('SERVICE_PROVIDER_NAME') or row.get('PROVIDER_NAME')
                provider_ein = row.get('SERVICE_PROVIDER_EIN') or row.get('PROV_EIN')
                service_codes = row.get('SERVICE_CODES') or row.get('SRVC_CODE')
                compensation = row.get('COMPENSATION') or 0
                if not (ein and plan_number and provider_name):
                    continue
                plan_id = plan_id_mapping.get((ein, plan_number))
                if plan_id:
                    classification = classify_provider(provider_name, service_codes)
                    cursor.execute(
                        "INSERT INTO service_providers (plan_id, provider_name, provider_ein, service_codes, compensation, classification) VALUES (?,?,?,?,?,?)",
                        (plan_id, provider_name, provider_ein, service_codes, compensation, classification)
                    )
    except Exception as e:
        logger.error(f"Schedule C parse error: {e}")
        raise
    finally:
        if owns_conn:
            conn.close()

def classify_provider(name, service_codes):
    """Classify provider based on name and service codes (simple heuristic)."""
    # Reuse the classification from classification.py if possible
    from app.classification import classify_provider as cp
    return cp(name, service_codes)