from models import db, User, Report, SearchHistory, ChatSession
from sqlalchemy import func, text
from datetime import datetime, timedelta
import math
import re
from collections import defaultdict
import Levenshtein

class AdminService:
    """Engine for admin analytics and misuse detection"""

    def __init__(self, db):
        self.db = db

    def get_system_statistics(self):
        """Get all system usage statistics"""
        stats = {}

        # Active Users (30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users_query = text("""
            SELECT COUNT(DISTINCT user_id) as monthly_active_users
            FROM (
                SELECT user_id FROM search_history
                WHERE created_at > :thirty_days_ago
                UNION
                SELECT user_id FROM report
                WHERE generated_at > :thirty_days_ago
                UNION
                SELECT u.id
                FROM chat_session cs
                JOIN "user" u ON cs.user_email = u.email
                WHERE cs.created_at > :thirty_days_ago
            ) as active_pool
        """)
        result = self.db.session.execute(active_users_query, {'thirty_days_ago': thirty_days_ago}).fetchone()
        stats['active_users'] = result.monthly_active_users if result else 0

        # Active Sessions (1 hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        active_sessions_query = text("""
            SELECT COUNT(DISTINCT user_id) as active_sessions_now
            FROM (
                SELECT user_id FROM search_history
                WHERE created_at > :one_hour_ago
                UNION
                SELECT user_id FROM report
                WHERE generated_at > :one_hour_ago
                UNION
                SELECT u.id
                FROM chat_session cs
                JOIN "user" u ON cs.user_email = u.email
                WHERE cs.created_at > :one_hour_ago
            ) as current_load
        """)
        result = self.db.session.execute(active_sessions_query, {'one_hour_ago': one_hour_ago}).fetchone()
        stats['active_sessions'] = result.active_sessions_now if result else 0

        # User Acquisition Velocity
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = today - timedelta(days=1)
        eight_days_ago = today - timedelta(days=8)

        today_users = self.db.session.query(func.count(User.id)).filter(User.created_at >= today).scalar()
        weekly_avg = self.db.session.query(func.count(User.id) / 7.0).filter(
            User.created_at.between(eight_days_ago, yesterday)
        ).scalar()
        stats['acquisition_velocity'] = today_users - weekly_avg if weekly_avg else today_users

        # Weekly Reports
        week_ago = datetime.utcnow() - timedelta(days=7)
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        current_week_reports = self.db.session.query(func.count(Report.id)).filter(
            Report.generated_at >= week_ago
        ).scalar()
        stats['weekly_reports'] = current_week_reports

        # Weekly Chat Sessions
        current_week_chats = self.db.session.query(func.count(ChatSession.id)).filter(
            ChatSession.created_at >= week_ago
        ).scalar()
        stats['weekly_chats'] = current_week_chats

        # Apdex Score
        total_searches = self.db.session.query(func.count(SearchHistory.id)).filter(
            SearchHistory.created_at >= thirty_days_ago
        ).scalar()
        stats['apdex_score'] = 1.0 if total_searches > 0 else 0.0  # Placeholder

        # Misuse Severity Index
        users = self.db.session.query(User).all()
        misuse_scores = [u.average_misuse_score or 0 for u in users if u.average_misuse_score]
        if misuse_scores:
            avg_misuse = sum(misuse_scores) / len(misuse_scores)
            stats['misuse_index'] = math.tanh(avg_misuse)  # Tanh for severity
        else:
            stats['misuse_index'] = 0.0

        print(f"[ANALYTICS] Calculated statistics: {stats}")
        return stats

    