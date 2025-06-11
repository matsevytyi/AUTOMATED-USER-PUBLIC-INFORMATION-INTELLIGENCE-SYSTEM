from datetime import datetime

import os
import sys

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)
from backend.models import InformationPiece, DiscoverSource, InformationCategory, db

import re
from typing import List, Tuple

def parse_search_results_to_information_pieces(data, report_id=0):
    """
    Parse the nested search results data and create InformationPiece objects
    """
    information_pieces = []
    
    web_search_source_id = db.session.query(DiscoverSource).filter_by(name="General Web Search").first().id
    platform_scraping_source_id = db.session.query(DiscoverSource).filter_by(name="Social Media").first().id
    
    # flatten the  structure and process each item
    for sublist in data:

        if isinstance(sublist, list):
            for item in sublist:
                if isinstance(item, str) and item.strip():
                    # simple string - facebook scraping
                    info_piece = create_string_information_piece(item, web_search_source_id, report_id)
                    if info_piece:
                        information_pieces.append(info_piece)
                        
                elif isinstance(item, dict):
                    #  structured search results - general web search
                    info_piece = create_dict_information_piece(item, platform_scraping_source_id, report_id)
                    if info_piece:
                        information_pieces.append(info_piece)
    
    # Save all infopieces to database
    for piece in information_pieces:
        db.session.add(piece)
    
    db.session.commit()
    return information_pieces

# helper conversion functions
def create_string_information_piece(content, source_id, report_id):
    """Create InformationPiece from string content"""
    
    return InformationPiece(
        report_id=report_id,
        source_id=source_id,
        source="facebook.com",
        content=content.strip(),
        created_at=datetime.utcnow()
    )

def create_dict_information_piece(item_dict, source_id, report_id):
    """Create InformationPiece from dictionary data"""
    
    # Extract information from the dictionary
    title = item_dict.get('title', '')
    link = item_dict.get('link', '')
    valuable_text = item_dict.get('valuable_text', '')
    
    valuable_text += title
    
    if not valuable_text:
        return
    
    return InformationPiece(
        report_id=report_id,
        source_id=source_id,
        source=link,
        content=valuable_text.strip(),
        created_at=datetime.utcnow()
    )
    
# data extraction functions

def extract_entities_from_data(datapiece: str) -> List[Tuple[str, str]]:
    relevant_data = []

    # 1. Emails
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', datapiece)
    relevant_data.extend([(email, 'email') for email in emails])

    # 2. Phone numbers (very basic pattern)
    phones = re.findall(r'(\+?\d[\d\-\s()]{7,}\d)', datapiece)
    relevant_data.extend([(phone, 'phone') for phone in phones])

    # 3. Social media (usernames or links)
    social = re.findall(r' @\S+', datapiece)
    relevant_data.extend([(item, 'social_media') for item in social])
    
    # 4. Location

    # 5. Financial info (keywords or patterns like $1000, UAH, etc.)
    financial = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\b(?:UAH|EUR|USD|грн|долар|євро|$|€|£|)\b', datapiece)
    relevant_data.extend([(fin, 'financial_info') for fin in financial])

    # 6. Professional titles (simple keyword match)
    professions = ['CEO', 'founder', 'developer', 'manager', 'engineer', 'analyst', 'specialist', 'student']
    for prof in professions:
        if re.search(r'\b' + re.escape(prof) + r'\b', datapiece, re.IGNORECASE):
            relevant_data.append((prof, 'professional_details'))

    # 7. Public statements (e.g., quotes or keywords like "said", "tweeted")
    if re.search(r'\b(said|stated|tweeted|posted|commented)\b', datapiece, re.IGNORECASE):
        relevant_data.append((datapiece, 'public_statement'))

    # 8. Social connections (e.g., mentioned names or family roles), organisations
    names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', datapiece)
    relevant_data.extend([(name, 'person') for name in names])

    # 9. Other personal identifiers (passport, ID, etc. — extend as needed)
    identifiers = re.findall(r'\bID[:\s]*\d+|passport[:\s]*\w+\d+', datapiece, re.IGNORECASE)
    relevant_data.extend([(id_val, 'personal_identifier') for id_val in identifiers])

    return relevant_data

a = [['Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], [], [{'title': 'CSC Hackathon 2023. Як це було. « Hackathon Expert Group', 'link': 'https://www.hackathon.expert/csc-hackathon-2023-report/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Щодо задачі з визначення міри подібності зображень, яку надала компанія ЛУН – перемогла командаCringe Minimizers(Антон Бражний, Андрій Мацевитий , Артем Орловський та Віталій Бутко, студенти Київського політехнічного інституту імені Ігоря Сікорського, Українського католицького університету у Львові та Вільнюского університету).Саме вони утримували першу позицію у приватному лідерборді практично від початку змагання. Разом з тим, ще дві команди,Team GARCH(Андрій Єрко, Андрій Шевцов, Нікіта Фордуі, Софія Шапошнікова, що також не вперше беруть участь у наших хакатонах) та вже згаданаSarcastic AI теж запропонували досить цікаві рішення, розділивши першу позицію з переможцями на публічному лідерборді.'}, {'title': 'Інститут проблем машинобудування імені А. М. Підгорного НАН ...', 'link': 'https://uk.wikipedia.org/wiki/%D0%86%D0%BD%D1%81%D1%82%D0%B8%D1%82%D1%83%D1%82_%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC_%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%BE%D0%B1%D1%83%D0%B4%D1%83%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F_%D1%96%D0%BC%D0%B5%D0%BD%D1%96_%D0%90._%D0%9C._%D0%9F%D1%96%D0%B4%D0%B3%D0%BE%D1%80%D0%BD%D0%BE%D0%B3%D0%BE_%D0%9D%D0%90%D0%9D_%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': ' Юрій Мацевитий, Андрій Русанов, Віктор Соловей, Микола Шульженко, Володимир Голощапов, Павло Гонтаровський, Андрій Костіков, Вадим Цибулько за роботу «Підвищення енергоефективності роботи турбоустановок ТЕС і ТЕЦ шляхом модернізації, реконструкції та удосконалення режимів їхньої експлуатації» отрималиДержавну премію України в галузі науки і техніки 2008 року "Лауреати Державної премії України в галузі науки і техніки \\(2008\\)").'}, {'title': 'Члени Академії – Інститут енергетичних машин і систем ім. А.М ...', 'link': 'https://ipmach.kharkov.ua/%D1%87%D0%BB%D0%B5%D0%BD%D0%B8-%D0%B0%D0%BA%D0%B0%D0%B4%D0%B5%D0%BC%D1%96%D1%97/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'КОСТІКОВ Андрій Олегович · КРАВЧЕНКО Олег Вікторович · МАЦЕВИТИЙ Юрій Михайлович · ПІДГОРНИЙ Анатолій Миколайович · ПРОСКУРА Георгій Федорович · РВАЧОВ\xa0...'}, {'title': 'Наша гордість - Спеціалізована школа І -ІІІ ступенів №251 імені ...', 'link': 'http://school251.edukit.kiev.ua/nasha_gordistj/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'І. 42. ІІ, Мацевитий Андрій, Українська мова, 4-В, Герасимчук Л.І. 43. ІІІ, Мацевитий Андрій, Англійська мова, 4-В, Ільєнко Т.В. Переможці міського етапу\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного', 'link': 'https://www.nas.gov.ua/institutions/institut-energeticnix-masin-i-sistem-im-a-m-pidgornogo-131', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Русанов Андрій Вікторович. академік НАН України. Радник при дирекції. Мацевитий Юрій Михайлович. академік НАН України. Заступник директора з наукової роботи.'}, {'title': 'освітній ступінь бакалавр факультет інформатики спеціальність ...', 'link': 'https://www.ukma.edu.ua/index.php/about-us/sogodennya/dokumenty-naukma/doc_download/3927-fakultet-informatyky', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Андрій Володимирович. 79.98. 26. Пілат Михайло Іванович. 79.87. 27. Молчанов Олексій Костянтинович. 78.38. 28. Нестерук Олена Олександрівна. 77.91. 29\xa0...'}, {'title': '03534570 — ІЕМС НАН України', 'link': 'https://opendatabot.ua/c/03534570', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Переглянути повну інформацію про юридичну особу ІНСТИТУТ ЕНЕРГЕТИЧНИХ МАШИН І СИСТЕМ ІМ. А. М. ПІДГОРНОГО НАЦІОНАЛЬНОЇ АКАДЕМІЇ НАУК УКРАЇНИ. Компанія ІЕМС НАН України зареєстрована — 10.05.1993. Керівник компанії — Русанов Андрій Вікторович. Юрідична адреса компанії ІЕМС НАН України: Україна, 61046, Харківська обл., місто Харків, вул.Комунальників, будинок 2/10. Основний КВЕД юридичної особи — 71.20 Технічні випробування та дослідження. Номер свідоцтва про реєстрацію платника податку на додану вартість - 035345720371. За 2020 ІЕМС НАН України отримала виторг на суму 37 105 783 ₴ гривень'}, {'title': 'Відділення енергетики та енергетичних технологій НАН України', 'link': 'https://www.nas.gov.ua/structure/section-physical-technical-mathematical-sciences/department-energy-and-energy-technologies', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Жаркін Андрій Федорович. академік НАН України. Кириленко Олександр Васильович. академік НАН України. Кулик Михайло Миколайович. академік НАН України. Мацевитий\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного НАН ...', 'link': 'https://old.nas.gov.ua/UA//Org/Pages/default.aspx?OrgID=0000299', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Юрій Михайлович. Почесний директор. Matsevity@nas.gov.ua. +38 0572 94 55 14. Русанов Андрій Вікторович. Директор. Rusanov.A.V@nas.gov.ua. +\xa0...'}, {'title': 'Лікар Васильцов Ігор Анатолійович, записатися на онлайн ...', 'link': 'https://e-likari.com.ua/doctor/vasilcov-igor-anatoliiovic/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Дякую! Волик Андрій. (5). 05.01.2025. Вдячний лікарю за консультацію ... Мацевитий Ернест Валерійович. (5). 10.04.2025. Анонімний відгук. (4). 09.04.2025.'}]]
for sub_a in a:
    for item in sub_a:
        print(type(item))
        if type(item) == dict and item.get('valuable_text'):
            item = item.get('valuable_text')
        print("="*20)
        print("evaluating:", item)
        print(extract_entities_from_data(item))