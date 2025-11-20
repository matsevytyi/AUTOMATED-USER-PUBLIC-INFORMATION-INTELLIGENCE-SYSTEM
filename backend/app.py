import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))


from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import bcrypt
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from scheduled import start_scheduler

from config import Config
from models import db, User, Report, SearchHistory, FacebookCookies
from data_processing.data_cleansing_and_convertion import parse_search_results_to_information_pieces

from report_generation.generate_report import init_report, generate_complete_report
from data_collection.data_collection_wrapper import collect_data

from facebook_cookie_manager import FacebookCookieManager

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["DEBUG"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = True
    
    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    CORS(app)
    
    start_scheduler(db)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app

app = create_app()

# with app.app_context():
#     a = [['Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], [], [{'title': 'CSC Hackathon 2023. Як це було. « Hackathon Expert Group', 'link': 'https://www.hackathon.expert/csc-hackathon-2023-report/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Щодо задачі з визначення міри подібності зображень, яку надала компанія ЛУН – перемогла командаCringe Minimizers(Антон Бражний, Андрій Мацевитий , Артем Орловський та Віталій Бутко, студенти Київського політехнічного інституту імені Ігоря Сікорського, Українського католицького університету у Львові та Вільнюского університету).Саме вони утримували першу позицію у приватному лідерборді практично від початку змагання. Разом з тим, ще дві команди,Team GARCH(Андрій Єрко, Андрій Шевцов, Нікіта Фордуі, Софія Шапошнікова, що також не вперше беруть участь у наших хакатонах) та вже згаданаSarcastic AI теж запропонували досить цікаві рішення, розділивши першу позицію з переможцями на публічному лідерборді.'}, {'title': 'Інститут проблем машинобудування імені А. М. Підгорного НАН ...', 'link': 'https://uk.wikipedia.org/wiki/%D0%86%D0%BD%D1%81%D1%82%D0%B8%D1%82%D1%83%D1%82_%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC_%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%BE%D0%B1%D1%83%D0%B4%D1%83%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F_%D1%96%D0%BC%D0%B5%D0%BD%D1%96_%D0%90._%D0%9C._%D0%9F%D1%96%D0%B4%D0%B3%D0%BE%D1%80%D0%BD%D0%BE%D0%B3%D0%BE_%D0%9D%D0%90%D0%9D_%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': ' Юрій Мацевитий, Андрій Русанов, Віктор Соловей, Микола Шульженко, Володимир Голощапов, Павло Гонтаровський, Андрій Костіков, Вадим Цибулько за роботу «Підвищення енергоефективності роботи турбоустановок ТЕС і ТЕЦ шляхом модернізації, реконструкції та удосконалення режимів їхньої експлуатації» отрималиДержавну премію України в галузі науки і техніки 2008 року "Лауреати Державної премії України в галузі науки і техніки \\(2008\\)").'}, {'title': 'Члени Академії – Інститут енергетичних машин і систем ім. А.М ...', 'link': 'https://ipmach.kharkov.ua/%D1%87%D0%BB%D0%B5%D0%BD%D0%B8-%D0%B0%D0%BA%D0%B0%D0%B4%D0%B5%D0%BC%D1%96%D1%97/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'КОСТІКОВ Андрій Олегович · КРАВЧЕНКО Олег Вікторович · МАЦЕВИТИЙ Юрій Михайлович · ПІДГОРНИЙ Анатолій Миколайович · ПРОСКУРА Георгій Федорович · РВАЧОВ\xa0...'}, {'title': 'Наша гордість - Спеціалізована школа І -ІІІ ступенів №251 імені ...', 'link': 'http://school251.edukit.kiev.ua/nasha_gordistj/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'І. 42. ІІ, Мацевитий Андрій, Українська мова, 4-В, Герасимчук Л.І. 43. ІІІ, Мацевитий Андрій, Англійська мова, 4-В, Ільєнко Т.В. Переможці міського етапу\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного', 'link': 'https://www.nas.gov.ua/institutions/institut-energeticnix-masin-i-sistem-im-a-m-pidgornogo-131', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Русанов Андрій Вікторович. академік НАН України. Радник при дирекції. Мацевитий Юрій Михайлович. академік НАН України. Заступник директора з наукової роботи.'}, {'title': 'освітній ступінь бакалавр факультет інформатики спеціальність ...', 'link': 'https://www.ukma.edu.ua/index.php/about-us/sogodennya/dokumenty-naukma/doc_download/3927-fakultet-informatyky', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Андрій Володимирович. 79.98. 26. Пілат Михайло Іванович. 79.87. 27. Молчанов Олексій Костянтинович. 78.38. 28. Нестерук Олена Олександрівна. 77.91. 29\xa0...'}, {'title': '03534570 — ІЕМС НАН України', 'link': 'https://opendatabot.ua/c/03534570', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Переглянути повну інформацію про юридичну особу ІНСТИТУТ ЕНЕРГЕТИЧНИХ МАШИН І СИСТЕМ ІМ. А. М. ПІДГОРНОГО НАЦІОНАЛЬНОЇ АКАДЕМІЇ НАУК УКРАЇНИ. Компанія ІЕМС НАН України зареєстрована — 10.05.1993. Керівник компанії — Русанов Андрій Вікторович. Юрідична адреса компанії ІЕМС НАН України: Україна, 61046, Харківська обл., місто Харків, вул.Комунальників, будинок 2/10. Основний КВЕД юридичної особи — 71.20 Технічні випробування та дослідження. Номер свідоцтва про реєстрацію платника податку на додану вартість - 035345720371. За 2020 ІЕМС НАН України отримала виторг на суму 37 105 783 ₴ гривень'}, {'title': 'Відділення енергетики та енергетичних технологій НАН України', 'link': 'https://www.nas.gov.ua/structure/section-physical-technical-mathematical-sciences/department-energy-and-energy-technologies', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Жаркін Андрій Федорович. академік НАН України. Кириленко Олександр Васильович. академік НАН України. Кулик Михайло Миколайович. академік НАН України. Мацевитий\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного НАН ...', 'link': 'https://old.nas.gov.ua/UA//Org/Pages/default.aspx?OrgID=0000299', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Юрій Михайлович. Почесний директор. Matsevity@nas.gov.ua. +38 0572 94 55 14. Русанов Андрій Вікторович. Директор. Rusanov.A.V@nas.gov.ua. +\xa0...'}, {'title': 'Лікар Васильцов Ігор Анатолійович, записатися на онлайн ...', 'link': 'https://e-likari.com.ua/doctor/vasilcov-igor-anatoliiovic/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Дякую! Волик Андрій. (5). 05.01.2025. Вдячний лікарю за консультацію ... Мацевитий Ернест Валерійович. (5). 10.04.2025. Анонімний відгук. (4). 09.04.2025.'}]]

#     result = parse_search_results_to_information_pieces(a, report_id=0, db=db)
#     print("======================RESULT======================")
#     print(result)

@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Helper functions
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

# API Routes

# ------ AUTH ------
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        
        # Validation
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required.'}), 400
        
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters long.'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({'success': False, 'message': 'Email already registered.'}), 400
        
        # Create new user
        password_hash = hash_password(password)
        new_user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            confirmed=False  # Email confirmation required
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # In real app: send confirmation email here
        return jsonify({
            'success': True, 
            'message': 'Registration successful. Please check your email for confirmation instructions.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Registration failed. Please try again.'}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'success': False, 'message': 'Email and password are required.'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not verify_password(password, user.password_hash):
            return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401
        
        if not user.confirmed:
            return jsonify({'success': False, 'message': 'Please confirm your email before logging in.'}), 403
        
        # Create access token
        access_token = create_access_token(identity=email)
        
        return jsonify({
            'success': True,
            'message': 'Login successful.',
            'access_token': access_token,
            'user': {
                'email': user.email,
                'name': user.name
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Login failed. Please try again.'}), 500

@app.route('/api/confirm', methods=['POST'])
def confirm_email():
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        user.confirmed = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Email confirmed successfully. You can now log in.'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Email confirmation failed.'}), 500

# ------ SEARCH ------
@app.route('/api/search', methods=['POST'])
@jwt_required()
def search():
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404 #TODO: replace with mock results
        
        data = request.json
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({'success': False, 'message': 'Search query is required.'}), 400
        
        report_id = init_report(db=db, user_id=user.id, query=query)
        
        print("creating report with ID", report_id)

        # Load facebook cookies for current user (if any) and verify before scraping
        fb_cookies_obj = None
        try:
            fc = FacebookCookies.query.filter_by(user_email=current_user_email).first()
            if fc and fc.cookies_json:
                try:
                    fb_cookies_obj = json.loads(fc.cookies_json)
                except Exception:
                    fb_cookies_obj = None
        except Exception:
            fb_cookies_obj = None

        # Verify cookies are still valid
        fb_ok = False
        try:
            if fb_cookies_obj:
                fb_ok = FacebookCookieManager.verify_cookies_map(fb_cookies_obj)
        except Exception:
            fb_ok = False

        if fb_ok:
            raw_search_results = collect_data(query, cookie_map=fb_cookies_obj, uid=str(user.id))
        else:
            # proceed without facebook scraping if cookies missing/invalid
            raw_search_results = collect_data(query)
        
        # for debug purposes
        #raw_search_results = [['Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com', 'Hello, I am Andrew, 20 y.o., IT and sportsman, no bad habits. This summer I am having Mitacs internship in Carleton university. I am searching for furnished (!) accommodation from June 30th to September 25th. June 30th to August 31st also works. Looking for 700-800 CAD per month.Feel free to reach me in instagram @frean_090 or on email amatsevytyi@icloud.com'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], ['З днем народження!', 'З Днем народження!', 'Have a great birthday!'], [], [{'title': 'CSC Hackathon 2023. Як це було. « Hackathon Expert Group', 'link': 'https://www.hackathon.expert/csc-hackathon-2023-report/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Щодо задачі з визначення міри подібності зображень, яку надала компанія ЛУН – перемогла командаCringe Minimizers(Антон Бражний, Андрій Мацевитий , Артем Орловський та Віталій Бутко, студенти Київського політехнічного інституту імені Ігоря Сікорського, Українського католицького університету у Львові та Вільнюского університету).Саме вони утримували першу позицію у приватному лідерборді практично від початку змагання. Разом з тим, ще дві команди,Team GARCH(Андрій Єрко, Андрій Шевцов, Нікіта Фордуі, Софія Шапошнікова, що також не вперше беруть участь у наших хакатонах) та вже згаданаSarcastic AI теж запропонували досить цікаві рішення, розділивши першу позицію з переможцями на публічному лідерборді.'}, {'title': 'Інститут проблем машинобудування імені А. М. Підгорного НАН ...', 'link': 'https://uk.wikipedia.org/wiki/%D0%86%D0%BD%D1%81%D1%82%D0%B8%D1%82%D1%83%D1%82_%D0%BF%D1%80%D0%BE%D0%B1%D0%BB%D0%B5%D0%BC_%D0%BC%D0%B0%D1%88%D0%B8%D0%BD%D0%BE%D0%B1%D1%83%D0%B4%D1%83%D0%B2%D0%B0%D0%BD%D0%BD%D1%8F_%D1%96%D0%BC%D0%B5%D0%BD%D1%96_%D0%90._%D0%9C._%D0%9F%D1%96%D0%B4%D0%B3%D0%BE%D1%80%D0%BD%D0%BE%D0%B3%D0%BE_%D0%9D%D0%90%D0%9D_%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D0%B8', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': ' Юрій Мацевитий, Андрій Русанов, Віктор Соловей, Микола Шульженко, Володимир Голощапов, Павло Гонтаровський, Андрій Костіков, Вадим Цибулько за роботу «Підвищення енергоефективності роботи турбоустановок ТЕС і ТЕЦ шляхом модернізації, реконструкції та удосконалення режимів їхньої експлуатації» отрималиДержавну премію України в галузі науки і техніки 2008 року "Лауреати Державної премії України в галузі науки і техніки \\(2008\\)").'}, {'title': 'Члени Академії – Інститут енергетичних машин і систем ім. А.М ...', 'link': 'https://ipmach.kharkov.ua/%D1%87%D0%BB%D0%B5%D0%BD%D0%B8-%D0%B0%D0%BA%D0%B0%D0%B4%D0%B5%D0%BC%D1%96%D1%97/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'КОСТІКОВ Андрій Олегович · КРАВЧЕНКО Олег Вікторович · МАЦЕВИТИЙ Юрій Михайлович · ПІДГОРНИЙ Анатолій Миколайович · ПРОСКУРА Георгій Федорович · РВАЧОВ\xa0...'}, {'title': 'Наша гордість - Спеціалізована школа І -ІІІ ступенів №251 імені ...', 'link': 'http://school251.edukit.kiev.ua/nasha_gordistj/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'І. 42. ІІ, Мацевитий Андрій, Українська мова, 4-В, Герасимчук Л.І. 43. ІІІ, Мацевитий Андрій, Англійська мова, 4-В, Ільєнко Т.В. Переможці міського етапу\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного', 'link': 'https://www.nas.gov.ua/institutions/institut-energeticnix-masin-i-sistem-im-a-m-pidgornogo-131', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Русанов Андрій Вікторович. академік НАН України. Радник при дирекції. Мацевитий Юрій Михайлович. академік НАН України. Заступник директора з наукової роботи.'}, {'title': 'освітній ступінь бакалавр факультет інформатики спеціальність ...', 'link': 'https://www.ukma.edu.ua/index.php/about-us/sogodennya/dokumenty-naukma/doc_download/3927-fakultet-informatyky', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Андрій Володимирович. 79.98. 26. Пілат Михайло Іванович. 79.87. 27. Молчанов Олексій Костянтинович. 78.38. 28. Нестерук Олена Олександрівна. 77.91. 29\xa0...'}, {'title': '03534570 — ІЕМС НАН України', 'link': 'https://opendatabot.ua/c/03534570', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Переглянути повну інформацію про юридичну особу ІНСТИТУТ ЕНЕРГЕТИЧНИХ МАШИН І СИСТЕМ ІМ. А. М. ПІДГОРНОГО НАЦІОНАЛЬНОЇ АКАДЕМІЇ НАУК УКРАЇНИ. Компанія ІЕМС НАН України зареєстрована — 10.05.1993. Керівник компанії — Русанов Андрій Вікторович. Юрідична адреса компанії ІЕМС НАН України: Україна, 61046, Харківська обл., місто Харків, вул.Комунальників, будинок 2/10. Основний КВЕД юридичної особи — 71.20 Технічні випробування та дослідження. Номер свідоцтва про реєстрацію платника податку на додану вартість - 035345720371. За 2020 ІЕМС НАН України отримала виторг на суму 37 105 783 ₴ гривень'}, {'title': 'Відділення енергетики та енергетичних технологій НАН України', 'link': 'https://www.nas.gov.ua/structure/section-physical-technical-mathematical-sciences/department-energy-and-energy-technologies', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Жаркін Андрій Федорович. академік НАН України. Кириленко Олександр Васильович. академік НАН України. Кулик Михайло Миколайович. академік НАН України. Мацевитий\xa0...'}, {'title': 'Інститут енергетичних машин і систем ім. А. М. Підгорного НАН ...', 'link': 'https://old.nas.gov.ua/UA//Org/Pages/default.aspx?OrgID=0000299', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Мацевитий Юрій Михайлович. Почесний директор. Matsevity@nas.gov.ua. +38 0572 94 55 14. Русанов Андрій Вікторович. Директор. Rusanov.A.V@nas.gov.ua. +\xa0...'}, {'title': 'Лікар Васильцов Ігор Анатолійович, записатися на онлайн ...', 'link': 'https://e-likari.com.ua/doctor/vasilcov-igor-anatoliiovic/', 'bm25_filter': 'Андрій Мацевитий', 'valuable_text': 'Дякую! Волик Андрій. (5). 05.01.2025. Вдячний лікарю за консультацію ... Мацевитий Ернест Валерійович. (5). 10.04.2025. Анонімний відгук. (4). 09.04.2025.'}]]

        information_pieces = parse_search_results_to_information_pieces(
            data=raw_search_results, 
            report_id=report_id, 
            db=db
        )
        
        final_report = generate_complete_report(db=db, report_id=report_id, information_pieces=information_pieces)
        
        # Add to search history
        search_history = SearchHistory(
            user_id=user.id,
            user_query=query,
            report_id=report_id
        )
        
        db.session.add(search_history)
        db.session.commit()
        
        return jsonify({'success': True, 'report': final_report})
        
    except Exception as e:
        print(e)
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Search failed. Please try again.'}), 500

# ------------ Dashboard ------------
@app.route('/api/report/<report_id>', methods=['GET'])
@jwt_required()
def get_report(report_id):
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        report = Report.query.filter_by(report_id=report_id, user_id=user.id).first()
        if not report:
            return jsonify({'success': False, 'message': 'Report not found.'}), 404
        
        return jsonify({'success': True, 'report': report.to_dict()})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to retrieve report.'}), 500

@app.route('/api/history', methods=['GET'])
@jwt_required()
def get_search_history():
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        searches = SearchHistory.query.filter_by(user_id=user.id).order_by(SearchHistory.created_at.desc()).all()
        history = [search.to_dict() for search in searches]
        
        return jsonify({'success': True, 'history': history})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to retrieve search history.'}), 500

# ------------ Profile/settings ------------
@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404
        
        profile = {
            'email': user.email,
            'name': user.name,
            'confirmed': user.confirmed,
            'created_at': user.created_at.isoformat() + 'Z',
            'total_reports': len(user.reports),
            'total_searches': len(user.searches)
        }
        
        return jsonify({'success': True, 'profile': profile})
        
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to retrieve profile.'}), 500
 
 # ------------ Settings / Derived from profile ------------   
@app.route('/api/profile/facebook/cookies', methods=['POST'])
@jwt_required()
def update_facebook_cookies():
    data = request.json
    print("cookies received", data) 
    if not data or 'cookies_json' not in data:
        print('No data provided')
        return jsonify({'error': 'No data provided'}), 400

    try:
        cookies = json.loads(data['cookies_json'])
        assert all(k in cookies for k in ['c_user', 'xs'])
        print("cookies parsed", cookies)
    except Exception:
        return jsonify({'error': 'Invalid cookies format or missing c_user/xs'}), 400

    # Lightweight verification
    try:
        ok = FacebookCookieManager.verify_cookies_map(cookies)
    except Exception:
        ok = False
        
    print("cookies verification result:", ok)

    if not ok:
        return jsonify({'error': 'Provided cookies appear invalid or not authenticated.'}), 400

    expires_at = datetime.utcnow() + relativedelta(months=1)

    # Upsert cookies in DB
    current_user_email = get_jwt_identity()
    fc = FacebookCookies.query.filter_by(user_email=current_user_email).first()
    if not fc:
        fc = FacebookCookies(user_email=current_user_email, cookies_json=json.dumps(cookies), 
                             saved_at=datetime.utcnow(), expires_at=expires_at)
        db.session.add(fc)
    else:
        fc.cookies_json = json.dumps(cookies)
        fc.saved_at = datetime.utcnow()
        fc.expires_at = expires_at
    db.session.commit()
    
    print("cookies updated", cookies)

    return jsonify({'success': True}), 200

@app.route('/api/profile/facebook/cookies', methods=['GET'])
@jwt_required()
def get_facebook_cookies_status():
    fc = FacebookCookies.query.filter_by(user_email=get_jwt_identity()).first()
    now = datetime.utcnow()
    has_cookies = bool(fc)
    is_expired = fc.expires_at < now if fc and fc.expires_at else True
    
    return jsonify({
        'has_cookies': has_cookies, 
        'is_expired': is_expired
    }), 200

    
# ------------ Other Settings ------------

@app.route('/api/profile/password', methods=['POST'])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        data = request.json or {}

        old_password = data.get('current_password')
        new_password = data.get('new_password')

        if not old_password or not new_password:
            return jsonify({'success': False, 'message': 'Current and new passwords are required.'}), 400

        if len(new_password) < 8:
            return jsonify({'success': False, 'message': 'New password must be at least 8 characters long.'}), 400

        # Get current user from JWT
        current_user_email = get_jwt_identity()
        user = User.query.filter_by(email=current_user_email).first()
        if not user:
            return jsonify({'success': False, 'message': 'User not found.'}), 404

        # Verify old password matches stored hash
        if not user.password_hash or not verify_password(old_password, user.password_hash):
            return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 401

        # Update password hash
        user.password_hash = hash_password(new_password)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Password changed successfully.'}), 200

    except Exception as e:
        db.session.rollback()
        print('Error changing password:', e)
        return jsonify({'success': False, 'message': 'Failed to change password. Please try again.'}), 500

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat() + 'Z'})

# Entry point of frontend serve
@app.route('/')
def home():
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)

