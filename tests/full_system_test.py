"""
EXHAUSTIVE SYSTEM AUDIT & DEBUG TEST SUITE
Campus Smart Lost & Found System
Exercises every function, route, button, role, boundary condition, and security vector.
"""

import unittest
import os
import sys
import json
from datetime import datetime, timedelta

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db
import matcher
from app import app, is_safe_url

class ExhaustiveSystemAuditTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Prepare test app client."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()
        db.init_db()
        from werkzeug.security import generate_password_hash
        h = generate_password_hash('Student@123')
        if not db.get_user_by_email('student1@campus.edu'):
            db.create_user('Student One', 'student1@campus.edu', 'STU001', '9876543201', h)
        if not db.get_user_by_email('student2@campus.edu'):
            db.create_user('Student Two', 'student2@campus.edu', 'STU002', '9876543202', h)

    @classmethod
    def tearDownClass(cls):
        """Clean up test records to leave the production database clean."""
        db.execute_query("DELETE FROM smart_matches", commit=True)
        db.execute_query("DELETE FROM notifications", commit=True)
        db.execute_query("DELETE FROM item_returns", commit=True)
        db.execute_query("DELETE FROM claims", commit=True)
        db.execute_query("DELETE FROM items", commit=True)
        db.execute_query("DELETE FROM users WHERE role != 'admin'", commit=True)

    # =========================================================================
    # MODULE 1: Database Layer & Utility Functions
    # =========================================================================
    def test_01_db_connection_and_stats(self):
        conn, engine = db.get_db_connection()
        self.assertIsNotNone(conn)
        self.assertIn(engine, ('mysql', 'sqlite'))
        conn.close()

        stats = db.get_dashboard_stats()
        self.assertIn('total_items', stats)
        self.assertIn('category_chart_labels', stats)
        self.assertIn('category_chart_data', stats)
        self.assertEqual(len(stats['category_chart_labels']), len(stats['category_chart_data']))

    def test_02_db_user_identifiers(self):
        # Admin lookup by username, email, and student_id
        admin1 = db.get_user_by_identifier('admin')
        self.assertIsNotNone(admin1)
        self.assertEqual(admin1['role'], 'admin')

        admin2 = db.get_user_by_identifier('admin@campus.edu')
        self.assertIsNotNone(admin2)
        self.assertEqual(admin1['id'], admin2['id'])

        admin3 = db.get_user_by_identifier('ADMIN001')
        self.assertIsNotNone(admin3)

        none_user = db.get_user_by_identifier('non_existent_user_99999')
        self.assertIsNone(none_user)

    # =========================================================================
    # MODULE 2: Python Smart Matcher Algorithm & Edge Cases
    # =========================================================================
    def test_03_matcher_boundary_conditions(self):
        # Empty inputs
        self.assertEqual(matcher.clean_tokens(""), set())
        self.assertEqual(matcher.clean_tokens(None), set())
        self.assertEqual(matcher.calculate_token_similarity(set(), set()), 0.0)
        self.assertEqual(matcher.calculate_sequence_similarity("", ""), 0.0)
        self.assertEqual(matcher.calculate_sequence_similarity(None, "test"), 0.0)

        # Date proximity edge cases
        self.assertEqual(matcher.calculate_date_proximity("2026-10-10", "2026-10-10"), 1.0)
        self.assertGreaterEqual(matcher.calculate_date_proximity("2026-10-10", "2026-10-12"), 0.8)
        self.assertEqual(matcher.calculate_date_proximity("invalid-date", "2026-10-10"), 0.3)

        # Match calculation robustness with corrupt fields
        item_corrupt = {'id': 999, 'title': None, 'description': None, 'location': None, 'event_date': None}
        item_normal = {'id': 1000, 'title': 'Calculator', 'description': 'Black Casio', 'location': 'Library', 'event_date': '2026-10-10'}
        res = matcher.match_score(item_corrupt, item_normal)
        self.assertIsInstance(res['total_score'], float)
        self.assertGreaterEqual(res['total_score'], 0.0)
        self.assertLessEqual(res['total_score'], 100.0)

    # =========================================================================
    # MODULE 3: Security & URL Validation (Open Redirect, SQLi, XSS)
    # =========================================================================
    def test_04_security_open_redirect_prevention(self):
        # Malicious redirect URLs
        self.assertFalse(is_safe_url('//evil.com'))
        self.assertFalse(is_safe_url('/\\evil.com'))
        self.assertFalse(is_safe_url('\\\\evil.com'))
        self.assertFalse(is_safe_url('http://evil.com'))
        self.assertFalse(is_safe_url('https://evil.com'))
        self.assertFalse(is_safe_url('javascript:alert(1)'))
        self.assertFalse(is_safe_url(None))
        self.assertFalse(is_safe_url(''))

        # Legitimate relative URLs
        self.assertTrue(is_safe_url('/browse'))
        self.assertTrue(is_safe_url('/admin'))
        self.assertTrue(is_safe_url('/items/1'))

    def test_05_security_sqli_and_xss_sanitization(self):
        # SQL Injection in browse search
        sqli_payload = "' OR '1'='1' --"
        resp = self.client.get(f'/browse?q={sqli_payload}')
        self.assertEqual(resp.status_code, 200)

        # XSS injection payload in search
        xss_payload = "<script>alert('xss')</script>"
        resp2 = self.client.get(f'/browse?q={xss_payload}')
        self.assertEqual(resp2.status_code, 200)
        # Ensure payload is escaped, not raw executable
        self.assertNotIn(b"<script>alert('xss')</script>", resp2.data)
        self.assertIn(b"&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;", resp2.data)

    def test_06_security_unauthorized_role_access(self):
        # Anonymous user cannot access admin
        resp1 = self.client.get('/admin', follow_redirects=False)
        self.assertEqual(resp1.status_code, 302)
        self.assertIn('/login', resp1.headers['Location'])

        # Regular student cannot access admin dashboard
        student_client = app.test_client()
        student_client.post('/login', data={'identifier': 'student1@campus.edu', 'password': 'Student@123'})
        resp2 = student_client.get('/admin', follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Access denied', resp2.data)

    # =========================================================================
    # MODULE 4: Authentication Flows (Student & Admin)
    # =========================================================================
    def test_07_auth_admin_login_with_username_and_password(self):
        client = app.test_client()
        # Login with username: admin and password: ADMIN@123
        resp = client.post('/login', data={'identifier': 'admin', 'password': 'ADMIN@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Security Command Dashboard', resp.data)

    def test_08_auth_student_registration_validation(self):
        client = app.test_client()
        # 1. Password mismatch
        resp1 = client.post('/register', data={
            'full_name': 'New Student',
            'email': 'newstudent1@campus.edu',
            'student_id': 'STU99001',
            'phone': '9876543210',
            'password': 'Password123',
            'confirm_password': 'DifferentPassword'
        })
        self.assertIn(b'Passwords do not match', resp1.data)

        # 2. Short password
        resp2 = client.post('/register', data={
            'full_name': 'New Student',
            'email': 'newstudent2@campus.edu',
            'student_id': 'STU99002',
            'phone': '9876543210',
            'password': '123',
            'confirm_password': '123'
        })
        self.assertIn(b'at least 6 characters', resp2.data)

        # 3. Successful registration
        unique_email = f"audit_stu_{datetime.now().strftime('%Y%m%d%H%M%S')}@campus.edu"
        unique_id = f"STUAUDIT_{datetime.now().strftime('%M%S')}"
        resp3 = client.post('/register', data={
            'full_name': 'Audit Student',
            'email': unique_email,
            'student_id': unique_id,
            'phone': '9876543299',
            'department': 'Information Technology',
            'password': 'Student@123',
            'confirm_password': 'Student@123'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', resp3.data)

    # =========================================================================
    # MODULE 5: Item Reporting & Server-side Validation
    # =========================================================================
    def test_09_report_item_validation(self):
        client = app.test_client()
        client.post('/login', data={'identifier': 'student1@campus.edu', 'password': 'Student@123'})

        # 1. Future date validation
        future_date = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d')
        resp1 = client.post('/report', data={
            'item_type': 'lost',
            'title': 'Future Lost Item',
            'category_id': 1,
            'location': 'Library',
            'event_date': future_date,
            'description': 'Testing future date'
        }, follow_redirects=True)
        self.assertIn(b'cannot be in the future', resp1.data)

        # 2. Missing mandatory fields
        resp2 = client.post('/report', data={
            'item_type': 'lost',
            'title': '',
            'category_id': 1,
            'location': 'Library',
            'event_date': '2026-10-10',
            'description': ''
        }, follow_redirects=True)
        self.assertIn(b'mandatory fields', resp2.data)

        # 3. Valid Lost Report
        resp3 = client.post('/report', data={
            'item_type': 'lost',
            'title': 'Lenovo ThinkPad Black Laptop',
            'category_id': 1,
            'location': 'Computer Lab 301',
            'event_date': datetime.now().strftime('%Y-%m-%d'),
            'primary_color': 'Black',
            'brand': 'Lenovo',
            'description': 'Black ThinkPad laptop with red trackpoint button.'
        }, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn(b'Lenovo ThinkPad', resp3.data)

    # =========================================================================
    # MODULE 6: Ownership Claim Protocol & Anti-Fraud Checks
    # =========================================================================
    def test_10_claim_workflow_and_guardrails(self):
        # 1. Priya (id=3) reports a found item
        priya_client = app.test_client()
        priya_client.post('/login', data={'identifier': 'student2@campus.edu', 'password': 'Student@123'})

        found_resp = priya_client.post('/report', data={
            'item_type': 'found',
            'title': 'Sony Wireless Headphones Case',
            'category_id': 1,
            'location': 'Cafeteria Table 7',
            'event_date': datetime.now().strftime('%Y-%m-%d'),
            'primary_color': 'Black',
            'brand': 'Sony',
            'storage_location': 'Security Desk Gate 2',
            'description': 'Found black charging case with headphones.'
        }, follow_redirects=True)
        self.assertEqual(found_resp.status_code, 200)

        # Extract item ID from database
        items = db.get_items(search_query='Sony Wireless Headphones Case')
        self.assertGreater(len(items), 0)
        item_id = items[0]['id']

        # 2. Priya tries to claim her own reported item -> Must fail
        self_claim_resp = priya_client.post(f'/items/{item_id}/claim', data={
            'proof_description': 'Self claim attempt',
            'contact_number': '9876543212'
        }, follow_redirects=True)
        self.assertIn(b'cannot claim an item you reported yourself', self_claim_resp.data)

        # 3. Rahul (id=2) submits a legitimate claim
        rahul_client = app.test_client()
        rahul_client.post('/login', data={'identifier': 'student1@campus.edu', 'password': 'Student@123'})

        claim_resp = rahul_client.post(f'/items/{item_id}/claim', data={
            'proof_description': 'Right earbud has a small scratch on outer rim, device model WF-1000XM4.',
            'contact_number': '9876543211'
        }, follow_redirects=True)
        self.assertIn(b'claim has been submitted', claim_resp.data.lower())

        # 4. Rahul tries to claim the same item twice -> Must fail
        dup_claim_resp = rahul_client.post(f'/items/{item_id}/claim', data={
            'proof_description': 'Second attempt',
            'contact_number': '9876543211'
        }, follow_redirects=True)
        self.assertIn(b'already submitted a claim', dup_claim_resp.data)

        # 5. Admin logs in, reviews side-by-side, and approves
        admin_client = app.test_client()
        admin_client.post('/login', data={'identifier': 'admin', 'password': 'ADMIN@123'})

        claims = db.get_claims_for_item(item_id)
        self.assertEqual(len(claims), 1)
        claim_id = claims[0]['id']

        approve_resp = admin_client.post(f'/admin/claims/{claim_id}', data={
            'action': 'approve',
            'admin_notes': 'Model number and scratch verified against physical case.'
        }, follow_redirects=True)
        self.assertEqual(approve_resp.status_code, 200)

        # 6. Admin completes handover and issues receipt
        return_resp = admin_client.post(f'/admin/return/{claim_id}', data={
            'verification_method': 'Student ID Card & Physical Inspection',
            'remarks': 'Handed over directly to student Rahul.'
        }, follow_redirects=True)
        self.assertEqual(return_resp.status_code, 200)
        self.assertIn(b'RETURNED TO OWNER', return_resp.data)

        # 7. Another student tries to claim this ALREADY RETURNED item -> Must fail
        another_client = app.test_client()
        another_client.post('/login', data={'identifier': 'student2@campus.edu', 'password': 'Student@123'})
        late_claim_resp = another_client.post(f'/items/{item_id}/claim', data={
            'proof_description': 'Late claim',
            'contact_number': '9876543299'
        }, follow_redirects=True)
        self.assertIn(b'already been returned', late_claim_resp.data)

    # =========================================================================
    # MODULE 7: Notifications & Receipt Verification
    # =========================================================================
    def test_11_notification_operations(self):
        client = app.test_client()
        client.post('/login', data={'identifier': 'student1@campus.edu', 'password': 'Student@123'})

        # View notifications
        notif_resp = client.get('/notifications')
        self.assertEqual(notif_resp.status_code, 200)

        # Mark all read
        mark_all_resp = client.post('/notifications/read-all', follow_redirects=True)
        self.assertEqual(mark_all_resp.status_code, 200)
        self.assertIn(b'marked as read', mark_all_resp.data)

    def test_12_receipt_token_verification(self):
        returns = db.get_all_returns()
        self.assertGreater(len(returns), 0)
        sample_token = returns[0]['receipt_token']

        # Valid receipt URL
        valid_resp = self.client.get(f'/receipt/{sample_token}')
        self.assertEqual(valid_resp.status_code, 200)
        self.assertIn(b'Official Lost &amp; Found Custody &amp; Handover Certificate', valid_resp.data)

        # Invalid receipt URL
        invalid_resp = self.client.get('/receipt/NON_EXISTENT_TOKEN_9999', follow_redirects=True)
        self.assertEqual(invalid_resp.status_code, 200)
        self.assertIn(b'Receipt token not found', invalid_resp.data)

    # =========================================================================
    # MODULE 8: REST API & Error Handlers
    # =========================================================================
    def test_13_rest_api_endpoints(self):
        items = db.get_items(limit=1)
        self.assertGreater(len(items), 0)
        valid_item_id = items[0]['id']

        # 1. Valid API call
        resp1 = self.client.get(f'/api/match/{valid_item_id}')
        self.assertEqual(resp1.status_code, 200)
        data = json.loads(resp1.data)
        self.assertEqual(data['item_id'], valid_item_id)
        self.assertIn('matches_found', data)

        # 2. Non-existent item
        resp2 = self.client.get('/api/match/999999')
        self.assertEqual(resp2.status_code, 404)

        # 3. Invalid negative ID
        resp3 = self.client.get('/api/match/-5')
        self.assertIn(resp3.status_code, (400, 404))

    def test_14_custom_404_page(self):
        resp = self.client.get('/a-completely-non-existent-page-url')
        self.assertEqual(resp.status_code, 404)
        self.assertIn(b'404 - Page Not Found', resp.data)

if __name__ == '__main__':
    unittest.main()
