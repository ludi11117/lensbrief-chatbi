from alembic import context

from backend.app.db import sqlite_engine
from backend.app.models import metadata
from backend.app.settings import Settings

def run():
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = sqlite_engine(Settings.from_env().database)
    with engine.connect() as owned:
        context.configure(connection=owned, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()

if context.is_offline_mode():
    context.configure(url="sqlite://", target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    run()
