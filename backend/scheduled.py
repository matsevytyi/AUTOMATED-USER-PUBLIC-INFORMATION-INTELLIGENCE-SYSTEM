from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from models import Report, InformationPiece

def delete_old_reports(db):
    try:
        cutoff = datetime.utcnow() - timedelta(weeks=1)
        db.session.query(Report).filter(Report.generated_at < cutoff).delete()
        db.commit()
        print("Old reports deleted.")
    except Exception as e:
        print("Failed to delete old reports:", e)
        
def delete_old_datapieces(db):
    try:
        cutoff = datetime.utcnow() - timedelta(weeks=1)
        db.session.query(InformationPiece).filter(InformationPiece.created_at < cutoff).delete()
        db.commit()
        print("Old data pieces deleted.")
    except Exception as e:
        print("Failed to delete old data pieces:", e)


def start_scheduler(db):
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(lambda: delete_old_reports(db), 'interval', days=1)
    scheduler.add_job(lambda: delete_old_reports(db), 'interval', days=1)
    
    scheduler.start()

