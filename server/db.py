from sqlmodel import create_engine, SQLModel, Session

DATABASE_URL = "sqlite:///./server.db"
engine = create_engine(DATABASE_URL, echo=False)


def get_session() -> Session:
    return Session(engine)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
