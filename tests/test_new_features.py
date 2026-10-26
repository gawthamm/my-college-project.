"""
Test suite for Campus Lost & Found newly implemented features:
1. Automatic Match Notifications
2. Secure & Private Ownership Verification
3. Admin Analytics Dashboard
4. AI Chatbot Assistant (/api/chat)
5. Natural Language Search (/browse)
6. AI-Based Duplicate Report Detection
7. Real-Time Notifications Polling (/api/notifications/poll)
8. Item Recovery Tracking Timeline (5-step)
9. College Email Verification
10. Suspicious Claim Detection
"""
import unittest
import json
from app import app
import database as db
import matcher

class TestNewFeatures(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_ctx = app.app_context()
        self.app_ctx.push()

    def tearDown(self):
        self.app_ctx.pop()

    def test_01_college_email_verification(self):
        """Test registration allows approved college domains and rejects non-college emails."""
        # Non-college domain
        resp_invalid = self.client.post('/register', data={
            'full_name': 'Hacker Person',
            'email': 'baduser@randommail.com',
            'student_id': 'BAD001',
            'phone': '9999999999',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Registration is restricted to verified college community email addresses', resp_invalid.data)

        # Valid college domain (@acharya.ac.in or @campus.edu)
        resp_valid = self.client.post('/register', data={
            'full_name': 'Test College Student',
            'email': 'student.test1@acharya.ac.in',
            'student_id': 'AGS24TEST001',
            'phone': '9876500001',
            'password': 'password123',
            'confirm_password': 'password123'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', resp_valid.data)

    def test_02_natural_language_search_extraction(self):
        """Test Natural Language query entity extraction."""
        query = "Find a red bag I might have lost in the computer lab last Friday"
        parsed = matcher.parse_natural_language_query(query)
        self.assertTrue(parsed['is_natural_language'])
        self.assertEqual(parsed['item_type'], 'lost')
        self.assertEqual(parsed['color'], 'Red')
        self.assertEqual(parsed['category_name'], 'Bags & Wallets')
        self.assertEqual(parsed['location'], 'Computer Lab')
        self.assertIsNotNone(parsed['date_hint'])

        # Test through browse route
        resp = self.client.get(f'/browse?q={query}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Natural Language Search', resp.data)

    def test_03_ai_duplicate_detection(self):
        """Test Duplicate Report Detection across identical/similar physical items."""
        item1 = {
            'id': 101,
            'item_type': 'found',
            'category_id': 1,
            'title': 'Black Dell 65W Laptop Charger',
            'description': 'Found near library reading desk',
            'location': 'Central Library',
            'event_date': '2026-10-18'
        }
        item2 = {
            'id': 102,
            'item_type': 'found',
            'category_id': 1,
            'title': 'Dell Laptop Charger 65W Black',
            'description': 'Charger picked up in library',
            'location': 'Library 1st floor',
            'event_date': '2026-10-18'
        }
        dups = matcher.detect_duplicates(item1, [item2], threshold=65.0)
        self.assertGreaterEqual(len(dups), 1)
        self.assertGreaterEqual(dups[0]['duplicate_score'], 65.0)
        self.assertIn('Same category', dups[0]['reasons'])

    def test_04_chatbot_assistant_api(self):
        """Test /api/chat endpoint conversational and search responses."""
        # 1. Procedural FAQ
        resp_faq = self.client.post('/api/chat', 
            data=json.dumps({'message': 'Where is the security office?'}),
            content_type='application/json'
        )
        self.assertEqual(resp_faq.status_code, 200)
        faq_data = resp_faq.get_json()
        self.assertIn('Campus Security Office', faq_data['text'])

        # 2. Procedural Claim Help
        resp_claim = self.client.post('/api/chat',
            data=json.dumps({'message': 'How do I claim a found item?'}),
            content_type='application/json'
        )
        self.assertEqual(resp_claim.status_code, 200)
        claim_data = resp_claim.get_json()
        self.assertIn('How to Claim a Found Item', claim_data['text'])

    def test_05_admin_analytics_and_suspicious_detection(self):
        """Test Admin Analytics and Suspicious Claim detection."""
        stats = db.get_dashboard_stats()
        self.assertIn('total_items', stats)
        self.assertIn('lost_items', stats)
        self.assertIn('found_items', stats)
        self.assertIn('returned_items', stats)
        self.assertIn('pending_claims', stats)
        self.assertIn('frequent_lost_cats', stats)
        self.assertIn('monthly_labels', stats)
        self.assertIn('monthly_data', stats)

        alerts = db.get_suspicious_claim_alerts()
        self.assertIsInstance(alerts, list)

    def test_06_realtime_notifications_poll(self):
        """Test /api/notifications/poll endpoint."""
        # Unauthenticated returns logged_in: False
        resp_guest = self.client.get('/api/notifications/poll')
        self.assertEqual(resp_guest.status_code, 200)
        self.assertFalse(resp_guest.get_json()['logged_in'])

if __name__ == '__main__':
    unittest.main()
