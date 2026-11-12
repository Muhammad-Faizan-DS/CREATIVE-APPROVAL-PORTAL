"""Tables 01-07: roles, users, client organisations and teams."""

from ..extensions import db


class Role(db.Model):
    """01 roles - the three portal roles: manager, designer, client."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), nullable=False, unique=True)
    label = db.Column(db.String(80), nullable=False)

    users = db.relationship("User", back_populates="role", passive_deletes="all")

    def __str__(self):
        return self.label


class User(db.Model):
    """02 users - one sign-in account with exactly one role."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.ForeignKey("roles.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    role = db.relationship("Role", back_populates="users")
    client_memberships = db.relationship(
        "ClientMembership", back_populates="user", passive_deletes="all"
    )
    team_memberships = db.relationship(
        "TeamMembership", back_populates="user", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class Client(db.Model):
    """03 clients - the advertiser organisation that orders the work."""

    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    website_url = db.Column(db.String(500))

    brands = db.relationship(
        "Brand", back_populates="client", passive_deletes="all"
    )
    memberships = db.relationship(
        "ClientMembership", back_populates="client", passive_deletes="all"
    )
    contacts = db.relationship(
        "ClientContact", back_populates="client", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class ClientMembership(db.Model):
    """04 client_memberships - which reviewers belong to a client."""

    __tablename__ = "client_memberships"
    __table_args__ = (db.UniqueConstraint("client_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.ForeignKey("clients.id"), nullable=False, index=True)
    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    can_approve = db.Column(db.Boolean, nullable=False, default=False)

    client = db.relationship("Client", back_populates="memberships")
    user = db.relationship("User", back_populates="client_memberships")


class Team(db.Model):
    """05 teams - the production team a campaign is assigned to."""

    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    description = db.Column(db.Text)

    memberships = db.relationship(
        "TeamMembership", back_populates="team", passive_deletes="all"
    )
    campaigns = db.relationship(
        "Campaign", back_populates="team", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class TeamMembership(db.Model):
    """06 team_memberships - which designers belong to a team."""

    __tablename__ = "team_memberships"
    __table_args__ = (db.UniqueConstraint("team_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.ForeignKey("teams.id"), nullable=False, index=True)
    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    joined_on = db.Column(db.Date, nullable=False)

    team = db.relationship("Team", back_populates="memberships")
    user = db.relationship("User", back_populates="team_memberships")


class ClientContact(db.Model):
    """07 client_contacts - address book entries for a client."""

    __tablename__ = "client_contacts"
    __table_args__ = (db.UniqueConstraint("client_id", "email"),)

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.ForeignKey("clients.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    job_title = db.Column(db.String(120))

    client = db.relationship("Client", back_populates="contacts")
