"""
Dataset exporter for fine-tuning.

Exports gold star conquests from Aristotle database to training format:
- Unsloth: ChatML JSONL format
- Axolotl: Alpaca/ShareGPT format
- OpenAI: OpenAI fine-tuning format
- HuggingFace: Standard dataset format
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


@dataclass
class GoldStarConquest:
    """Gold star conquest data."""
    
    conquest_id: str
    conquest_type: str
    title: str
    prompt: str
    response: str
    rating: int
    feedback: str | None
    philosopher: str
    domain: str
    created_at: datetime
    
    def to_chatml(self) -> dict[str, Any]:
        """Convert to ChatML format for Unsloth."""
        messages = [
            {
                "role": "system",
                "content": f"You are an expert {self.conquest_type.lower()} analyst."
            },
            {
                "role": "user",
                "content": self.prompt
            },
            {
                "role": "assistant",
                "content": self.response
            }
        ]
        
        return {"messages": messages}
    
    def to_alpaca(self) -> dict[str, Any]:
        """Convert to Alpaca format for Axolotl."""
        return {
            "instruction": self.prompt,
            "output": self.response,
            "input": ""
        }
    
    def to_openai(self) -> dict[str, Any]:
        """Convert to OpenAI fine-tuning format."""
        return {
            "messages": [
                {"role": "system", "content": f"You are an expert {self.conquest_type.lower()} analyst."},
                {"role": "user", "content": self.prompt},
                {"role": "assistant", "content": self.response}
            ]
        }


class DatasetExporter:
    """
    Export gold star conquests to training datasets.
    
    Connects to Aristotle database and exports gold star conquests
    in various formats for different training backends.
    """
    
    def __init__(
        self,
        db_host: str = "localhost",
        db_port: int = 4001,
        db_name: str = "aris_dev",
        db_user: str = "postgres",
        db_password: str = "postgres"
    ):
        """Initialize exporter with database connection."""
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
    
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=self.db_user,
            password=self.db_password
        )
    
    def fetch_gold_star_conquests(
        self,
        philosopher: str,
        domain: str,
        conquest_type: str | None = None,
        limit: int | None = None
    ) -> list[GoldStarConquest]:
        """
        Fetch gold star conquests from database.
        
        Args:
            philosopher: User email
            domain: Organization domain
            conquest_type: Optional filter by conquest type
            limit: Optional limit on number of results
        
        Returns:
            List of gold star conquests
        """
        query = """
        SELECT 
            ca.id as conquest_id,
            ca.conquest_type,
            ca.title,
            cp.data->>'prompt' as prompt,
            cr.data->>'response' as response,
            r.rating,
            r.feedback,
            r.philosopher,
            r.domain,
            r.created_at
        FROM ml_analysis_rating r
        JOIN conquest_analysis ca ON r.conquest_analysis_id = ca.id
        LEFT JOIN conquest_prompt cp ON ca.id = cp.conquest_analysis_id
        LEFT JOIN conquest_response cr ON ca.id = cr.conquest_analysis_id
        WHERE r.is_gold_star = true
          AND r.use_as_sample_response = true
          AND r.philosopher = %s
          AND r.domain = %s
          AND r.analysis_type = 'conquest_analysis'
        """
        
        params: list[Any] = [philosopher, domain]
        
        if conquest_type:
            query += " AND ca.conquest_type = %s"
            params.append(conquest_type)
        
        query += " ORDER BY r.created_at DESC"
        
        if limit:
            query += " LIMIT %s"
            params.append(limit)
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
        
        conquests = []
        for row in rows:
            # Skip if missing prompt or response
            if not row['prompt'] or not row['response']:
                logger.warning(f"Skipping conquest {row['conquest_id']} - missing prompt or response")
                continue
            
            conquests.append(GoldStarConquest(
                conquest_id=row['conquest_id'],
                conquest_type=row['conquest_type'],
                title=row['title'],
                prompt=row['prompt'],
                response=row['response'],
                rating=row['rating'],
                feedback=row['feedback'],
                philosopher=row['philosopher'],
                domain=row['domain'],
                created_at=row['created_at']
            ))
        
        logger.info(f"Fetched {len(conquests)} gold star conquests for {philosopher}")
        return conquests
    
    def export_to_chatml(
        self,
        conquests: list[GoldStarConquest],
        output_path: Path
    ) -> int:
        """
        Export to ChatML JSONL format (Unsloth).
        
        Returns:
            Number of samples exported
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for conquest in conquests:
                f.write(json.dumps(conquest.to_chatml()) + '\n')
        
        logger.info(f"Exported {len(conquests)} samples to {output_path} (ChatML format)")
        return len(conquests)
    
    def export_to_alpaca(
        self,
        conquests: list[GoldStarConquest],
        output_path: Path
    ) -> int:
        """
        Export to Alpaca JSONL format (Axolotl).
        
        Returns:
            Number of samples exported
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for conquest in conquests:
                f.write(json.dumps(conquest.to_alpaca()) + '\n')
        
        logger.info(f"Exported {len(conquests)} samples to {output_path} (Alpaca format)")
        return len(conquests)
    
    def export_to_openai(
        self,
        conquests: list[GoldStarConquest],
        output_path: Path
    ) -> int:
        """
        Export to OpenAI fine-tuning format.
        
        Returns:
            Number of samples exported
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for conquest in conquests:
                f.write(json.dumps(conquest.to_openai()) + '\n')
        
        logger.info(f"Exported {len(conquests)} samples to {output_path} (OpenAI format)")
        return len(conquests)
    
    def export_dataset(
        self,
        philosopher: str,
        domain: str,
        output_dir: Path,
        format: str = "chatml",
        conquest_type: str | None = None,
        limit: int | None = None
    ) -> tuple[Path, int]:
        """
        Export complete dataset.
        
        Args:
            philosopher: User email
            domain: Organization domain
            output_dir: Output directory
            format: Export format (chatml, alpaca, openai)
            conquest_type: Optional filter by conquest type
            limit: Optional limit on number of results
        
        Returns:
            (output_path, sample_count)
        """
        # Fetch conquests
        conquests = self.fetch_gold_star_conquests(
            philosopher=philosopher,
            domain=domain,
            conquest_type=conquest_type,
            limit=limit
        )
        
        if not conquests:
            raise ValueError(f"No gold star conquests found for {philosopher}")
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"gold_star_dataset_{timestamp}.jsonl"
        output_path = output_dir / filename
        
        # Export based on format
        if format == "chatml":
            count = self.export_to_chatml(conquests, output_path)
        elif format == "alpaca":
            count = self.export_to_alpaca(conquests, output_path)
        elif format == "openai":
            count = self.export_to_openai(conquests, output_path)
        else:
            raise ValueError(f"Unknown format: {format}")
        
        return output_path, count

