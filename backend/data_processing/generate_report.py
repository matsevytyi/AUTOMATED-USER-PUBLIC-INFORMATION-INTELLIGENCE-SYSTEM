from datetime import datetime
import random
from typing import List

import json

import os
import sys

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)
from backend.models import User, Report, DiscoverSource, InformationCategory, InformationPiece

from backend.data_processing.formulas import calculate_validation_score, adjusted_risk_score

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
    
    if not information_pieces or not information_pieces[0]:
        print("No information pieces found for report", report_id)
        information_pieces = db.session.query(InformationPiece).filter_by(report_id=report_id).all()
        
    print(f"Generating report for {len(information_pieces)} information pieces")
    
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
    
    risk_vals = []
    
    for piece in information_pieces:
        # Get category and source names
        category_name = get_category_name(db, piece.category_id)
        source_name = get_source_name(db, piece.source_id)

        # Determine risk level based on category and content
        word_based_risk_score = determine_risk_level(piece)

        contradicting_count = db.session.query(InformationPiece).filter(
                InformationPiece.content == piece.content,
                InformationPiece.report_id != piece.report_id
            ).count()
        
        earlier_infopiece = db.session.query(InformationPiece).filter(
                                        InformationPiece.content == piece.content
                                        ).order_by(InformationPiece.created_at.asc()).first()
        
        if earlier_infopiece:
            earlier_infopiece_date = earlier_infopiece.created_at
        else:
            earlier_infopiece_date = piece.created_at
        
        validation_score = calculate_validation_score(piece.repetition_count, contradicting_count)
        
        word_based_risk_score = min(word_based_risk_score + validation_score, 7)
        relevance_score = piece.relevance_score or 0.1
        #relevance_score = 1 - (abs(relevance_score - 1) / 4)
        relevance_score = relevance_score * word_based_risk_score
        
        final_relevance_score = adjusted_risk_score(relevance_score, earlier_infopiece_date)
        
        risk_level = "low" if final_relevance_score < 4 else "medium" if final_relevance_score < 7 else "high"
        
        print(f"InfoPiece ID {piece.content} - Word Risk: {word_based_risk_score:.2f}, Validation Score: {validation_score:.2f}, Relevance Score: {relevance_score:.2f}, Final Risk Score: {final_relevance_score:.2f}, Risk Level: {risk_level}")
        
        risk_counts[risk_level] += 1
        risk_vals.append(final_relevance_score)
        
        # Count sources
        source_counts[source_name] = source_counts.get(source_name, 0) + 1
        
        # Create finding entry
        finding = {
            "id": piece.id,
            "source": source_name,
            "category": category_name,
            "info": piece.content[:200] + ("..." if len(piece.content) > 200 else ""),
            "risk": risk_level,
            "timestamp": piece.created_at.strftime("%Y-%m-%d"),
            "url": piece.source if piece.source.startswith('http') else "N/A",
            "relevance_score": piece.relevance_score or 0.5
        }
        detailed_findings.append(finding)
        
        # Store a short plaintext snippet on the InformationPiece itself ot give context to assistant
        try:
            raw = piece.content or ''
            snippet = raw.split('\n', 1)[0][:400]
            piece.snippet = snippet if snippet else (raw[:400] + ("..." if len(raw) > 400 else ""))
            # persist changes if piece is attached to session (best-effort)
            try:
                db.session.merge(piece)
            except Exception:
                pass
        except Exception:
            pass
    
    # Calculate overall risk score
    overall_risk_score = sum(risk_vals) / len(risk_vals) if risk_vals else 0.0
    
    print("overall risk score", overall_risk_score)
    
    # Generate executive summary
    executive_summary = generate_executive_summary(
        report.user_query, 
        len(information_pieces), 
        risk_counts, 
        overall_risk_score
    )
    
    print("summary", executive_summary)
    
    # Generate recommendations
    recommendations = generate_recommendations(risk_counts, source_counts)
    
    print("recommendations", recommendations)
    
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
    report.executive_summary = executive_summary
    report.risk_distribution = json.dumps(risk_counts)
    report.detailed_findings = json.dumps(detailed_findings)
    report.recommendations = json.dumps(recommendations)
    report.source_distribution = json.dumps(source_counts)
    
    print("updating report in db with id ", report_id)
    db.session.merge(report)
    db.session.commit()
    
    return final_report

def get_category_name(db, category_id: int) -> str:
    """Get category name from ID"""
    if not category_id:
        return "Uncategorized"
    
    category = db.session.query(InformationCategory).filter_by(id=category_id).first()
    return category.name if category else "Unknown Category"

def get_report(db, report_id: int) -> Report:
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

def determine_risk_level(piece: InformationPiece) -> int:
    """Determine risk level based on content and category"""
    content_lower = piece.snippet.lower()
    
    score = 0.0
    
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
        return 10
    
    # Check for medium risk
    for keyword in medium_risk_keywords:
        if keyword in content_lower:
            score += 3
    
    return min(score, 10)

def generate_executive_summary(query: str, total_findings: int, risk_counts: dict, overall_risk_score: float) -> str:
    """Generate executive summary based on findings"""
    risk_level_desc = "Low"
    if overall_risk_score >= 4:
        risk_level_desc = "High"
    elif overall_risk_score >= 1.7:
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