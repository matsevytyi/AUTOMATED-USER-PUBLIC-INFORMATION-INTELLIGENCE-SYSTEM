from models import db, User, Report, SearchHistory, ChatSession
from sqlalchemy import func, text, case
from datetime import datetime, timedelta
import math
from backend.utils.config import Config

class AdminService:
    """Engine for admin analytics and misuse detection"""

    def __init__(self, db):
        self.db = db
        self.satisfactory_generation_time = Config.SATISFACTORY_GENERATION_TIME
        self.tolerating_generation_time = Config.SATISFACTORY_GENERATION_TIME * 1.1

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
        counts = self.db.session.query(
            func.count(Report.id).label('total'),
            func.count(case((Report.generation_time_seconds <= self.satisfactory_generation_time, Report.id))).label('satisfied'),
            func.count(case((Report.generation_time_seconds <= self.tolerating_generation_time, Report.id))).label('tolerating')
        ).filter(
            Report.generated_at >= thirty_days_ago
        ).first()

        # Access the results
        total_searches = counts.total or 1
        satisfied_searches = counts.satisfied or 0
        tolerating_searches = counts.tolerating or 0
        
        tolerating_converted = 0.5*(tolerating_searches - satisfied_searches)
        
        stats['apdex_score'] = (satisfied_searches + tolerating_converted) / total_searches

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
    
    def detect_potential_misusers(self):
        """Detect potential system misusers"""
        misusers = []

        # outerjoin so don't skip users with 0 reports
        
        results = self.db.session.query(
            User,
            func.count(Report.id).label('total_reports')
        ).outerjoin(
            Report, User.id == Report.user_id
        ).filter(
            User.is_admin == False,
            User.is_deactivated == False
        ).group_by(
            User.id
        ).order_by(
            User.average_misuse_score.desc()
        ).all()

        for user, total_reports in results:
            score = user.average_misuse_score or 0.0
            
            if score > 0.1:
                misusers.append({
                    'user_id': user.id,
                    'email': user.email,
                    'name': user.name or user.email.split('@')[0],
                    'misuse_score': round(score, 3),
                    'recent_searches_count': total_reports or 0,
                    'joined_at': user.created_at.isoformat() if user.created_at else None
                })

        print(f"[MISUSE DETECTION] Found {len(misusers)} potential misusers")
        return misusers


    def get_user_recent_requests(self, user_id):
        """Get recent requests for a user (without full reports)"""
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        # Get recent searches
        searches = self.db.session.query(SearchHistory).filter(
            SearchHistory.user_id == user_id,
            SearchHistory.created_at >= thirty_days_ago
        ).order_by(SearchHistory.created_at.desc()).limit(10).all()

        requests = []
        for search in searches:
            requests.append({
                'type': 'search',
                'query': search.user_query,
                'timestamp': search.created_at.isoformat(),
                'status': 'completed'
            })

        # Get recent reports (just metadata)
        reports = self.db.session.query(Report).filter(
            Report.user_id == user_id,
            Report.generated_at >= thirty_days_ago
        ).order_by(Report.generated_at.desc()).limit(10).all()

        for report in reports:
            requests.append({
                'type': 'report',
                'query': report.user_query,
                'timestamp': report.generated_at.isoformat(),
                'status': report.status,
                'report_id': report.report_id
            })

        return sorted(requests, key=lambda x: x['timestamp'], reverse=True)

    def get_suspended_users(self):
        suspended_users = self.db.session.query(User).filter(User.is_deactivated == True).all()
        suspended_list = [{
            'user_id': user.id,
            'email': user.email,
            'name': user.name,
            'created_at': user.created_at.isoformat(),
            'suspended_at': user.deactivated_reason
        } for user in suspended_users]
        
        print(f"[ADMIN SUSPENDED] Found {len(suspended_list)} suspended users")
        return suspended_list

    def suspend_user(self, user_id, reason):
        """Suspend a user account"""
        user = self.db.session.query(User).filter(User.id == user_id).first()
        if user:
            user.is_deactivated = True
            user.deactivated_reason = reason
            self.db.session.commit()
            return True
        return False

    def reactivate_user(self, user_id):
        """Reactivate a suspended user"""
        user = self.db.session.query(User).filter(User.id == user_id).first()
        if user:
            user.is_deactivated = False
            self.db.session.commit()
            return True
        return False
    
    # do on report generation
    # def detect_potential_misusers(self):
    #     """Detect potential system misusers"""
    #     misusers = []

    #     # Get all users with their search history
    #     users = self.db.session.query(User).filter(
    #             User.is_admin == False, 
    #             User.is_deactivated == False
    #         ).all()

    #     for user in users:
    #         # Get recent searches (last 30 days)
    #         thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    #         recent_searches = self.db.session.query(SearchHistory).filter(
    #             SearchHistory.user_id == user.id,
    #             SearchHistory.created_at >= thirty_days_ago
    #         ).all()

    #         if not recent_searches:
    #             continue

    #         # Extract persons from queries using NER-like approach
    #         persons_in_queries = []
    #         for search in recent_searches:
    #             # Simple NER: look for capitalized words that might be names
    #             query = search.query.lower()
    #             # Extract potential person names (simplified)
    #             words = re.findall(r'\b[A-Z][a-z]+\b', search.query)
    #             persons_in_queries.extend(words)

    #         if not persons_in_queries:
    #             continue

    #         # Calculate misuse metrics
    #         user_name = user.name or user.email.split('@')[0]

    #         # 1. Levenshtein ratios between persons in queries
    #         if len(persons_in_queries) > 1:
    #             ratios = []
    #             for i in range(len(persons_in_queries)):
    #                 for j in range(i+1, len(persons_in_queries)):
    #                     ratio = Levenshtein.ratio(persons_in_queries[i].lower(), persons_in_queries[j].lower())
    #                     ratios.append(1 - ratio)  # Inverse ratio
    #             std_dev_levenshtein = sum(ratios) / len(ratios) if ratios else 0
    #         else:
    #             std_dev_levenshtein = 0

    #         # 2. Levenshtein ratio between user name and persons in query
    #         user_ratios = []
    #         for person in persons_in_queries:
    #             ratio = Levenshtein.ratio(user_name.lower(), person.lower())
    #             user_ratios.append(1 - ratio)  # Inverse ratio
    #         user_name_ratio = sum(user_ratios) / len(user_ratios) if user_ratios else 0

    #         # Combined misuse score
    #         misuse_score = (std_dev_levenshtein + user_name_ratio) / 2

    #         # Update user's average misuse score
    #         user.average_misuse_score = misuse_score
    #         self.db.session.commit()

    #         # Flag as potential misuser if score > threshold
    #         if misuse_score > 0.3:  # Threshold for potential misusers
    #             misusers.append({
    #                 'user_id': user.id,
    #                 'email': user.email,
    #                 'name': user.name,
    #                 'misuse_score': misuse_score,
    #                 'recent_searches_count': len(recent_searches)
    #             })

    #     print(f"[MISUSE DETECTION] Found {len(misusers)} potential misusers")
    #     return misusers
