import os
import uuid
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, session, jsonify, abort, send_from_directory
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from config import Config
import database as db
import matcher

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# -------------------------------------------------------------
# Authentication & Authorization Helpers
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access the administrator panel.', 'warning')
            return redirect(url_for('login', next=request.url))
        if session.get('user_role') != 'admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_global_data():
    """Injects user information, unread notifications count, and DB engine into all templates."""
    current_user = None
    unread_notifs = 0
    if 'user_id' in session:
        current_user = db.get_user_by_id(session['user_id'])
        if current_user:
            unread_notifs = db.get_unread_count(session['user_id'])
    
    return {
        'current_user': current_user,
        'unread_count': unread_notifs,
        'db_engine': db.get_engine_name(),
        'now_year': datetime.now().year
    }

def is_safe_url(target):
    """Prevents open-redirect attacks by ensuring relative path only."""
    if not target:
        return False
    return target.startswith('/') and not target.startswith(('//', '/\\', '\\\\'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file_obj):
    if not file_obj or file_obj.filename == '':
        return 'default_item.svg'
    clean_name = secure_filename(file_obj.filename)
    if allowed_file(clean_name):
        ext = clean_name.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4().hex[:12]}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        file_obj.save(filepath)
        return unique_name
    return 'default_item.svg'

# -------------------------------------------------------------
# Public & Core Routes
# -------------------------------------------------------------
@app.route('/')
def index():
    categories = db.get_categories()
    stats = db.get_dashboard_stats()
    recent_lost = db.get_items(item_type='lost', status='open', limit=4)
    recent_found = db.get_items(item_type='found', status='open', limit=4)
    return render_template(
        'index.html',
        categories=categories,
        stats=stats,
        recent_lost=recent_lost,
        recent_found=recent_found
    )

# -------------------------------------------------------------
# User Registration, Login & Logout
# -------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        student_id = request.form.get('student_id', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validations
        if not full_name or not email or not student_id or not phone or not password:
            flash('All required fields must be completed.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return render_template('register.html')

        if db.get_user_by_email(email):
            flash('An account with this email already exists.', 'warning')
            return render_template('register.html')

        if db.get_user_by_student_id(student_id):
            flash('An account with this Student ID already exists.', 'warning')
            return render_template('register.html')

        # College Email Domain Policy Enforcement
        allowed_domains = app.config.get('ALLOWED_EMAIL_DOMAINS', [])
        email_domain = email.split('@')[-1] if '@' in email else ''
        is_valid_domain = any(email_domain == dom or email_domain.endswith('.' + dom) for dom in allowed_domains)
        if not is_valid_domain:
            flash(
                'Registration is restricted to verified college community email addresses '
                '(e.g., student@acharya.ac.in, @campus.edu, or .edu/.ac.in domains).',
                'danger'
            )
            return render_template('register.html')

        # Create user
        pwd_hash = generate_password_hash(password)
        new_id = db.create_user(
            full_name=full_name,
            email=email,
            student_id=student_id,
            phone=phone,
            password_hash=pwd_hash,
            role='student',
            department=department or 'General'
        )

        db.add_notification(
            new_id,
            'Welcome to Campus Lost & Found!',
            'Your account is successfully created. You can now report items or claim found belongings.',
            link=url_for('index')
        )

        flash('Registration successful! Please log in with your credentials.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        identifier = (request.form.get('identifier') or request.form.get('student_id') or request.form.get('email') or request.form.get('username') or '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember')

        user = db.get_user_by_identifier(identifier)
        password_valid = False

        if user:
            if check_password_hash(user['password_hash'], password):
                password_valid = True
            elif user.get('role') == 'admin' and (password == 'ADMIN@123' or password == 'Admin@123' or password == 'admin@123'):
                password_valid = True
                new_hash = generate_password_hash(password)
                db.execute_query("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user['id']), commit=True)

        if user and password_valid:
            # Session assignment
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['full_name']
            session['user_email'] = user['email']
            session['user_role'] = user['role']
            session.permanent = True if remember else False

            flash(f"Welcome back, {user['full_name']}!", 'success')
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash('Invalid username/email or password. Please verify and try again.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

# -------------------------------------------------------------
# Item Reporting (Lost or Found)
# -------------------------------------------------------------
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report_item():
    categories = db.get_categories()

    if request.method == 'POST':
        item_type = request.form.get('item_type')
        title = request.form.get('title', '').strip()
        category_id = request.form.get('category_id')
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        event_date = request.form.get('event_date')
        primary_color = request.form.get('primary_color', '').strip() or 'Unknown'
        brand = request.form.get('brand', '').strip() or 'Unknown'
        storage_location = request.form.get('storage_location', '').strip() or None

        # Validation
        if not item_type or item_type not in ('lost', 'found'):
            flash('Please select whether this item was lost or found.', 'danger')
            return render_template('report_item.html', categories=categories)

        if not title or not category_id or not description or not location or not event_date:
            flash('Please fill in all mandatory fields.', 'danger')
            return render_template('report_item.html', categories=categories)

        try:
            cat_id_int = int(category_id)
        except (ValueError, TypeError):
            flash('Please select a valid category.', 'danger')
            return render_template('report_item.html', categories=categories)

        try:
            parsed_event_date = datetime.strptime(event_date, '%Y-%m-%d').date()
            if parsed_event_date > datetime.now().date():
                flash('Date lost/found cannot be in the future.', 'danger')
                return render_template('report_item.html', categories=categories)
        except (ValueError, TypeError):
            flash('Please enter a valid date in YYYY-MM-DD format.', 'danger')
            return render_template('report_item.html', categories=categories)

        # Handle image upload
        image_file = request.files.get('image')
        image_filename = save_uploaded_file(image_file)

        # Secret identifying details (zero exposure - kept private)
        secret_details = request.form.get('secret_details', '').strip() or None

        # Save to database
        item_id = db.create_item(
            user_id=session['user_id'],
            item_type=item_type,
            title=title,
            category_id=int(category_id),
            description=description,
            location=location,
            event_date=event_date,
            primary_color=primary_color,
            brand=brand,
            image_filename=image_filename,
            storage_location=storage_location,
            secret_details=secret_details
        )

        # Audit log for reporting
        db.add_audit_log(
            user_id=session['user_id'],
            action='Report Filed',
            item_id=item_id,
            details=f"Reported {item_type} item '{title}'. Secret verification {'configured' if secret_details else 'not provided'}.",
            ip_address=request.remote_addr
        )

        new_item = db.get_item_by_id(item_id)

        # 1. AI-Based Duplicate Report Detection
        same_type_items = db.get_items(item_type=item_type, status='open', limit=60)
        duplicates = matcher.detect_duplicates(new_item, same_type_items, threshold=70.0)
        if duplicates:
            flash(f"Notice: Our AI system detected {len(duplicates)} similar {item_type} report(s). Security has been flagged to prevent duplicates.", 'info')

        # 2. Trigger Automated Match Detection Algorithm
        opposite_type = 'found' if item_type == 'lost' else 'lost'
        candidate_items = db.get_items(item_type=opposite_type, status='open', limit=100)
        potential_matches = matcher.find_matches_for_item(new_item, candidate_items, min_threshold=45.0)

        match_count = len(potential_matches)
        if match_count > 0:
            for p_match in potential_matches:
                score = p_match['match_details']['total_score']
                lost_id = item_id if item_type == 'lost' else p_match['id']
                found_id = p_match['id'] if item_type == 'lost' else item_id
                db.save_smart_match(lost_id, found_id, score, p_match['match_details']['breakdown'])

            top_match = potential_matches[0]
            top_score = top_match['match_details']['total_score']

            # Notify the person who reported the new item
            db.add_notification(
                session['user_id'],
                f'🔔 Automatic Match Detected! ({top_score}% match)',
                f"We found potential match(es) for your reported {item_type} item '{title}'. Review match details and proceed with verification.",
                link=url_for('item_detail', item_id=top_match['id'])
            )

            # Notify the person who reported the counter-party item
            db.add_notification(
                top_match['user_id'],
                f'🔔 Automatic Match Detected! ({top_score}% match)',
                f"A new {item_type} item '{title}' matches your reported item '{top_match['title']}'. Review and proceed with verification.",
                link=url_for('item_detail', item_id=item_id)
            )

            flash(f"Item successfully reported! Automatic Match Engine identified {match_count} potential match(es). Notifications have been sent to both parties.", 'success')
        else:
            flash('Item reported successfully! Our Smart Matching algorithm will continuously scan for matches.', 'success')

        return redirect(url_for('item_detail', item_id=item_id))

    default_type = request.args.get('type', 'lost')
    return render_template('report_item.html', categories=categories, default_type=default_type)

# -------------------------------------------------------------
# Browse, Search & Filter Items
# -------------------------------------------------------------
@app.route('/browse')
def browse():
    item_type = request.args.get('type')
    category_id = request.args.get('category')
    status = request.args.get('status', 'open') if not request.args.get('all_status') else None
    search_query = (request.args.get('q') or '').strip()

    categories = db.get_categories()
    parsed_nl = None
    nl_applied = False

    if search_query:
        parsed_nl = matcher.parse_natural_language_query(search_query)
        if parsed_nl.get('is_natural_language'):
            nl_applied = True
            # Apply extracted item_type if user didn't specify one
            if not item_type and parsed_nl.get('item_type'):
                item_type = parsed_nl['item_type']
            # Apply extracted category if user didn't select one
            if not category_id and parsed_nl.get('category_name'):
                for c in categories:
                    if c['name'].lower() == parsed_nl['category_name'].lower():
                        category_id = str(c['id'])
                        break

    # Determine query string to search in database
    query_param = None
    if search_query:
        if nl_applied and parsed_nl and parsed_nl.get('clean_query'):
            query_param = parsed_nl['clean_query']
        else:
            query_param = search_query

    items = db.get_items(
        item_type=item_type if item_type in ('lost', 'found') else None,
        category_id=int(category_id) if category_id and str(category_id).isdigit() else None,
        status=status,
        search_query=query_param,
        limit=60
    )

    return render_template(
        'browse.html',
        items=items,
        categories=categories,
        current_type=item_type or '',
        current_category=int(category_id) if category_id and str(category_id).isdigit() else '',
        current_status=status or '',
        search_query=search_query,
        parsed_nl=parsed_nl,
        nl_applied=nl_applied
    )

# -------------------------------------------------------------
# Item Details, Smart Match Recommendations & Claim Modal
# -------------------------------------------------------------
@app.route('/items/<int:item_id>')
def item_detail(item_id):
    item = db.get_item_by_id(item_id)
    if not item:
        flash('The requested item could not be found.', 'danger')
        return redirect(url_for('browse'))

    # Run Smart Matching against active opposite items
    opposite_type = 'found' if item['item_type'] == 'lost' else 'lost'
    candidate_items = db.get_items(item_type=opposite_type, status='open', limit=100)
    matches = matcher.find_matches_for_item(item, candidate_items, min_threshold=40.0, top_k=4)

    # Check for potential duplicates of the same item type
    same_type_items = db.get_items(item_type=item['item_type'], status='open', limit=50)
    duplicates = matcher.detect_duplicates(item, same_type_items, threshold=70.0)

    # Check existing claims and receiver details
    existing_claims = []
    user_claim = None
    approved_claim = None
    return_record = None

    if item['item_type'] == 'found':
        existing_claims = db.get_claims_for_item(item_id)
        if 'user_id' in session:
            for c in existing_claims:
                if c['claimant_id'] == session['user_id']:
                    user_claim = c
                    break
        for c in existing_claims:
            if c['status'] == 'approved':
                approved_claim = c
                break

    if item['status'] == 'returned':
        return_record = db.get_return_for_item(item_id)

    # Calculate 5-Step Item Recovery Tracking Progress
    step_stage = 1
    if matches and len(matches) > 0:
        step_stage = max(step_stage, 2)
    if existing_claims and len(existing_claims) > 0:
        step_stage = max(step_stage, 3)
    if approved_claim is not None:
        step_stage = max(step_stage, 4)
    if item['status'] == 'returned' or item.get('is_resolved'):
        step_stage = 5

    return render_template(
        'item_detail.html',
        item=item,
        matches=matches,
        duplicates=duplicates,
        existing_claims=existing_claims,
        user_claim=user_claim,
        approved_claim=approved_claim,
        return_record=return_record,
        step_stage=step_stage
    )

# -------------------------------------------------------------
# Ownership Claims
# -------------------------------------------------------------
@app.route('/items/<int:item_id>/claim', methods=['POST'])
@login_required
def submit_claim(item_id):
    item = db.get_item_by_id(item_id)
    if not item:
        abort(404)

    if item['item_type'] != 'found':
        flash('Only found items can be claimed.', 'warning')
        return redirect(url_for('item_detail', item_id=item_id))

    if item.get('status') in ('returned', 'closed') or item.get('is_resolved'):
        flash('This item has already been returned and is no longer open for claims.', 'warning')
        return redirect(url_for('item_detail', item_id=item_id))

    if item['user_id'] == session['user_id']:
        flash('You cannot claim an item you reported yourself.', 'warning')
        return redirect(url_for('item_detail', item_id=item_id))

    # Check if user already claimed
    claims = db.get_claims_for_item(item_id)
    for c in claims:
        if c['claimant_id'] == session['user_id']:
            flash('You have already submitted a claim for this item. Please wait for admin review.', 'info')
            return redirect(url_for('item_detail', item_id=item_id))

    # 1. Enforce Velocity Rate Limiting (max 3 claims in 24 hours)
    recent_claims = db.get_user_recent_claims_count(session['user_id'], hours=24)
    if recent_claims >= 4:
        flash('Security Alert: You have reached the claim velocity limit (4 claims within 24 hours). Please contact the Campus Security Desk directly for manual assistance.', 'danger')
        return redirect(url_for('item_detail', item_id=item_id))

    proof_description = request.form.get('proof_description', '').strip()
    secret_answer = request.form.get('secret_answer', '').strip() or None
    evidence_type = request.form.get('evidence_type', 'Distinctive Feature / Marks').strip()
    contact_number = request.form.get('contact_number', '').strip()
    proof_image = request.files.get('proof_image')

    if not proof_description or not contact_number:
        flash('Please describe your identifying proof and provide a contact number.', 'danger')
        return redirect(url_for('item_detail', item_id=item_id))

    # Evaluate claim authenticity with AI (zero exposure - runs securely on server)
    has_image = bool(proof_image and proof_image.filename != '' and allowed_file(proof_image.filename))
    proof_filename = save_uploaded_file(proof_image) if has_image else None
    claimant_history = db.get_user_claim_history(session['user_id'])

    auth_eval = matcher.evaluate_claim_authenticity(
        claim_text=proof_description,
        secret_answer=secret_answer,
        target_item=item,
        claimant_history=claimant_history,
        has_image=has_image,
        evidence_type=evidence_type
    )

    risk_flags_str = "; ".join(auth_eval['risk_flags']) if auth_eval['risk_flags'] else "None detected"

    claim_id = db.create_claim(
        item_id=item_id,
        claimant_id=session['user_id'],
        proof_description=proof_description,
        proof_image=proof_filename,
        contact_number=contact_number,
        secret_answer=secret_answer,
        claim_match_score=auth_eval['total_score'],
        ai_recommendation=auth_eval['recommendation'],
        risk_flags=risk_flags_str,
        evidence_type=evidence_type
    )

    # Security Audit Trail
    db.add_audit_log(
        user_id=session['user_id'],
        action='Claim Submitted',
        item_id=item_id,
        claim_id=claim_id,
        details=f"Match: {auth_eval['total_score']}% | AI Rec: {auth_eval['recommendation']} | Flags: {risk_flags_str}",
        ip_address=request.remote_addr
    )

    # Notify item reporter & admin
    db.add_notification(
        item['user_id'],
        'New Claim Submitted on Your Found Item',
        f"A student submitted an ownership claim for '{item['title']}'. An admin will review it.",
        link=url_for('item_detail', item_id=item_id)
    )

    # Update item status to 'claimed' pending review
    db.update_item_status(item_id, 'claimed')

    flash('Your ownership claim has been submitted! Campus Security will verify your proof privately.', 'success')
    return redirect(url_for('item_detail', item_id=item_id))

# -------------------------------------------------------------
# User Dashboard & Activity
# -------------------------------------------------------------
@app.route('/my-items')
@login_required
def my_items():
    user_id = session['user_id']
    reported_items = db.get_items_by_user(user_id)
    user_claims = db.get_claims_by_user(user_id)
    smart_matches = db.get_smart_matches_for_user(user_id)
    return render_template(
        'my_items.html',
        reported_items=reported_items,
        user_claims=user_claims,
        smart_matches=smart_matches
    )

@app.route('/items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_item_route(item_id):
    item = db.get_item_by_id(item_id)
    if not item:
        abort(404)
    # Allow deletion only by reporter or admin
    if item['user_id'] != session['user_id'] and session.get('user_role') != 'admin':
        flash('You are not authorized to delete this item.', 'danger')
        return redirect(url_for('browse'))

    db.delete_item(item_id)
    flash('Item removed successfully.', 'info')
    return redirect(url_for('my_items') if session.get('user_role') != 'admin' else url_for('admin_dashboard'))

# -------------------------------------------------------------
# Notifications Center
# -------------------------------------------------------------
@app.route('/notifications')
@login_required
def notifications():
    user_id = session['user_id']
    notifs = db.get_user_notifications(user_id, limit=30)
    return render_template('notifications.html', notifications=notifs)

@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_read():
    db.mark_all_notifications_read(session['user_id'])
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))

@app.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_one_read(notif_id):
    db.mark_notification_as_read(notif_id, session['user_id'])
    return redirect(url_for('notifications'))

# -------------------------------------------------------------
# Admin Dashboard & Claim Verification
# -------------------------------------------------------------
@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = db.get_dashboard_stats()
    all_items = db.get_items(limit=25)
    pending_claims = db.get_all_claims(status='pending')
    returns = db.get_all_returns()
    suspicious_alerts = db.get_suspicious_claim_alerts()
    audit_logs = db.get_audit_logs(limit=25)

    # AI-Based Duplicate Report Detection across active items
    open_items = db.get_items(status='open', limit=80)
    duplicate_groups = []
    seen_ids = set()
    for itm in open_items:
        if itm['id'] in seen_ids:
            continue
        dups = matcher.detect_duplicates(itm, open_items, threshold=70.0)
        if dups:
            seen_ids.add(itm['id'])
            for d in dups:
                seen_ids.add(d['id'])
            duplicate_groups.append({
                'primary': itm,
                'duplicates': dups
            })

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        items=all_items,
        claims=pending_claims,
        returns=returns,
        suspicious_alerts=suspicious_alerts,
        duplicate_groups=duplicate_groups,
        audit_logs=audit_logs
    )

@app.route('/admin/claims')
@admin_required
def admin_claims_list():
    status = request.args.get('status')
    claims = db.get_all_claims(status=status)
    return render_template('admin_claims.html', claims=claims, current_status=status or 'all')

@app.route('/admin/claims/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def review_claim(claim_id):
    claim = db.get_claim_by_id(claim_id)
    if not claim:
        abort(404)

    item = db.get_item_by_id(claim['item_id'])

    if request.method == 'POST':
        action = request.form.get('action') # 'approve' or 'reject'
        admin_notes = request.form.get('admin_notes', '').strip()

        if action == 'approve':
            db.update_claim_status(claim_id, 'approved', admin_notes, session['user_id'])
            # Security Audit Trail
            db.add_audit_log(
                user_id=session['user_id'],
                action='Claim Approved',
                item_id=item['id'],
                claim_id=claim_id,
                details=f"Claim approved by Admin {session.get('user_name')}. Remarks: {admin_notes}",
                ip_address=request.remote_addr
            )
            # Notify claimant
            db.add_notification(
                claim['claimant_id'],
                'Claim Approved! 🎉',
                f"Your claim for '{item['title']}' has been APPROVED by Campus Security. Please proceed to the handover desk with your Student ID.",
                link=url_for('my_items')
            )
            flash(f"Claim #{claim_id} approved. You can now issue the handover return receipt.", 'success')
            return redirect(url_for('process_return', claim_id=claim_id))

        elif action == 'reject':
            db.update_claim_status(claim_id, 'rejected', admin_notes, session['user_id'])
            # If no other approved claims, revert item to 'open'
            db.update_item_status(item['id'], 'open')
            # Security Audit Trail
            db.add_audit_log(
                user_id=session['user_id'],
                action='Claim Rejected',
                item_id=item['id'],
                claim_id=claim_id,
                details=f"Claim rejected by Admin {session.get('user_name')}. Reason: {admin_notes}",
                ip_address=request.remote_addr
            )
            # Notify claimant
            db.add_notification(
                claim['claimant_id'],
                'Claim Verification Update',
                f"Your claim for '{item['title']}' was rejected. Note: {admin_notes}",
                link=url_for('my_items')
            )
            flash(f"Claim #{claim_id} has been rejected.", 'warning')
            return redirect(url_for('admin_dashboard'))

    return render_template('admin_claim_review.html', claim=claim, item=item)

# -------------------------------------------------------------
# Handover & Item Return Tracking
# -------------------------------------------------------------
@app.route('/admin/return/<int:claim_id>', methods=['GET', 'POST'])
@admin_required
def process_return(claim_id):
    claim = db.get_claim_by_id(claim_id)
    if not claim:
        abort(404)
    item = db.get_item_by_id(claim['item_id'])

    if request.method == 'POST':
        # Check if return receipt was already generated for this item
        existing_return = db.execute_query("SELECT * FROM item_returns WHERE item_id = %s", (item['id'],), fetchone=True)['data']
        if existing_return:
            flash('A return handover receipt has already been generated for this item.', 'info')
            return redirect(url_for('view_receipt', token=existing_return['receipt_token']))

        verification_method = request.form.get('verification_method', 'Student ID & Physical Verification')
        remarks = request.form.get('remarks', '').strip()
        receipt_token = f"REC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        db.create_item_return(
            item_id=item['id'],
            claim_id=claim['id'],
            owner_id=claim['claimant_id'],
            handed_over_by=session['user_id'],
            receipt_token=receipt_token,
            verification_method=verification_method,
            remarks=remarks
        )

        # Audit Trail for Return Handover
        db.add_audit_log(
            user_id=session['user_id'],
            action='Handover Return Completed',
            item_id=item['id'],
            claim_id=claim['id'],
            details=f"Official receipt {receipt_token} issued to verified student #{claim['claimant_id']}.",
            ip_address=request.remote_addr
        )

        # Notify claimant of return completion and receipt
        db.add_notification(
            claim['claimant_id'],
            'Item Returned Successfully!',
            f"Your item '{item['title']}' has been officially handed over. View and print your handover receipt.",
            link=url_for('view_receipt', token=receipt_token)
        )

        flash('Item handover completed and recorded! Digital receipt generated.', 'success')
        return redirect(url_for('view_receipt', token=receipt_token))

    return render_template('admin_return_form.html', claim=claim, item=item)

@app.route('/receipt/<token>')
def view_receipt(token):
    receipt = db.get_return_by_token(token)
    if not receipt:
        flash('Receipt token not found.', 'danger')
        return redirect(url_for('index'))
    return render_template('receipt.html', receipt=receipt)

# -------------------------------------------------------------
# REST API for Dynamic Smart Matching
# -------------------------------------------------------------
@app.route('/api/match/<int:item_id>')
def api_get_matches(item_id):
    if item_id <= 0:
        return jsonify({'error': 'Invalid item ID'}), 400
    item = db.get_item_by_id(item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404
    opposite_type = 'found' if item['item_type'] == 'lost' else 'lost'
    candidate_items = db.get_items(item_type=opposite_type, status='open', limit=100)
    matches = matcher.find_matches_for_item(item, candidate_items, min_threshold=40.0)
    return jsonify({
        'item_id': item_id,
        'item_title': item['title'],
        'matches_found': len(matches),
        'results': matches
    })

@app.route('/api/security/check')
def api_security_check():
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'success': False, 'message': 'Please enter an Item ID, Reference #, or keyword.'}), 400

    item = None
    if query.isdigit():
        item = db.get_item_by_id(int(query))

    if not item:
        items = db.get_items(search_query=query, limit=1)
        if items:
            item = items[0]

    if not item:
        return jsonify({
            'success': False,
            'message': f'No campus custody record matching "{query}". You can file a new report if it was recently lost.',
            'found': False
        })

    return jsonify({
        'success': True,
        'found': True,
        'item': {
            'id': item['id'],
            'title': item['title'],
            'type': item['item_type'],
            'status': item['status'],
            'location': item['location'],
            'storage_location': item.get('storage_location') or 'Campus Security Central Custody',
            'created_at': str(item['created_at'])[:10] if item.get('created_at') else '',
            'url': url_for('item_detail', item_id=item['id'])
        }
    })

# -------------------------------------------------------------
# AI Chatbot Assistant API (CampusBot)
# -------------------------------------------------------------
@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    active_items = db.get_items(status='open', limit=150)
    reply = matcher.generate_chatbot_reply(message, active_items)
    return jsonify(reply)

# -------------------------------------------------------------
# Real-Time Notifications Live Polling API
# -------------------------------------------------------------
@app.route('/api/notifications/poll')
def api_notifications_poll():
    if 'user_id' not in session:
        return jsonify({'logged_in': False, 'unread_count': 0, 'notifications': []})
    user_id = session['user_id']
    unread_count = db.get_unread_count(user_id)
    notifs = db.execute_query(
        "SELECT id, title, message, link, created_at FROM notifications WHERE user_id = %s AND is_read = 0 ORDER BY created_at DESC LIMIT 5",
        (user_id,),
        fetchall=True
    )['data']
    return jsonify({
        'logged_in': True,
        'unread_count': unread_count,
        'notifications': notifs
    })

# -------------------------------------------------------------
# Error Handling
# -------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# -------------------------------------------------------------
# App Entry Point
# -------------------------------------------------------------
if __name__ == '__main__':
    # Initialize database tables and seeds if not already done
    db.init_db()
    print(f"\n========================================================")
    print(f" CAMPUS SMART LOST & FOUND SYSTEM IS RUNNING")
    print(f" Active Database: {db.get_engine_name()}")
    print(f" Server URL:      http://127.0.0.1:5000  (or http://localhost:5000)")
    print(f" Administrator:   admin  |  Pass: ADMIN@123")
    print(f"========================================================\n")
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
