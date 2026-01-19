import uuid

def candidate_id_generator() -> str:
    return f"CAN-{uuid.uuid4()}"

def user_id_generator() -> str:
    return f"USER-{uuid.uuid4()}"

def form_id_generator() -> str:
    return f"FORM-{uuid.uuid4()}"

def generate_password() -> str:
    return f"PASS-{uuid.uuid4()}"   