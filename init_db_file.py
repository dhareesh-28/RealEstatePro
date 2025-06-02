from app import app  # Make sure this imports your Flask app instance correctly
from database import init_db

init_db(app)
