"""Creatives, their versions, and the image files uploaded to a draft."""

import uuid
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from ..access import (
    campaign_of_creative,
    campaign_of_deliverable,
    campaign_of_version,
    can_produce,
    require_view,
)
from ..extensions import db
from ..models import BriefDeliverable, Creative, CreativeVersion, VersionFile
from ..security import current_user, login_required
from ..workflow import is_draft, version_status

bp = Blueprint("creatives", __name__)

# Only these two image types are accepted, checked by file signature.
IMAGE_TYPES = {
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
}


def uploads_dir():
    """Uploaded images live outside the package, in the instance folder."""
    folder = current_app.config.get("UPLOAD_FOLDER")
    path = Path(folder) if folder else Path(current_app.instance_path) / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


@bp.get("/deliverables/<int:deliverable_id>")
@login_required
def deliverable_detail(deliverable_id):
    deliverable = db.get_or_404(BriefDeliverable, deliverable_id)
    require_view(current_user(), campaign_of_deliverable(deliverable))
    return render_template(
        "creatives/deliverable_detail.html", deliverable=deliverable
    )


@bp.get("/creatives/<int:creative_id>")
@login_required
def detail(creative_id):
    creative = db.get_or_404(Creative, creative_id)
    require_view(current_user(), campaign_of_creative(creative))
    return render_template("creatives/detail.html", creative=creative)


@bp.get("/versions/<int:version_id>")
@login_required
def version_detail(version_id):
    version = db.get_or_404(CreativeVersion, version_id)
    require_view(current_user(), campaign_of_version(version))
    user = current_user()
    campaign = campaign_of_version(version)
    return render_template(
        "versions/detail.html",
        version=version,
        status=version_status(version),
        can_edit=can_produce(user, campaign) and is_draft(version),
    )


@bp.post("/versions/<int:version_id>/files")
@login_required
def upload_file(version_id):
    """Store one PNG or JPEG against a draft version."""
    version = db.get_or_404(CreativeVersion, version_id)
    user = current_user()
    campaign = campaign_of_version(version)
    require_view(user, campaign)
    if not can_produce(user, campaign):
        abort(403)

    back = url_for("creatives.version_detail", version_id=version.id)
    if not is_draft(version):
        flash("This version is in review. Start a new version instead.", "error")
        return redirect(back, code=303)

    upload = request.files.get("image")
    if upload is None or not upload.filename:
        flash("Choose a PNG or JPEG image to upload.", "error")
        return redirect(back, code=303)

    extension = upload.filename.rsplit(".", 1)[-1].casefold()
    if extension not in IMAGE_TYPES:
        flash("Upload a PNG or JPEG image.", "error")
        return redirect(back, code=303)

    mime_type, signatures = IMAGE_TYPES[extension]
    head = upload.stream.read(8)
    upload.stream.seek(0)
    if not any(head.startswith(signature) for signature in signatures):
        flash("That file is not a valid PNG or JPEG image.", "error")
        return redirect(back, code=303)

    kind = request.form.get("kind", "preview")
    if kind not in ("preview", "export"):
        kind = "preview"
    display_name = secure_filename(upload.filename) or f"{kind}.{extension}"

    stored_name = f"{uuid.uuid4().hex}.{'jpg' if extension == 'jpeg' else extension}"
    target = uploads_dir() / stored_name
    upload.save(target)

    record = VersionFile(
        creative_version_id=version.id,
        kind=kind,
        display_name=display_name[:160],
        stored_name=stored_name,
        mime_type=mime_type,
        size_bytes=target.stat().st_size,
    )
    db.session.add(record)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        target.unlink(missing_ok=True)
        flash("The upload could not be saved. Try again.", "error")
        return redirect(back, code=303)

    flash("Image uploaded.", "success")
    return redirect(back, code=303)


@bp.post("/files/<int:file_id>/delete")
@login_required
def delete_file(file_id):
    """Commit the record deletion first, then remove the stored bytes."""
    record = db.get_or_404(VersionFile, file_id)
    user = current_user()
    version = record.version
    campaign = campaign_of_version(version)
    require_view(user, campaign)
    if not can_produce(user, campaign) or not is_draft(version):
        abort(403)

    stored = uploads_dir() / record.stored_name
    db.session.delete(record)
    db.session.commit()
    stored.unlink(missing_ok=True)
    flash("File deleted.", "success")
    return redirect(
        url_for("creatives.version_detail", version_id=version.id), code=303
    )


@bp.get("/files/<int:file_id>")
@login_required
def serve_file(file_id):
    """Serve an upload only to accounts that may see its campaign."""
    record = db.get_or_404(VersionFile, file_id)
    require_view(current_user(), campaign_of_version(record.version))
    response = send_from_directory(
        uploads_dir(),
        record.stored_name,
        mimetype=record.mime_type,
        download_name=record.display_name,
        as_attachment=request.args.get("download") == "1",
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
