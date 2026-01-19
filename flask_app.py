import os
from flask import Flask, render_template, redirect, url_for, session

app = Flask(__name__)

# --- АВТОМАТИЧЕСКАЯ НАСТРОЙКА ПУТЕЙ ---
# Этот код определяет папку, в которой лежит сам файл flask_app.py
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# База данных всегда будет лежать рядом с файлом скрипта
DB_PATH = os.path.join(BASE_DIR, 'lms.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-dev-key-777')

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

# --- МОДЕЛИ (Остаются без изменений) ---
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
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)

# --- ИНИЦИАЛИЗАЦИЯ (Универсальная) ---
with app.app_context():
    db.create_all()
    # Проверяем, есть ли уже данные, чтобы не дублировать их
    if not Course.query.first():
        test_course = Course(title="Python для начинающих")
        db.session.add(test_course)
        db.session.commit()

        l1 = Lesson(course_id=test_course.id, title="Основы Python", content="Это контент первого урока.")
        l2 = Lesson(course_id=test_course.id, title="Циклы и условия", content="Это контент второго урока.")
        db.session.add_all([l1, l2])

        if not User.query.filter_by(username="student").first():
            db.session.add(User(username="student"))

        db.session.commit()

# --- РОУТЫ (Универсальные) ---
@app.route('/')
def index():
    if 'user_id' not in session:
        user = User.query.first()
        if user: session['user_id'] = user.id

    courses = Course.query.all()
    bought_ids = []
    if session.get('user_id'):
        bought_ids = [e.course_id for e in Enrollment.query.filter_by(user_id=session['user_id']).all()]
    return render_template('index.html', courses=courses, bought_ids=bought_ids)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    u_id = session.get('user_id')
    is_bought = Enrollment.query.filter_by(user_id=u_id, course_id=course_id).first() is not None

    prog = 0
    comp_ids = []
    if is_bought:
        comp_lessons = Progress.query.filter_by(user_id=u_id).join(Lesson).filter(Lesson.course_id == course_id).all()
        comp_ids = [p.lesson_id for p in comp_lessons]
        if course.lessons:
            prog = int((len(comp_ids) / len(course.lessons)) * 100)

    return render_template('course.html', course=course, is_bought=is_bought, progress=prog, completed_ids=comp_ids)

@app.route('/buy/<int:course_id>')
def buy_course(course_id):
    u_id = session.get('user_id')
    if u_id and not Enrollment.query.filter_by(user_id=u_id, course_id=course_id).first():
        db.session.add(Enrollment(user_id=u_id, course_id=course_id))
        db.session.commit()
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/lesson/<int:lesson_id>')
def lesson_view(lesson_id):
    lesson = Lesson.query.get_or_404(lesson_id)
    u_id = session.get('user_id')
    if not Enrollment.query.filter_by(user_id=u_id, course_id=lesson.course_id).first():
        return "Доступ ограничен", 403
    return render_template('lesson.html', lesson=lesson)

@app.route('/complete/<int:lesson_id>')
def complete_lesson(lesson_id):
    u_id = session.get('user_id')
    lesson = Lesson.query.get_or_404(lesson_id)
    if u_id and not Progress.query.filter_by(user_id=u_id, lesson_id=lesson_id).first():
        db.session.add(Progress(user_id=u_id, lesson_id=lesson_id))
        db.session.commit()
    return redirect(url_for('course_detail', course_id=lesson.course_id))

if __name__ == '__main__':
    app.run(debug=True)
