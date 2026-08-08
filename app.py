from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'bms-secret-key-2025'

# Database setup
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ─── Models ────────────────────────────────────────────────────────────────────

class Revenue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=True)
    client = db.Column(db.String(100), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=True)
    description = db.Column(db.String(255), nullable=True)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=True)
    vendor = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=True)
    description = db.Column(db.String(255), nullable=True)


class Payroll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    salary = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.String(255), nullable=True)


# ─── Auth ──────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def do_login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == "admin" and password == "admin":
        session['logged_in'] = True
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('login.html', error="Invalid credentials")


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ─── Dashboard ─────────────────────────────────────────────────────────────────

@app.route('/index')
@login_required
def index():
    total_revenue = db.session.query(db.func.sum(Revenue.amount)).scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    total_payroll = db.session.query(db.func.sum(Payroll.salary)).scalar() or 0
    net_profit = total_revenue - total_expenses - total_payroll

    revenue_count = Revenue.query.count()
    expense_count = Expense.query.count()
    payroll_count = Payroll.query.count()

    # Monthly revenue for chart (last 6 months)
    all_revenues = Revenue.query.all()
    monthly_revenue = {}
    for r in all_revenues:
        if r.date:
            try:
                month = r.date[:7]  # YYYY-MM
                monthly_revenue[month] = monthly_revenue.get(month, 0) + r.amount
            except Exception:
                pass

    all_expenses = Expense.query.all()
    monthly_expenses = {}
    for e in all_expenses:
        if e.date:
            try:
                month = e.date[:7]
                monthly_expenses[month] = monthly_expenses.get(month, 0) + e.amount
            except Exception:
                pass

    # Expense by category for pie chart
    expense_categories = {}
    for e in all_expenses:
        cat = e.category or 'Other'
        expense_categories[cat] = expense_categories.get(cat, 0) + e.amount

    # Revenue by status
    revenue_statuses = {}
    for r in all_revenues:
        st = r.status or 'Unknown'
        revenue_statuses[st] = revenue_statuses.get(st, 0) + r.amount

    # Recent transactions
    recent_revenues = Revenue.query.order_by(Revenue.id.desc()).limit(5).all()
    recent_expenses = Expense.query.order_by(Expense.id.desc()).limit(5).all()

    return render_template('index.html',
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        total_payroll=total_payroll,
        net_profit=net_profit,
        revenue_count=revenue_count,
        expense_count=expense_count,
        payroll_count=payroll_count,
        monthly_revenue=json.dumps(monthly_revenue),
        monthly_expenses=json.dumps(monthly_expenses),
        expense_categories=json.dumps(expense_categories),
        revenue_statuses=json.dumps(revenue_statuses),
        recent_revenues=recent_revenues,
        recent_expenses=recent_expenses,
    )


# ─── Revenue ───────────────────────────────────────────────────────────────────

@app.route('/revenue')
@login_required
def revenue():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    revenues = Revenue.query
    if search:
        revenues = revenues.filter(
            db.or_(
                Revenue.title.ilike(f'%{search}%'),
                Revenue.client.ilike(f'%{search}%'),
                Revenue.description.ilike(f'%{search}%'),
            )
        )
    if status_filter:
        revenues = revenues.filter(Revenue.status == status_filter)
    revenues = revenues.order_by(Revenue.id.desc()).all()
    total = sum(r.amount for r in revenues)
    return render_template('revenue.html', revenues=revenues, total=total,
                           search=search, status_filter=status_filter)


@app.route('/add_revenue', methods=['GET', 'POST'])
@login_required
def add_revenue():
    if request.method == 'POST':
        new_revenue = Revenue(
            title=request.form['title'],
            amount=float(request.form['amount']),
            date=request.form.get('date'),
            client=request.form.get('client'),
            status=request.form.get('status'),
            description=request.form.get('description'),
        )
        db.session.add(new_revenue)
        db.session.commit()
        return redirect(url_for('revenue'))
    return render_template('add_revenue.html')


@app.route('/edit_revenue/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_revenue(id):
    revenue = Revenue.query.get_or_404(id)
    if request.method == 'POST':
        revenue.title = request.form['title']
        revenue.amount = float(request.form['amount'])
        revenue.date = request.form.get('date')
        revenue.client = request.form.get('client')
        revenue.status = request.form.get('status')
        revenue.description = request.form.get('description')
        db.session.commit()
        return redirect(url_for('revenue'))
    return render_template('edit_revenue.html', revenue=revenue)


@app.route('/delete_revenue/<int:id>', methods=['POST'])
@login_required
def delete_revenue(id):
    revenue = Revenue.query.get_or_404(id)
    db.session.delete(revenue)
    db.session.commit()
    return redirect(url_for('revenue'))


# ─── Expenses ──────────────────────────────────────────────────────────────────

@app.route('/expenses')
@login_required
def expenses():
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '')
    status_filter = request.args.get('status', '')
    expenses_list = Expense.query
    if search:
        expenses_list = expenses_list.filter(
            db.or_(
                Expense.vendor.ilike(f'%{search}%'),
                Expense.description.ilike(f'%{search}%'),
            )
        )
    if category_filter:
        expenses_list = expenses_list.filter(Expense.category == category_filter)
    if status_filter:
        expenses_list = expenses_list.filter(Expense.status == status_filter)
    expenses_list = expenses_list.order_by(Expense.id.desc()).all()
    total = sum(e.amount for e in expenses_list)
    categories = ['Office', 'Travel', 'Software', 'Hardware', 'Marketing', 'Utilities', 'Other']
    return render_template('expenses.html', expenses=expenses_list, total=total,
                           search=search, category_filter=category_filter,
                           status_filter=status_filter, categories=categories)


@app.route('/add_expense', methods=['GET', 'POST'])
@login_required
def add_expense():
    categories = ['Office', 'Travel', 'Software', 'Hardware', 'Marketing', 'Utilities', 'Other']
    if request.method == 'POST':
        new_expense = Expense(
            date=request.form.get('date'),
            vendor=request.form.get('vendor'),
            category=request.form.get('category'),
            amount=float(request.form.get('amount')),
            status=request.form.get('status'),
            description=request.form.get('description'),
        )
        db.session.add(new_expense)
        db.session.commit()
        return redirect(url_for('expenses'))
    return render_template('add_expense.html', categories=categories)


@app.route('/edit_expense/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    categories = ['Office', 'Travel', 'Software', 'Hardware', 'Marketing', 'Utilities', 'Other']
    if request.method == 'POST':
        expense.date = request.form.get('date')
        expense.vendor = request.form.get('vendor')
        expense.category = request.form.get('category')
        expense.amount = float(request.form.get('amount'))
        expense.status = request.form.get('status')
        expense.description = request.form.get('description')
        db.session.commit()
        return redirect(url_for('expenses'))
    return render_template('edit_expense.html', expense=expense, categories=categories)


@app.route('/delete_expense/<int:id>', methods=['POST'])
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for('expenses'))


# ─── Payroll ───────────────────────────────────────────────────────────────────

@app.route('/payroll')
@login_required
def payroll():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    payrolls = Payroll.query
    if search:
        payrolls = payrolls.filter(
            db.or_(
                Payroll.employee.ilike(f'%{search}%'),
                Payroll.role.ilike(f'%{search}%'),
            )
        )
    if status_filter:
        payrolls = payrolls.filter(Payroll.status == status_filter)
    payrolls = payrolls.order_by(Payroll.id.desc()).all()
    total = sum(p.salary for p in payrolls)
    return render_template('payroll.html', payrolls=payrolls, total=total,
                           search=search, status_filter=status_filter)


@app.route('/add_payroll', methods=['GET', 'POST'])
@login_required
def add_payroll():
    if request.method == 'POST':
        new_payroll = Payroll(
            employee=request.form.get('employee'),
            role=request.form.get('role'),
            salary=float(request.form.get('salary')),
            payment_date=request.form.get('payment_date'),
            status=request.form.get('status'),
            notes=request.form.get('notes'),
        )
        db.session.add(new_payroll)
        db.session.commit()
        return redirect(url_for('payroll'))
    return render_template('add_payroll.html')


@app.route('/edit_payroll/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_payroll(id):
    payroll = Payroll.query.get_or_404(id)
    if request.method == 'POST':
        payroll.employee = request.form.get('employee')
        payroll.role = request.form.get('role')
        payroll.salary = float(request.form.get('salary'))
        payroll.payment_date = request.form.get('payment_date')
        payroll.status = request.form.get('status')
        payroll.notes = request.form.get('notes')
        db.session.commit()
        return redirect(url_for('payroll'))
    return render_template('edit_payroll.html', payroll=payroll)


@app.route('/delete_payroll/<int:id>', methods=['POST'])
@login_required
def delete_payroll(id):
    payroll = Payroll.query.get_or_404(id)
    db.session.delete(payroll)
    db.session.commit()
    return redirect(url_for('payroll'))


# ─── Report ────────────────────────────────────────────────────────────────────

@app.route('/report')
@login_required
def report():
    total_revenue = db.session.query(db.func.sum(Revenue.amount)).scalar() or 0
    total_expenses = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    total_payroll = db.session.query(db.func.sum(Payroll.salary)).scalar() or 0
    net_profit = total_revenue - total_expenses - total_payroll
    profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0

    paid_revenue = db.session.query(db.func.sum(Revenue.amount)).filter(Revenue.status == 'Paid').scalar() or 0
    pending_revenue = db.session.query(db.func.sum(Revenue.amount)).filter(Revenue.status == 'Pending').scalar() or 0

    expense_by_category = db.session.query(
        Expense.category, db.func.sum(Expense.amount)
    ).group_by(Expense.category).all()

    payroll_by_status = db.session.query(
        Payroll.status, db.func.sum(Payroll.salary)
    ).group_by(Payroll.status).all()

    return render_template('report.html',
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        total_payroll=total_payroll,
        net_profit=net_profit,
        profit_margin=profit_margin,
        paid_revenue=paid_revenue,
        pending_revenue=pending_revenue,
        expense_by_category=expense_by_category,
        payroll_by_status=payroll_by_status,
    )


# ─── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
