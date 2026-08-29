-- BAOBAB workspace identifiers use the "ws_<hex>" format, not UUIDs.
ALTER TABLE cm_analyze_log
    ALTER COLUMN workspace_id TYPE VARCHAR(40) USING workspace_id::text;
