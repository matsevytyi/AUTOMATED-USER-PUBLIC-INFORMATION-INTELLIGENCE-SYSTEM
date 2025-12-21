from backend.models import User, Report, SearchHistory, InformationPiece,  DiscoverSource, InformationCategory
from backend.services.data_collection_service import DataCollectionService

from backend.engines.risk_assessment_engine import RiskAssessmentEngine
from backend.engines.data_processing_engine import data_processing_engine
import math



from typing import List

from datetime import datetime
import json, random

class ReportService:
    def __init__(self, db):
        self.db = db
        self.data_collection = DataCollectionService()
        self.risk_engine = RiskAssessmentEngine(db)

    def create_report(self, user_email, query, fb_cookies=None, use_facebook=False, use_general=True):
        user = self.db.session.query(User).filter_by(email=user_email).first()
        report_id = self._init_report(user.id, query)

        # 1. Data Collection
        raw_data = self.data_collection.collect_data(query, fb_cookies=fb_cookies, use_facebook=use_facebook, use_general=use_general)
       # raw_data = [['Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], [], [{'title': 'CSC Hackathon 2023. Як це було. « Hackathon Expert Group', 'link': 'https://www.hackathon.expert/csc-hackathon-2023-report/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Щодо задачі з визначення міри подібності зображень, яку надала компанія ЛУН – перемогла командаCringe Minimizers(Антон Бражний, Андрій Мацевитий , Артем Орловський та Віталій Бутко, студенти Київського політехнічного інституту імені Ігоря Сікорського, Українського католицького університету у Львові та Вільнюского університету).Саме вони утримували першу позицію у приватному лідерборді практично від початку змагання. Разом з тим, ще дві команди,Team GARCH(Андрій Єрко, Андрій Шевцов, Нікіта Фордуі, Софія Шапошнікова, що також не вперше беруть участь у наших хакатонах) та вже згаданаSarcastic AI теж запропонували досить цікаві рішення, розділивши першу позицію з переможцями на публічному лідерборді.'}, {'title': 'Інститут проблем машинобудування імені А. М. Підгорного НАН ...', 'link': 'https://uk.wikipedia.org/wiki/%D0%86%D0%BD%D1%81%D1%82%D0%B8%D1%82%D1%83%D1%82_%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC_%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%BE%D0%B1%D1%83%D0%B4%D1%83%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F_%D1%96%D0%BC%D0%B5%D0%BD%D1%96_%D0%90._%D0%9C._%D0%9F%D1%96%D0%B4%D0%B3%D0%BE%D1%80%D0%BD%D0%BE%D0%B3%D0%BE_%D0%9D%D0%90%D0%9D_%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': ' Юрій Мацевитий, Андрій Русанов, Віктор Соловей, Микола Шульженко, Володимир Голощапов, Павло Гонтаровський, Андрій Костіков, Вадим Цибулько за роботу «Підвищення енергоефективності роботи турбоустановок ТЕС і ТЕЦ шляхом модернізації, реконструкції та удосконалення режимів їхньої експлуатації» отрималиДержавну премію України в галузі науки і техніки 2008 року "Лауреати Державної премії України в галузі науки і техніки \\(2008\\)").'}, {'title': 'Члени Академії – Інститут енергетичних машин і систем ім. А.М ...', 'link': 'https://ipmach.kharkov.ua/%D1%87%D0%BB%D0%B5%D0%BD%D0%B8-%D0%B0%D0%BA%D0%B0%D0%B4%D0%B5%D0%BC%D1%96%D1%97/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'КОСТІКОВ Андрій Олегович · КРАВЧЕНКО Олег Вікторович · МАЦЕВИТИЙ Юрій Михайлович · ПІДГОРНИЙ Анатолій Миколайович · ПРОСКУРА Георгій Федорович · РВАЧОВ\xa0...'}, {'title': 'Наша гордість - Спеціалізована школа І -ІІІ ступенів №251 імені ...', 'link': 'http://school251.edukit.kiev.ua/nasha_gordistj/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'І. 42. ІІ, Мацевитий Андрій, Українська мова, 4-В, Герасимчук Л.І. 43. ІІІ, Мацевитий Андрій, Англійська мова, 4-В, Ільєнко Т.В. Переможці міського етапу\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного', 'link': 'https://www.nas.gov.ua/institutions/institut-energeticnix-masin-i-sistem-im-a-m-pidgornogo-131', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Русанов Андрій Вікторович. академік НАН України. Радник при дирекції. Мацевитий Юрій Михайлович. академік НАН України. Заступник директора з наукової роботи.'}, {'title': 'освітній ступінь бакалавр факультет інформатики спеціальність ...', 'link': 'https://www.ukma.edu.ua/index.php/about-us/sogodennya/dokumenty-naukma/doc_download/3927-fakultet-informatyky', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Андрій Володимирович. 79.98. 26. Пілат Михайло Іванович. 79.87. 27. Молчанов Олексій Костянтинович. 78.38. 28. Нестерук Олена Олександрівна. 77.91. 29\xa0...'}, {'title': '03534570 — ІЕМС НАН України', 'link': 'https://opendatabot.ua/c/03534570', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Переглянути повну інформацію про юридичну особу ІНСТИТУТ ЕНЕРГЕТИЧНИХ МАШИН І СИСТЕМ ІМ. А. М. ПІДГОРНОГО НАЦІОНАЛЬНОЇ АКАДЕМІЇ НАУК УКРАЇНИ. Компанія ІЕМС НАН України зареєстрована — 10.05.1993. Керівник компанії — Русанов Андрій Вікторович. Юрідична адреса компанії ІЕМС НАН України: Україна, 61046, Харківська обл., місто Харків, вул.Комунальників, будинок 2/10. Основний КВЕД юридичної особи — 71.20 Технічні випробування та дослідження. Номер свідоцтва про реєстрацію платника податку на додану вартість - 035345720371. За 2020 ІЕМС НАН України отримала виторг на суму 37 105 783 ₴ гривень'}, {'title': 'Відділення енергетики та енергетичних технологій НАН України', 'link': 'https://www.nas.gov.ua/structure/section-physical-technical-mathematical-sciences/department-energy-and-energy-technologies', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Жаркін Андрій Федорович. академік НАН України. Кириленко Олександр Васильович. академік НАН України. Кулик Михайло Миколайович. академік НАН України. Мацевитий\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного НАН ...', 'link': 'https://old.nas.gov.ua/UA//Org/Pages/default.aspx?OrgID=0000299', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Юрій Михайлович. Почесний директор. Matsevity@nas.gov.ua. +38 0572 94 55 14. Русанов Андрій Вікторович. Директор. Rusanov.A.V@nas.gov.ua. +\xa0...'}, {'title': 'Лікар Васильцов Ігор Анатолійович, записатися на онлайн ...', 'link': 'https://e-likari.com.ua/doctor/vasilcov-igor-anatoliiovic/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Дякую! Волик Андрій. (5). 05.01.2025. Вдячний лікарю за консультацію ... Мацевитий Ернест Валерійович. (5). 10.04.2025. Анонімний відгук. (4). 09.04.2025.'}]]
        

        # 2. Data Processing
        info_pieces = data_processing_engine.process_raw_data(
            data_list=raw_data,
            report_id=report_id,
            report_query=query,
            db=self.db
        )
        
        # 3. Risk Assessment (New Engine)
        processed, risk_values = self.risk_engine.process_risk_assessment(info_pieces, query)
        
        self.db.session.commit()

        # 4. Generate Report
        jsona = self._generate_final_json(report_id, info_pieces, user, query)
        return jsona
    
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
        user = self.db.session.query(User).filter_by(email=user_email).first()
        if not user:
            raise ValueError('User not found.')
        
        report = self.db.session.query(Report).filter_by(report_id=report_id, user_id=user.id).first()
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
        user = self.db.session.query(User).filter_by(email=user_email).first()
        
        if not user:
            raise ValueError('User not found.')
        
        searches = user.searches or []
        
        searches = [search.to_dict() for search in searches]
        
        return searches
    
    # HELPER FUNCTIONS
    
    def _init_report(self, user_id: str, query: str) -> str:
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
        
        new_history_entry = SearchHistory(
            user_id=user_id,
            user_query=query,
            report_id=report_id
        )
        
        # add local misusse calculation
        
        
        print("adding report to self.db with id ", report_id)
        self.db.session.add(report)
        self.db.session.add(new_history_entry)
        self.db.session.commit()
        
        return report_id

    def _generate_final_json(self, report_id, pieces, user, query):
        # Report-wide  Statistics
        risk_counts = {"high": 0, "medium": 0, "low": 0}
        source_distribution = {}
        risk_vals = []
        
        for p in pieces:
            # Risk Stats
            if p.risk_score is not None:
                risk_level = "low" if p.risk_score < 4 else "medium" if p.risk_score < 7 else "high"
                risk_counts[risk_level] = risk_counts.get(risk_level, 0) + 1
                risk_vals.append(p.risk_score)
            
            # Source Stats (to id)
            if p.source_id:   
                sid = str(p.source_id)
                source_distribution[sid] = source_distribution.get(sid, 0) + 1
                
        # Source IDs -> names (swap ID to name as a key, keep value same)
        new_source_distribution = {}    
        for k, v in source_distribution.items():
            new_k = self.db.session.query(DiscoverSource).filter_by(id=k).first()
            new_source_distribution[new_k.name] = v
        
        source_distribution = new_source_distribution or source_distribution
            
                
        print("risk_counts: ", risk_counts)
        print("source_distribution: ", source_distribution)

        if risk_vals:
            sorted_vals = sorted(risk_vals, reverse=True)
            
            # how many items make up the top 20% (minimum 1)
            top_count = max(1, math.ceil(len(sorted_vals) * 0.20))
            
            top_slice = sorted_vals[:top_count]
            avg_risk = sum(top_slice) / len(top_slice)
            
        else:
            avg_risk = 0.0
        
        # 2. Summary & Recommendations
        executive_summary = self._generate_executive_summary(
            query, 
            len(pieces), 
            risk_counts, 
            avg_risk
        )
        
        recommendations = self._generate_recommendations(risk_counts, source_distribution) 

        # 3. Update Report Model
        report = self.db.session.query(Report).filter_by(report_id=report_id).first()
        
        report.status = "completed"
        report.overall_risk_score = avg_risk
        report.executive_summary = executive_summary
        
        report.risk_distribution = json.dumps(risk_counts)
        print(report.risk_distribution)
        report.source_distribution = json.dumps(source_distribution)
        report.recommendations = json.dumps(recommendations)
        
        now = datetime.utcnow()
        if report.generated_at:
                delta = now - report.generated_at
                report.generation_time_seconds = int(delta.total_seconds())
                
        result = report.to_dict()

        # 4. Commit and Return
        self.db.session.add(report)
        self.db.session.commit()
        
        return result
    
    def _get_category_name(self, category_id: int) -> str:
        """Get category name from ID"""
        if not category_id:
            return "Uncategorized"
        
        category = self.db.session.query(InformationCategory).filter_by(id=category_id).first()
        return category.name if category else "Unknown Category"

    def _get_report(self, report_id: int) -> Report:
        """Get source name from ID"""
        source = self.db.session.query(Report).filter_by(report_id=report_id).first()
        return source

    def _get_user(self, user_id: int) -> str:
        """Get source name from ID"""
        source = self.db.session.query(User).filter_by(id=user_id).first()
        return source

    def _get_source_name(self, source_id: int) -> str:
        """Get source name from ID"""
        source = self.db.session.query(DiscoverSource).filter_by(id=source_id).first()
        return source.name if source else "Unknown Source"

    def _generate_executive_summary(self, query: str, total_findings: int, risk_counts: dict, overall_risk_score: float) -> str:
        """Generate executive summary based on findings"""
        risk_level_desc = "Low"
        if overall_risk_score >= 4:
            risk_level_desc = "High"
        elif overall_risk_score >= 1.7:
            risk_level_desc = "Medium"
        
        summary = f"Digital footprint analysis for '{query}' reveals {total_findings} information pieces across multiple platforms. "
        summary += f"Overall risk level: {risk_level_desc} (score: {overall_risk_score:.2f}/10). "
        
        if risk_counts["high"] > 0:
            summary += f"Found {risk_counts['high']} high-risk items requiring immediate attention. "
        
        if risk_counts["medium"] > 0:
            summary += f"Identified {risk_counts['medium']} medium-risk items for review. "
        
        return summary

    def _generate_recommendations(self, risk_counts: dict, source_counts: dict) -> List[str]:
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