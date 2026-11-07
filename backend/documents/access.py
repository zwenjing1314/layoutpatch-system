from sqlalchemy import and_, or_
from backend.db.models import Document, User


def readable_document(user):
    """Same own+active-admin-shared rule for search and object access."""
    return and_(Document.status == "ready", Document.deleted_at.is_(None),
                or_(Document.owner_id == user.id,
                    and_(Document.visibility == "shared", User.role == "admin", User.active.is_(True))))
