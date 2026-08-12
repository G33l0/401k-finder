import csv
from app.models import insert_service_provider
from app.classification import classify_provider
import logging

logger = logging.getLogger(__name__)

def parse_schedule_c(filepath, plan_id_mapping):
    """
    Parse a Schedule C CSV file and store providers.
    Args:
        filepath: path to CSV file
        plan_id_mapping: dict mapping (ein, plan_number) -> plan.id
    """
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Expected columns may vary; use flexible mapping
                ein = row.get('SPONSOR_EIN') or row.get('EIN')
                plan_number = row.get('PLAN_NUMBER') or row.get('PLAN_NUM')
                provider_name = row.get('SERVICE_PROVIDER_NAME') or row.get('PROVIDER_NAME')
                provider_ein = row.get('SERVICE_PROVIDER_EIN') or row.get('PROV_EIN')
                service_codes = row.get('SERVICE_CODES') or row.get('SRVC_CODE')
                compensation = row.get('COMPENSATION') or 0
                if ein and plan_number and provider_name:
                    plan_id = plan_id_mapping.get((ein, plan_number))
                    if plan_id:
                        classification = classify_provider(provider_name, service_codes, row)
                        insert_service_provider(plan_id, provider_name, provider_ein, service_codes, compensation, classification)
    except Exception as e:
        logger.error(f"Error parsing Schedule C: {e}")
        raise