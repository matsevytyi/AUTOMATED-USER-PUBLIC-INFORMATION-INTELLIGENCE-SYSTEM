from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reports = db.relationship('Report', backref='user', lazy=True)
    searches = db.relationship('SearchHistory', backref='user', lazy=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    query = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Report data (stored as JSON)
    executive_summary = db.Column(db.Text)
    risk_distribution = db.Column(db.Text)  # JSON string
    detailed_findings = db.Column(db.Text)  # JSON string
    recommendations = db.Column(db.Text)  # JSON string
    source_distribution = db.Column(db.Text)  # JSON string
    
    def to_dict(self):
        return {
            'report_id': self.report_id,
            'query': self.query,
            'status': self.status,
            'generated_at': self.generated_at.isoformat() + 'Z',
            'executive_summary': self.executive_summary,
            'risk_distribution': json.loads(self.risk_distribution) if self.risk_distribution else {},
            'detailed_findings': json.loads(self.detailed_findings) if self.detailed_findings else [],
            'recommendations': json.loads(self.recommendations) if self.recommendations else [],
            'source_distribution': json.loads(self.source_distribution) if self.source_distribution else {}
        }
