from datetime import datetime
import random
from typing import List

import os
import sys

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)
from backend.models import User, Report, DiscoverSource, InformationCategory, InformationPiece

def init_report(db, user_id: str, query: str) -> str:
    """Initialize a new report and save it to database"""
    report_id = f"RPT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    
    # Create new Report record
    report = Report(
        report_id=report_id,
        user_id=user_id,
        user_query=query,
        status="processing",
        generated_at=datetime.utcnow()
    )
    
    print("adding report to db with id ", report_id)
    db.session.add(report)
    db.session.commit()
    
    return report_id



def generate_complete_report(db, report_id: str, information_pieces: List[InformationPiece]) -> dict:
    """Generate complete report from InformationPiece objects"""
    
    # Get the report from database
    print("querying report with id", report_id)
    report = get_report(db=db, report_id=report_id)
    user = get_user(db, report.user_id)
    if not report:
        raise ValueError(f"Report {report_id} not found")
    
    # Process information pieces into report format
    detailed_findings = []
    risk_counts = {"high": 0, "medium": 0, "low": 0}
    source_counts = {}
    
    for piece in information_pieces:
        # Get category and source names
        category_name = get_category_name(db, piece.category_id)
        source_name = get_source_name(db, piece.source_id)
        
        # Determine risk level based on category and content
        risk_level = determine_risk_level(piece, category_name)
        risk_counts[risk_level] += 1
        
        # Count sources
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
        
        # Create finding entry
        finding = {
            "source": source_name,
            "category": category_name,
            "info": piece.content[:200] + ("..." if len(piece.content) > 200 else ""),
            "risk": risk_level,
            "timestamp": piece.created_at.strftime("%Y-%m-%d"),
            "url": piece.source if piece.source.startswith('http') else "N/A",
            "relevance_score": piece.relevance_score or 0.5
        }
        detailed_findings.append(finding)
    
    # Calculate overall risk score
    overall_risk_score = calculate_overall_risk_score(risk_counts, len(information_pieces))
    
    # Generate executive summary
    executive_summary = generate_executive_summary(
        report.user_query, 
        len(information_pieces), 
        risk_counts, 
        overall_risk_score
    )
    
    # Generate recommendations
    recommendations = generate_recommendations(risk_counts, source_counts)
    
    # Create final report structure
    final_report = {
        "report_id": report_id,
        "user": user.email,
        "query": report.user_query,
        "generated_at": datetime.utcnow().isoformat() + 'Z',
        "status": "completed",
        "overall_risk_score": round(overall_risk_score, 2),
        "executive_summary": executive_summary,
        "risk_distribution": risk_counts,
        "detailed_findings": detailed_findings,
        "recommendations": recommendations,
        "source_distribution": source_counts,
        "total_findings": len(information_pieces)
    }
    
    # Update report status in database
    report.status = "completed"
    report.summary = executive_summary
    report.risk_score = overall_risk_score
    
    print("updating report in db")
    db.session.commit()
    
    return final_report

def get_category_name(db, category_id: int) -> str:
    """Get category name from ID"""
    if not category_id:
        return "Uncategorized"
    
    category = db.session.query(InformationCategory).filter_by(id=category_id).first()
    return category.name if category else "Unknown Category"

def get_report(db, report_id: int) -> str:
    """Get source name from ID"""
    source = db.session.query(Report).filter_by(report_id=report_id).first()
    return source

def get_user(db, user_id: int) -> str:
    """Get source name from ID"""
    source = db.session.query(User).filter_by(id=user_id).first()
    return source

def get_source_name(db, source_id: int) -> str:
    """Get source name from ID"""
    source = db.session.query(DiscoverSource).filter_by(id=source_id).first()
    return source.name if source else "Unknown Source"

def determine_risk_level(piece: InformationPiece, category_name: str) -> str:
    """Determine risk level based on content and category"""
    content_lower = piece.content.lower()
    
    # High risk indicators
    high_risk_keywords = [
        'password', 'breach', 'leaked', 'exposed', 'compromised', 
        'ssn', 'social security', 'credit card', 'bank account',
        'address', 'phone number', 'personal information'
    ]
    
    # Medium risk indicators
    medium_risk_keywords = [
        'email', 'profile', 'public post', 'social media',
        'work', 'employment', 'location', 'university'
    ]
    
    # Check for high risk
    if any(keyword in content_lower for keyword in high_risk_keywords):
        return "high"
    
    # Check for medium risk
    if any(keyword in content_lower for keyword in medium_risk_keywords):
        return "medium"
    
    # Check category-based risk
    if category_name.lower() in ['contact_info', 'financial_info', 'personal_identifier']:
        return "high"
    elif category_name.lower() in ['professional', 'social_connections']:
        return "medium"
    
    return "low"

def calculate_overall_risk_score(risk_counts: dict, total_pieces: int) -> float:
    """Calculate overall risk score based on risk distribution"""
    if total_pieces == 0:
        return 0.0
    
    # Risk weights
    risk_weights = {"high": 10, "medium": 5, "low": 1}
    
    # Calculate weighted score
    total_score = 0
    for risk_level, count in risk_counts.items():
        weight = risk_weights.get(risk_level, 0)
        total_score += weight * count
    
    # Return average score (0-10 scale)
    return total_score / total_pieces

def generate_executive_summary(query: str, total_findings: int, risk_counts: dict, overall_risk_score: float) -> str:
    """Generate executive summary based on findings"""
    risk_level_desc = "Low"
    if overall_risk_score >= 7:
        risk_level_desc = "High"
    elif overall_risk_score >= 4:
        risk_level_desc = "Medium"
    
    summary = f"Digital footprint analysis for '{query}' reveals {total_findings} information pieces across multiple platforms. "
    summary += f"Overall risk level: {risk_level_desc} (score: {overall_risk_score:.1f}/10). "
    
    if risk_counts["high"] > 0:
        summary += f"Found {risk_counts['high']} high-risk items requiring immediate attention. "
    
    if risk_counts["medium"] > 0:
        summary += f"Identified {risk_counts['medium']} medium-risk items for review. "
    
    return summary

def generate_recommendations(risk_counts: dict, source_counts: dict) -> List[str]:
    """Generate recommendations based on findings"""
    recommendations = []
    
    if risk_counts["high"] > 0:
        recommendations.extend([
            "Immediately review and secure accounts with compromised information",
            "Change passwords for all affected accounts",
            "Enable two-factor authentication where possible",
            "Monitor credit reports for suspicious activity"
        ])
    
    if risk_counts["medium"] > 0:
        recommendations.extend([
            "Review privacy settings on social media accounts",
            "Limit publicly visible personal information",
            "Consider removing or updating outdated profiles"
        ])
    
    if "Social Media" in source_counts and source_counts["Social Media"] > 5:
        recommendations.append("Consider reducing social media presence or improving privacy controls")
    
    if len(recommendations) == 0:
        recommendations.append("Continue monitoring digital footprint regularly")
    
    return recommendations[:6]  # Limit to 6 recommendations