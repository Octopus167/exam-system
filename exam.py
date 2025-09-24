from flask import Flask, request, redirect, url_for, render_template, g, flash, session
import sqlite3, os, requests, time
from jinja2 import DictLoader

# ===== إعدادات البوت =====
BOT_TOKEN = "8395555565:AAHuM-5UbaC8Grx3HAn7YxEb46cRu2vQk5Q"
ADMIN_CHAT_ID = "-4910266557"
DATABASE = r'C:\Users\Lenovo\Desktop\exam\exam.db'
EXAM_DURATION = 1 * 60  # نصف ساعة
ADMIN_PASSWORD = "12345"  # كلمة مرور الأدمن

app = Flask(__name__)
app.secret_key = 'change_me_in_production'

# ===== القوالب =====
templates = {
    "layout.html": """<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>امتحان أونلاين</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body{background:#f8f9fa;}
    .card{margin-top:20px; border-radius:20px; box-shadow:0 4px 12px rgba(0,0,0,0.1)}
    .btn{border-radius:12px;}
    .option {margin-bottom: 6px;}
    .option input[type="radio"] {display: none;}
    .option label {
      display: block;
      padding: 8px 12px;
      border: 1px solid #ccc;
      border-radius: 10px;
      cursor: pointer;
      transition: 0.2s;
    }
    .option input[type="radio"]:checked + label {
      background: #d4edda;
      border-color: #28a745;
      color: #155724;
      font-weight: bold;
    }
  </style>
</head>
<body class="container py-4">
  <div class="mb-4 text-center">
    <h1 class="fw-bold text-primary">📘 نظام امتحانات أونلاين</h1>
    <a class="btn btn-outline-secondary" href="{{ url_for('login') }}">لوحة الإدارة</a>
    <a class="btn btn-outline-success" href="{{ url_for('take') }}">رابط الموظفين</a>
  </div>
  {% with messages = get_flashed_messages() %}
    {% if messages %}<div class="alert alert-info">{{ messages[0] }}</div>{% endif %}
  {% endwith %}
  {% block body %}{% endblock %}
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>""",

    "login.html": """{% extends "layout.html" %}{% block body %}
<div class="card p-4 col-md-6 mx-auto">
  <h3 class="mb-3 text-center">🔑 تسجيل دخول الأدمن</h3>
  <form method="post" action="{{ url_for('login') }}">
    <input type="password" name="password" class="form-control mb-3" placeholder="أدخل كلمة المرور" required>
    <button class="btn btn-primary w-100">دخول</button>
  </form>
</div>
{% endblock %}""",

    "admin.html": """{% extends "layout.html" %}{% block body %}
<div class="row">
  <div class="col-md-6">
    <div class="card p-4">
      <h4>➕ إضافة سؤال</h4>
      <form method="post" action="{{ url_for('add_question') }}">
        <textarea name="text" class="form-control mb-2" placeholder="نص السؤال" required></textarea>
        <input name="a" class="form-control mb-2" placeholder="الخيار A" required>
        <input name="b" class="form-control mb-2" placeholder="الخيار B" required>
        <input name="c" class="form-control mb-2" placeholder="الخيار C" required>
        <input name="d" class="form-control mb-2" placeholder="الخيار D" required>
        <input name="correct" class="form-control mb-2" placeholder="الإجابة الصحيحة A/B/C/D" required>
        <button class="btn btn-primary">أضف</button>
      </form>
    </div>
  </div>
  <div class="col-md-6">
    <div class="card p-4">
      <h4>➕ إضافة موظف</h4>
      <form method="post" action="{{ url_for('add_student') }}">
        <input name="identifier" class="form-control mb-2" placeholder="المعرّف" required>
        <input name="name" class="form-control mb-2" placeholder="اسم الموظف" required>
        <button class="btn btn-primary">أضف</button>
      </form>
    </div>
  </div>
</div>
<div class="card p-4 mt-3">
  <h4>📋 قائمة الموظفين</h4>
  <table class="table">
    <tr><th>المعرف</th><th>الاسم</th><th>محاولة</th><th>الدرجة</th></tr>
    {% for s in students %}<tr><td>{{ s['identifier'] }}</td><td>{{ s['name'] }}</td><td>{{ '✔' if s['attempted'] else '✖' }}</td><td>{{ s['score'] }}</td></tr>{% endfor %}
  </table>
</div>
{% endblock %}""",

    "start.html": """{% extends "layout.html" %}{% block body %}
<div class="card p-4">
  <h3>ابدأ الامتحان</h3>
  <form method="post" action="{{ url_for('start_exam') }}">
    <input name="identifier" class="form-control mb-3" placeholder="المعرف" required>
    <button class="btn btn-success">ابدأ</button>
  </form>
</div>
{% endblock %}""",

    "exam.html": """{% extends "layout.html" %}{% block body %}
<h3>امتحان الموظف: {{student['name']}}</h3>
<div id='timer' class='alert alert-warning'></div>
<form method='post' action='{{ url_for('submit', student_id=student['id']) }}'>
  {% for q in questions %}
    <div class='card p-3'>
      <p><b>{{ loop.index }}. {{ q['text'] }}</b></p>
      {% for opt in ['a','b','c','d'] %}
        <div class="option">
          <input type="radio" id="q{{q['id']}}{{opt}}" name="q{{q['id']}}" value="{{ opt.upper() }}">
          <label for="q{{q['id']}}{{opt}}"><b>{{ opt.upper() }}.</b> {{ q[opt] }}</label>
        </div>
      {% endfor %}
    </div>
  {% endfor %}
  <button class='btn btn-success mt-3'>إنهاء</button>
</form>
<script>
  var duration={{duration}};
  function updateTimer(){
    var m=Math.floor(duration/60), s=duration%60;
    document.getElementById('timer').innerText='الوقت المتبقي: '+m+":"+('0'+s).slice(-2);
    if(duration<=0) document.forms[0].submit();
    duration--; setTimeout(updateTimer,1000);
  }
  updateTimer();
</script>
{% endblock %}""",

    "result.html": """{% extends "layout.html" %}{% block body %}
<div class="card p-5 text-center">
  <h2 class="text-success fw-bold">🎉 مبروك {{ student['name'] }}!</h2>
  <p class="mt-3 fs-4">درجتك النهائية: <b>{{ score }}</b> / {{ total }}</p>
  <div class="mt-4">
    <a href="{{ url_for('take') }}" class="btn btn-primary btn-lg">🔄 العودة للصفحة الرئيسية</a>
  </div>
</div>
{% endblock %}"""
}

app.jinja_loader = DictLoader(templates)

# ===== قاعدة البيانات =====
def get_db():
    db = getattr(g, '_db', None)
    if db is None:
        init_db = not os.path.exists(DATABASE)
        db = g._db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        if init_db:
            cur = db.cursor()
            cur.execute("CREATE TABLE students(id INTEGER PRIMARY KEY, identifier TEXT UNIQUE, name TEXT, attempted INTEGER DEFAULT 0, score INTEGER DEFAULT 0, start_time REAL)")
            cur.execute("CREATE TABLE questions(id INTEGER PRIMARY KEY, text TEXT, a TEXT, b TEXT, c TEXT, d TEXT, correct TEXT)")
            db.commit()
    return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_db', None)
    if db is not None:
        db.close()

# ===== تيليغرام =====
def send_to_telegram(msg):
    if BOT_TOKEN and ADMIN_CHAT_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": ADMIN_CHAT_ID, "text": msg})
        except: pass

# ===== الصفحات =====
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin'))
        else:
            flash("كلمة مرور غير صحيحة")
    return render_template("login.html")

@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    db = get_db()
    students = db.execute("SELECT * FROM students").fetchall()
    return render_template("admin.html", students=students)

@app.route('/admin/add_question', methods=['POST'])
def add_question():
    if not session.get('admin'): return redirect(url_for('login'))
    db = get_db()
    db.execute("INSERT INTO questions(text,a,b,c,d,correct) VALUES(?,?,?,?,?,?)",
               (request.form['text'], request.form['a'], request.form['b'], request.form['c'], request.form['d'], request.form['correct'].upper()))
    db.commit()
    flash("تمت إضافة السؤال")
    return redirect(url_for('admin'))

@app.route('/admin/add_student', methods=['POST'])
def add_student():
    if not session.get('admin'): return redirect(url_for('login'))
    db = get_db()
    db.execute("INSERT INTO students(identifier,name) VALUES(?,?)", (request.form['identifier'], request.form['name']))
    db.commit()
    flash("تمت إضافة الموظف")
    return redirect(url_for('admin'))

@app.route('/take')
def take():
    return render_template("start.html")

@app.route('/start', methods=['POST'])
def start_exam():
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE identifier=?", (request.form['identifier'],)).fetchone()
    if not student:
        flash("معرّف غير صحيح")
        return redirect(url_for('take'))
    if student['attempted']:
        flash("لقد قمت بالمحاولة مسبقاً")
        return redirect(url_for('take'))
    db.execute("UPDATE students SET start_time=? WHERE id=?", (time.time(), student['id']))
    db.commit()
    return redirect(url_for('exam', student_id=student['id']))

@app.route('/exam/<int:student_id>')
def exam(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student: return "غير موجود"
    if student['attempted']: return "لقد أكملت الامتحان"
    questions = db.execute("SELECT * FROM questions").fetchall()
    return render_template("exam.html", student=student, questions=questions, duration=EXAM_DURATION)

@app.route('/submit/<int:student_id>', methods=['POST'])
def submit(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not student or student['attempted']:
        return "غير صالح"
    questions = db.execute("SELECT * FROM questions").fetchall()
    score = 0; details = []
    for q in questions:
        ans = request.form.get(f"q{q['id']}")
        if ans == q['correct']: score += 1
        details.append(f"سؤال {q['id']}: {ans or '-'} (صح:{q['correct']})")
    db.execute("UPDATE students SET attempted=1, score=? WHERE id=?", (score, student_id))
    db.commit()
    msg = f"📢 نتيجة الموظف :{student['name']} \
      النتيجة: {score}/{len(questions)}\
        " + "\
          ".join(details)
    send_to_telegram(msg)
    return render_template("result.html", student=student, score=score, total=len(questions))

if __name__ == '__main__':
    app.run(debug=True)
