import hmac
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, send_file, session, url_for
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(".env файлд SUPABASE_URL болон SUPABASE_SECRET_KEY утгыг оруулна уу.")
if not FLASK_SECRET_KEY or len(FLASK_SECRET_KEY) < 32:
    raise RuntimeError(".env файлд 32-оос багагүй тэмдэгттэй FLASK_SECRET_KEY утгыг оруулна уу.")

supabase = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("APP_ENV", "").strip().lower() == "production",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)
app.logger.setLevel(logging.INFO)


def get_csrf_token():
    return session.setdefault("csrf_token", secrets.token_urlsafe(32))


def valid_csrf_token():
    expected = session.get("csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(expected, submitted)


def format_mongolia_time(value):
    if not value:
        return ""
    try:
        scheduled_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value).replace("T", " ")[:16]
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
    mongolia_timezone = timezone(timedelta(hours=8))
    return scheduled_at.astimezone(mongolia_timezone).strftime("%Y-%m-%d %H:%M")


def parse_mongolia_datetime(value):
    scheduled_at = datetime.fromisoformat(value)
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=timezone(timedelta(hours=8)))
    return scheduled_at.isoformat()


@app.get("/brand.svg")
def brand_logo():
    return send_file(BASE_DIR / "YUN-logo1-color.svg", mimetype="image/svg+xml")


@app.get("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_email") else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_email"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        if not valid_csrf_token():
            abort(400)

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        try:
            result = (
                supabase.table("users")
                .select("email, password_hash")
                .eq("email", email)
                .limit(1)
                .execute()
            )
            user = result.data[0] if result.data else None
            password_matches = user and bcrypt.checkpw(
                password.encode("utf-8"), user["password_hash"].encode("utf-8")
            )
        except Exception:
            app.logger.exception("Login lookup failed")
            flash("Нэвтрэх үед алдаа гарлаа. Холболтоо шалгаад дахин оролдоно уу.", "error")
            return render_template("login.html", csrf_token=get_csrf_token()), 503

        if not password_matches:
            flash("И-мэйл эсвэл нууц үг буруу байна.", "error")
            return render_template("login.html", csrf_token=get_csrf_token()), 401

        session.clear()
        session.permanent = True
        session["user_email"] = user["email"]
        return redirect(url_for("dashboard"))

    return render_template("login.html", csrf_token=get_csrf_token())


def render_dashboard(section):
    user_email = session.get("user_email")
    if not user_email:
        return redirect(url_for("login"))

    error = None
    drafts = []
    bookings = []
    appointments = []
    staff_records = []
    staff_options = []
    staff_by_id = {}
    search_query = request.args.get("q", "").strip()

    if section == "content":
        try:
            result = (
                supabase.table("content_drafts")
                .select("id, title, content, status, created_at")
                .eq("status", "draft")
                .order("created_at", desc=True)
                .execute()
            )
            drafts = result.data or []
        except Exception:
            app.logger.exception("Draft lookup failed")
            error = "Нооргуудыг ачаалж чадсангүй. Холболтоо шалгаад дахин оролдоно уу."
    elif section == "bookings":
        try:
            result = (
                supabase.table("bookings")
                .select("id, customer_name, email, scheduled_at, notes, status")
                .order("scheduled_at")
                .execute()
            )
            bookings = result.data or []
            for booking in bookings:
                booking["display_scheduled_at"] = format_mongolia_time(booking.get("scheduled_at"))
        except Exception:
            app.logger.exception("Booking lookup failed")
            error = "Захиалгуудыг ачаалж чадсангүй. Холболтоо шалгаад дахин оролдоно уу."
    elif section == "appointments":
        try:
            staff_result = supabase.table("staff").select("id, name").order("name").execute()
            staff_options = staff_result.data or []
            staff_by_id = {member["id"]: member["name"] for member in staff_options}
            query = supabase.table("appointments").select(
                "id, customer_name, customer_email, scheduled_at, staff_id, notes, status"
            )
            if search_query:
                query = query.ilike("customer_name", f"%{search_query}%")
            result = query.order("scheduled_at").execute()
            appointments = result.data or []
            for appointment in appointments:
                appointment["display_scheduled_at"] = format_mongolia_time(appointment.get("scheduled_at"))
        except Exception:
            app.logger.exception("Appointment lookup failed")
            error = "Цагийн мэдээлэл ачаалж чадсангүй. Холболтоо шалгаад дахин оролдоно уу."
    elif section == "staff":
        try:
            query = supabase.table("staff").select("id, name, email, phone, position")
            if search_query:
                query = query.ilike("name", f"%{search_query}%")
            result = query.order("name").execute()
            staff_records = result.data or []
        except Exception:
            app.logger.exception("Staff lookup failed")
            error = "Ажилтны мэдээлэл ачаалж чадсангүй. Холболтоо шалгаад дахин оролдоно уу."

    return render_template(
        "dashboard.html",
        section=section,
        user_email=user_email,
        drafts=drafts,
        bookings=bookings,
        appointments=appointments,
        staff_records=staff_records,
        staff_options=staff_options,
        staff_by_id=staff_by_id,
        search_query=search_query,
        status_labels={
            "pending": "Хүлээгдэж буй",
            "confirmed": "Баталгаажсан",
            "cancelled": "Цуцалсан",
            "approved": "Баталсан",
        },
        error=error,
        csrf_token=get_csrf_token(),
    )


@app.get("/dashboard")
def dashboard():
    return render_dashboard("content")


@app.get("/dashboard/<section>")
def dashboard_section(section):
    if section not in {"facebook", "chat", "bookings", "appointments", "staff"}:
        abort(404)
    return render_dashboard(section)


@app.post("/dashboard/bookings/<uuid:booking_id>/<action>")
def update_booking(booking_id, action):
    if not session.get("user_email"):
        return redirect(url_for("login"))
    if action not in {"confirm", "reject"}:
        abort(404)
    if not valid_csrf_token():
        abort(400)

    new_status = "confirmed" if action == "confirm" else "cancelled"
    try:
        result = (
            supabase.table("bookings")
            .update({"status": new_status})
            .eq("id", str(booking_id))
            .eq("status", "pending")
            .select("id")
            .execute()
        )
        if result.data:
            message = "Захиалгыг баталлаа." if action == "confirm" else "Захиалгаас татгалзлаа."
            flash(message, "success")
        else:
            flash("Энэ захиалга аль хэдийн шийдвэрлэгдсэн эсвэл олдсонгүй.", "error")
    except Exception:
        app.logger.exception("Booking status update failed")
        flash("Захиалгын төлөвийг шинэчилж чадсангүй.", "error")

    return redirect(url_for("dashboard_section", section="bookings"))


def require_management_access():
    if not session.get("user_email"):
        return redirect(url_for("login"))
    if not valid_csrf_token():
        abort(400)
    return None


@app.post("/dashboard/appointments/create")
def create_appointment():
    response = require_management_access()
    if response:
        return response

    customer_name = request.form.get("customer_name", "").strip()
    customer_email = request.form.get("customer_email", "").strip()
    try:
        scheduled_at = parse_mongolia_datetime(request.form.get("scheduled_at", ""))
    except ValueError:
        flash("Цагийн огноо, цагийг зөв оруулна уу.", "error")
        return redirect(url_for("dashboard_section", section="appointments"))
    if not customer_name or not customer_email:
        flash("Захиалагчийн нэр болон и-мэйлийг бөглөнө үү.", "error")
        return redirect(url_for("dashboard_section", section="appointments"))

    try:
        supabase.table("appointments").insert({
            "customer_name": customer_name,
            "customer_email": customer_email,
            "scheduled_at": scheduled_at,
            "staff_id": request.form.get("staff_id") or None,
            "notes": request.form.get("notes", "").strip() or None,
            "status": "pending",
        }).execute()
        flash("Шинэ цаг нэмлээ.", "success")
    except Exception:
        app.logger.exception("Appointment creation failed")
        flash("Цаг нэмэхэд алдаа гарлаа.", "error")
    return redirect(url_for("dashboard_section", section="appointments"))


@app.post("/dashboard/appointments/<uuid:appointment_id>/update")
def update_appointment(appointment_id):
    response = require_management_access()
    if response:
        return response

    customer_name = request.form.get("customer_name", "").strip()
    customer_email = request.form.get("customer_email", "").strip()
    status = request.form.get("status", "")
    try:
        scheduled_at = parse_mongolia_datetime(request.form.get("scheduled_at", ""))
    except ValueError:
        flash("Цагийн огноо, цагийг зөв оруулна уу.", "error")
        return redirect(url_for("dashboard_section", section="appointments"))
    if not customer_name or not customer_email or status not in {"pending", "confirmed", "cancelled"}:
        flash("Мэдээллээ шалгаад дахин хадгална уу.", "error")
        return redirect(url_for("dashboard_section", section="appointments"))

    try:
        result = supabase.table("appointments").update({
            "customer_name": customer_name,
            "customer_email": customer_email,
            "scheduled_at": scheduled_at,
            "staff_id": request.form.get("staff_id") or None,
            "notes": request.form.get("notes", "").strip() or None,
            "status": status,
        }).eq("id", str(appointment_id)).select("id").execute()
        flash("Цагийн мэдээлэл шинэчлэгдлээ." if result.data else "Цаг олдсонгүй.", "success" if result.data else "error")
    except Exception:
        app.logger.exception("Appointment update failed")
        flash("Цаг засахад алдаа гарлаа.", "error")
    return redirect(url_for("dashboard_section", section="appointments"))


@app.post("/dashboard/appointments/<uuid:appointment_id>/delete")
def delete_appointment(appointment_id):
    response = require_management_access()
    if response:
        return response
    try:
        result = (
            supabase.table("appointments")
            .delete()
            .eq("id", str(appointment_id))
            .select("id")
            .execute()
        )
        flash("Цаг устгагдлаа." if result.data else "Цаг олдсонгүй.", "success" if result.data else "error")
    except Exception:
        app.logger.exception("Appointment deletion failed")
        flash("Цаг устгахад алдаа гарлаа.", "error")
    return redirect(url_for("dashboard_section", section="appointments"))


@app.post("/dashboard/staff/create")
def create_staff():
    response = require_management_access()
    if response:
        return response

    member = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip() or None,
        "position": request.form.get("position", "").strip(),
    }
    if not member["name"] or not member["email"] or not member["position"]:
        flash("Нэр, и-мэйл, албан тушаалыг бөглөнө үү.", "error")
        return redirect(url_for("dashboard_section", section="staff"))
    try:
        supabase.table("staff").insert(member).execute()
        flash("Шинэ ажилтан нэмлээ.", "success")
    except Exception:
        app.logger.exception("Staff creation failed")
        flash("Ажилтан нэмэхэд алдаа гарлаа.", "error")
    return redirect(url_for("dashboard_section", section="staff"))


@app.post("/dashboard/staff/<uuid:staff_id>/update")
def update_staff(staff_id):
    response = require_management_access()
    if response:
        return response

    member = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "phone": request.form.get("phone", "").strip() or None,
        "position": request.form.get("position", "").strip(),
    }
    if not member["name"] or not member["email"] or not member["position"]:
        flash("Нэр, и-мэйл, албан тушаалыг бөглөнө үү.", "error")
        return redirect(url_for("dashboard_section", section="staff"))
    try:
        result = supabase.table("staff").update(member).eq("id", str(staff_id)).select("id").execute()
        flash("Ажилтны мэдээлэл шинэчлэгдлээ." if result.data else "Ажилтан олдсонгүй.", "success" if result.data else "error")
    except Exception:
        app.logger.exception("Staff update failed")
        flash("Ажилтан засахад алдаа гарлаа.", "error")
    return redirect(url_for("dashboard_section", section="staff"))


@app.post("/dashboard/staff/<uuid:staff_id>/delete")
def delete_staff(staff_id):
    response = require_management_access()
    if response:
        return response
    try:
        result = (
            supabase.table("staff")
            .delete()
            .eq("id", str(staff_id))
            .select("id")
            .execute()
        )
        flash("Ажилтан устгагдлаа." if result.data else "Ажилтан олдсонгүй.", "success" if result.data else "error")
    except Exception:
        app.logger.exception("Staff deletion failed")
        flash("Ажилтан устгахад алдаа гарлаа.", "error")
    return redirect(url_for("dashboard_section", section="staff"))


@app.post("/logout")
def logout():
    if not valid_csrf_token():
        abort(400)
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)