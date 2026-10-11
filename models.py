"""
models.py - Database Models for AI Content Detector
Uses Flask-SQLAlchemy to define the Scan table and schema.
"""

from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Scan(db.Model):
    """
    Represents an analyzed content record (image or video).
    Stores score, classification label, file path, and granular breakdown metrics.
    """
    __tablename__ = 'scans'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=True)
    file_type = db.Column(db.String(50), nullable=False)  # 'image' or 'video'
    ai_score = db.Column(db.Float, nullable=False)        # 0.0 to 100.0 %
    label = db.Column(db.String(100), nullable=False)     # e.g., 'Likely AI-Generated'
    file_path = db.Column(db.String(500), nullable=False)
    details_json = db.Column(db.Text, nullable=True)      # JSON string of granular metrics
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    @property
    def details(self):
        """Parse JSON details into Python dictionary."""
        if not self.details_json:
            return {}
        try:
            return json.loads(self.details_json)
        except Exception:
            return {}

    @details.setter
    def details(self, val):
        """Serialize details dictionary into JSON string."""
        if isinstance(val, (dict, list)):
            self.details_json = json.dumps(val)
        elif isinstance(val, str):
            self.details_json = val
        else:
            self.details_json = "{}"

    def to_dict(self):
        """Serialize scan record for JSON API responses."""
        return {
            'id': self.id,
            'filename': self.filename,
            'original_filename': self.original_filename or self.filename,
            'file_type': self.file_type,
            'ai_score': round(self.ai_score, 1),
            'label': self.label,
            'file_path': self.file_path,
            'details': self.details,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

    def __repr__(self):
        return f"<Scan id={self.id} type={self.file_type} score={self.ai_score}% label='{self.label}'>"
