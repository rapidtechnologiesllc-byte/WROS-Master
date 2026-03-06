import uuid
from sqlalchemy.orm.strategy_options import _ClassStrategyLoad
import uuid

def candidate_id_generator() -> str:
    return f"CAN-{uuid.uuid4()}"

def user_id_generator() -> str:
    return f"USER-{uuid.uuid4()}"

def form_id_generator() -> str:
    return f"FORM-{uuid.uuid4()}"

def generate_password() -> str:
    return f"PASS-{uuid.uuid4()}"   

def job_id_generator() -> str:
    return f"JOB-{uuid.uuid1()}"

def panel_id_generator() -> str:
    return f"PANEL-{uuid.uuid1()}"

def newsletter_id_generator() -> str:
    return f"NEWS-{uuid.uuid1()}"
