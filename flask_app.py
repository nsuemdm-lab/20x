import os
from flask import Flask, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# --- КОНФИГУРАЦИЯ ДЛЯ PYTHONANYWHERE ---
# Указываем абсолютный путь к базе данных, чтобы Flask не "терял" её
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'lms.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-key-12345' # Нужно для работы сессий (куки)

db = SQLAlchemy(app)

# --- МОДЕЛИ ДАННЫХ ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    lessons = db.relationship('Lesson', backref='course', lazy=True)

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)

class Enrollment(db.Model):
    """Таблица покупок/доступов"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

class Progress(db.Model):
    """Таблица пройденных уроков"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
# На PythonAnywhere таблицы создаются при первом запуске через app_context
with app.app_context():
    db.create_all()
    # Добавляем тестовые данные, если курсов еще нет
    if not Course.query.first():
        test_course = Course(title="Python для начинающих")
        db.session.add(test_course)
        db.session.commit()
        
        l1 = Lesson(course_id=test_course.id, title="Основы Python", content="Это контент первого урока.")
        l2 = Lesson(course_id=test_course.id, title="Циклы и условия", content="Это контент второго урока.")
        db.session.add_all([l1, l2])
        
        # Создаем тестового пользователя
        if not User.query.filter_by(username="student").first():
            db.session.add(User(username="student"))
        
        db.session.commit()

# --- МАРШРУТЫ (РОУТЫ) ---

@app.route('/')
def index():
    # Авто-логин для теста (если не вошли, входим как первый юзер)
    if 'user_id' not in session:
        user = User.query.first()
        if user:
            session['user_id'] = user.id

    courses = Course.query.all()
    user_id = session.get('user_id')
    
    # Получаем список ID курсов, которые пользователь уже купил
    bought_ids = []
    if user_id:
        bought_ids = [e.course_id for e in Enrollment.query.filter_by(user_id=user_id).all()]
    
    return render_template('index.html', courses=courses, bought_ids=bought_ids)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    user_id = session.get('user_id')
    
    # Проверка покупки
    enrollment = Enrollment.query.filter_by(user_id=user_id, course_id=course_id).first()
    is_bought = enrollment is not None
    
    # Расчет прогресса
    progress_percent = 0
    completed_lesson_ids = []
    
    if is_bought:
        # Считаем уроки этого курса, которые юзер отметил как пройденные
        completed_lessons = Progress.query.filter_by(user_id=user_id).join(Lesson).filter(Lesson.course_id == course_id).all()
        completed_lesson_ids = [p.lesson_id for p in completed_lessons]
        
        if course.lessons:
            progress_percent = int((len(completed_lesson_ids) / len(course.lessons)) * 100)

    return render_template('course.html', 
                           course=course, 
                           is_bought=is_bought, 
                           progress=progress_percent,
                           completed_ids=completed_lesson_ids)

@app.route('/lesson/<int:lesson_id>')
def lesson_view(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    user_id = session.get('user_id')
    
    # Проверка доступа
    is_bought = Enrollment.query.filter_by(user_id=user_id, course_id=lesson.course_id).first()
    
    if not is_bought:
        return "<h1>Доступ запрещен</h1><p>Сначала купите этот курс.</p><a href='/'>Назад</a>", 403
    
    return render_template('lesson.html', lesson=lesson)

@app.route('/buy/<int:course_id>')
def buy_course(course_id):
    user_id = session.get('user_id')
    if user_id:
        existing = Enrollment.query.filter_by(user_id=user_id, course_id=course_id).first()
        if not existing:
            new_enroll = Enrollment(user_id=user_id, course_id=course_id)
            db.session.add(new_enroll)
            db.session.commit()
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/complete/<int:lesson_id>')
def complete_lesson(lesson_id):
    user_id = session.get('user_id')
    lesson = Lesson.query.get_or_404(lesson_id)
    
    if user_id:
        # Проверяем, не отмечен ли уже
        already_done = Progress.query.filter_by(user_id=user_id, lesson_id=lesson_id).first()
        if not already_done:
            db.session.add(Progress(user_id=user_id, lesson_id=lesson_id))
            db.session.commit()
            
    return redirect(url_for('course_detail', course_id=lesson.course_id))

# Не нужно app.run() для PythonAnywhere, но оставим для локальных тестов
if __name__ == '__main__':
    app.run(debug=True)
