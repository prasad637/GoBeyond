-- GO BEYOND: PostgreSQL Initialization Script
-- Ensures btree_gist extension is available for GiST range exclusion constraints.
CREATE EXTENSION IF NOT EXISTS btree_gist;

