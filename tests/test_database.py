from app.db.session import create_db_engine


def test_sqlalchemy_engine_supports_sqlite_urls() -> None:
    engine = create_db_engine("sqlite:///:memory:")
    assert engine.url.get_backend_name() == "sqlite"
