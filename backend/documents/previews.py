"""Preview URLs grant no access without the issuing, still-valid session."""
import hashlib
import hmac


def preview_token(row, page_id, render_sha256, access_version=1):
    message = f"layoutpatch-preview-v2:{page_id}:{render_sha256}:{access_version}".encode()
    return hmac.new(row.csrf_token.encode(), message, hashlib.sha256).hexdigest()


def preview_url(row, page_id, render_sha256, access_version=1):
    return f"/pages/{page_id}/image?preview={preview_token(row, page_id, render_sha256, access_version)}"
