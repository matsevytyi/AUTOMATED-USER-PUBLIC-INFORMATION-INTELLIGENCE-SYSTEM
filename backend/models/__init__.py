from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=True)
    theme = db.Column(db.String(20), nullable=True, default='device')
    confirmed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reports = db.relationship('Report', backref='user', lazy=True)
    searches = db.relationship('SearchHistory', backref='user', lazy=True)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_query = db.Column(db.Text, nullable=False)
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
            'query': self.user_query,
            'status': self.status,
            'generated_at': self.generated_at.isoformat() + 'Z',
            'executive_summary': self.executive_summary,
            'risk_distribution': json.loads(self.risk_distribution) if self.risk_distribution else {},
            'detailed_findings': json.loads(self.detailed_findings) if self.detailed_findings else [],
            'recommendations': json.loads(self.recommendations) if self.recommendations else [],
            'source_distribution': json.loads(self.source_distribution) if self.source_distribution else {}
        }

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_query = db.Column(db.Text, nullable=False)
    report_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'query': self.user_query,
            'report_id': self.report_id,
            'created_at': self.created_at.isoformat() + 'Z'
        }

class InformationPiece(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(50), db.ForeignKey('report.report_id'), nullable=False)
    
    category_id = db.Column(db.Integer, db.ForeignKey('information_category.id'), nullable=True)  # because is added later
    source_id = db.Column(db.Integer, db.ForeignKey('discover_source.id'), nullable=False)
    
    source = db.Column(db.Text, nullable=False)
    content = db.Column(db.Text, nullable=False)
    
    relevance_score = db.Column(db.Float, nullable=True) # because is added later
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified_by_user = db.Column(db.Boolean, default=False)
    # Short chat context and human-friendly title
    snippet = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_id': self.report_id,
            'category_id': self.category_id,
            'source_id': self.source_id,
            'source': self.source,
            'content': self.content,
            'snippet': self.snippet,
            'relevance_score': self.relevance_score,
            'created_at': self.created_at.isoformat() + 'Z'
        }

class InformationCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    weight = db.Column(db.Float, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'weight': self.weight
        }
        
class DiscoverSource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }

class FacebookCookies(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.Integer, db.ForeignKey('user.email'), nullable=False, unique=True)
    cookies_json = db.Column(db.Text, nullable=False)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
