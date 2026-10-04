from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import settings


class Base(DeclarativeBase):
    pass


engine_kwargs = {
    "pool_pre_ping": True,
}

if settings.database_url.startswith("sqlite"):

    # FastAPI serves requests on multiple threads;
    # SQLite requires check_same_thread=False for that.
    engine_kwargs["connect_args"] = {
        "check_same_thread": False
    }

# Give remote databases (e.g. Neon/PostgreSQL) a
# bounded connect timeout so startup cannot hang.
elif settings.database_url.startswith("postgresql"):

    engine_kwargs["pool_timeout"] = 10
    engine_kwargs["pool_recycle"] = 1800
    engine_kwargs["connect_args"] = {
        "connect_timeout": 10,
        "application_name": "onerecon-backend",
    }

engine = create_engine(
    settings.database_url,
    **engine_kwargs
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)