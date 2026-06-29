import datetime
from sqlalchemy import Column, Integer, String, DateTime, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Rewrite postgres:// or postgresql:// to postgresql+asyncpg:// for SQLAlchemy async driver
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

class PublishedArticle(Base):
    __tablename__ = "published_articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    published_at = Column(String, nullable=True) # Stored as raw string or timestamp
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def is_article_published(url: str) -> bool:
    normalized_url = url[:-1] if url.endswith("/") else url
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(PublishedArticle).where(
                (PublishedArticle.url == normalized_url) |
                (PublishedArticle.url == normalized_url + "/")
            )
        )
        return result.scalar_one_or_none() is not None

async def mark_article_published(url: str, title: str = None, published_at: str = None):
    async with AsyncSessionLocal() as session:
        article = PublishedArticle(url=url, title=title, published_at=published_at)
        session.add(article)
        await session.commit()
