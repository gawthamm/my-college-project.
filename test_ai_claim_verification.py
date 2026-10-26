import os
import sys
from datetime import datetime

# Add app folder to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', '..', '..', 'scratch', 'campus_lost_and_found'))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import database as db
import matcher

def run_tests():
    print("=================================================================")
    print(" TESTING AI-ASSISTED SECURE OWNERSHIP VERIFICATION SYSTEM")
    print("=================================================================")
    
    # 1. Initialize DB and verify engine
    db.init_db()
    engine = db.get_engine_name()
    print(f"[1] Active Engine: {engine}")

    # 2. Get or create test users
    admin = db.get_user_by_identifier('admin')
    assert admin is not None, "Admin user must exist"
    print(f"[2] Admin user verified: {admin['full_name']} (Role: {admin['role']})")

    # Get or create student users
    alice = db.get_user_by_email('alice_test@campus.edu')
    if not alice:
        alice_id = db.create_user('Alice Sharma', 'alice_test@campus.edu', '1AY22CS001', '9876543201', 'hashed_pass', 'student', 'CSE')
        alice = db.get_user_by_id(alice_id)
    print(f"[3] Student Alice: {alice['full_name']} ({alice['student_id']})")

    bob = db.get_user_by_email('bob_fake@campus.edu')
    if not bob:
        bob_id = db.create_user('Bob Hacker', 'bob_fake@campus.edu', '1AY22CS999', '9876543299', 'hashed_pass', 'student', 'ISE')
        bob = db.get_user_by_id(bob_id)
    print(f"[4] Student Bob (Imposter): {bob['full_name']} ({bob['student_id']})")

    # 3. Finder creates a found item with secret identifying detail
    categories = db.get_categories()
    cat_id = categories[0]['id']
    
    item_id = db.create_item(
        user_id=alice['id'],
        item_type='found',
        title='Wildcraft Black Travel Backpack',
        category_id=cat_id,
        description='Found a black backpack near the central library staircase. Good condition.',
        location='Central Library Staircase 2nd Floor',
        event_date=str(datetime.now().date()),
        primary_color='Black',
        brand='Wildcraft',
        image_filename='default_item.svg',
        storage_location='Main Security Desk Gate 1',
        secret_details='Small tear inside left zip pocket; contains blue cardholder and Casio FX-991CW calculator'
    )
    
    item = db.get_item_by_id(item_id)
    print(f"[5] Found Item logged: #{item['id']} '{item['title']}'")
    assert item['secret_details'] is not None, "Secret details must be saved"

    # Log audit
    db.add_audit_log(
        user_id=alice['id'],
        action='Report Filed',
        item_id=item_id,
        details="Found item logged with secret verification details"
    )

    # 4. Imposter Bob attempts to claim with generic text and wrong secret
    bob_history = db.get_user_claim_history(bob['id'])
    eval_fake = matcher.evaluate_claim_authenticity(
        claim_text="Hey that's my bag please give it to me",
        secret_answer="Nothing special, just some normal books and a red pen",
        target_item=item,
        claimant_history=bob_history,
        has_image=False,
        evidence_type="Distinctive Feature / Marks"
    )

    print(f"[6] Fake Claim AI Evaluation Score: {eval_fake['total_score']}%")
    print(f"    AI Recommendation: {eval_fake['recommendation']}")
    print(f"    Secret Verification: {eval_fake['secret_verification_level']}")
    print(f"    Risk Flags: {eval_fake['risk_flags']}")
    assert eval_fake['total_score'] < 45.0, "Fake claim score must be low"
    assert eval_fake['recommendation'] == "High Risk / Likely Fake Claim", "Fake claim must be flagged as high risk"

    # 5. Legitimate owner Alice attempts to claim with exact secret detail and photo proof
    alice_history = db.get_user_claim_history(alice['id'])
    eval_legit = matcher.evaluate_claim_authenticity(
        claim_text="My black Wildcraft backpack lost yesterday near the library. Has my notes and calculator inside.",
        secret_answer="Small tear inside the left zip pocket, contains blue cardholder with my ID card and a Casio FX991CW calculator",
        target_item=item,
        claimant_history=alice_history,
        has_image=True,
        evidence_type="Photo with Item"
    )

    print(f"[7] Legitimate Claim AI Evaluation Score: {eval_legit['total_score']}%")
    print(f"    AI Recommendation: {eval_legit['recommendation']}")
    print(f"    Secret Verification: {eval_legit['secret_verification_level']}")
    print(f"    Evidence Status: {eval_legit['evidence_status']}")
    print(f"    Risk Flags: {eval_legit['risk_flags']}")
    assert eval_legit['total_score'] >= 75.0, "Legit claim score must be >= 75%"
    assert eval_legit['recommendation'] == "Recommend Approval", "Legit claim must recommend approval"

    # 6. Create the claim in DB
    claim_id = db.create_claim(
        item_id=item['id'],
        claimant_id=alice['id'],
        proof_description="My black Wildcraft backpack lost yesterday near library.",
        proof_image="default_item.svg",
        contact_number="9876543201",
        secret_answer="Small tear inside left zip pocket, blue cardholder, Casio FX991CW",
        claim_match_score=eval_legit['total_score'],
        ai_recommendation=eval_legit['recommendation'],
        risk_flags="None detected",
        evidence_type="Photo with Item"
    )
    print(f"[8] Claim #{claim_id} stored in database")

    # Audit log
    db.add_audit_log(
        user_id=alice['id'],
        action='Claim Submitted',
        item_id=item['id'],
        claim_id=claim_id,
        details=f"Score: {eval_legit['total_score']}% | Rec: {eval_legit['recommendation']}"
    )

    # 7. Verify retrieval from DB
    retrieved_claim = db.get_claim_by_id(claim_id)
    assert retrieved_claim is not None
    assert retrieved_claim['claim_match_score'] == eval_legit['total_score']
    assert retrieved_claim['item_secret_details'] == item['secret_details']
    print(f"[9] Claim retrieval verified with item_secret_details intact")

    # 8. Admin reviews and approves claim
    db.update_claim_status(claim_id, 'approved', 'Verified Student ID and secret pocket markings matched physically.', admin['id'])
    db.add_audit_log(
        user_id=admin['id'],
        action='Claim Approved',
        item_id=item['id'],
        claim_id=claim_id,
        details="Admin approved claim after physical check"
    )
    print(f"[10] Admin approved claim #{claim_id}")

    # 9. Admin completes handover
    receipt_token = f"REC-{datetime.now().strftime('%Y%m%d')}-TEST99"
    ret_id = db.create_item_return(
        item_id=item['id'],
        claim_id=claim_id,
        owner_id=alice['id'],
        handed_over_by=admin['id'],
        receipt_token=receipt_token,
        verification_method='Student ID & Physical Verification',
        remarks='Item handed over in person at Central Security Gate 1'
    )
    db.add_audit_log(
        user_id=admin['id'],
        action='Handover Return Completed',
        item_id=item['id'],
        claim_id=claim_id,
        details=f"Receipt token {receipt_token} generated"
    )
    print(f"[11] Return #{ret_id} created with receipt: {receipt_token}")

    # 10. Audit logs validation
    audit_logs = db.get_audit_logs(limit=10)
    print(f"[12] Total audit logs captured: {len(audit_logs)}")
    assert len(audit_logs) >= 4, "Must have recorded multiple audit log entries"
    actions = [a['action'] for a in audit_logs]
    print(f"    Logged Actions: {actions[:4]}")

    print("\n=================================================================")
    print(" ALL 12 VERIFICATION & ANTI-FRAUD TESTS PASSED SUCCESSFULLY! ")
    print("=================================================================\n")

if __name__ == '__main__':
    run_tests()
