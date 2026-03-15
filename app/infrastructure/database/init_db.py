from sqlalchemy import inspect

from app.config import Settings, get_settings
from app.infrastructure.database.base import Base
from app.infrastructure.database.session import create_engine_from_settings
from app.infrastructure.database import models  # noqa: F401


def init_database(settings: Settings | None = None) -> list[str]:
    active_settings = settings or get_settings()
    engine = create_engine_from_settings(active_settings)
    Base.metadata.create_all(bind=engine)
    return inspect(engine).get_table_names()
