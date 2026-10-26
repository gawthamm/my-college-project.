# 🎓 Viva Voce & Technical Interview Questions & Answers

### Campus Smart Lost & Found System

---

### Category 1: Python Flask & Web Architecture

#### Q1: What is Flask, and why did you choose it over Django for this project?
**Answer**:  
Flask is a lightweight Python WSGI micro-framework. Unlike Django, which is an opinionated full-stack framework with heavy built-in ORM overhead, Flask is minimalist, modular, and gives full flexibility over database drivers (such as native PyMySQL) and application structure. For a focused campus solution requiring customized algorithmic matching and custom query adapters, Flask provides high speed, simplicity, and zero unnecessary boilerplate.

#### Q2: How does session management work in your application?
**Answer**:  
Flask uses cryptographically signed client-side cookies managed via `SECRET_KEY`. When a user logs in, their identity (`user_id`, `user_role`, `user_name`) is stored in the session dictionary. On each request, Flask verifies the cookie signature to prevent client tampering. We implemented custom Python decorators `@login_required` and `@admin_required` to guard restricted endpoints by inspecting these session attributes.

#### Q3: What is a Flask Context Processor, and why did you use it?
**Answer**:  
A context processor (`@app.context_processor`) runs before every template render and automatically injects global variables into all Jinja2 templates. We used it in `app.py` (`inject_global_data()`) to make `current_user`, `unread_count`, `db_engine`, and `now_year` globally accessible across all web pages without having to manually pass them inside every single view function.

#### Q4: How is cross-site scripting (XSS) prevented in your frontend?
**Answer**:  
Jinja2 template engine automatically escapes all dynamic expressions (e.g. `{{ item.title }}`) by converting potentially dangerous HTML characters (`<`, `>`, `&`, `"`) into their safe HTML entities (`&lt;`, `&gt;`, etc.), preventing malicious scripts from executing in client browsers.

---

### Category 2: MySQL Database & Data Management

#### Q5: Describe your database schema design and normalization level.
**Answer**:  
Our database schema is organized into 6 normalized tables (`users`, `categories`, `items`, `claims`, `item_returns`, `notifications`). The design satisfies Third Normal Form (3NF):
- Every table has a primary key.
- All non-key attributes are fully functionally dependent on the primary key (no partial dependencies).
- There are no transitive dependencies (e.g., Category metadata is stored in `categories` and linked via `category_id`).

#### Q6: How do you prevent SQL Injection attacks?
**Answer**:  
We strictly use **parameterized queries** with placeholder bindings (`%s` in PyMySQL and `?` in SQLite). User inputs are passed as separate parameter tuples to `cursor.execute(sql, params)`. The database driver treats user inputs purely as literal values, never as executable SQL commands, completely neutralizing SQL injection vulnerabilities.

#### Q7: What are Foreign Keys with `ON DELETE CASCADE` and why are they used?
**Answer**:  
Foreign keys enforce referential integrity between related tables. For instance, in the `items` table, `user_id` references `users(id) ON DELETE CASCADE`. If a user account is deleted, all their associated item reports and notifications are automatically cleaned up, eliminating orphaned records and preventing database corruption.

#### Q8: Explain your Dual-Engine Database Architecture (MySQL + Auto-Fallback).
**Answer**:  
The application connects to **MySQL** as its primary production database. If the MySQL service is stopped or port 3306 is temporarily closed, our database adapter catches the socket error and smoothly switches to a local **SQLite** database (`campus_lost_found.db`). It automatically translates query placeholders between `%s` and `?`, ensuring that students and evaluators can test the application without crashes.

---

### Category 3: Smart Matching Algorithm & Mathematics

#### Q9: How does the Python Smart Matching Engine compute similarity?
**Answer**:  
It employs a multi-attribute weighted scoring formula normalized from 0% to 100%:
$$\text{Score} = 30\% \cdot \text{Category} + 30\% \cdot \text{Title} + 20\% \cdot \text{Description} + 10\% \cdot \text{Location} + 10\% \cdot \text{Date}$$
- **Category (30%)**: Binary match (1.0 if identical category, 0.0 otherwise).
- **Title (30%)**: Combines Jaccard token overlap (60%) and Levenshtein Sequence Ratio (40%).
- **Description (20%)**: Keyword overlap stripped of common campus stopwords with bonuses for color and brand.
- **Location (10%)**: Campus zone token matching.
- **Date (10%)**: Proximity decay (same day: 1.0; within 3 days: 0.85; within 7 days: 0.70; decaying with time).

#### Q10: What is Jaccard Similarity and how is it calculated in code?
**Answer**:  
Jaccard Similarity measures the overlap between two token sets. It is defined as the size of the intersection divided by the size of the union:
$$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
In Python:
```python
intersection = len(set_a.intersection(set_b))
union = len(set_a.union(set_b))
similarity = intersection / union if union > 0 else 0.0
```

#### Q11: Why is Levenshtein/SequenceMatcher combined with token overlap?
**Answer**:  
Token overlap alone cannot detect typographical errors (e.g. "Calclator" vs "Calculator"). Levenshtein Sequence Ratio measures character edit distance, so even if a student misspells a brand or title, the sequence matcher retains partial similarity, creating a robust, fault-tolerant comparison.

---

### Category 4: Security & Anti-Fraud Verification

#### Q12: How are user passwords secured? Why not use MD5 or SHA-256?
**Answer**:  
We use Werkzeug's `generate_password_hash()`, which implements the modern **`scrypt`** key derivation function. MD5 and standard SHA-256 are fast hash algorithms that are vulnerable to rainbow table attacks and GPU-accelerated brute-force attacks. `scrypt` is intentionally memory-hard and CPU-intensive, with automatic salt generation, making offline brute-force attacks infeasible.

#### Q13: How does the system prevent fraudulent claims on high-value items?
**Answer**:  
When a student reports a found item, sensitive identifying features (such as serial numbers, screen wallpapers, internal bag contents, or secret scratches) are withheld from the public listing. To claim an item, a student must provide these secret identifiers in their claim description. The Campus Security Administrator performs a side-by-side comparison between the claimant's proof and the physical item before approving the release.

#### Q14: What is the Digital Handover Receipt and how does it ensure accountability?
**Answer**:  
When an item is returned, the system generates a unique cryptographic receipt token (`REC-YYYYMMDD-XXXXXXXX`). It records the owner's student roll number, the verifying officer's ID, the date and time, the physical verification method, and custodian remarks. This creates a permanent, tamper-evident digital certificate that can be printed or audited.

---

### Category 5: Real-World Scalability & Deployment

#### Q15: How would you deploy this application in a live university production environment?
**Answer**:  
In production:
1. Run Flask behind a production WSGI HTTP server like **Gunicorn** or **Waitress** with multiple worker processes.
2. Put **Nginx** in front as a reverse proxy to handle SSL/TLS encryption, static file caching, and rate limiting.
3. Host the MySQL database on a dedicated server with automated daily backups.
4. Store uploaded photos in cloud object storage (e.g., AWS S3 or Google Cloud Storage).

#### Q16: How does the system handle image file uploads securely?
**Answer**:  
1. We enforce an allowed extensions whitelist (`png`, `jpg`, `jpeg`, `webp`).
2. We rename every uploaded file with a randomized UUID prefix and timestamp (`uuid.uuid4().hex[:12] + timestamp`), preventing path traversal attacks and file overwrite collisions.
3. We configure `MAX_CONTENT_LENGTH = 16MB` in Flask to guard against denial-of-service via large file uploads.

#### Q17: Can this smart matching algorithm be integrated with Machine Learning in the future?
**Answer**:  
Yes. The current multi-factor algorithm provides an interpretable, zero-dependency baseline. In future iterations, we can integrate Computer Vision models (such as pre-trained ResNet or CLIP embeddings) to calculate visual cosine similarity directly between photos of lost and found items.
