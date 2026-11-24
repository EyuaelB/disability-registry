-- Which register an inbound DCI message lands in, and where its record
-- identifier sits.
--
-- reg_type accepts the standard's example value (ns:org:RegistryType:DR, see
-- dr_api_v1.0.0 search_criteria) and the legacy spelling this registry used. Only PersonWithDisability accepts inbound messages: the
-- support sub-registers are written as part of the person's payload, never
-- addressed on their own.
INSERT INTO "public"."incoming_model_register_semantic_patterns" ("register_semantic_pattern_id","data_model_id","register_id","pattern_for_register","key_path_for_record_identifier") VALUES
('REG-SEM-PATTERN-1','DM1','a0000000-0000-4000-8000-000000000001','$.body.message.search_response[0].data.reg_type=>^ns:org:RegistryType:(DR|Disability)$','$.body.message.search_response[0].data.reg_records[0].member_identifier[0].identifier_value')
ON CONFLICT ("register_semantic_pattern_id") DO NOTHING;
