import pymysql
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, text
from sqlalchemy.orm import sessionmaker, declarative_base

# AIS to DB setup and functions
DATABASE_HOST = config.get("DATABASE", "DATABASE_HOST")
DATABASE_PORT = config.get("DATABASE", "DATABASE_PORT")
DATABASE_USER = config.get("DATABASE", "DATABASE_USER")
DATABASE_PASSWORD = config.get("DATABASE", "DATABASE_PASSWORD")
DATABASE_NAME = config.get("DATABASE", "DATABASE_NAME")

def getconn() -> pymysql.connections.Connection:
    conn: pymysql.connections.Connection = pymysql.connect(
        host=DATABASE_HOST,
        port=int(DATABASE_PORT),
        user=DATABASE_USER,
        password=DATABASE_PASSWORD,
        db=DATABASE_NAME
    )
    return conn

engine = create_engine(
    "mysql+pymysql://",
    creator=getconn,)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
db = SessionLocal()