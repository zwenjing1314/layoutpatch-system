"""Initial frozen metadata schema, generated once from reviewed 1B-2 models."""
from alembic import op

revision = "0001_metadata"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
CREATE TABLE users (
	id VARCHAR(36) NOT NULL, 
	username VARCHAR(64) COLLATE "NOCASE" NOT NULL, 
	password_hash TEXT NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	active BOOLEAN NOT NULL, 
	must_change_password BOOLEAN NOT NULL, 
	auth_version INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	updated_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_user_role CHECK (role IN ('admin','user')), 
	CONSTRAINT ck_user_flags CHECK (active IN (0,1) AND must_change_password IN (0,1)), 
	CONSTRAINT ck_auth_version CHECK (auth_version >= 1), 
	UNIQUE (username)
)

""")
    op.execute("""
CREATE TABLE documents (
	id VARCHAR(36) NOT NULL, 
	source_key VARCHAR NOT NULL, 
	owner_id VARCHAR(36) NOT NULL, 
	display_name VARCHAR NOT NULL, 
	visibility VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	active_version_id VARCHAR(36), 
	deleted_at VARCHAR, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_visibility CHECK (visibility IN ('private','shared')), 
	CONSTRAINT ck_document_status CHECK (status IN ('registered','ready','deleted')), 
	CONSTRAINT fk_active_version_belongs_to_document FOREIGN KEY(id, active_version_id) REFERENCES document_versions (document_id, id) DEFERRABLE INITIALLY DEFERRED, 
	UNIQUE (source_key), 
	FOREIGN KEY(owner_id) REFERENCES users (id)
)

""")
    op.execute("""
CREATE TABLE document_versions (
	id VARCHAR(36) NOT NULL, 
	document_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	pdf_sha256 VARCHAR(64) NOT NULL, 
	pdf_path VARCHAR NOT NULL, 
	page_count INTEGER NOT NULL, 
	render_profile_json TEXT NOT NULL, 
	render_profile_sha256 VARCHAR(64) NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_document_version UNIQUE (document_id, version), 
	CONSTRAINT uq_document_version_identity UNIQUE (document_id, id), 
	CONSTRAINT ck_version_counts CHECK (version >= 1 AND page_count > 0), 
	CONSTRAINT ck_version_hashes CHECK (length(pdf_sha256)=64 AND length(render_profile_sha256)=64), 
	FOREIGN KEY(document_id) REFERENCES documents (id)
)

""")
    op.execute("""
CREATE TABLE pages (
	id VARCHAR(36) NOT NULL, 
	document_version_id VARCHAR(36) NOT NULL, 
	source_page_id VARCHAR NOT NULL, 
	page_index INTEGER NOT NULL, 
	width_px INTEGER NOT NULL, 
	height_px INTEGER NOT NULL, 
	render_sha256 VARCHAR(64) NOT NULL, 
	image_path VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_page_order UNIQUE (document_version_id, page_index), 
	CONSTRAINT ck_page_geometry CHECK (page_index >= 0 AND width_px > 0 AND height_px > 0), 
	CONSTRAINT ck_page_hash CHECK (length(render_sha256)=64), 
	FOREIGN KEY(document_version_id) REFERENCES document_versions (id), 
	UNIQUE (source_page_id)
)

""")
    op.execute("""
CREATE TABLE pipeline_profiles (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR NOT NULL, 
	config_json TEXT NOT NULL, 
	config_sha256 VARCHAR(64) NOT NULL, 
	status VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_profile_status CHECK (status IN ('pending','validated')), 
	UNIQUE (name), 
	UNIQUE (config_sha256)
)

""")
    op.execute("""
CREATE TABLE index_generations (
	id VARCHAR(36) NOT NULL, 
	profile_id VARCHAR(36) NOT NULL, 
	collection_name VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	page_count INTEGER NOT NULL, 
	vector_count INTEGER NOT NULL, 
	created_at VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_index_status CHECK (status IN ('pending','building','ready','failed')), 
	CONSTRAINT ck_index_counts CHECK (page_count >= 0 AND vector_count >= 0), 
	FOREIGN KEY(profile_id) REFERENCES pipeline_profiles (id), 
	UNIQUE (collection_name)
)

""")
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])
    op.create_index("ix_document_versions_document_id", "document_versions", ["document_id"])
    op.create_index("ix_pages_document_version_id", "pages", ["document_version_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade disabled; restore an explicit backup instead")
