from models import User, Report, SearchHistory
from data_collection.data_collection_wrapper import collect_data
from data_processing.data_cleansing_and_convertion import parse_search_results_to_information_pieces
from report_generation.generate_report import init_report, generate_complete_report


class ReportService:
    """Service for handling report generation and search operations"""
    
    def __init__(self, db):
        self.db = db
    
    def create_report(self, user_email, query, fb_cookies=None):
        """
        Create a new report by collecting data, processing it, and generating findings
        
        Args:
            user_email: Email of the user requesting the report
            query: Search query string
            fb_cookies: Optional Facebook cookies for authenticated scraping
            
        Returns:
            dict: Complete report with findings and risk analysis
            
        Raises:
            ValueError: If user not found or query is empty
        """
        # Validate query
        if not query or not query.strip():
            raise ValueError('Search query is required.')
        
        # Get user
        user = User.query.filter_by(email=user_email).first()
        if not user:
            raise ValueError('User not found.')
        
        # Initialize report in database
        report_id = init_report(db=self.db, user_id=user.id, query=query)
        print(f"Creating report with ID: {report_id}")
        
        # Collect data from various sources
        raw_search_results = collect_data(query, cookie_map=fb_cookies, uid=str(user.id))
        
        # Process and extract information pieces
        information_pieces = parse_search_results_to_information_pieces(
            data=raw_search_results,
            report_id=report_id,
            db=self.db
        )
        
        # Generate complete report with risk analysis
        final_report = generate_complete_report(
            db=self.db,
            report_id=report_id,
            information_pieces=information_pieces
        )
        
        # Add to search history
        search_history = SearchHistory(
            user_id=user.id,
            user_query=query,
            report_id=report_id
        )
        self.db.session.add(search_history)
        self.db.session.commit()
        
        return final_report
    
    def get_report(self, user_email, report_id):
        """
        Retrieve a specific report for a user
        
        Args:
            user_email: Email of the user
            report_id: ID of the report to retrieve
            
        Returns:
            dict: Report data
            
        Raises:
            ValueError: If user or report not found
        """
        user = User.query.filter_by(email=user_email).first()
        if not user:
            raise ValueError('User not found.')
        
        report = Report.query.filter_by(report_id=report_id, user_id=user.id).first()
        if not report:
            raise ValueError('Report not found.')
        
        return report.to_dict()
    
    def get_search_history(self, user_email):
        """
        Get search history for a user
        
        Args:
            user_email: Email of the user
            
        Returns:
            list: List of search history items
            
        Raises:
            ValueError: If user not found
        """
        user = User.query.filter_by(email=user_email).first()
        if not user:
            raise ValueError('User not found.')
        
        searches = SearchHistory.query.filter_by(user_id=user.id)\
            .order_by(SearchHistory.created_at.desc())\
            .all()
        
        return [search.to_dict() for search in searches]
