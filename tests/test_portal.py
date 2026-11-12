"""Automated checks for the Creative Approval Portal.

Run from the project root:  python -m unittest discover -s tests
"""

import base64
import io
import tempfile
import unittest
from datetime import date

from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

from portal import create_app
from portal.extensions import db
from portal.models import (
    Audience,
    DeliveryBatch,
    Brand,
    Brief,
    BriefDeliverable,
    BriefRequirement,
    Campaign,
    CampaignChannel,
    Channel,
    Client,
    ClientMembership,
    Creative,
    CreativeFormat,
    CreativeVersion,
    ReviewAssignment,
    ReviewRound,
    Role,
    Task,
    Team,
    TeamMembership,
    User,
)

PASSWORD = "portal-test-pass"

# A real 1 x 1 PNG, so the signature check passes.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8"
    "BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class PortalTestCase(unittest.TestCase):
    """Shared demo data: one campaign, one brief and two client organisations."""

    def setUp(self):
        self.uploads = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "SECRET_KEY": "test-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "UPLOAD_FOLDER": self.uploads.name,
            "WTF_CSRF_ENABLED": False,
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self._seed()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.ctx.pop()
        self.uploads.cleanup()

    # -- helpers ----------------------------------------------------------
    def _user(self, name, email, role):
        user = User(
            name=name, email=email, role=role,
            password_hash=generate_password_hash(PASSWORD),
        )
        db.session.add(user)
        return user

    def _seed(self):
        roles = {
            code: Role(code=code, label=code.capitalize())
            for code in ("manager", "designer", "client")
        }
        db.session.add_all(roles.values())
        db.session.flush()

        self.manager = self._user("Dana", "manager@example.test", roles["manager"])
        self.designer = self._user("Sam", "designer@example.test", roles["designer"])
        self.reviewer = self._user("Riya", "client@example.test", roles["client"])
        self.outsider = self._user("Tom", "other@example.test", roles["client"])
        db.session.flush()

        self.client_org = Client(name="Northwind")
        self.other_org = Client(name="Lumen")
        db.session.add_all([self.client_org, self.other_org])
        db.session.flush()
        db.session.add_all([
            ClientMembership(client_id=self.client_org.id,
                             user_id=self.reviewer.id, can_approve=True),
            ClientMembership(client_id=self.other_org.id,
                             user_id=self.outsider.id, can_approve=True),
        ])

        self.team = Team(name="Studio One")
        db.session.add(self.team)
        db.session.flush()
        db.session.add(TeamMembership(team_id=self.team.id,
                                      user_id=self.designer.id,
                                      joined_on=date.today()))

        self.brand = Brand(client_id=self.client_org.id, name="Roast")
        db.session.add(self.brand)
        db.session.flush()
        db.session.add(Audience(brand_id=self.brand.id, label="Commuters",
                                description="City commuters."))

        self.campaign = Campaign(brand_id=self.brand.id, team_id=self.team.id,
                                 name="Autumn", starts_on=date.today(),
                                 status="active")
        channel = Channel(name="Instagram feed")
        self.format = CreativeFormat(name="Square 1080", width_px=1080,
                                     height_px=1080)
        db.session.add_all([self.campaign, channel, self.format])
        db.session.flush()

        self.link = CampaignChannel(campaign_id=self.campaign.id,
                                    channel_id=channel.id)
        db.session.add(self.link)
        db.session.flush()

        self.brief = Brief(campaign_id=self.campaign.id,
                           created_by=self.reviewer.id, title="Launch posts",
                           goal="Launch the autumn roast.", due_on=date.today(),
                           status="draft")
        db.session.add(self.brief)
        db.session.flush()
        db.session.add(BriefRequirement(brief_id=self.brief.id,
                                        label="Logo", details="Show the logo."))
        self.deliverable = BriefDeliverable(
            brief_id=self.brief.id, campaign_channel_id=self.link.id,
            creative_format_id=self.format.id, label="Square posts", quantity=2,
        )
        db.session.add(self.deliverable)
        db.session.commit()

    def signed_in(self, email):
        """Return a test client already signed in as the given account."""
        client = self.app.test_client()
        client.get("/login")
        response = client.post("/login", data=self.with_token(client, {
            "email": email, "password": PASSWORD,
        }))
        self.assertEqual(response.status_code, 303)
        return client

    def with_token(self, client, data):
        """Add the session form token to a POST body.

        A GET first, exactly as a browser does, so the session holds a token.
        """
        with client.session_transaction() as session:
            token = session.get("csrf_token")
        if token is None:
            client.get("/login")
            with client.session_transaction() as session:
                token = session.get("csrf_token")
        payload = dict(data)
        payload["csrf_token"] = token
        return payload

    def post(self, client, url, data=None, follow=False):
        return client.post(url, data=self.with_token(client, data or {}),
                           follow_redirects=follow)


class SchemaTests(PortalTestCase):

    def test_schema_has_forty_tables(self):
        self.assertEqual(len(inspect(db.engine).get_table_names()), 40)

    def test_foreign_keys_are_enforced(self):
        """SQLite must refuse a child row with an unknown parent."""
        from sqlalchemy.exc import IntegrityError

        db.session.add(Brand(client_id=9999, name="Ghost"))
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()


class SessionTests(PortalTestCase):

    def test_login_page_loads(self):
        self.assertEqual(self.app.test_client().get("/login").status_code, 200)

    def test_bad_password_is_rejected(self):
        client = self.app.test_client()
        client.get("/login")
        response = client.post("/login", data=self.with_token(client, {
            "email": "manager@example.test", "password": "wrong",
        }))
        self.assertEqual(response.status_code, 400)

    def test_guest_is_redirected_to_login(self):
        response = self.app.test_client().get("/brands")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_post_without_token_is_rejected(self):
        client = self.signed_in("manager@example.test")
        response = client.post("/brands/new", data={"name": "No token"})
        self.assertEqual(response.status_code, 400)

    def test_client_cannot_open_manager_settings(self):
        client = self.signed_in("client@example.test")
        self.assertEqual(client.get("/settings/").status_code, 403)

    def test_other_organisation_gets_404(self):
        outsider = self.signed_in("other@example.test")
        url = f"/briefs/{self.brief.id}"
        self.assertEqual(outsider.get(url).status_code, 404)


class BrandCrudTests(PortalTestCase):

    def test_create_list_rename_and_delete(self):
        client = self.signed_in("manager@example.test")

        response = self.post(client, "/brands/new", {
            "name": "Cold Brew", "client_id": self.client_org.id,
        })
        self.assertEqual(response.status_code, 303)

        listing = client.get("/brands")
        self.assertIn(b"Cold Brew", listing.data)

        brand = db.session.scalar(db.select(Brand).filter_by(name="Cold Brew"))
        response = self.post(client, f"/brands/{brand.id}/edit",
                             {"name": "Cold Brew Classic"})
        self.assertEqual(response.status_code, 303)
        db.session.refresh(brand)
        self.assertEqual(brand.name, "Cold Brew Classic")

        response = self.post(client, f"/brands/{brand.id}/delete")
        self.assertEqual(response.status_code, 303)
        self.assertIsNone(db.session.get(Brand, brand.id))

    def test_blank_name_is_rejected(self):
        client = self.signed_in("manager@example.test")
        response = self.post(client, "/brands/new", {
            "name": "   ", "client_id": self.client_org.id,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"1 to 120 characters", response.data)

    def test_duplicate_name_for_one_client_is_rejected(self):
        client = self.signed_in("manager@example.test")
        response = self.post(client, "/brands/new", {
            "name": "Roast", "client_id": self.client_org.id,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"already has a brand", response.data)

    def test_unknown_client_is_rejected(self):
        client = self.signed_in("manager@example.test")
        response = self.post(client, "/brands/new",
                             {"name": "Ghost", "client_id": 9999})
        self.assertEqual(response.status_code, 400)

    def test_parent_with_children_is_protected(self):
        """Deleting a client that still has a brand must fail cleanly."""
        client = self.signed_in("manager@example.test")
        response = self.post(
            client, f"/manage/clients/{self.client_org.id}/delete", follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"depend on this client", response.data)
        self.assertIsNotNone(db.session.get(Client, self.client_org.id))


class SharedFormTests(PortalTestCase):

    def test_quantity_must_be_positive(self):
        client = self.signed_in("client@example.test")
        response = self.post(
            client,
            f"/manage/brief_deliverables/new?parent_id={self.brief.id}",
            {
                "campaign_channel_id": self.link.id,
                "creative_format_id": self.format.id,
                "label": "Extra posts",
                "quantity": "0",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"1 or more", response.data)

    def test_channel_from_another_campaign_is_rejected(self):
        other_brand = Brand(client_id=self.other_org.id, name="Gym")
        db.session.add(other_brand)
        db.session.flush()
        other_campaign = Campaign(brand_id=other_brand.id, team_id=self.team.id,
                                  name="Spring", starts_on=date.today())
        channel = Channel(name="Display")
        db.session.add_all([other_campaign, channel])
        db.session.flush()
        foreign_link = CampaignChannel(campaign_id=other_campaign.id,
                                       channel_id=channel.id)
        db.session.add(foreign_link)
        db.session.commit()

        client = self.signed_in("client@example.test")
        response = self.post(
            client,
            f"/manage/brief_deliverables/new?parent_id={self.brief.id}",
            {
                "campaign_channel_id": foreign_link.id,
                "creative_format_id": self.format.id,
                "label": "Wrong channel",
                "quantity": "1",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Choose an existing channel", response.data)

    def test_successful_post_redirects_and_does_not_duplicate_on_refresh(self):
        client = self.signed_in("manager@example.test")
        url = f"/manage/client_contacts/new?parent_id={self.client_org.id}"
        response = self.post(client, url, {
            "name": "Riya", "email": "riya@northwind.example",
            "job_title": "Brand lead",
        })
        self.assertEqual(response.status_code, 303)
        target = response.headers["Location"]
        self.assertEqual(client.get(target).status_code, 200)
        self.assertEqual(client.get(target).status_code, 200)
        self.assertEqual(len(self.client_org.contacts), 1)


class ApprovalFlowTests(PortalTestCase):
    """The brief, draft, review, revision, approval and delivery path."""

    def submit_brief(self):
        client = self.signed_in("client@example.test")
        response = self.post(client, f"/briefs/{self.brief.id}/submit")
        self.assertEqual(response.status_code, 303)
        db.session.refresh(self.brief)
        self.assertEqual(self.brief.status, "submitted")
        return client

    def make_version(self, creative):
        version = CreativeVersion(
            creative_id=creative.id, created_by=self.designer.id,
            version_number=len(creative.versions) + 1,
        )
        db.session.add(version)
        db.session.commit()
        return version

    def upload_png(self, client, version, filename="preview.png"):
        return client.post(
            f"/versions/{version.id}/files",
            data=self.with_token(client, {
                "kind": "preview",
                "image": (io.BytesIO(PNG_BYTES), filename),
            }),
            content_type="multipart/form-data",
        )

    def test_incomplete_brief_cannot_be_submitted(self):
        for requirement in list(self.brief.requirements):
            db.session.delete(requirement)
        db.session.commit()
        client = self.signed_in("client@example.test")
        response = self.post(client, f"/briefs/{self.brief.id}/submit",
                             follow=True)
        self.assertIn(b"at least one requirement", response.data)
        db.session.refresh(self.brief)
        self.assertEqual(self.brief.status, "draft")

    def test_creative_needs_a_submitted_brief(self):
        designer = self.signed_in("designer@example.test")
        response = self.post(
            designer,
            f"/manage/creatives/new?parent_id={self.deliverable.id}",
            {"name": "Too early"},
        )
        self.assertEqual(response.status_code, 403)

    def test_full_approval_and_delivery(self):
        self.submit_brief()
        designer = self.signed_in("designer@example.test")

        # Version 1
        response = self.post(
            designer,
            f"/manage/creatives/new?parent_id={self.deliverable.id}",
            {"name": "Morning cup"},
        )
        self.assertEqual(response.status_code, 303)
        creative = db.session.scalar(db.select(Creative))
        version_one = self.make_version(creative)

        # A version needs a preview before it can go to review.
        response = self.post(
            designer, f"/versions/{version_one.id}/submit",
            {"reviewer_id": self.reviewer.id}, follow=True,
        )
        self.assertIn(b"Upload a preview image", response.data)

        self.assertEqual(self.upload_png(designer, version_one).status_code, 303)
        self.assertEqual(len(version_one.previews), 1)

        response = self.post(designer, f"/versions/{version_one.id}/submit",
                             {"reviewer_id": self.reviewer.id})
        self.assertEqual(response.status_code, 303)
        round_one = version_one.review_round
        self.assertIsNotNone(round_one)

        # A second version may not start while the first is in review.
        response = self.post(
            designer,
            f"/manage/creative_versions/new?parent_id={creative.id}", {},
        )
        self.assertEqual(response.status_code, 400)

        # The client asks for changes; a note is required.
        reviewer = self.signed_in("client@example.test")
        response = self.post(reviewer, f"/reviews/{round_one.id}/decision",
                             {"outcome": "changes_requested", "note": ""},
                             follow=True)
        self.assertIn(b"Explain what should change", response.data)

        response = self.post(
            reviewer, f"/reviews/{round_one.id}/decision",
            {"outcome": "changes_requested", "note": "Make the logo bigger."},
        )
        self.assertEqual(response.status_code, 303)

        # A second decision on the same round is refused.
        response = self.post(reviewer, f"/reviews/{round_one.id}/decision",
                             {"outcome": "approved", "note": ""})
        self.assertEqual(response.status_code, 403)

        # Version 2 is allowed now, and keeps version 1 in history.
        response = self.post(
            designer,
            f"/manage/creative_versions/new?parent_id={creative.id}",
            {"notes": "Bigger logo."},
        )
        self.assertEqual(response.status_code, 303)
        db.session.refresh(creative)
        version_two = creative.latest_version
        self.assertEqual(version_two.version_number, 2)

        self.upload_png(designer, version_two, "v2.png")
        self.post(designer, f"/versions/{version_two.id}/submit",
                  {"reviewer_id": self.reviewer.id})
        round_two = version_two.review_round
        self.post(reviewer, f"/reviews/{round_two.id}/decision",
                  {"outcome": "approved", "note": "Looks good."})
        db.session.refresh(version_two)
        self.assertEqual(round_two.decision.outcome, "approved")
        self.assertEqual(round_one.decision.outcome, "changes_requested")

        # The manager builds, sends and the client acknowledges a batch.
        manager = self.signed_in("manager@example.test")
        response = self.post(
            manager,
            f"/manage/delivery_batches/new?parent_id={self.campaign.id}",
            {"title": "Autumn pack 1"},
        )
        self.assertEqual(response.status_code, 303)
        batch = self.campaign.delivery_batches[0]

        # A version that was only in review cannot be delivered.
        response = self.post(
            manager, f"/manage/delivery_items/new?parent_id={batch.id}",
            {"creative_version_id": version_one.id, "label": "Rejected draft"},
        )
        self.assertEqual(response.status_code, 400)

        # An empty batch cannot be sent.
        response = self.post(manager, f"/deliveries/{batch.id}/send",
                             follow=True)
        self.assertIn(b"at least one approved version", response.data)

        response = self.post(
            manager, f"/manage/delivery_items/new?parent_id={batch.id}",
            {"creative_version_id": version_two.id, "label": "Square post"},
        )
        self.assertEqual(response.status_code, 303)

        response = self.post(manager, f"/deliveries/{batch.id}/send")
        self.assertEqual(response.status_code, 303)
        db.session.refresh(batch)
        self.assertTrue(batch.is_sent)

        response = self.post(reviewer, f"/deliveries/{batch.id}/receipt",
                             {"note": "Received, thank you."})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(len(batch.receipts), 1)

        # The same recipient cannot acknowledge twice.
        response = self.post(reviewer, f"/deliveries/{batch.id}/receipt",
                             follow=True)
        self.assertIn(b"already acknowledged", response.data)
        self.assertEqual(len(batch.receipts), 1)

        # History is protected: a reviewed version and a sent batch stay.
        response = self.post(
            designer, f"/manage/creative_versions/{version_one.id}/delete"
        )
        self.assertEqual(response.status_code, 403)
        response = self.post(
            manager, f"/manage/delivery_batches/{batch.id}/delete"
        )
        self.assertEqual(response.status_code, 403)
        self.assertIsNotNone(db.session.get(CreativeVersion, version_one.id))


class UploadTests(PortalTestCase):

    def setUp(self):
        super().setUp()
        self.brief.status = "submitted"
        creative = Creative(brief_deliverable_id=self.deliverable.id,
                            created_by=self.designer.id, name="Morning cup")
        db.session.add(creative)
        db.session.flush()
        self.version = CreativeVersion(creative_id=creative.id,
                                       created_by=self.designer.id,
                                       version_number=1)
        db.session.add(self.version)
        db.session.commit()

    def upload(self, client, payload, filename):
        return client.post(
            f"/versions/{self.version.id}/files",
            data=self.with_token(client, {
                "kind": "preview",
                "image": (io.BytesIO(payload), filename),
            }),
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    def test_valid_png_is_stored_and_served(self):
        designer = self.signed_in("designer@example.test")
        self.upload(designer, PNG_BYTES, "cup.png")
        db.session.refresh(self.version)
        self.assertEqual(len(self.version.files), 1)

        stored = self.version.files[0]
        self.assertEqual(stored.mime_type, "image/png")
        response = designer.get(f"/files/{stored.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.data, PNG_BYTES)
        response.close()

    def test_wrong_extension_is_rejected(self):
        designer = self.signed_in("designer@example.test")
        response = self.upload(designer, b"not an image", "notes.txt")
        self.assertIn(b"Upload a PNG or JPEG image", response.data)
        self.assertEqual(len(self.version.files), 0)

    def test_contents_must_match_the_extension(self):
        designer = self.signed_in("designer@example.test")
        response = self.upload(designer, b"<html>hello</html>", "fake.png")
        self.assertIn(b"not a valid PNG or JPEG", response.data)
        self.assertEqual(len(self.version.files), 0)

    def test_another_organisation_cannot_read_the_file(self):
        designer = self.signed_in("designer@example.test")
        self.upload(designer, PNG_BYTES, "cup.png")
        stored = self.version.files[0]
        outsider = self.signed_in("other@example.test")
        self.assertEqual(outsider.get(f"/files/{stored.id}").status_code, 404)

    def test_deleting_a_draft_file_removes_the_record_and_bytes(self):
        import os

        designer = self.signed_in("designer@example.test")
        self.upload(designer, PNG_BYTES, "cup.png")
        stored = self.version.files[0]
        path = os.path.join(self.uploads.name, stored.stored_name)
        self.assertTrue(os.path.exists(path))

        response = self.post(designer, f"/files/{stored.id}/delete")
        self.assertEqual(response.status_code, 303)
        self.assertFalse(os.path.exists(path))
        db.session.refresh(self.version)
        self.assertEqual(len(self.version.files), 0)


class ScreenTests(PortalTestCase):
    """Every screen in the schema table renders for the roles that own it."""

    def setUp(self):
        super().setUp()
        self.brief.status = "submitted"
        creative = Creative(brief_deliverable_id=self.deliverable.id,
                            created_by=self.designer.id, name="Morning cup")
        db.session.add(creative)
        db.session.flush()
        self.creative = creative
        self.version = CreativeVersion(creative_id=creative.id,
                                       created_by=self.designer.id,
                                       version_number=1)
        db.session.add(self.version)
        db.session.flush()
        self.round = ReviewRound(creative_version_id=self.version.id,
                                 opened_by=self.designer.id)
        db.session.add(self.round)
        db.session.flush()
        db.session.add(ReviewAssignment(review_round_id=self.round.id,
                                        reviewer_id=self.reviewer.id))
        self.task = Task(brief_id=self.brief.id, title="Design the posts")
        self.batch = DeliveryBatch(campaign_id=self.campaign.id,
                                   prepared_by=self.manager.id,
                                   title="Pack 1")
        db.session.add_all([self.task, self.batch])
        db.session.commit()

    def test_manager_screens(self):
        client = self.signed_in("manager@example.test")
        pages = [
            "/", "/settings/", "/clients/", "/brands", "/brands/new",
            f"/clients/{self.client_org.id}",
            f"/brands/{self.brand.id}", f"/brands/{self.brand.id}/edit",
            f"/settings/teams/{self.team.id}",
            f"/campaigns/{self.campaign.id}",
            f"/campaigns/{self.campaign.id}/deliveries",
            f"/deliveries/{self.batch.id}",
            f"/briefs/{self.brief.id}", f"/tasks/{self.task.id}",
            f"/deliverables/{self.deliverable.id}",
            f"/creatives/{self.creative.id}",
            f"/versions/{self.version.id}", f"/reviews/{self.round.id}",
        ]
        for key in ("roles", "users", "teams", "channels", "creative_formats",
                    "tags", "campaigns", "clients"):
            pages.append(f"/manage/{key}")
            pages.append(f"/manage/{key}/new")
        for page in pages:
            with self.subTest(page=page):
                self.assertEqual(client.get(page).status_code, 200)

    def test_child_forms_open_for_their_owner(self):
        manager = self.signed_in("manager@example.test")
        designer = self.signed_in("designer@example.test")
        reviewer = self.signed_in("client@example.test")
        cases = [
            (manager, "client_memberships", self.client_org.id),
            (manager, "client_contacts", self.client_org.id),
            (manager, "team_memberships", self.team.id),
            (manager, "brand_guidelines", self.brand.id),
            (manager, "brand_assets", self.brand.id),
            (manager, "audiences", self.brand.id),
            (manager, "campaign_channels", self.campaign.id),
            (manager, "campaign_audiences", self.campaign.id),
            (manager, "tasks", self.brief.id),
            (manager, "task_assignees", self.task.id),
            (manager, "delivery_batches", self.campaign.id),
            (manager, "delivery_items", self.batch.id),
            (manager, "review_assignments", self.round.id),
            (reviewer, "briefs", self.campaign.id),
            (reviewer, "review_comments", self.round.id),
            (reviewer, "change_requests", self.round.id),
            (designer, "creatives", self.deliverable.id),
            (designer, "creative_versions", self.creative.id),
            (designer, "copy_variants", self.creative.id),
            (designer, "creative_tags", self.creative.id),
            (designer, "task_checklist_items", self.task.id),
            (designer, "task_comments", self.task.id),
        ]
        for client, key, parent_id in cases:
            with self.subTest(resource=key):
                response = client.get(f"/manage/{key}/new?parent_id={parent_id}")
                self.assertEqual(response.status_code, 200)

    def test_designer_and_client_see_their_own_work(self):
        designer = self.signed_in("designer@example.test")
        self.assertEqual(designer.get("/").status_code, 200)
        self.assertEqual(
            designer.get(f"/versions/{self.version.id}").status_code, 200
        )
        self.assertEqual(designer.get("/settings/").status_code, 403)

        reviewer = self.signed_in("client@example.test")
        self.assertEqual(reviewer.get("/").status_code, 200)
        self.assertEqual(
            reviewer.get(f"/reviews/{self.round.id}").status_code, 200
        )
        self.assertEqual(reviewer.get("/brands").status_code, 403)


if __name__ == "__main__":
    unittest.main()
