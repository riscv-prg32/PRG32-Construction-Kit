"""Classes: teachers and facilitators see their students' work (ADR-0016).

A class has members, each a ``student``, ``teacher`` or ``facilitator``:

- an account with the academic role ``teacher`` (or an administrator) makes a class
  and is its first teacher;
- a class's teachers add and remove **students** (accounts whose academic role is
  ``student``); only administrators add teachers and facilitators, so nobody can
  give themselves more rights;
- teachers and facilitators may **read** the projects, sprites, builds and artifacts
  of the students in their classes, never change them; students see only themselves.

Classes and their roles stay in the kit: they are not sent to CartridgeStore.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request
from sqlalchemy import delete, select
from sqlalchemy.orm import Mapped, mapped_column

from . import security
from .db import db, list_resources, utcnow

CLASS_ROLES = ("student", "teacher", "facilitator")


class SchoolClass(db.Model):
    __tablename__ = "classes"
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(db.Text, nullable=False)
    created_by: Mapped[int | None] = mapped_column(db.Integer)
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


class ClassMember(db.Model):
    __tablename__ = "class_members"
    class_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(db.Text, nullable=False, default="student")
    added_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


# --- who supervises whom ---------------------------------------------------------

def supervised_students(principal) -> set[int]:
    """Ids of the students in the classes where this person is a teacher or facilitator."""
    if not principal.authenticated or principal.id is None:
        return set()
    cache = g.setdefault("prg32_supervised", {})
    if principal.id not in cache:
        classes = select(ClassMember.class_id).where(ClassMember.user_id == principal.id,
                                                     ClassMember.role.in_(("teacher", "facilitator")))
        cache[principal.id] = set(db.session.scalars(
            select(ClassMember.user_id).where(ClassMember.class_id.in_(classes), ClassMember.role == "student")))
    return cache[principal.id]


def supervises(principal, owner_id: Any) -> bool:
    return owner_id is not None and owner_id != principal.id and owner_id in supervised_students(principal)


def _forget() -> None:
    g.pop("prg32_supervised", None)


# --- the API ----------------------------------------------------------------------

bp = Blueprint("classes", __name__)


def _member(class_id: int, user_id: int) -> ClassMember | None:
    return db.session.get(ClassMember, (class_id, user_id))


def _class_role(principal, class_id: int) -> str | None:
    member = _member(class_id, principal.id)
    return member.role if member else None


def _as_dict(item: SchoolClass, principal) -> dict[str, Any]:
    from .auth import User

    role = _class_role(principal, item.id)
    out = {"id": item.id, "name": item.name, "created_at": item.created_at, "my_role": role}
    if principal.is_admin or role in ("teacher", "facilitator"):
        members = db.session.execute(select(ClassMember, User).join(User, User.id == ClassMember.user_id)
                                     .where(ClassMember.class_id == item.id).order_by(User.username)).all()
        out["members"] = [{"user_id": user.id, "username": user.username, "role": member.role}
                          for member, user in members]
    return out


def _find_user(data: dict[str, Any]):
    from .auth import User, find_user_by_email

    if data.get("user_id") is not None:
        return db.session.get(User, data.get("user_id"))
    name = str(data.get("username") or "").strip()
    return db.session.scalar(select(User).where(User.username == name)) or (find_user_by_email(name) if name else None)


@bp.route("/api/classes", methods=["GET", "POST"])
def api_classes():
    from .auth import current_principal

    principal = current_principal()
    if request.method == "GET":
        query = select(SchoolClass).order_by(SchoolClass.name)
        if not principal.is_admin:
            query = query.where(SchoolClass.id.in_(select(ClassMember.class_id).where(ClassMember.user_id == principal.id)))
        return jsonify({"classes": [_as_dict(item, principal) for item in db.session.scalars(query)]})
    if not (principal.is_admin or principal.is_teacher):
        security.record("class_create", target_type="class", outcome="denied")
        return jsonify({"error": "Only teachers can make classes"}), 403
    name = str((request.get_json(silent=True) or {}).get("name") or "").strip()[:80]
    if not name:
        return jsonify({"error": "name is required"}), 400
    item = SchoolClass(name=name, created_by=principal.id)
    db.session.add(item)
    db.session.flush()
    if principal.is_teacher:
        db.session.add(ClassMember(class_id=item.id, user_id=principal.id, role="teacher"))
    db.session.commit()
    security.record("class_create", target_type="class", target_id=item.id, metadata={"name": name})
    return jsonify(_as_dict(item, principal)), 201


@bp.route("/api/classes/<int:class_id>", methods=["GET", "PUT", "DELETE"])
def api_class(class_id: int):
    from .auth import current_principal

    principal = current_principal()
    item = db.session.get(SchoolClass, class_id)
    role = _class_role(principal, class_id) if item else None
    if item is None or not (principal.is_admin or role):
        return jsonify({"error": "class not found"}), 404
    if request.method == "GET":
        return jsonify(_as_dict(item, principal))
    if not (principal.is_admin or role == "teacher"):
        security.record("class_update", target_type="class", target_id=class_id, outcome="denied")
        return jsonify({"error": "Only the class's teachers can change it"}), 403
    if request.method == "DELETE":
        db.session.delete(item)
        db.session.commit()
        _forget()
        security.record("class_delete", target_type="class", target_id=class_id, metadata={"name": item.name})
        return jsonify({"deleted": True})
    name = str((request.get_json(silent=True) or {}).get("name") or "").strip()[:80]
    if not name:
        return jsonify({"error": "name is required"}), 400
    item.name = name
    db.session.commit()
    return jsonify(_as_dict(item, principal))


@bp.post("/api/classes/<int:class_id>/members")
def api_add_member(class_id: int):
    from .auth import current_principal

    principal = current_principal()
    item = db.session.get(SchoolClass, class_id)
    role = _class_role(principal, class_id) if item else None
    if item is None or not (principal.is_admin or role):
        return jsonify({"error": "class not found"}), 404
    data = request.get_json(silent=True) or {}
    wanted = str(data.get("role") or "student")
    user = _find_user(data)
    if wanted not in CLASS_ROLES:
        return jsonify({"error": "role must be one of: " + ", ".join(CLASS_ROLES)}), 400
    if user is None:
        return jsonify({"error": "no such account"}), 404
    # Teachers add students only; teachers and facilitators are added by an administrator.
    allowed = principal.is_admin or (role == "teacher" and wanted == "student")
    fits = {"student": ("student",), "teacher": ("teacher",), "facilitator": ("facilitator", "teacher")}[wanted]
    if not allowed or (user.kit_role or "student") not in fits:
        security.record("class_member_add", target_type="class", target_id=class_id, outcome="denied",
                        metadata={"user_id": user.id, "role": wanted})
        reason = ("only an administrator can add teachers or facilitators" if not allowed
                  else f"{user.username} is a {user.kit_role or 'student'}, not a {wanted}")
        return jsonify({"error": reason}), 403
    member = _member(class_id, user.id)
    if member is None:
        db.session.add(ClassMember(class_id=class_id, user_id=user.id, role=wanted))
    else:
        member.role = wanted
    db.session.commit()
    _forget()
    security.record("class_member_add", target_type="class", target_id=class_id,
                    metadata={"user_id": user.id, "role": wanted})
    return jsonify(_as_dict(item, principal)), 201


@bp.delete("/api/classes/<int:class_id>/members/<int:user_id>")
def api_remove_member(class_id: int, user_id: int):
    from .auth import current_principal

    principal = current_principal()
    item = db.session.get(SchoolClass, class_id)
    role = _class_role(principal, class_id) if item else None
    member = _member(class_id, user_id) if item else None
    if item is None or not (principal.is_admin or role):
        return jsonify({"error": "class not found"}), 404
    if member is None:
        return jsonify({"error": "not a member"}), 404
    if not (principal.is_admin or (role == "teacher" and member.role == "student")):
        security.record("class_member_remove", target_type="class", target_id=class_id, outcome="denied",
                        metadata={"user_id": user_id})
        return jsonify({"error": "teachers remove students only; ask an administrator"}), 403
    db.session.execute(delete(ClassMember).where(ClassMember.class_id == class_id, ClassMember.user_id == user_id))
    db.session.commit()
    _forget()
    security.record("class_member_remove", target_type="class", target_id=class_id, metadata={"user_id": user_id})
    return jsonify(_as_dict(item, principal))


@bp.get("/api/classes/<int:class_id>/projects")
def api_class_projects(class_id: int):
    """The projects of the class's students, for its teachers and facilitators (read-only)."""
    from .auth import current_principal

    principal = current_principal()
    item = db.session.get(SchoolClass, class_id)
    role = _class_role(principal, class_id) if item else None
    if item is None or not (principal.is_admin or role in ("teacher", "facilitator")):
        return jsonify({"error": "class not found"}), 404
    students = list(db.session.scalars(select(ClassMember.user_id).where(ClassMember.class_id == class_id,
                                                                        ClassMember.role == "student")))
    projects = []
    for student in students:
        projects.extend(list_resources("projects", {}, viewer_id=student))
    shown = [{"id": project["id"], "title": project["title"], "owner_id": project.get("owner_id"),
              "updated_at": project.get("updated_at"), "can_edit": False}
             for project in projects if project.get("owner_id") in students]
    return jsonify({"class": item.name, "projects": sorted(shown, key=lambda project: project["title"])})


@bp.get("/classes")
def classes_page():
    from flask import render_template

    return render_template("classes.html")


def init_app(app) -> None:
    app.register_blueprint(bp)
