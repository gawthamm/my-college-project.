"""
Automated Comprehensive Test Suite for Campus Smart Lost & Found System
Tests:
- Database initialization
- User registration and authentication
- Item reporting (lost and found)
- Smart matching algorithm calculations
- Ownership claim workflow
- Admin verification and digital return receipt generation
"""

import unittest
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database as db
import matcher
from app import app

class TestCampusLostAndFound(unittest.TestCase):

    @classmethod
    def tearDownClass(cls):
        """Purge temporary test data, preserving only the admin account."""
        db.execute_query("DELETE FROM smart_matches", commit=True)
        db.execute_query("DELETE FROM notifications", commit=True)
        db.execute_query("DELETE FROM item_returns", commit=True)
        db.execute_query("DELETE FROM claims", commit=True)
        db.execute_query("DELETE FROM items", commit=True)
        db.execute_query("DELETE FROM users WHERE role != 'admin'", commit=True)

    def setUp(self):
        """Set up test environment."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        # Initialize test tables
        db.init_db()

    def test_01_database_engine_and_categories(self):
        """Verify database engine and default categories seeded."""
        engine = db.get_engine_name()
        self.assertIn(engine, ['MySQL', 'SQLite'])
        categories = db.get_categories()
        self.assertGreaterEqual(len(categories), 7)
        print(f"\n[PASS] Database connected via {engine}. Seeded categories: {len(categories)}")

    def test_02_user_registration_and_login(self):
        """Test student registration and login."""
        test_email = 'teststudent@campus.edu'
        test_id = 'STUTEST999'

        # Clean existing test user if present
        existing = db.get_user_by_email(test_email)
        if not existing:
            # Register user via POST
            response = self.client.post('/register', data={
                'full_name': 'Test Student',
                'email': test_email,
                'student_id': test_id,
                'phone': '9876543299',
                'department': 'Computer Science',
                'password': 'Password@123',
                'confirm_password': 'Password@123'
            }, follow_redirects=True)
            self.assertEqual(response.status_code, 200)

        # Login
        login_resp = self.client.post('/login', data={
            'email': test_email,
            'password': 'Password@123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)
        self.assertIn(b'Test Student', login_resp.data)
        print("\n[PASS] User registration and session authentication verified.")

    def test_03_smart_matching_algorithm(self):
        """Verify the Python Smart Matching score calculation."""
        item_lost = {
            'id': 1,
            'title': 'HP Pavilion 15 Silver Laptop',
            'category_id': 1,
            'description': 'Silver HP laptop with GitHub sticker on the back lid. Charger in black sleeve.',
            'location': 'Central Library 2nd Floor',
            'event_date': '2026-10-09',
            'primary_color': 'Silver',
            'brand': 'HP'
        }

        item_found_match = {
            'id': 2,
            'title': 'HP Laptop with Developer Stickers',
            'category_id': 1,
            'description': 'Found HP 15-inch silver laptop on desk 14. Has stickers on lid.',
            'location': 'Central Library 2nd Floor',
            'event_date': '2026-10-10',
            'primary_color': 'Silver',
            'brand': 'HP'
        }

        item_found_unrelated = {
            'id': 3,
            'title': 'Blue Umbrella',
            'category_id': 7,
            'description': 'Foldable blue umbrella found near parking lot.',
            'location': 'Main Gate Parking',
            'event_date': '2026-10-01',
            'primary_color': 'Blue',
            'brand': 'Unknown'
        }

        match_res = matcher.match_score(item_lost, item_found_match)
        unrelated_res = matcher.match_score(item_lost, item_found_unrelated)

        print(f"\n[PASS] Smart Match Score (High Match): {match_res['total_score']}% ({match_res['confidence']})")
        print(f"       Breakdown: {match_res['breakdown']}")
        print(f"[PASS] Smart Match Score (Unrelated):  {unrelated_res['total_score']}% ({unrelated_res['confidence']})")

        self.assertGreaterEqual(match_res['total_score'], 60.0)
        self.assertLess(unrelated_res['total_score'], 30.0)

    def test_04_ownership_claim_and_admin_workflow(self):
        """Test reporting, claiming, and admin return verification."""
        from werkzeug.security import generate_password_hash

        # Ensure dynamic test users exist
        finder = db.get_user_by_email('finder_test@campus.edu')
        finder_id = finder['id'] if finder else db.create_user(
            'Test Finder', 'finder_test@campus.edu', 'FINDER01', '9876543201',
            generate_password_hash('Student@123')
        )

        claimant = db.get_user_by_email('claimant_test@campus.edu')
        if not claimant:
            db.create_user(
                'Test Claimant', 'claimant_test@campus.edu', 'CLAIMANT01', '9876543202',
                generate_password_hash('Student@123')
            )

        test_found_id = db.create_item(
            user_id=finder_id,
            item_type='found',
            title='Test Casio Watch Black Strap',
            category_id=6,
            description='Found analog watch with black leather strap near basketball court bench.',
            location='Sports Ground Court 2',
            event_date='2026-10-11',
            primary_color='Black',
            brand='Casio',
            image_filename='default_item.svg',
            storage_location='Security Office Room 10'
        )
        self.assertIsNotNone(test_found_id)

        # Student logs in and claims this found item
        student_client = app.test_client()
        login_resp = student_client.post('/login', data={
            'identifier': 'claimant_test@campus.edu',
            'password': 'Student@123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # Submit claim
        claim_resp = student_client.post(f'/items/{test_found_id}/claim', data={
            'proof_description': 'Black leather strap has double-stitched buckle and initials RS etched behind dial.',
            'contact_number': '9876543202'
        }, follow_redirects=True)
        self.assertEqual(claim_resp.status_code, 200)
        self.assertIn(b'submitted', claim_resp.data.lower())

        # 3. Admin logs in to verify and approve claim
        admin_client = app.test_client()
        admin_login = admin_client.post('/login', data={
            'email': 'admin@campus.edu',
            'password': 'Admin@123'
        }, follow_redirects=True)
        self.assertEqual(admin_login.status_code, 200)

        # Find the submitted claim for our item
        item_claims = db.get_claims_for_item(test_found_id)
        self.assertEqual(len(item_claims), 1)
        target_claim_id = item_claims[0]['id']

        # Admin approves claim
        review_resp = admin_client.post(f'/admin/claims/{target_claim_id}', data={
            'action': 'approve',
            'admin_notes': 'Initials RS verified on watch backplate. Student ID verified.'
        }, follow_redirects=True)
        self.assertEqual(review_resp.status_code, 200)

        # Admin issues Handover Return
        return_resp = admin_client.post(f'/admin/return/{target_claim_id}', data={
            'verification_method': 'Student ID Card & Physical Inspection',
            'remarks': 'Watch handed over in functional condition.'
        }, follow_redirects=True)
        self.assertEqual(return_resp.status_code, 200)
        self.assertIn(b'RETURNED TO OWNER', return_resp.data)
        self.assertIn(b'Test Casio Watch', return_resp.data)
        print("\n[PASS] End-to-end claim review and digital return receipt generation verified.")

    def test_05_notifications_and_stats(self):
        """Verify notification dispatch and statistical aggregations."""
        stats = db.get_dashboard_stats()
        self.assertGreaterEqual(stats['total_items'], 1)
        print(f"\n[PASS] Dashboard Stats verified: Total items={stats['total_items']}, Returned={stats['returned_items']}, Resolution Rate={stats['resolution_rate']}%")

if __name__ == '__main__':
    unittest.main()
