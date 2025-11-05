"""
Generic dataset exporter interface.

Provides abstract base class for exporting training datasets from any data source.
OSS users can implement this interface to export data from their own databases,
files, APIs, or other sources.

Example implementations:
- PostgreSQL database exporter
- JSONL file exporter
- API-based exporter
- Label Studio exporter
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import json


@dataclass
class TrainingExample:
    """
    Single training example in a generic format.
    
    This represents one input/output pair for fine-tuning.
    """
    
    # Unique identifier
    example_id: str
    
    # Input/output in ChatML format
    messages: list[dict[str, str]]  # [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    
    # Metadata
    source: str  # Where this example came from (e.g., "database", "label_studio", "manual")
    quality_score: Optional[float] = None  # 0-1 quality rating (if available)
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def to_chatml(self) -> dict[str, Any]:
        """Convert to ChatML format (OpenAI/vLLM standard)."""
        return {"messages": self.messages}
    
    def to_alpaca(self) -> dict[str, Any]:
        """
        Convert to Alpaca format.
        
        Extracts instruction from user message and response from assistant message.
        """
        instruction = ""
        response = ""
        
        for msg in self.messages:
            if msg["role"] == "user":
                instruction = msg["content"]
            elif msg["role"] == "assistant":
                response = msg["content"]
        
        return {
            "instruction": instruction,
            "input": "",
            "output": response
        }
    
    def to_openai(self) -> dict[str, Any]:
        """Convert to OpenAI format (same as ChatML)."""
        return {"messages": self.messages}


class DatasetExporter(ABC):
    """
    Abstract base class for dataset exporters.
    
    Implement this to export training data from your data source.
    
    Example:
        class MyDatabaseExporter(DatasetExporter):
            def fetch_examples(self, user_id, filters=None, limit=None):
                # Connect to your database
                # Fetch high-quality examples
                # Convert to TrainingExample format
                return examples
    """
    
    @abstractmethod
    def fetch_examples(
        self,
        user_id: str,
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> list[TrainingExample]:
        """
        Fetch training examples from your data source.
        
        Args:
            user_id: User identifier (email, ID, etc.)
            filters: Optional filters to apply
                Examples:
                - {"dataset_type": "classification"}
                - {"quality_threshold": 0.8}
                - {"date_range": {"start": "2024-01-01", "end": "2024-12-31"}}
            limit: Optional limit on number of examples
            
        Returns:
            List of TrainingExample objects
            
        Raises:
            ValueError: If no examples found or invalid filters
            ConnectionError: If data source is unavailable
        """
        pass
    
    def export_dataset(
        self,
        user_id: str,
        output_dir: Path,
        format: str = "chatml",
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> tuple[Path, int]:
        """
        Export dataset to file.
        
        This is a convenience method that:
        1. Fetches examples using fetch_examples()
        2. Converts to specified format
        3. Writes to JSONL file
        
        Args:
            user_id: User identifier
            output_dir: Output directory
            format: Dataset format ("chatml", "alpaca", "openai")
            filters: Optional filters
            limit: Optional limit on examples
            
        Returns:
            Tuple of (dataset_path, sample_count)
            
        Raises:
            ValueError: If no examples found
        """
        # Fetch examples
        examples = self.fetch_examples(user_id, filters, limit)
        
        if not examples:
            raise ValueError("No examples found to export")
        
        # Create output file
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"dataset_{user_id}_{format}.jsonl"
        
        # Write examples
        with open(output_file, 'w') as f:
            for example in examples:
                if format == "chatml":
                    data = example.to_chatml()
                elif format == "alpaca":
                    data = example.to_alpaca()
                elif format == "openai":
                    data = example.to_openai()
                else:
                    data = example.to_chatml()  # Default to ChatML
                
                f.write(json.dumps(data) + '\n')
        
        return output_file, len(examples)


class FileDatasetExporter(DatasetExporter):
    """
    Example implementation: Export from JSONL files.
    
    This is a simple reference implementation that reads from JSONL files.
    """
    
    def __init__(self, data_dir: Path):
        """
        Initialize file-based exporter.
        
        Args:
            data_dir: Directory containing JSONL files
        """
        self.data_dir = data_dir
    
    def fetch_examples(
        self,
        user_id: str,
        filters: Optional[dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> list[TrainingExample]:
        """
        Fetch examples from JSONL files.
        
        Looks for files matching pattern: {data_dir}/{user_id}_*.jsonl
        """
        examples = []
        
        # Find user's JSONL files
        pattern = f"{user_id}_*.jsonl"
        files = list(self.data_dir.glob(pattern))
        
        if not files:
            raise ValueError(f"No JSONL files found for user {user_id}")
        
        # Read examples from files
        for file_path in files:
            with open(file_path) as f:
                for line_num, line in enumerate(f):
                    if limit and len(examples) >= limit:
                        break
                    
                    try:
                        data = json.loads(line)
                        
                        # Apply filters if provided
                        if filters:
                            # Example: filter by quality score
                            if "quality_threshold" in filters:
                                quality = data.get("quality_score", 0)
                                if quality < filters["quality_threshold"]:
                                    continue
                            
                            # Example: filter by dataset type
                            if "dataset_type" in filters:
                                if data.get("dataset_type") != filters["dataset_type"]:
                                    continue
                        
                        # Convert to TrainingExample
                        example = TrainingExample(
                            example_id=data.get("id", f"{file_path.stem}_{line_num}"),
                            messages=data.get("messages", []),
                            source=str(file_path),
                            quality_score=data.get("quality_score"),
                            metadata=data.get("metadata", {})
                        )
                        
                        examples.append(example)
                    
                    except json.JSONDecodeError:
                        continue  # Skip invalid lines
        
        return examples


# Example usage:
"""
# 1. Implement your own exporter
class MyDatabaseExporter(DatasetExporter):
    def __init__(self, db_url):
        self.db_url = db_url
    
    def fetch_examples(self, user_id, filters=None, limit=None):
        # Connect to database
        # Fetch high-quality examples
        # Convert to TrainingExample format
        return examples

# 2. Use the exporter
exporter = MyDatabaseExporter("postgresql://...")
dataset_path, count = exporter.export_dataset(
    user_id="user@example.com",
    output_dir=Path("./datasets"),
    format="chatml",
    filters={"quality_threshold": 0.8},
    limit=1000
)

print(f"Exported {count} examples to {dataset_path}")
"""

