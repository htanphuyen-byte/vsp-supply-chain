import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'vietsovpetro-supplychain-secure-key-2026'
    DATABASE = os.path.join(BASE_DIR, 'vsp_supply_chain.db')
    DEBUG = True
