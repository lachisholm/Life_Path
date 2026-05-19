import re
import smtplib
from email.message import EmailMessage

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .db import get_db, init_db
from .services.payment import create_checkout_session

bp = Blueprint("main", __name__)


PLANS = {
    "free": {
        "name": "Starter Trial",
        "price": "$0",
        "details": "30 days with limited features",
        "price_id": None,
    },
    "basic": {
        "name": "Navigator",
        "price": "$19/mo",
        "details": "Individual planning toolkit",
        "price_id_key": "STRIPE_PRICE_BASIC",
    },
    "pro": {
        "name": "Commander",
        "price": "$49/mo",
        "details": "Manager + family tracking",
        "price_id_key": "STRIPE_PRICE_PRO",
    },
    "elite": {
        "name": "Fleet",
        "price": "$99/mo",
        "details": "Advanced analytics and scale",
        "price_id_key": "STRIPE_PRICE_ELITE",
    },
}


@bp.before_app_request
def ensure_db_and_security():
    if not current_app.config.get("TESTING"):
        db = get_db()
        db.execute("SELECT 1 FROM sqlite_master WHERE name='people'")
        try:
            db.execute("SELECT id FROM people LIMIT 1")
        except Exception:
            init_db()
            db = get_db()

        exists = db.execute(
            "SELECT id FROM people WHERE is_primary = 1 LIMIT 1"
        ).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO people (name, role, is_primary) VALUES (?, ?, 1)",
                ("Main Person", "Owner"),
            )
            db.commit()

    if request.method == "POST" and not current_app.config.get("TESTING"):
        form_token = request.form.get("csrf_token", "")
        if form_token != session.get("csrf_token"):
            return "Invalid CSRF token", 400


@bp.after_app_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self';"
        " img-src 'self' data:;"
    )
    return response


@bp.route("/")
def home():
    return render_template("home.html")


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/dashboard")
def dashboard():
    db = get_db()
    people = db.execute("SELECT * FROM people ORDER BY is_primary DESC, id").fetchall()
    goals = db.execute(
        """
        SELECT goals.*, people.name AS person_name
        FROM goals
        JOIN people ON people.id = goals.person_id
        WHERE goals.status != 'done'
        ORDER BY goals.target_date IS NULL, goals.target_date ASC
        """
    ).fetchall()
    return render_template("dashboard.html", people=people, goals=goals)


@bp.route("/people/add", methods=["POST"])
def add_person():
    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    if not name or not role:
        flash("Name and role are required.", "error")
        return redirect(url_for("main.dashboard"))

    db = get_db()
    db.execute(
        "INSERT INTO people (name, role, is_primary) VALUES (?, ?, 0)",
        (name, role),
    )
    db.commit()
    flash("Person added.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/people/<int:person_id>/delete", methods=["POST"])
def delete_person(person_id):
    db = get_db()
    person = db.execute("SELECT * FROM people WHERE id = ?", (person_id,)).fetchone()
    if person and person["is_primary"]:
        flash("Primary account holder cannot be removed.", "error")
    else:
        db.execute("DELETE FROM people WHERE id = ?", (person_id,))
        db.commit()
        flash("Person removed.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/goals/new", methods=["GET", "POST"])
def goal_new():
    db = get_db()
    people = db.execute("SELECT * FROM people ORDER BY id").fetchall()
    all_goals = db.execute("SELECT id, title FROM goals ORDER BY id DESC").fetchall()
    if request.method == "POST":
        form = request.form
        person_id = form.get("person_id")
        title = form.get("title", "").strip()
        description = form.get("description", "").strip()
        resources = form.get("resources", "").strip()
        start_date = form.get("start_date") or None
        target_date = form.get("target_date") or None
        goal_notes = form.get("goal_notes", "").strip()
        future_goal_id = form.get("future_goal_id") or None

        if not person_id or not title or not description:
            flash("Person, title, and description are required.", "error")
            return render_template(
                "goal_form.html",
                people=people,
                all_goals=all_goals,
                selected=form,
            )

        db.execute(
            """
            INSERT INTO goals (
                person_id, title, description, resources, start_date,
                target_date, future_goal_id, goal_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                person_id,
                title,
                description,
                resources,
                start_date,
                target_date,
                future_goal_id,
                goal_notes,
            ),
        )
        db.commit()
        flash("Goal created.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template(
        "goal_form.html", people=people, all_goals=all_goals, selected={}
    )


@bp.route("/goals/<int:goal_id>")
def goal_detail(goal_id):
    db = get_db()
    goal = db.execute(
        """
        SELECT goals.*, people.name AS person_name
        FROM goals JOIN people ON goals.person_id = people.id
        WHERE goals.id = ?
        """,
        (goal_id,),
    ).fetchone()
    if not goal:
        return redirect(url_for("main.dashboard"))

    steps = db.execute(
        "SELECT * FROM steps WHERE goal_id = ? ORDER BY position, id", (goal_id,)
    ).fetchall()
    people = db.execute("SELECT * FROM people ORDER BY id").fetchall()
    goals = db.execute("SELECT id, title FROM goals WHERE id != ?", (goal_id,)).fetchall()
    linked_goal = None
    if goal["future_goal_id"]:
        linked_goal = db.execute(
            "SELECT id, title FROM goals WHERE id = ?", (goal["future_goal_id"],)
        ).fetchone()

    return render_template(
        "goal_detail.html",
        goal=goal,
        steps=steps,
        people=people,
        goals=goals,
        linked_goal=linked_goal,
    )


@bp.route("/goals/<int:goal_id>/edit", methods=["POST"])
def goal_edit(goal_id):
    db = get_db()
    db.execute(
        """
        UPDATE goals
        SET person_id = ?, title = ?, description = ?, resources = ?,
            start_date = ?, target_date = ?, future_goal_id = ?, goal_notes = ?
        WHERE id = ?
        """,
        (
            request.form.get("person_id"),
            request.form.get("title", "").strip(),
            request.form.get("description", "").strip(),
            request.form.get("resources", "").strip(),
            request.form.get("start_date") or None,
            request.form.get("target_date") or None,
            request.form.get("future_goal_id") or None,
            request.form.get("goal_notes", "").strip(),
            goal_id,
        ),
    )
    db.commit()
    flash("Goal updated.", "success")
    return redirect(url_for("main.goal_detail", goal_id=goal_id))


@bp.route("/goals/<int:goal_id>/steps/add", methods=["POST"])
def goal_add_step(goal_id):
    title = request.form.get("title", "").strip()
    if not title:
        flash("Step title is required.", "error")
        return redirect(url_for("main.goal_detail", goal_id=goal_id))

    db = get_db()
    last_position = db.execute(
        "SELECT COALESCE(MAX(position), 0) AS maxp FROM steps WHERE goal_id = ?",
        (goal_id,),
    ).fetchone()["maxp"]

    db.execute(
        """
        INSERT INTO steps (goal_id, title, resources, timeframe, step_notes, position)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            goal_id,
            title,
            request.form.get("resources", "").strip(),
            request.form.get("timeframe", "").strip(),
            request.form.get("step_notes", "").strip(),
            last_position + 1,
        ),
    )
    db.commit()
    flash("Step added.", "success")
    return redirect(url_for("main.goal_detail", goal_id=goal_id))


@bp.route("/steps/<int:step_id>/toggle", methods=["POST"])
def step_toggle(step_id):
    db = get_db()
    step = db.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
    if not step:
        return redirect(url_for("main.dashboard"))

    db.execute(
        "UPDATE steps SET is_done = ? WHERE id = ?",
        (0 if step["is_done"] else 1, step_id),
    )
    db.commit()
    return redirect(url_for("main.goal_detail", goal_id=step["goal_id"]))


@bp.route("/steps/<int:step_id>/delete", methods=["POST"])
def step_delete(step_id):
    db = get_db()
    step = db.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
    if step:
        db.execute("DELETE FROM steps WHERE id = ?", (step_id,))
        db.commit()
        return redirect(url_for("main.goal_detail", goal_id=step["goal_id"]))
    return redirect(url_for("main.dashboard"))


@bp.route("/goals/<int:goal_id>/complete", methods=["POST"])
def goal_complete(goal_id):
    db = get_db()
    db.execute(
        """
        UPDATE goals
        SET status = 'done', completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (goal_id,),
    )
    db.commit()
    flash("Goal marked as complete.", "success")
    return redirect(url_for("main.goal_detail", goal_id=goal_id))


@bp.route("/goals/<int:goal_id>/delete", methods=["POST"])
def goal_delete(goal_id):
    db = get_db()
    db.execute("DELETE FROM steps WHERE goal_id = ?", (goal_id,))
    db.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    db.commit()
    flash("Goal deleted.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/history")
def history():
    db = get_db()
    goals = db.execute(
        """
        SELECT goals.*, people.name AS person_name
        FROM goals
        JOIN people ON people.id = goals.person_id
        WHERE goals.status = 'done'
        ORDER BY goals.completed_at DESC
        """
    ).fetchall()
    return render_template("history.html", goals=goals)


@bp.route("/flowchart")
def flowchart():
    db = get_db()
    people = db.execute("SELECT id, name FROM people ORDER BY id").fetchall()
    selected_person = request.args.get("person_id", "")
    orientation = request.args.get("view", "vertical")

    query = (
        "SELECT goals.id, goals.title, goals.status, people.name AS person_name "
        "FROM goals JOIN people ON people.id = goals.person_id"
    )
    args = ()
    if selected_person:
        query += " WHERE person_id = ?"
        args = (selected_person,)
    query += " ORDER BY goals.id DESC"
    goals = db.execute(query, args).fetchall()

    steps_by_goal = {}
    for goal in goals:
        steps_by_goal[goal["id"]] = db.execute(
            "SELECT * FROM steps WHERE goal_id = ? ORDER BY position, id", (goal["id"],)
        ).fetchall()

    return render_template(
        "flowchart.html",
        people=people,
        goals=goals,
        steps_by_goal=steps_by_goal,
        selected_person=selected_person,
        orientation=orientation,
    )


@bp.route("/pricing")
def pricing():
    return render_template("pricing.html", plans=PLANS)


@bp.route("/cart")
def cart():
    return render_template("cart.html", plans=PLANS)


@bp.route("/checkout")
def checkout_page():
    selected = request.args.get("plan", "basic")
    return render_template(
        "checkout.html",
        plans=PLANS,
        selected=selected,
        publishable_key=current_app.config["STRIPE_PUBLISHABLE_KEY"],
    )


@bp.route("/create-checkout-session", methods=["POST"])
def checkout_session():
    plan = request.form.get("plan")
    if plan not in PLANS or plan == "free":
        return jsonify({"error": "Invalid plan."}), 400

    price_key = PLANS[plan]["price_id_key"]
    price_id = current_app.config.get(price_key, "")
    if not price_id:
        return jsonify({"error": "Price ID missing."}), 400

    try:
        checkout = create_checkout_session(
            app=current_app,
            plan_price_id=price_id,
            success_url=url_for("main.checkout_page", _external=True)
            + "?status=success",
            cancel_url=url_for("main.checkout_page", _external=True)
            + "?status=cancelled",
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({"url": checkout.url})


@bp.route("/auth/login")
def auth_login():
    oauth_client = current_app.extensions["authlib.integrations.flask_client"]
    google = oauth_client.create_client("google")
    if google is None:
        flash("OAuth is configured and ready once provider keys are set.", "error")
        return redirect(url_for("main.home"))
    redirect_uri = url_for("main.auth_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@bp.route("/auth/callback")
def auth_callback():
    oauth_client = current_app.extensions["authlib.integrations.flask_client"]
    google = oauth_client.create_client("google")
    if google is None:
        return redirect(url_for("main.home"))
    token = google.authorize_access_token()
    user = token.get("userinfo")
    if user:
        session["user_email"] = user.get("email")
    return redirect(url_for("main.dashboard"))


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        if (
            not name
            or not subject
            or not message
            or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)
        ):
            flash("Please provide valid contact details.", "error")
            return render_template("contact.html")

        db = get_db()
        db.execute(
            "INSERT INTO contacts (name, email, subject, message) VALUES (?, ?, ?, ?)",
            (name, email, subject, message),
        )
        db.commit()

        try:
            send_contact_email(name, email, subject, message)
            flash("Message sent successfully.", "success")
        except Exception:
            flash(
                "Message saved. Email is queued until company mailbox is ready.",
                "success",
            )

        return redirect(url_for("main.contact"))

    return render_template("contact.html")


def send_contact_email(name, sender, subject, body):
    host = current_app.config["SMTP_HOST"]
    user = current_app.config["SMTP_USER"]
    password = current_app.config["SMTP_PASS"]
    company_email = current_app.config["COMPANY_EMAIL"]
    if not host or not user or not password:
        raise RuntimeError("SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = f"Life Path Contact: {subject}"
    msg["From"] = user
    msg["To"] = company_email
    msg.set_content(f"From: {name} <{sender}>\n\n{body}")

    with smtplib.SMTP(host, current_app.config["SMTP_PORT"], timeout=15) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


@bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@bp.route("/terms")
def terms():
    return render_template("legal/terms.html")


@bp.route("/refund")
def refund():
    return render_template("legal/refund.html")


@bp.route("/cookies")
def cookies():
    return render_template("legal/cookies.html")
