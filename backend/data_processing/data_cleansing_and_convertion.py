from datetime import datetime
from transformers import pipeline

import os
import sys

models_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
sys.path.append(models_path)
from backend.models import InformationPiece, DiscoverSource, InformationCategory, Report

from backend.data_processing.formulas import total_relevance_score

import re
from typing import List, Tuple

model_name = "Davlan/bert-base-multilingual-cased-ner-hrl"
nlp = pipeline("ner", model=model_name, grouped_entities=True)
categories_and_weights = {}

CATEGORY_WEIGHTS = {
    'contact_info': 9,
    'financial_info': 10,
    'professional': 5,
    'location': 9,
    'social_connections': 5,
    'public_statement': 5,
    'personal_identifier': 10,
}


def parse_search_results_to_information_pieces(data, report_id, db):
    """
    Parse the nested search results data and create InformationPiece objects
    """
    information_pieces = []

    # obtain source ids
    web_search_source_id = get_or_create_source(db=db, name="Web Search")
    platform_scraping_source_id = get_or_create_source(db=db, name="Social Media")
    
    report_query = db.session.query(Report).filter_by(report_id=report_id).first().user_query
    
    # flatten the  structure and process each item
    for sublist in data:

        if isinstance(sublist, list):
            for item in sublist:
                if isinstance(item, str) and item.strip():
                    # simple string - facebook scraping
                    info_piece = multiple_create_string_information_piece(db, item, platform_scraping_source_id, report_id, report_query)
                    if info_piece:
                        information_pieces.extend(info_piece)
                        
                elif isinstance(item, dict):
                    #  structured search results - general web search
                    info_piece = multiple_create_dict_information_piece(db, item, web_search_source_id, report_id, report_query)
                    if info_piece:
                        information_pieces.extend(info_piece)
    
    # Save all infopieces to database
    print(f"Saving {len(information_pieces)} information pieces to database")
    for piece in information_pieces:
        db.session.add(piece)
    
    db.session.commit()
    return information_pieces

# helper conversion functions

def multiple_create_string_information_piece(db, content, source_id, report_id, report_query) -> List[InformationPiece]: # facebook
    
    """Create InformationPiece from string content"""
    
    result = []
    
    extracted_content = extract_entities_from_data(content)
    
    for item in extracted_content:
        if len(item[0]) > 0:
            
            # TODO: pass facebook search request/profile from fbn scraping
            info_piece = create_string_information_piece(db, item[0], source_id, report_id, category_name = item[1], source="https://www.facebook.com", snippet=content, report_query=report_query)
            
            if info_piece:
                result.append(info_piece)
    
    return result

def multiple_create_dict_information_piece(db, item_dict, source_id, report_id, report_query): # web search
    """Create InformationPiece from dictionary data"""
    
    result = []

    # Extract information from the dictionary
    if type(item_dict) == dict and item_dict.get('valuable_text'):
        title = item_dict.get('title', '')
        link = item_dict.get('link', '')
        valuable_text = item_dict.get('valuable_text', '')
        
        valuable_text += title
    else:
        return
    
    extracted_content = extract_entities_from_data(valuable_text)
    
    for item in extracted_content:
        if len(item[0]) > 0:
            
            info_piece = create_string_information_piece(db, item[0], source_id, report_id, category_name = item[1], source=link, snippet=valuable_text, report_query=report_query)
            
            if info_piece:
                result.append(info_piece)
    
    return result
    

def create_string_information_piece(db, content, source_id, report_id, category_name = None,  source="facebook.com", snippet=None, report_query=None) -> InformationPiece:
    """Create InformationPiece from string content"""
    
    category_id, type_weight = get_or_create_category(db, name=category_name)
    
    relevance_score = total_relevance_score(user_query=report_query, extracted_content=content, extracted_context=snippet or "")
    
    relevance_score *= type_weight
    
    print("creating info piece for content:", content, "with score:", relevance_score)
    
    return InformationPiece(
        report_id=report_id,
        source_id=source_id,
        category_id=category_id,
        relevance_score=relevance_score,
        source=source,
        content=content.strip(),
        created_at=datetime.utcnow(),
        snippet=snippet
    )
    
# data extraction functions

def extract_entities_from_data(datapiece: str) -> List[Tuple[str, str]]:
    relevant_data = []
    
    # 1. Named Entity Recognition
    entities = nlp(datapiece)
    for entity in entities:
        
        # group and sort by entities
        if entity.get("entity_group"):
            if entity.get("entity_group") == "PER":
                entity_type = "social_connections"
            elif entity.get("entity_group") == "ORG":
                entity_type = "professional"
            elif entity.get("entity_group") == "LOC":
                entity_type = "location"
            else: 
                continue
        
        # keep extracted velue    
        if entity.get("word"):
            word = entity.get("word")
            word = word.replace("#", "")
            
            # manual rules to reduce false positives
            if entity_type == "social_connections" and not " " in word:
                continue
            
            if len(word) > 2:
                relevant_data.append((word, entity_type))

    # 2. Emails
    emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', datapiece)
    relevant_data.extend([(email, 'contact_info') for email in emails])
    
    # 3. Financial info (keywords or patterns like $1000, UAH, etc.)
    financial = re.findall(r'\$\d+(?:,\d{3})*(?:\.\d{2})?|\b(?:UAH|EUR|USD|грн|долар|євро|euro|buck|dollar|$|€|£)\b', datapiece)
    relevant_data.extend([(fin, 'financial_info') for fin in financial])

    # 4. Phone numbers (with extended cases support)
    phones = re.findall(r'(\+?\d[\d\-\s()]{7,}\d)', datapiece)
    relevant_data.extend([(phone, 'contact_info') for phone in phones])

    # 5. Social media (usernames or links)
    social = re.findall(r' @\S+', datapiece)
    relevant_data.extend([(item, 'contact_info') for item in social])
    
    # 6. Professional titles (simple keyword match)
    professions = ['CEO', 'founder', 'developer', 'manager', 'engineer', 'analyst', 'specialist', 'student']
    for prof in professions:
        if re.search(r'\b' + re.escape(prof) + r'\b', datapiece, re.IGNORECASE):
            relevant_data.append((prof, 'professional'))

    # 7. Public statements (e.g., quotes or keywords like "said", "tweeted")
    if re.search(r'\b(said|stated|tweeted|posted|commented)\b', datapiece, re.IGNORECASE):
        relevant_data.append((datapiece, 'public_statement'))

    # 9. Other personal identifiers (passport, ID, etc. — extend as needed)
    identifiers = re.findall(r'\bID[:\s]*\d+|passport[:\s]*\w+\d+', datapiece, re.IGNORECASE)
    relevant_data.extend([(id_val, 'personal_identifier') for id_val in identifiers])

    return relevant_data


# helper function to handle new catefories added/obtained on the fly
def get_or_create_category(db, name, description=None):
    """
    Get existing category (from cache if available) or create a new one if it doesn't exist.
    Returns: (category_id, weight)
    """
    if name in categories_and_weights:
        return categories_and_weights[name]

    print(f"Creating new category: {name}")
    category = db.session.query(InformationCategory).filter_by(name=name).first()

    if category is None:
        
        weight = CATEGORY_WEIGHTS.get(name, 0.5)
        
        category = InformationCategory(
            name=name,
            description=description or f"Auto-created category: {name}",
            weight=weight
        )
        print(f"Created new category: {name}")
        db.session.add(category)
        db.session.flush()  # So we can access category.id and category.weight

    # Update cache
    categories_and_weights[name] = (category.id, category.weight)
    return category.id, category.weight

# helper function to handle new sources additions on the fly
def get_or_create_source(db, name, description=None):
    """
    Get existing source or create new one if it doesn't exist
    """
    print(f"Creating new source: {name}")
    source = db.session.query(DiscoverSource).filter_by(name=name).first()
    
    if source is None:
        # Create new source if it doesn't exist
        source = DiscoverSource(
            name=name,
            description=description or f"Auto-created source: {name}"
        )
        print(f"Created new source: {name}")
        db.session.add(source)
        db.session.flush()  # Get the ID without committing the transaction
    
    return source.id

# example of usage of feature extraction
# a = [['Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 
# 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 
# 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com'], 
# ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], 
# ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], [], [{'title': 'CSC Hackathon 2023. Як це було. « Hackathon Expert Group', 'link': 'https://www.hackathon.expert/csc-hackathon-2023-report/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Щодо задачі з визначення міри подібності зображень, яку надала компанія ЛУН – перемогла командаCringe Minimizers(Антон Бражний, Андрій Мацевитий , Артем Орловський та Віталій Бутко, студенти Київського політехнічного інституту імені Ігоря Сікорського, Українського католицького університету у Львові та Вільнюского університету).Саме вони утримували першу позицію у приватному лідерборді практично від початку змагання. Разом з тим, ще дві команди,Team GARCH(Андрій Єрко, Андрій Шевцов, Нікіта Фордуі, Софія Шапошнікова, що також не вперше беруть участь у наших хакатонах) та вже згаданаSarcastic AI теж запропонували досить цікаві рішення, розділивши першу позицію з переможцями на публічному лідерборді.'}, {'title': 'Інститут проблем машинобудування імені А. М. Підгорного НАН ...', 'link': 'https://uk.wikipedia.org/wiki/%D0%86%D0%BD%D1%81%D1%82%D0%B8%D1%82%D1%83%D1%82_%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC_%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%BE%D0%B1%D1%83%D0%B4%D1%83%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F_%D1%96%D0%BC%D0%B5%D0%BD%D1%96_%D0%90._%D0%9C._%D0%9F%D1%96%D0%B4%D0%B3%D0%BE%D1%80%D0%BD%D0%BE%D0%B3%D0%BE_%D0%9D%D0%90%D0%9D_%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': ' Юрій Мацевитий, Андрій Русанов, Віктор Соловей, Микола Шульженко, Володимир Голощапов, Павло Гонтаровський, Андрій Костіков, Вадим Цибулько за роботу «Підвищення енергоефективності роботи турбоустановок ТЕС і ТЕЦ шляхом модернізації, реконструкції та удосконалення режимів їхньої експлуатації» отрималиДержавну премію України в галузі науки і техніки 2008 року "Лауреати Державної премії України в галузі науки і техніки \\(2008\\)").'}, {'title': 'Члени Академії – Інститут енергетичних машин і систем ім. А.М ...', 'link': 'https://ipmach.kharkov.ua/%D1%87%D0%BB%D0%B5%D0%BD%D0%B8-%D0%B0%D0%BA%D0%B0%D0%B4%D0%B5%D0%BC%D1%96%D1%97/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'КОСТІКОВ Андрій Олегович · КРАВЧЕНКО Олег Вікторович · МАЦЕВИТИЙ Юрій Михайлович · ПІДГОРНИЙ Анатолій Миколайович · ПРОСКУРА Георгій Федорович · РВАЧОВ\xa0...'}, {'title': 'Наша гордість - Спеціалізована школа І -ІІІ ступенів №251 імені ...', 'link': 'http://school251.edukit.kiev.ua/nasha_gordistj/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'І. 42. ІІ, Мацевитий Андрій, Українська мова, 4-В, Герасимчук Л.І. 43. ІІІ, Мацевитий Андрій, Англійська мова, 4-В, Ільєнко Т.В. Переможці міського етапу\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного', 'link': 'https://www.nas.gov.ua/institutions/institut-energeticnix-masin-i-sistem-im-a-m-pidgornogo-131', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Русанов Андрій Вікторович. академік НАН України. Радник при дирекції. Мацевитий Юрій Михайлович. академік НАН України. Заступник директора з наукової роботи.'}, {'title': 'освітній ступінь бакалавр факультет інформатики спеціальність ...', 'link': 'https://www.ukma.edu.ua/index.php/about-us/sogodennya/dokumenty-naukma/doc_download/3927-fakultet-informatyky', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Андрій Володимирович. 79.98. 26. Пілат Михайло Іванович. 79.87. 27. Молчанов Олексій Костянтинович. 78.38. 28. Нестерук Олена Олександрівна. 77.91. 29\xa0...'}, {'title': '03534570 — ІЕМС НАН України', 'link': 'https://opendatabot.ua/c/03534570', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Переглянути повну інформацію про юридичну особу ІНСТИТУТ ЕНЕРГЕТИЧНИХ МАШИН І СИСТЕМ ІМ. А. М. ПІДГОРНОГО НАЦІОНАЛЬНОЇ АКАДЕМІЇ НАУК УКРАЇНИ. Компанія ІЕМС НАН України зареєстрована — 10.05.1993. Керівник компанії — Русанов Андрій Вікторович. Юрідична адреса компанії ІЕМС НАН України: Україна, 61046, Харківська обл., місто Харків, вул.Комунальників, будинок 2/10. Основний КВЕД юридичної особи — 71.20 Технічні випробування та дослідження. Номер свідоцтва про реєстрацію платника податку на додану вартість - 035345720371. За 2020 ІЕМС НАН України отримала виторг на суму 37 105 783 ₴ гривень'}, {'title': 'Відділення енергетики та енергетичних технологій НАН України', 'link': 'https://www.nas.gov.ua/structure/section-physical-technical-mathematical-sciences/department-energy-and-energy-technologies', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Жаркін Андрій Федорович. академік НАН України. Кириленко Олександр Васильович. академік НАН України. Кулик Михайло Миколайович. академік НАН України. Мацевитий\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного НАН ...', 'link': 'https://old.nas.gov.ua/UA//Org/Pages/default.aspx?OrgID=0000299', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Юрій Михайлович. Почесний директор. Matsevity@nas.gov.ua. +38 0572 94 55 14. Русанов Андрій Вікторович. Директор. Rusanov.A.V@nas.gov.ua. +\xa0...'}, {'title': 'Лікар Васильцов Ігор Анатолійович, записатися на онлайн ...', 'link': 'https://e-likari.com.ua/doctor/vasilcov-igor-anatoliiovic/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Дякую! Волик Андрій. (5). 05.01.2025. Вдячний лікарю за консультацію ... Мацевитий Ернест Валерійович. (5). 10.04.2025. Анонімний відгук. (4). 09.04.2025.'}]]

# result = []

# for sub_a in a:
#     for item in sub_a:
#         if type(item) == dict and item.get('valuable_text'):
#             item = item.get('valuable_text')
#         result.append(extract_entities_from_data(item))
        
# print(result)

# example of overall usage

# a = [['Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], [], [{'title': 'CSC Hackathon 2023. Як це було. « Hackathon Expert Group', 'link': 'https://www.hackathon.expert/csc-hackathon-2023-report/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Щодо задачі з визначення міри подібності зображень, яку надала компанія ЛУН – перемогла командаCringe Minimizers(Антон Бражний, Андрій Мацевитий , Артем Орловський та Віталій Бутко, студенти Київського політехнічного інституту імені Ігоря Сікорського, Українського католицького університету у Львові та Вільнюского університету).Саме вони утримували першу позицію у приватному лідерборді практично від початку змагання. Разом з тим, ще дві команди,Team GARCH(Андрій Єрко, Андрій Шевцов, Нікіта Фордуі, Софія Шапошнікова, що також не вперше беруть участь у наших хакатонах) та вже згаданаSarcastic AI теж запропонували досить цікаві рішення, розділивши першу позицію з переможцями на публічному лідерборді.'}, {'title': 'Інститут проблем машинобудування імені А. М. Підгорного НАН ...', 'link': 'https://uk.wikipedia.org/wiki/%D0%86%D0%BD%D1%81%D1%82%D0%B8%D1%82%D1%83%D1%82_%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC_%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%BE%D0%B1%D1%83%D0%B4%D1%83%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F_%D1%96%D0%BC%D0%B5%D0%BD%D1%96_%D0%90._%D0%9C._%D0%9F%D1%96%D0%B4%D0%B3%D0%BE%D1%80%D0%BD%D0%BE%D0%B3%D0%BE_%D0%9D%D0%90%D0%9D_%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': ' Юрій Мацевитий, Андрій Русанов, Віктор Соловей, Микола Шульженко, Володимир Голощапов, Павло Гонтаровський, Андрій Костіков, Вадим Цибулько за роботу «Підвищення енергоефективності роботи турбоустановок ТЕС і ТЕЦ шляхом модернізації, реконструкції та удосконалення режимів їхньої експлуатації» отрималиДержавну премію України в галузі науки і техніки 2008 року "Лауреати Державної премії України в галузі науки і техніки \\(2008\\)").'}, {'title': 'Члени Академії – Інститут енергетичних машин і систем ім. А.М ...', 'link': 'https://ipmach.kharkov.ua/%D1%87%D0%BB%D0%B5%D0%BD%D0%B8-%D0%B0%D0%BA%D0%B0%D0%B4%D0%B5%D0%BC%D1%96%D1%97/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'КОСТІКОВ Андрій Олегович · КРАВЧЕНКО Олег Вікторович · МАЦЕВИТИЙ Юрій Михайлович · ПІДГОРНИЙ Анатолій Миколайович · ПРОСКУРА Георгій Федорович · РВАЧОВ\xa0...'}, {'title': 'Наша гордість - Спеціалізована школа І -ІІІ ступенів №251 імені ...', 'link': 'http://school251.edukit.kiev.ua/nasha_gordistj/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'І. 42. ІІ, Мацевитий Андрій, Українська мова, 4-В, Герасимчук Л.І. 43. ІІІ, Мацевитий Андрій, Англійська мова, 4-В, Ільєнко Т.В. Переможці міського етапу\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного', 'link': 'https://www.nas.gov.ua/institutions/institut-energeticnix-masin-i-sistem-im-a-m-pidgornogo-131', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Русанов Андрій Вікторович. академік НАН України. Радник при дирекції. Мацевитий Юрій Михайлович. академік НАН України. Заступник директора з наукової роботи.'}, {'title': 'освітній ступінь бакалавр факультет інформатики спеціальність ...', 'link': 'https://www.ukma.edu.ua/index.php/about-us/sogodennya/dokumenty-naukma/doc_download/3927-fakultet-informatyky', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Андрій Володимирович. 79.98. 26. Пілат Михайло Іванович. 79.87. 27. Молчанов Олексій Костянтинович. 78.38. 28. Нестерук Олена Олександрівна. 77.91. 29\xa0...'}, {'title': '03534570 — ІЕМС НАН України', 'link': 'https://opendatabot.ua/c/03534570', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Переглянути повну інформацію про юридичну особу ІНСТИТУТ ЕНЕРГЕТИЧНИХ МАШИН І СИСТЕМ ІМ. А. М. ПІДГОРНОГО НАЦІОНАЛЬНОЇ АКАДЕМІЇ НАУК УКРАЇНИ. Компанія ІЕМС НАН України зареєстрована — 10.05.1993. Керівник компанії — Русанов Андрій Вікторович. Юрідична адреса компанії ІЕМС НАН України: Україна, 61046, Харківська обл., місто Харків, вул.Комунальників, будинок 2/10. Основний КВЕД юридичної особи — 71.20 Технічні випробування та дослідження. Номер свідоцтва про реєстрацію платника податку на додану вартість - 035345720371. За 2020 ІЕМС НАН України отримала виторг на суму 37 105 783 ₴ гривень'}, {'title': 'Відділення енергетики та енергетичних технологій НАН України', 'link': 'https://www.nas.gov.ua/structure/section-physical-technical-mathematical-sciences/department-energy-and-energy-technologies', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Жаркін Андрій Федорович. академік НАН України. Кириленко Олександр Васильович. академік НАН України. Кулик Михайло Миколайович. академік НАН України. Мацевитий\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного НАН ...', 'link': 'https://old.nas.gov.ua/UA//Org/Pages/default.aspx?OrgID=0000299', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Юрій Михайлович. Почесний директор. Matsevity@nas.gov.ua. +38 0572 94 55 14. Русанов Андрій Вікторович. Директор. Rusanov.A.V@nas.gov.ua. +\xa0...'}, {'title': 'Лікар Васильцов Ігор Анатолійович, записатися на онлайн ...', 'link': 'https://e-likari.com.ua/doctor/vasilcov-igor-anatoliiovic/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Дякую! Волик Андрій. (5). 05.01.2025. Вдячний лікарю за консультацію ... Мацевитий Ернест Валерійович. (5). 10.04.2025. Анонімний відгук. (4). 09.04.2025.'}]]

# parse_search_results_to_information_pieces(a, report_id=0)