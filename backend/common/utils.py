from pathlib import Path
from uuid import uuid4


def generate_id():

    return str(uuid4())


def safe_filename(filename: str):

    filename = Path(filename).name

    return f"{uuid4().hex}_{filename}"