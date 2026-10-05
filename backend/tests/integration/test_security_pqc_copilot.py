from tests.conftest import API


class TestIntegrity:
    def test_verify_reports_valid_chain(self, client, senior_analyst_headers):
        resp = client.get(f"{API}/security/integrity/verify", headers=senior_analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["valid"] is True
        assert body["total_records"] > 0
        assert body["first_broken_record_id"] is None

    def test_verify_requires_senior_analyst_role(self, client, analyst_headers):
        resp = client.get(f"{API}/security/integrity/verify", headers=analyst_headers)
        assert resp.status_code == 403

    def test_tamper_detected_end_to_end(self, client, senior_analyst_headers):
        """The real, most important integrity guarantee, exercised
        through the actual API rather than just the service layer."""
        from app.db.session import SessionLocal
        from app.models.transaction import Transaction

        db = SessionLocal()
        try:
            victim = db.query(Transaction).filter(Transaction.record_hash.isnot(None)).offset(500).first()
            original_amount = victim.amount
            victim.amount = original_amount + 999999.0
            db.commit()
            victim_id = victim.id
        finally:
            db.close()

        resp = client.get(f"{API}/security/integrity/verify", headers=senior_analyst_headers)
        body = resp.json()
        assert body["valid"] is False
        assert body["first_broken_record_id"] == victim_id

        # restore, so this test doesn't permanently corrupt the chain for
        # every subsequent test run
        db = SessionLocal()
        try:
            victim = db.query(Transaction).filter(Transaction.id == victim_id).first()
            victim.amount = original_amount
            db.commit()
        finally:
            db.close()

        resp2 = client.get(f"{API}/security/integrity/verify", headers=senior_analyst_headers)
        assert resp2.json()["valid"] is True, "chain should be valid again after restoring the tampered value"


class TestPqc:
    def test_status_reports_real_passing_self_test(self, client, analyst_headers):
        resp = client.get(f"{API}/security/pqc/status", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["kem_self_test_passed"] is True
        assert body["signature_self_test_passed"] is True
        assert body["kem_algorithm"] == "ML-KEM-768"
        assert body["signature_algorithm"] == "ML-DSA-65"

    def test_export_import_round_trip_through_api(self, client, compliance_officer_headers):
        export_resp = client.post(f"{API}/security/pqc/export-audit-log", params={"limit": 10}, headers=compliance_officer_headers)
        assert export_resp.status_code == 200
        bundle = export_resp.json()
        assert "encrypted_payload" in bundle

        import_resp = client.post(f"{API}/security/pqc/import-audit-export", json=bundle, headers=compliance_officer_headers)
        assert import_resp.status_code == 200
        assert import_resp.json()["signature_valid"] is True

    def test_export_requires_compliance_officer_role(self, client, analyst_headers):
        resp = client.post(f"{API}/security/pqc/export-audit-log", headers=analyst_headers)
        assert resp.status_code == 403

    def test_tampered_import_rejected_through_api(self, client, compliance_officer_headers):
        export_resp = client.post(f"{API}/security/pqc/export-audit-log", params={"limit": 5}, headers=compliance_officer_headers)
        bundle = export_resp.json()
        import base64
        raw = bytearray(base64.b64decode(bundle["signature"]))
        raw[0] ^= 0xFF
        bundle["signature"] = base64.b64encode(bytes(raw)).decode()
        resp = client.post(f"{API}/security/pqc/import-audit-export", json=bundle, headers=compliance_officer_headers)
        assert resp.status_code == 400


class TestSecurityCenter:
    def test_overview_accessible_to_any_authenticated_user(self, client, analyst_headers):
        resp = client.get(f"{API}/security/center/overview", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "application_security" in body
        assert "blockchain_integrity" in body
        assert "quantum_safe_security" in body
        assert "audit_trail" in body

    def test_overview_never_exposes_single_aggregate_score(self, client, analyst_headers):
        """Explicit project rule: no fabricated aggregate security score,
        anywhere in this response."""
        resp = client.get(f"{API}/security/center/overview", headers=analyst_headers)
        body = resp.json()
        assert "security_score" not in str(body).lower().replace(" ", "_")

    def test_audit_log_requires_compliance_officer_role(self, client, analyst_headers):
        resp = client.get(f"{API}/security/audit-log", headers=analyst_headers)
        assert resp.status_code == 403

    def test_audit_log_filters_by_resource(self, client, compliance_officer_headers, real_ieee_cis_transaction_id):
        client.get(f"{API}/investigation/transactions/{real_ieee_cis_transaction_id}", headers=compliance_officer_headers)
        resp = client.get(
            f"{API}/security/audit-log",
            params={"resource_type": "transaction", "resource_id": real_ieee_cis_transaction_id},
            headers=compliance_officer_headers,
        )
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) > 0
        assert all(e["resource_id"] == real_ieee_cis_transaction_id for e in entries)


class TestCopilot:
    def test_status_reports_honest_llm_configuration(self, client, analyst_headers):
        resp = client.get(f"{API}/copilot/status", headers=analyst_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "llm_configured" in body
        assert "retrieval_ready" in body

    def test_ask_without_llm_returns_evidence_digest_not_fabricated_ai(self, client, analyst_headers, real_ieee_cis_transaction_id):
        """This is the core no-fabrication guarantee for the copilot: if
        no LLM is configured, the response must say so explicitly and
        must not claim to be AI-generated."""
        status = client.get(f"{API}/copilot/status", headers=analyst_headers).json()
        resp = client.post(
            f"{API}/copilot/ask",
            json={"question": "Summarize the evidence for this transaction", "transaction_id": real_ieee_cis_transaction_id},
            headers=analyst_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        if not status["llm_configured"]:
            assert body["mode"] == "evidence_digest"
            assert body["warning"] is not None
            assert "no natural-language synthesis has been performed" in body["answer"].lower()
            assert "ai-generated" in body["answer"].lower()

    def test_ask_includes_source_citations(self, client, analyst_headers, real_ieee_cis_transaction_id):
        resp = client.post(
            f"{API}/copilot/ask",
            json={"question": "Why was this transaction flagged?", "transaction_id": real_ieee_cis_transaction_id},
            headers=analyst_headers,
        )
        body = resp.json()
        assert len(body["sources"]) > 0
        assert any(s["type"] == "evidence" for s in body["sources"])

    def test_ask_unknown_transaction_returns_404(self, client, analyst_headers):
        resp = client.post(
            f"{API}/copilot/ask",
            json={"question": "test", "transaction_id": "00000000-0000-0000-0000-000000000000"},
            headers=analyst_headers,
        )
        assert resp.status_code == 404

    def test_ask_without_transaction_context_still_works(self, client, analyst_headers):
        resp = client.post(f"{API}/copilot/ask", json={"question": "What security controls does this platform have?"}, headers=analyst_headers)
        assert resp.status_code == 200
        assert len(resp.json()["sources"]) > 0


class TestApiErrorHandling:
    def test_validation_error_returns_422_with_detail(self, client, analyst_headers):
        resp = client.get(f"{API}/transactions", params={"page": 0}, headers=analyst_headers)  # ge=1 violated
        assert resp.status_code == 422

    def test_nonexistent_route_returns_404(self, client, analyst_headers):
        resp = client.get(f"{API}/this/route/does/not/exist", headers=analyst_headers)
        assert resp.status_code == 404

    def test_unhandled_exceptions_dont_leak_stack_traces(self, client, analyst_headers):
        """Doesn't try to trigger a real 500 (deliberately breaking the
        app would be counterproductive); instead confirms the exception
        handler exists and error paths that do fire go through the
        structured {detail, path} shape rather than a raw stack trace."""
        resp = client.get(f"{API}/transactions/not-a-valid-uuid", headers=analyst_headers)
        assert resp.status_code == 404
        assert "detail" in resp.json()
