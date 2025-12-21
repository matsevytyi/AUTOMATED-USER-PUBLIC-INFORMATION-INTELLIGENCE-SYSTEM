from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from backend.utils.AES256_encrypted_type import EncryptedString

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
    average_misuse_score = db.Column(db.Float, nullable=True)
    
    is_admin = db.Column(db.Boolean, default=False)
    is_deactivated = db.Column(db.Boolean, default=False)
    deactivated_reason = db.Column(db.Text, nullable=True)
    
    # Relationships
    reports = db.relationship('Report', backref='user', lazy=True)
    searches = db.relationship('SearchHistory', backref='user', lazy=True, order_by='desc(SearchHistory.created_at)')

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(50), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_query = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    generation_time_seconds = db.Column(db.Integer, default=45.0)
    overall_risk_score = db.Column(db.Float, default=0.0)
    
    # Report data (stored as JSON), encrypted
    executive_summary = db.Column(EncryptedString)
    risk_distribution = db.Column(EncryptedString)  # JSON string
    detailed_findings = db.Column(EncryptedString)  # JSON string
    recommendations = db.Column(EncryptedString)  # JSON string
    source_distribution = db.Column(EncryptedString)  # JSON string
    
    # Relationships
    information_pieces = db.relationship('InformationPiece', backref='report', lazy='selectin', primaryjoin="Report.report_id == InformationPiece.report_id")
    
    def to_dict(self):

        detailed_findings = [d.to_dict() for d in self.information_pieces]
        
        return {
            'report_id': self.report_id,
            'query': self.user_query,
            'generated_at': self.generated_at.isoformat() + 'Z',
            'status': self.status,
            'overall_risk_score': round(self.overall_risk_score, 2),
            'executive_summary': self.executive_summary,
            'risk_distribution': json.loads(self.risk_distribution) if self.risk_distribution and self.risk_distribution != "null" else {},
            'detailed_findings': detailed_findings,
            'recommendations': json.loads(self.recommendations) if self.recommendations and self.recommendations != "null" else [],
            'source_distribution': json.loads(self.source_distribution) if self.source_distribution and self.source_distribution != "null" else {},
            'total_findings': len(self.information_pieces)
        }

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user_query = db.Column(db.Text, nullable=False)
    report_id = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    local_misuse_score = db.Column(db.Float, nullable=True)  # because is added later
    
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
    content = db.Column(EncryptedString, nullable=False)
    
    relevance_score = db.Column(db.Float, nullable=True) # because is added later
    risk_score = db.Column(db.Float, nullable=True)
    risk_level = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Short chat context and human-friendly title
    snippet = db.Column(EncryptedString, nullable=True)
    
    repetition_count = db.Column(db.Integer, default=1)
    
    # Relationships
    category = db.relationship('InformationCategory', backref='information_pieces', lazy='selectin')
    obtained_from = db.relationship('DiscoverSource', backref='information_pieces', lazy='selectin')
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_id': self.report_id,
            'source': self.obtained_from.name,
            'category': self.category.name if self.category else "Uncategorized",
            'info': self.content[:200] or self.snippet,  # for frontend
            'risk': self.risk_level,
            'timestamp': self.created_at.isoformat() + 'Z',
            'url': self.source if self.source.startswith('http') else 'N/A',  # assuming source is url for web
            'relevance_score': self.relevance_score,
            
            'content': self.content,
            'snippet': self.snippet,
            'risk_score': self.risk_score
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
    cookies_json = db.Column(EncryptedString, nullable=False) # EncryptedString
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)


class ChatSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), db.ForeignKey('user.email'), nullable=False)
    report_id = db.Column(db.String(50), db.ForeignKey('report.report_id'), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    save_history = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    messages = db.relationship('ChatMessage', backref='session', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_email': self.user_email,
            'report_id': self.report_id,
            'title': self.title,
            'save_history': self.save_history,
            'created_at': self.created_at.isoformat() + 'Z'
        }


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    sender = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant' | 'system'
    content = db.Column(EncryptedString, nullable=False)
    meta = db.Column(EncryptedString, nullable=True)  # JSON string for optional metadata (sources, provider info)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'sender': self.sender,
            'content': self.content,
            'meta': json.loads(self.meta) if self.meta else None,
            'created_at': self.created_at.isoformat() + 'Z'
        }
