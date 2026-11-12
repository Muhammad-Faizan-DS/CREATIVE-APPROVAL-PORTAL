# Schema

The portal stores 40 related tables. Every row has an integer `id` primary key. An arrow marks a foreign key and its target table. Fields are required unless marked optional.

| # | Table | Fields and foreign keys | CRUD screen |
| --- | --- | --- | --- |
| 01 | `roles` | code unique, label | Settings › Roles |
| 02 | `users` | role_id → roles, name, email unique, password_hash, is_active | Settings › Users |
| 03 | `clients` | name unique, website_url optional | Clients |
| 04 | `client_memberships` | client_id → clients, user_id → users, can_approve, unique client_id and user_id | Client › Members |
| 05 | `teams` | name unique, description optional | Settings › Teams |
| 06 | `team_memberships` | team_id → teams, user_id → users, joined_on, unique team_id and user_id | Team › Members |
| 07 | `client_contacts` | client_id → clients, name, email, job_title optional, unique client_id and email | Client › Contacts |
| 08 | `brands` | client_id → clients, name, unique client_id and name | Brands |
| 09 | `brand_guidelines` | brand_id → brands, title, rule_text, unique brand_id and title | Brand › Guidelines |
| 10 | `brand_assets` | brand_id → brands, label, asset_type, url | Brand › Assets |
| 11 | `campaigns` | brand_id → brands, team_id → teams, name, starts_on, ends_on optional, status, unique brand_id and name | Campaigns |
| 12 | `channels` | name unique | Settings › Channels |
| 13 | `campaign_channels` | campaign_id → campaigns, channel_id → channels, note optional, unique campaign_id and channel_id | Campaign › Channels |
| 14 | `audiences` | brand_id → brands, label, description, unique brand_id and label | Brand › Audiences |
| 15 | `campaign_audiences` | campaign_id → campaigns, audience_id → audiences, priority, unique campaign_id and audience_id | Campaign › Audiences |
| 16 | `briefs` | campaign_id → campaigns, created_by → users, title, goal, due_on, status | Campaign › Briefs |
| 17 | `brief_references` | brief_id → briefs, label, url | Brief › References |
| 18 | `brief_requirements` | brief_id → briefs, label, details | Brief › Requirements |
| 19 | `brief_deliverables` | brief_id → briefs, campaign_channel_id → campaign_channels, creative_format_id → creative_formats, label, quantity | Brief › Deliverables |
| 20 | `tasks` | brief_id → briefs, title, due_on optional, status | Brief › Tasks |
| 21 | `task_assignees` | task_id → tasks, user_id → users, note optional, unique task_id and user_id | Task › Assignees |
| 22 | `task_checklist_items` | task_id → tasks, label, is_done | Task › Checklist |
| 23 | `task_comments` | task_id → tasks, author_id → users, body, created_at | Task › Comments |
| 24 | `creatives` | brief_deliverable_id → brief_deliverables, created_by → users, name | Deliverable › Creatives |
| 25 | `creative_versions` | creative_id → creatives, created_by → users, version_number, notes optional, created_at, unique creative_id and version_number | Creative › Versions |
| 26 | `creative_formats` | name unique, width_px, height_px | Settings › Formats |
| 27 | `version_files` | creative_version_id → creative_versions, kind, display_name, stored_name unique, mime_type, size_bytes | Version › Files |
| 28 | `copy_variants` | creative_id → creatives, label, headline, primary_text, unique creative_id and label | Creative › Copy |
| 29 | `version_copy_variants` | creative_version_id → creative_versions, copy_variant_id → copy_variants, placement optional, unique creative_version_id and copy_variant_id | Version › Copy |
| 30 | `tags` | name unique | Settings › Tags |
| 31 | `creative_tags` | creative_id → creatives, tag_id → tags, note optional, unique creative_id and tag_id | Creative › Tags |
| 32 | `review_rounds` | creative_version_id → creative_versions unique, opened_by → users, opened_at, due_on optional | Version › Review |
| 33 | `review_assignments` | review_round_id → review_rounds, reviewer_id → users, can_decide, unique review_round_id and reviewer_id | Review › Reviewers |
| 34 | `review_comments` | review_round_id → review_rounds, author_id → users, body, created_at | Review › Comments |
| 35 | `review_decisions` | review_round_id → review_rounds unique, decided_by → users, outcome, note optional, created_at | Review › Decision |
| 36 | `change_requests` | review_round_id → review_rounds, created_by → users, instruction, resolved_by_version_id → creative_versions optional | Review › Changes |
| 37 | `review_attachments` | review_comment_id → review_comments, label, url | Comment › References |
| 38 | `delivery_batches` | campaign_id → campaigns, prepared_by → users, title, sent_at optional | Campaign › Deliveries |
| 39 | `delivery_items` | delivery_batch_id → delivery_batches, creative_version_id → creative_versions, label, unique delivery_batch_id and creative_version_id | Delivery › Items |
| 40 | `delivery_receipts` | delivery_batch_id → delivery_batches, received_by → users, received_at, note optional, unique delivery_batch_id and received_by | Delivery › Receipts |

## Reading the table

Bridge tables (`client_memberships`, `team_memberships`, `campaign_channels`, `campaign_audiences`, `task_assignees`, `version_copy_variants`, `creative_tags`, `review_assignments`, `delivery_items`, `delivery_receipts`) carry their own `id` and a unique constraint on the two foreign keys, and some store extra fields such as `priority` or `placement`.
