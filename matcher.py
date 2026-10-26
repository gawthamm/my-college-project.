import re
from difflib import SequenceMatcher
from datetime import datetime

# Common campus stop words to ignore during similarity calculations
STOP_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 
    'my', 'i', 'was', 'is', 'it', 'item', 'lost', 'found', 'please', 'help', 
    'near', 'by', 'around', 'color', 'colour', 'brand', 'name', 'has', 'have'
}

def clean_tokens(text):
    """Normalize text into lowercase alphanumeric keywords without stopwords."""
    if not text:
        return set()
    words = re.findall(r'\b[a-z0-9]+\b', text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}

def calculate_token_similarity(set1, set2):
    """Calculate Jaccard similarity between two token sets."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union > 0 else 0.0

def calculate_sequence_similarity(str1, str2):
    """Calculate Levenshtein-like character sequence similarity."""
    if not str1 or not str2:
        return 0.0
    return SequenceMatcher(None, str1.lower().strip(), str2.lower().strip()).ratio()

def calculate_date_proximity(date1_str, date2_str):
    """
    Calculate similarity based on event dates.
    Returns score between 0.0 and 1.0.
    Lost items usually happen just before or on the day the item is found.
    """
    try:
        if isinstance(date1_str, str):
            d1 = datetime.strptime(date1_str, '%Y-%m-%d').date()
        else:
            d1 = date1_str
            
        if isinstance(date2_str, str):
            d2 = datetime.strptime(date2_str, '%Y-%m-%d').date()
        else:
            d2 = date2_str

        # Difference in days
        diff_days = abs((d1 - d2).days)
        if diff_days == 0:
            return 1.0
        elif diff_days <= 3:
            return 0.85
        elif diff_days <= 7:
            return 0.70
        elif diff_days <= 14:
            return 0.50
        elif diff_days <= 30:
            return 0.25
        else:
            return 0.05
    except Exception:
        return 0.3

def match_score(item_a, item_b):
    """
    Computes a weighted similarity score between two items.
    item_a and item_b should be dictionary records of items.
    
    Weights Breakdown (Total 100%):
    - Category Match: 30%
    - Title Similarity: 30% (Token overlap + Sequence similarity)
    - Description Similarity: 20%
    - Location Proximity: 10%
    - Date Proximity: 10%
    """
    breakdown = {}

    # 1. Category Match (30 pts)
    cat_a = item_a.get('category_id')
    cat_b = item_b.get('category_id')
    cat_score = 30.0 if (cat_a and cat_b and cat_a == cat_b) else 0.0
    breakdown['category'] = round(cat_score, 1)

    # 2. Title Similarity (30 pts)
    title_a = item_a.get('title', '')
    title_b = item_b.get('title', '')
    t_seq = calculate_sequence_similarity(title_a, title_b)
    t_tokens = calculate_token_similarity(clean_tokens(title_a), clean_tokens(title_b))
    title_combined = (t_seq * 0.4) + (t_tokens * 0.6)
    title_score = title_combined * 30.0
    breakdown['title'] = round(title_score, 1)

    # 3. Description Similarity (20 pts)
    desc_a = item_a.get('description', '')
    desc_b = item_b.get('description', '')
    d_tokens = calculate_token_similarity(clean_tokens(desc_a), clean_tokens(desc_b))
    desc_score = d_tokens * 20.0
    
    # Check bonus for brand / color matches
    color_a = (item_a.get('primary_color') or '').strip().lower()
    color_b = (item_b.get('primary_color') or '').strip().lower()
    if color_a and color_b and color_a != 'unknown' and color_a == color_b:
        desc_score = min(20.0, desc_score + 5.0)

    brand_a = (item_a.get('brand') or '').strip().lower()
    brand_b = (item_b.get('brand') or '').strip().lower()
    if brand_a and brand_b and brand_a != 'unknown' and brand_a == brand_b:
        desc_score = min(20.0, desc_score + 5.0)

    breakdown['description'] = round(desc_score, 1)

    # 4. Location Match (10 pts)
    loc_a = clean_tokens(item_a.get('location', ''))
    loc_b = clean_tokens(item_b.get('location', ''))
    loc_overlap = calculate_token_similarity(loc_a, loc_b)
    loc_score = loc_overlap * 10.0
    breakdown['location'] = round(loc_score, 1)

    # 5. Date Proximity (10 pts)
    date_prox = calculate_date_proximity(item_a.get('event_date'), item_b.get('event_date'))
    date_score = date_prox * 10.0
    breakdown['date'] = round(date_score, 1)

    # Total Score Calculation
    total = cat_score + title_score + desc_score + loc_score + date_score
    total = max(0.0, min(100.0, round(total, 1)))

    # Classification
    if total >= 75.0:
        confidence = "High"
        badge_class = "success"
    elif total >= 50.0:
        confidence = "Moderate"
        badge_class = "warning"
    else:
        confidence = "Low"
        badge_class = "secondary"

    return {
        'total_score': total,
        'confidence': confidence,
        'badge_class': badge_class,
        'breakdown': breakdown
    }

def find_matches_for_item(target_item, candidate_items, min_threshold=35.0, top_k=5):
    """
    Scans a list of candidate items (usually opposite item_type)
    and returns items with a similarity score >= min_threshold, sorted descending.
    """
    results = []
    for candidate in candidate_items:
        # Ignore same item or same user's item or resolved items
        if candidate.get('id') == target_item.get('id'):
            continue
        
        result = match_score(target_item, candidate)
        if result['total_score'] >= min_threshold:
            candidate_copy = dict(candidate)
            candidate_copy['match_details'] = result
            results.append(candidate_copy)

    # Sort descending by match score
    results.sort(key=lambda x: x['match_details']['total_score'], reverse=True)
    return results[:top_k]

# =============================================================
# Natural Language Search & Entity Extraction
# =============================================================

COLOR_KEYWORDS = [
    'dark blue', 'navy blue', 'sky blue', 'light blue', 'red', 'black', 'blue', 
    'green', 'yellow', 'brown', 'white', 'grey', 'gray', 'silver', 'gold', 
    'golden', 'pink', 'purple', 'orange', 'maroon', 'beige'
]

CATEGORY_KEYWORDS = {
    'Electronics & Gadgets': [
        'laptop', 'macbook', 'phone', 'mobile', 'iphone', 'android', 'samsung', 
        'charger', 'headphones', 'earphones', 'airpods', 'calculator', 'usb', 
        'pendrive', 'watch', 'smartwatch', 'tablet', 'ipad', 'powerbank'
    ],
    'ID Cards & Documents': [
        'id card', 'id', 'badge', 'license', 'driving license', 'atm card', 
        'debit card', 'credit card', 'certificate', 'passport', 'hall ticket'
    ],
    'Bags & Wallets': [
        'bag', 'backpack', 'wallet', 'purse', 'pouch', 'handbag', 'tote', 
        'duffle', 'sack', 'kit'
    ],
    'Keys & Access Cards': [
        'key', 'keys', 'keychain', 'car key', 'bike key', 'room key', 'rfid', 
        'access card', 'smart card'
    ],
    'Books & Study Material': [
        'book', 'textbook', 'notebook', 'binder', 'notes', 'journal', 'manual', 
        'diary', 'file'
    ],
    'Clothing & Accessories': [
        'jacket', 'hoodie', 'cap', 'hat', 'glasses', 'spectacles', 'sunglasses', 
        'bottle', 'water bottle', 'umbrella', 'scarf', 'sweater', 'coat'
    ]
}

CAMPUS_LOCATIONS = [
    'computer lab', 'chemistry lab', 'physics lab', 'electronics lab', 'lab',
    'central library', 'library', 'cafeteria', 'canteen', 'food court',
    'auditorium', 'audi', 'seminar hall', 'sports complex', 'gym', 'badminton court',
    'hostel block', 'boys hostel', 'girls hostel', 'hostel',
    'block a', 'block b', 'block c', 'main block', 'admin block', 'reception',
    'parking area', 'parking', 'playground', 'ground', 'classroom', 'staircase', 'corridor',
    'security gate', 'main gate', 'gate 1', 'gate 2'
]

def parse_natural_language_query(query_text):
    """
    Parses natural conversational queries like:
    'Find a red bag I might have lost in the computer lab last Friday'
    Extracts item type, category, item keyword, color, location, and date hints.
    """
    if not query_text or not query_text.strip():
        return {
            'is_natural_language': False,
            'clean_query': '',
            'item_type': None,
            'color': None,
            'category_name': None,
            'item_keyword': None,
            'location': None,
            'date_hint': None,
            'extracted_entities': []
        }

    raw = query_text.strip()
    low = raw.lower()
    extracted = []

    # 1. Detect Intent / Item Type
    item_type = None
    if re.search(r'\b(lost|misplaced|dropped|left behind|forgot|missing)\b', low):
        item_type = 'lost'
        extracted.append(('Type', 'Lost'))
    elif re.search(r'\b(found|picked up|spotted|handed in|recovered)\b', low):
        item_type = 'found'
        extracted.append(('Type', 'Found'))

    # 2. Extract Color
    found_color = None
    for color in COLOR_KEYWORDS:
        if re.search(r'\b' + re.escape(color) + r'\b', low):
            found_color = color.title()
            extracted.append(('Color', found_color))
            break

    # 3. Extract Category & Item keyword
    found_category = None
    found_item_keyword = None
    for cat_name, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if re.search(r'\b' + re.escape(kw) + r'\b', low):
                found_category = cat_name
                found_item_keyword = kw.title()
                extracted.append(('Category', cat_name))
                extracted.append(('Item', found_item_keyword))
                break
        if found_category:
            break

    # 4. Extract Location
    found_location = None
    for loc in CAMPUS_LOCATIONS:
        if re.search(r'\b' + re.escape(loc) + r'\b', low):
            found_location = loc.title()
            extracted.append(('Location', found_location))
            break

    # 5. Extract Date/Time hint
    found_date_hint = None
    date_patterns = [
        (r'\b(today|this morning|this afternoon)\b', 'Today'),
        (r'\b(yesterday|last night)\b', 'Yesterday'),
        (r'\b(last friday|last monday|last tuesday|last wednesday|last thursday|last saturday|last sunday)\b', 'Past week'),
        (r'\b(last week|past week)\b', 'Last week'),
        (r'\b(\d+)\s+days?\s+ago\b', 'Recently')
    ]
    for pat, label in date_patterns:
        m = re.search(pat, low)
        if m:
            found_date_hint = m.group(0).title()
            extracted.append(('When', found_date_hint))
            break

    # Clean residual query keywords
    tokens = clean_tokens(raw)
    clean_kw = " ".join(tokens)

    is_nl = len(extracted) >= 2 or len(raw.split()) >= 4

    return {
        'is_natural_language': is_nl,
        'raw_query': raw,
        'clean_query': clean_kw,
        'item_type': item_type,
        'color': found_color,
        'category_name': found_category,
        'item_keyword': found_item_keyword,
        'location': found_location,
        'date_hint': found_date_hint,
        'extracted_entities': extracted
    }

# =============================================================
# Duplicate Report Detection
# =============================================================

def detect_duplicates(target_item, candidate_items, threshold=70.0):
    """
    Detects potential duplicate reports for the same physical item.
    Compares reports with the SAME item_type (e.g. multiple students reporting the same found backpack).
    """
    duplicates = []
    t_id = target_item.get('id')
    t_type = target_item.get('item_type')
    t_cat = target_item.get('category_id')
    t_title = target_item.get('title', '')
    t_desc = target_item.get('description', '')
    t_loc = target_item.get('location', '')
    t_date = target_item.get('event_date')

    for cand in candidate_items:
        # Ignore self, different item type, or already closed/returned items
        if cand.get('id') == t_id or cand.get('item_type') != t_type:
            continue
        
        # 1. Category similarity (25 pts)
        c_cat = cand.get('category_id')
        cat_pts = 25.0 if (t_cat and c_cat and t_cat == c_cat) else 0.0

        # 2. Title similarity (35 pts)
        t_seq = calculate_sequence_similarity(t_title, cand.get('title', ''))
        t_tokens = calculate_token_similarity(clean_tokens(t_title), clean_tokens(cand.get('title', '')))
        title_pts = ((t_seq * 0.4) + (t_tokens * 0.6)) * 35.0

        # 3. Location similarity (25 pts)
        loc_tokens = calculate_token_similarity(clean_tokens(t_loc), clean_tokens(cand.get('location', '')))
        loc_pts = loc_tokens * 25.0

        # 4. Date proximity (15 pts)
        date_pts = calculate_date_proximity(t_date, cand.get('event_date')) * 15.0

        dup_score = round(cat_pts + title_pts + loc_pts + date_pts, 1)

        if dup_score >= threshold:
            dup_info = dict(cand)
            dup_info['duplicate_score'] = dup_score
            dup_info['reasons'] = []
            if cat_pts > 0:
                dup_info['reasons'].append('Same category')
            if title_pts >= 20.0:
                dup_info['reasons'].append('Highly similar title')
            if loc_pts >= 12.0:
                dup_info['reasons'].append('Matching location')
            if date_pts >= 10.0:
                dup_info['reasons'].append('Same/adjacent date')
            duplicates.append(dup_info)

    duplicates.sort(key=lambda x: x['duplicate_score'], reverse=True)
    return duplicates

# =============================================================
# Conversational AI Assistant (CampusBot)
# =============================================================

def generate_chatbot_reply(user_message, active_items=None):
    """
    Intelligent campus chatbot assistant that assists students in finding belongings,
    answering procedural questions, and providing direct navigation links.
    """
    msg = (user_message or '').strip()
    if not msg:
        return {
            'text': "Hello! I am **CampusBot**, your AI campus lost & found assistant. How can I help you today? You can describe an item you lost, ask about found items, or check campus custody procedures.",
            'items': [],
            'quick_replies': ["I lost my wallet", "Did anyone find keys?", "How do I claim an item?", "Security Office location"]
        }

    low = msg.lower()

    # 1. Procedural FAQ responses
    if any(q in low for q in ['where is security', 'security office', 'room number', 'desk location', 'contact security']):
        return {
            'text': "🏢 **Campus Security Office & Central Custody Desk**\n\n"
                    "• **Location:** Ground Floor, Main Administrative Block, Room 102\n"
                    "• **Operating Hours:** Monday to Saturday: 8:30 AM – 6:30 PM\n"
                    "• **Emergency Phone:** (080) 2372-9999 / Ext. 102\n"
                    "• **Email:** security@campus.edu\n\n"
                    "You can visit in person with your Student ID card to claim approved items or hand over found articles.",
            'items': [],
            'quick_replies': ["How do I claim an item?", "Report a found item", "Search items"]
        }

    if any(q in low for q in ['how do i claim', 'how to claim', 'claim process', 'claim an item', 'verification process']):
        return {
            'text': "🔐 **How to Claim a Found Item:**\n\n"
                    "1. Search or browse our catalog for your item.\n"
                    "2. Open the item page and click **'Claim This Item'**.\n"
                    "3. Enter your private ownership details (unique markings, serial numbers, password lock description, etc.).\n"
                    "4. Campus Security reviews your claim privately.\n"
                    "5. Once approved, visit the Security Desk with your Student ID to receive your item and digital return receipt!",
            'items': [],
            'quick_replies': ["Browse Found Items", "Where is the security office?", "Report Lost Item"]
        }

    if any(q in low for q in ['privacy', 'sensitive', 'confidential', 'private details', 'is my data safe']):
        return {
            'text': "🛡️ **Ownership Privacy Shield Active**\n\n"
                    "Our platform strictly protects claimant privacy. Identifying proof details (such as partial serial numbers, lock wallpapers, or internal wallet contents) are **never shown publicly**.\n\n"
                    "Only designated Campus Security officers and the claimant have access during official verification.",
            'items': [],
            'quick_replies': ["How do I claim an item?", "Report a lost item"]
        }

    if any(q in low for q in ['hello', 'hi', 'hey', 'greetings', 'who are you', 'help']):
        return {
            'text': "👋 Hello! I am **CampusBot**, your dedicated Campus Lost & Found Assistant. You can describe an item you lost (for example: *'I lost my black wallet near the library yesterday'*), and I will scan all campus records to find matches for you!",
            'items': [],
            'quick_replies': ["I lost my black bag", "Lost my student ID card", "Found an item", "Security office hours"]
        }

    # 2. Search / Entity Extraction
    parsed = parse_natural_language_query(msg)
    
    # Query candidate items
    matched_items = []
    if active_items:
        target_mock = {
            'id': 0,
            'title': parsed['clean_query'] or msg,
            'description': msg,
            'category_id': None,
            'primary_color': parsed.get('color') or 'Unknown',
            'brand': 'Unknown',
            'location': parsed.get('location') or '',
            'event_date': str(datetime.now().date())
        }

        # Determine target pool based on intent
        filtered_candidates = []
        for itm in active_items:
            # If user said 'lost', they want to find 'found' items
            if parsed['item_type'] == 'lost' and itm.get('item_type') != 'found':
                continue
            elif parsed['item_type'] == 'found' and itm.get('item_type') != 'lost':
                continue
            filtered_candidates.append(itm)

        pool = filtered_candidates if filtered_candidates else active_items
        scored = []
        for itm in pool:
            sc = match_score(target_mock, itm)
            # Add bonus if parsed color matches
            if parsed['color'] and parsed['color'].lower() in (itm.get('primary_color') or '').lower():
                sc['total_score'] = min(100.0, sc['total_score'] + 15.0)
            # Add bonus if parsed location matches
            if parsed['location'] and parsed['location'].lower() in (itm.get('location') or '').lower():
                sc['total_score'] = min(100.0, sc['total_score'] + 15.0)
            
            if sc['total_score'] >= 35.0:
                itm_copy = dict(itm)
                itm_copy['match_score'] = sc['total_score']
                scored.append(itm_copy)

        scored.sort(key=lambda x: x['match_score'], reverse=True)
        matched_items = scored[:4]

    if matched_items:
        count = len(matched_items)
        reply_text = f"🎯 I found **{count} report{'s' if count > 1 else ''}** that might match your description! Would you like to view them below?"
        if parsed['extracted_entities']:
            tags_str = ", ".join([f"{k}: **{v}**" for k, v in parsed['extracted_entities']])
            reply_text += f"\n\n*(Detected {tags_str})*"

        cards = []
        for m in matched_items:
            cards.append({
                'id': m['id'],
                'title': m.get('title'),
                'type': m.get('item_type'),
                'location': m.get('location'),
                'event_date': str(m.get('event_date'))[:10] if m.get('event_date') else '',
                'image_filename': m.get('image_filename') or 'default_item.svg',
                'status': m.get('status'),
                'score': m.get('match_score')
            })

        return {
            'text': reply_text,
            'items': cards,
            'quick_replies': ["Browse All Items", "Report a lost item", "How to claim?"]
        }
    else:
        entities_note = ""
        if parsed['extracted_entities']:
            tags_str = ", ".join([f"{k}: **{v}**" for k, v in parsed['extracted_entities']])
            entities_note = f"\n\nI looked for: {tags_str}."

        return {
            'text': f"🔍 I searched our active campus custody reports for **'{msg}'**, but no exact match was found at this moment.{entities_note}\n\n"
                    "Would you like to report this as an official **Lost Item** so Campus Security and finders can match it automatically as soon as it is turned in?",
            'items': [],
            'quick_replies': ["Report Lost Item", "Browse All Items", "Contact Security"]
        }

# =============================================================
# AI-Assisted Secure Ownership Verification & Fake Claim Detection
# =============================================================

def evaluate_claim_authenticity(claim_text, secret_answer, target_item, claimant_history=None, has_image=False, evidence_type='Feature Description'):
    """
    Evaluates claimant authenticity to prevent fake ownership claims on campus items.
    
    Evaluates 4 Pillars:
    1. Description & Context Match (0-35 pts)
    2. Private Secret Ownership Details Verification (0-40 pts)
    3. Supporting Proof Evidence (0-25 pts)
    4. Suspicious Velocity & Risk Factor Flagging
    
    Returns structured scorecard with AI recommendation (never auto-approves).
    """
    breakdown = {}
    risk_flags = []
    
    claim_text = (claim_text or '').strip()
    secret_answer = (secret_answer or '').strip()
    
    # ---------------------------------------------------------
    # 1. Description & Context Match (35 pts max)
    # ---------------------------------------------------------
    target_desc = target_item.get('description', '') or ''
    target_title = target_item.get('title', '') or ''
    target_brand = (target_item.get('brand') or '').strip().lower()
    target_color = (target_item.get('primary_color') or '').strip().lower()
    
    c_tokens = clean_tokens(claim_text)
    t_tokens = clean_tokens(target_desc + ' ' + target_title)
    
    token_overlap = calculate_token_similarity(c_tokens, t_tokens)
    seq_sim = calculate_sequence_similarity(claim_text, target_desc)
    
    desc_score = (token_overlap * 0.5 + seq_sim * 0.5) * 25.0
    
    # Attribute bonuses if claimant independently mentions matching color or brand
    claim_low = claim_text.lower()
    if target_brand and target_brand != 'unknown' and target_brand in claim_low:
        desc_score += 5.0
    if target_color and target_color != 'unknown' and target_color in claim_low:
        desc_score += 5.0
        
    desc_score = min(35.0, round(desc_score, 1))
    breakdown['description_score'] = desc_score
    
    if desc_score >= 20.0:
        desc_match_level = "Strong Match"
    elif desc_score >= 10.0:
        desc_match_level = "Moderate Match"
    else:
        desc_match_level = "Weak / Generic"
        
    if len(claim_text) < 15:
        risk_flags.append("Sparse claim description (< 15 characters)")

    # ---------------------------------------------------------
    # 2. Secret Ownership Details Verification (40 pts max)
    # ---------------------------------------------------------
    ground_truth_secret = (target_item.get('secret_details') or '').strip()
    secret_score = 0.0
    
    if ground_truth_secret:
        # Ground truth secret exists - check claimant's secret answer
        if not secret_answer:
            secret_score = 0.0
            secret_verification_level = "Secret Details Missing (Reporter specified secret details)"
            risk_flags.append("Claimant provided no secret ownership answer")
        else:
            ans_tokens = clean_tokens(secret_answer)
            gt_tokens = clean_tokens(ground_truth_secret)
            ans_overlap = calculate_token_similarity(ans_tokens, gt_tokens)
            ans_seq = calculate_sequence_similarity(secret_answer, ground_truth_secret)
            
            # Check numbers / serial numbers overlap
            ans_nums = set(re.findall(r'\d+', secret_answer))
            gt_nums = set(re.findall(r'\d+', ground_truth_secret))
            num_match = bool(ans_nums and gt_nums and ans_nums.intersection(gt_nums))
            
            if ans_overlap >= 0.4 or ans_seq >= 0.55 or num_match:
                secret_score = 40.0
                secret_verification_level = "Strong Match (Consistent with Private Records)"
            elif ans_overlap >= 0.2 or ans_seq >= 0.35:
                secret_score = 25.0
                secret_verification_level = "Partial Match (Needs Physical Inspection)"
            else:
                secret_score = 0.0
                secret_verification_level = "Secret Mismatch / Inconclusive"
                risk_flags.append("Secret identifying details do not match reporter baseline")
    else:
        # Reporter did not enter a secret detail
        if secret_answer:
            secret_score = 25.0
            secret_verification_level = "Provided (Reporter did not record secret baseline)"
        else:
            secret_score = 20.0  # Neutral baseline
            secret_verification_level = "Not Applicable (No secret details recorded by reporter)"
            
    breakdown['secret_score'] = round(secret_score, 1)

    # ---------------------------------------------------------
    # 3. Supporting Proof Evidence (25 pts max)
    # ---------------------------------------------------------
    evidence_score = 0.0
    high_value_types = [
        'Purchase Invoice / Bill', 'Photo with Item', 
        'Device Serial / Warranty', 'Distinctive Feature / Marks'
    ]
    
    if has_image:
        if evidence_type in high_value_types:
            evidence_score = 25.0
            evidence_status = f"Verified ({evidence_type} Document Attached)"
        else:
            evidence_score = 18.0
            evidence_status = f"Attached ({evidence_type})"
    else:
        if evidence_type in high_value_types:
            evidence_score = 10.0
            evidence_status = f"Text Stated ({evidence_type}, No Photo)"
        else:
            evidence_score = 5.0
            evidence_status = "Text Description Only"
            
    breakdown['evidence_score'] = round(evidence_score, 1)

    # ---------------------------------------------------------
    # 4. Claimant History & Velocity Risk Checking
    # ---------------------------------------------------------
    if claimant_history:
        recent_24h = claimant_history.get('recent_24h', 0)
        rejected = claimant_history.get('rejected', 0)
        total_claims = claimant_history.get('total', 0)
        
        if recent_24h >= 3:
            risk_flags.append(f"High claim velocity ({recent_24h} claims in last 24 hours)")
        if rejected >= 2:
            risk_flags.append(f"Multiple previously rejected claims ({rejected} rejected)")
        if total_claims >= 5:
            risk_flags.append(f"High lifetime claiming activity ({total_claims} claims)")

    # ---------------------------------------------------------
    # 5. Total Score & AI Recommendation Synthesis
    # ---------------------------------------------------------
    total = desc_score + secret_score + evidence_score
    
    # Severe penalty if there is a direct secret mismatch
    if ground_truth_secret and secret_score == 0.0:
        total = min(total, 38.0)
        
    total = max(0.0, min(100.0, round(total, 1)))
    
    has_critical_flag = any(
        'mismatch' in f.lower() or 'rejected' in f.lower() or 'velocity' in f.lower()
        for f in risk_flags
    )
    
    if total >= 70.0 and not has_critical_flag:
        recommendation = "Recommend Approval"
        badge_class = "success"
        recommendation_notes = "Claimant provided consistent identifiers matching private records. Safe to proceed to handover upon Student ID check."
    elif total >= 40.0:
        recommendation = "Requires Admin Investigation"
        badge_class = "warning"
        recommendation_notes = "Evidence is moderate or partial. Campus Security should examine the physical item in person before approving."
    else:
        recommendation = "High Risk / Likely Fake Claim"
        badge_class = "danger"
        recommendation_notes = "High discrepancy or mismatched secret details detected. Heightened scrutiny required to prevent illegitimate claiming."

    return {
        'total_score': total,
        'recommendation': recommendation,
        'badge_class': badge_class,
        'recommendation_notes': recommendation_notes,
        'desc_match_level': desc_match_level,
        'secret_verification_level': secret_verification_level,
        'evidence_status': evidence_status,
        'risk_flags': risk_flags,
        'breakdown': breakdown
    }

