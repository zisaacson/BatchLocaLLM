"""
Benchmark storage and retrieval system

Stores benchmark results for different models, configurations, and context sizes
to help users make informed decisions about model selection and expected timing.
"""

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import Column, Float, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import settings
from src.logger import logger

Base = declarative_base()


class BenchmarkResultDB(Base):  # type: ignore[valid-type,misc]
    """Database model for benchmark results"""

    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Model info
    model_name = Column(String, nullable=False, index=True)
    model_size_params = Column(String, nullable=True)  # e.g., "1b", "4b", "12b"
    model_size_bytes = Column(Integer, nullable=True)  # Model file size in bytes

    # Configuration
    num_workers = Column(Integer, nullable=False)
    context_window = Column(Integer, nullable=True)  # Max context size used

    # Test parameters
    num_requests = Column(Integer, nullable=False)
    avg_prompt_tokens = Column(Integer, nullable=True)
    avg_completion_tokens = Column(Integer, nullable=True)

    # Performance metrics
    total_time_seconds = Column(Float, nullable=False)
    requests_per_second = Column(Float, nullable=False)
    time_per_request_seconds = Column(Float, nullable=False)

    # Success metrics
    successful_requests = Column(Integer, nullable=False)
    failed_requests = Column(Integer, nullable=False)
    success_rate = Column(Float, nullable=False)

    # Quality samples (JSON)
    sample_responses = Column(Text, nullable=True)  # JSON array of sample responses

    # Metadata
    created_at = Column(Integer, nullable=False)
    benchmark_type = Column(String, nullable=False, default="model_comparison")  # model_comparison, worker_optimization, scale_test
    notes = Column(Text, nullable=True)
    hardware_info = Column(Text, nullable=True)  # JSON with GPU, RAM, etc.


@dataclass
class BenchmarkResult:
    """Benchmark result data class"""

    # Model info
    model_name: str
    model_size_params: str | None = None
    model_size_bytes: int | None = None

    # Configuration
    num_workers: int = 4
    context_window: int | None = None

    # Test parameters
    num_requests: int = 100
    avg_prompt_tokens: int | None = None
    avg_completion_tokens: int | None = None

    # Performance metrics
    total_time_seconds: float = 0.0
    requests_per_second: float = 0.0
    time_per_request_seconds: float = 0.0

    # Success metrics
    successful_requests: int = 0
    failed_requests: int = 0
    success_rate: float = 0.0

    # Quality samples
    sample_responses: list[str] | None = None

    # Metadata
    created_at: int | None = None
    benchmark_type: str = "model_comparison"
    notes: str | None = None
    hardware_info: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = int(time.time())

        # Calculate derived metrics
        if self.total_time_seconds > 0 and self.num_requests > 0:
            self.requests_per_second = self.num_requests / self.total_time_seconds
            self.time_per_request_seconds = self.total_time_seconds / self.num_requests

        if self.num_requests > 0:
            self.success_rate = (self.successful_requests / self.num_requests) * 100


class BenchmarkStorage:
    """Manages storage and retrieval of benchmark results"""

    def __init__(self, database_path: str | None = None):
        if database_path is None:
            database_path = settings.database_path

        db_url = f"sqlite+aiosqlite:///{database_path}"
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = sessionmaker(  # type: ignore[call-overload]
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

        logger.info("Benchmark storage initialized", extra={"database_path": database_path})

    async def init_db(self) -> None:
        """Initialize database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Benchmark tables created")

    async def save_benchmark(self, result: BenchmarkResult) -> int:
        """Save a benchmark result to the database"""
        async with self.async_session() as session:
            db_result = BenchmarkResultDB(
                model_name=result.model_name,
                model_size_params=result.model_size_params,
                model_size_bytes=result.model_size_bytes,
                num_workers=result.num_workers,
                context_window=result.context_window,
                num_requests=result.num_requests,
                avg_prompt_tokens=result.avg_prompt_tokens,
                avg_completion_tokens=result.avg_completion_tokens,
                total_time_seconds=result.total_time_seconds,
                requests_per_second=result.requests_per_second,
                time_per_request_seconds=result.time_per_request_seconds,
                successful_requests=result.successful_requests,
                failed_requests=result.failed_requests,
                success_rate=result.success_rate,
                sample_responses=json.dumps(result.sample_responses) if result.sample_responses else None,
                created_at=result.created_at,
                benchmark_type=result.benchmark_type,
                notes=result.notes,
                hardware_info=json.dumps(result.hardware_info) if result.hardware_info else None,
            )

            session.add(db_result)
            await session.commit()
            await session.refresh(db_result)

            logger.info(
                "Benchmark result saved",
                extra={
                    "id": db_result.id,
                    "model": result.model_name,
                    "requests": result.num_requests,
                    "rate": f"{result.requests_per_second:.2f} req/s",
                }
            )

            return db_result.id  # type: ignore[return-value]

    async def get_benchmarks_for_model(
        self,
        model_name: str,
        benchmark_type: str | None = None,
        limit: int = 10
    ) -> list[BenchmarkResult]:
        """Get benchmark results for a specific model"""
        async with self.async_session() as session:
            query = select(BenchmarkResultDB).where(
                BenchmarkResultDB.model_name == model_name
            )

            if benchmark_type:
                query = query.where(BenchmarkResultDB.benchmark_type == benchmark_type)

            query = query.order_by(BenchmarkResultDB.created_at.desc()).limit(limit)

            result = await session.execute(query)
            db_results = result.scalars().all()

            return [self._db_to_dataclass(db_result) for db_result in db_results]

    async def get_all_models(self) -> list[str]:
        """Get list of all models that have been benchmarked"""
        async with self.async_session() as session:
            query = select(BenchmarkResultDB.model_name).distinct()
            result = await session.execute(query)
            return [row[0] for row in result.all()]

    async def get_model_comparison(
        self,
        num_requests: int | None = None,
        benchmark_type: str = "model_comparison"
    ) -> list[BenchmarkResult]:
        """Get benchmark results for model comparison"""
        async with self.async_session() as session:
            query = select(BenchmarkResultDB).where(
                BenchmarkResultDB.benchmark_type == benchmark_type
            )

            if num_requests:
                query = query.where(BenchmarkResultDB.num_requests == num_requests)

            query = query.order_by(
                BenchmarkResultDB.model_name,
                BenchmarkResultDB.created_at.desc()
            )

            result = await session.execute(query)
            db_results = result.scalars().all()

            # Get most recent result for each model
            seen_models = set()
            unique_results = []
            for db_result in db_results:
                if db_result.model_name not in seen_models:
                    seen_models.add(db_result.model_name)
                    unique_results.append(self._db_to_dataclass(db_result))

            return unique_results

    def _db_to_dataclass(self, db_result: BenchmarkResultDB) -> BenchmarkResult:
        """Convert database model to dataclass"""
        return BenchmarkResult(
            model_name=db_result.model_name,  # type: ignore[arg-type]
            model_size_params=db_result.model_size_params,  # type: ignore[arg-type]
            model_size_bytes=db_result.model_size_bytes,  # type: ignore[arg-type]
            num_workers=db_result.num_workers,  # type: ignore[arg-type]
            context_window=db_result.context_window,  # type: ignore[arg-type]
            num_requests=db_result.num_requests,  # type: ignore[arg-type]
            avg_prompt_tokens=db_result.avg_prompt_tokens,  # type: ignore[arg-type]
            avg_completion_tokens=db_result.avg_completion_tokens,  # type: ignore[arg-type]
            total_time_seconds=db_result.total_time_seconds,  # type: ignore[arg-type]
            requests_per_second=db_result.requests_per_second,  # type: ignore[arg-type]
            time_per_request_seconds=db_result.time_per_request_seconds,  # type: ignore[arg-type]
            successful_requests=db_result.successful_requests,  # type: ignore[arg-type]
            failed_requests=db_result.failed_requests,  # type: ignore[arg-type]
            success_rate=db_result.success_rate,  # type: ignore[arg-type]
            sample_responses=json.loads(db_result.sample_responses) if db_result.sample_responses else None,  # type: ignore[arg-type]
            created_at=db_result.created_at,  # type: ignore[arg-type]
            benchmark_type=db_result.benchmark_type,  # type: ignore[arg-type]
            notes=db_result.notes,  # type: ignore[arg-type]
            hardware_info=json.loads(db_result.hardware_info) if db_result.hardware_info else None,  # type: ignore[arg-type]
        )

    async def export_benchmarks_json(self, output_path: str) -> None:
        """Export all benchmarks to JSON file"""
        async with self.async_session() as session:
            query = select(BenchmarkResultDB).order_by(BenchmarkResultDB.created_at.desc())
            result = await session.execute(query)
            db_results = result.scalars().all()

            benchmarks = [asdict(self._db_to_dataclass(db_result)) for db_result in db_results]

            with open(output_path, 'w') as f:
                json.dump(benchmarks, f, indent=2)

            logger.info(f"Exported {len(benchmarks)} benchmarks to {output_path}")

