import sqlite3
import pymysql
import pymysql.cursors
from werkzeug.security import generate_password_hash
from config import Config

import socket

# Track active database engine
_ACTIVE_ENGINE = None

def is_mysql_available():
    """Quickly checks if MySQL port is open to avoid socket connection timeouts."""
    try:
        host = '127.0.0.1' if Config.MYSQL_HOST in ('localhost', '') else Config.MYSQL_HOST
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.4)
        result = sock.connect_ex((host, Config.MYSQL_PORT))
        sock.close()
        return result == 0
    except Exception:
        return False

def get_db_connection():
    """
    Attempts to connect to MySQL first.
    If MySQL server is unavailable or fails to connect,
    gracefully connects to local SQLite file for uninterrupted operation.
    Caches active engine to make all subsequent queries instant.
    """
    global _ACTIVE_ENGINE
    
    # If already determined, reuse immediately
    if _ACTIVE_ENGINE == 'sqlite':
        conn = sqlite3.connect(Config.SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn, 'sqlite'
    elif _ACTIVE_ENGINE == 'mysql':
        try:
            conn = pymysql.connect(
                host='127.0.0.1' if Config.MYSQL_HOST == 'localhost' else Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=2
            )
            return conn, 'mysql'
        except Exception:
            # Fall back to sqlite if mysql drops
            _ACTIVE_ENGINE = 'sqlite'
            conn = sqlite3.connect(Config.SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            return conn, 'sqlite'

    # Initial probe: Try MySQL first if port is open
    if is_mysql_available():
        try:
            conn = pymysql.connect(
                host='127.0.0.1' if Config.MYSQL_HOST == 'localhost' else Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=2
            )
            _ACTIVE_ENGINE = 'mysql'
            return conn, 'mysql'
        except Exception:
            pass

    # Graceful fallback to SQLite
    conn = sqlite3.connect(Config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    _ACTIVE_ENGINE = 'sqlite'
    return conn, 'sqlite'

def get_engine_name():
    """Returns the current database engine name ('MySQL' or 'SQLite')."""
    global _ACTIVE_ENGINE
    if _ACTIVE_ENGINE is None:
        try:
            _, engine = get_db_connection()
            return 'MySQL' if engine == 'mysql' else 'SQLite'
        except Exception:
            return 'SQLite'
    return 'MySQL' if _ACTIVE_ENGINE == 'mysql' else 'SQLite'

def execute_query(sql, params=None, fetchone=False, fetchall=False, commit=False):
    """
    Executes a query safely on the active database engine.
    Automatically adapts placeholders (%s for MySQL vs ? for SQLite).
    """
    conn, engine = get_db_connection()
    params = params or ()
    
    # Normalize params to tuple if list
    if isinstance(params, list):
        params = tuple(params)
    elif not isinstance(params, (tuple, dict)):
        params = (params,)

    # Adapt SQL placeholders if needed
    adapted_sql = sql
    if engine == 'sqlite':
        # Replace %s with ?
        adapted_sql = adapted_sql.replace('%s', '?')
    elif engine == 'mysql':
        # Replace ? with %s
        adapted_sql = adapted_sql.replace('?', '%s')

    result = None
    last_id = None

    try:
        cursor = conn.cursor()
        cursor.execute(adapted_sql, params)

        if fetchone:
            row = cursor.fetchone()
            if row and engine == 'sqlite':
                result = dict(row)
            else:
                result = row
        elif fetchall:
            rows = cursor.fetchall()
            if rows and engine == 'sqlite':
                result = [dict(r) for r in rows]
            else:
                result = list(rows) if rows else []

        if commit:
            conn.commit()
            last_id = cursor.lastrowid

        return {
            'data': result,
            'last_id': last_id,
            'rowcount': cursor.rowcount,
            'engine': engine
        }
    finally:
        conn.close()

def init_db():
    """
    Initializes tables and seeds initial data in the active database.
    """
    conn, engine = get_db_connection()
    try:
        cursor = conn.cursor()
        if engine == 'mysql':
            # Create tables in MySQL if not exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(120) NOT NULL UNIQUE,
                student_id VARCHAR(50) NOT NULL UNIQUE,
                phone VARCHAR(20) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('student', 'admin') DEFAULT 'student',
                department VARCHAR(100) DEFAULT 'General',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL UNIQUE,
                icon VARCHAR(50) DEFAULT 'bi-box-seam',
                description VARCHAR(255)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                item_type ENUM('lost', 'found') NOT NULL,
                title VARCHAR(150) NOT NULL,
                category_id INT NOT NULL,
                description TEXT NOT NULL,
                location VARCHAR(150) NOT NULL,
                event_date DATE NOT NULL,
                primary_color VARCHAR(50) DEFAULT 'Unknown',
                brand VARCHAR(100) DEFAULT 'Unknown',
                image_filename VARCHAR(255) DEFAULT 'default_item.png',
                storage_location VARCHAR(255) DEFAULT NULL,
                status ENUM('open', 'claimed', 'returned', 'closed') DEFAULT 'open',
                is_resolved BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id INT NOT NULL,
                claimant_id INT NOT NULL,
                proof_description TEXT NOT NULL,
                proof_image VARCHAR(255) DEFAULT NULL,
                contact_number VARCHAR(20) NOT NULL,
                status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
                admin_notes TEXT DEFAULT NULL,
                reviewed_by INT DEFAULT NULL,
                reviewed_at TIMESTAMP NULL DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (claimant_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_returns (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_id INT NOT NULL UNIQUE,
                claim_id INT NOT NULL,
                owner_id INT NOT NULL,
                handed_over_by INT NOT NULL,
                receipt_token VARCHAR(64) NOT NULL UNIQUE,
                returned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_method VARCHAR(100) DEFAULT 'Student ID & Physical Verification',
                remarks TEXT DEFAULT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (handed_over_by) REFERENCES users(id) ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(150) NOT NULL,
                message TEXT NOT NULL,
                link VARCHAR(255) DEFAULT '#',
                is_read BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS smart_matches (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lost_item_id INT NOT NULL,
                found_item_id INT NOT NULL,
                similarity_score DECIMAL(5,2) NOT NULL,
                match_breakdown TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lost_item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (found_item_id) REFERENCES items(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT,
                action VARCHAR(100) NOT NULL,
                item_id INT DEFAULT NULL,
                claim_id INT DEFAULT NULL,
                details TEXT,
                ip_address VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            conn.commit()

        else:
            # SQLite Table definitions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                student_id TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'student',
                department TEXT DEFAULT 'General',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                icon TEXT DEFAULT 'bi-box-seam',
                description TEXT
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                title TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                event_date DATE NOT NULL,
                primary_color TEXT DEFAULT 'Unknown',
                brand TEXT DEFAULT 'Unknown',
                image_filename TEXT DEFAULT 'default_item.png',
                storage_location TEXT DEFAULT NULL,
                secret_details TEXT DEFAULT NULL,
                status TEXT DEFAULT 'open',
                is_resolved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id)
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                claimant_id INTEGER NOT NULL,
                proof_description TEXT NOT NULL,
                proof_image TEXT DEFAULT NULL,
                contact_number TEXT NOT NULL,
                secret_answer TEXT DEFAULT NULL,
                claim_match_score REAL DEFAULT 0.0,
                ai_recommendation TEXT DEFAULT NULL,
                risk_flags TEXT DEFAULT NULL,
                evidence_type TEXT DEFAULT 'Feature Description',
                status TEXT DEFAULT 'pending',
                admin_notes TEXT DEFAULT NULL,
                reviewed_by INTEGER DEFAULT NULL,
                reviewed_at TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (claimant_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS item_returns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL UNIQUE,
                claim_id INTEGER NOT NULL,
                owner_id INTEGER NOT NULL,
                handed_over_by INTEGER NOT NULL,
                receipt_token TEXT NOT NULL UNIQUE,
                returned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                verification_method TEXT DEFAULT 'Student ID & Physical Verification',
                remarks TEXT DEFAULT NULL,
                FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE,
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (handed_over_by) REFERENCES users(id)
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                link TEXT DEFAULT '#',
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS smart_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lost_item_id INTEGER NOT NULL,
                found_item_id INTEGER NOT NULL,
                similarity_score REAL NOT NULL,
                match_breakdown TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lost_item_id) REFERENCES items(id) ON DELETE CASCADE,
                FOREIGN KEY (found_item_id) REFERENCES items(id) ON DELETE CASCADE
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                item_id INTEGER DEFAULT NULL,
                claim_id INTEGER DEFAULT NULL,
                details TEXT,
                ip_address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()

        # Idempotent Column Migrations for existing databases
        def add_col_if_missing(table, col, col_def):
            try:
                if engine == 'sqlite':
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [r[1] for r in cursor.fetchall()]
                    if col not in cols:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
                else:
                    cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{col}'")
                    if not cursor.fetchone():
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                pass

        add_col_if_missing('items', 'secret_details', 'TEXT DEFAULT NULL')
        add_col_if_missing('claims', 'secret_answer', 'TEXT DEFAULT NULL')
        add_col_if_missing('claims', 'claim_match_score', 'REAL DEFAULT 0.0' if engine == 'sqlite' else 'DECIMAL(5,2) DEFAULT 0.0')
        add_col_if_missing('claims', 'ai_recommendation', 'TEXT DEFAULT NULL')
        add_col_if_missing('claims', 'risk_flags', 'TEXT DEFAULT NULL')
        add_col_if_missing('claims', 'evidence_type', 'TEXT DEFAULT "Feature Description"')
        conn.commit()

        # Seed categories if empty
        cursor.execute("SELECT COUNT(*) as count FROM categories")
        count_res = cursor.fetchone()
        count = count_res['count'] if isinstance(count_res, dict) else (count_res[0] if count_res else 0)
        
        if count == 0:
            categories_data = [
                ('Electronics & Gadgets', 'bi-laptop', 'Laptops, mobile phones, chargers, headphones, calculators, USB drives'),
                ('ID Cards & Documents', 'bi-person-badge', 'Campus ID cards, driver licenses, ATM cards, notebooks, certificates'),
                ('Bags & Wallets', 'bi-bag', 'Backpacks, handbags, purses, wallets, pouches'),
                ('Keys & Access Cards', 'bi-key', 'Room keys, bike/car keys, hostel keychains, RFID tags'),
                ('Books & Study Material', 'bi-book', 'Textbooks, lab manuals, assignment notebooks, binders'),
                ('Clothing & Accessories', 'bi-eyeglasses', 'Jackets, hoodies, caps, watches, spectacles, sunglasses, water bottles'),
                ('Other Items', 'bi-box', 'Sports equipment, umbrellas, musical instruments, miscellaneous items')
            ]
            for name, icon, desc in categories_data:
                placeholder = '%s' if engine == 'mysql' else '?'
                cursor.execute(
                    f"INSERT INTO categories (name, icon, description) VALUES ({placeholder}, {placeholder}, {placeholder})",
                    (name, icon, desc)
                )
            conn.commit()

        # Seed Administrator account if users table is empty
        cursor.execute("SELECT COUNT(*) as count FROM users")
        user_count_res = cursor.fetchone()
        user_count = user_count_res['count'] if isinstance(user_count_res, dict) else (user_count_res[0] if user_count_res else 0)

        if user_count == 0:
            admin_hash = generate_password_hash('ADMIN@123')
            placeholder = '%s' if engine == 'mysql' else '?'
            
            # Insert System Administrator
            cursor.execute(
                f"""INSERT INTO users (full_name, email, student_id, phone, password_hash, role, department)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})""",
                ('Campus Security Administrator', 'admin@campus.edu', 'ADMIN', '9876543210', admin_hash, 'admin', 'Campus Security Office')
            )
            conn.commit()

    finally:
        conn.close()

# -------------------------------------------------------------
# User Data Access Functions
# -------------------------------------------------------------
def get_user_by_email(email):
    return execute_query("SELECT * FROM users WHERE LOWER(email) = %s", (email.strip().lower(),), fetchone=True)['data']

def get_user_by_student_id(student_id):
    return execute_query("SELECT * FROM users WHERE LOWER(student_id) = %s", (student_id.strip().lower(),), fetchone=True)['data']

def get_user_by_identifier(identifier):
    """Fetches user by email, student_id, or username 'admin'."""
    if not identifier:
        return None
    ident = identifier.strip().lower()
    user = execute_query(
        "SELECT * FROM users WHERE LOWER(email) = %s OR LOWER(student_id) = %s",
        (ident, ident),
        fetchone=True
    )['data']
    if not user and ident in ('admin', 'admin001', 'security'):
        user = execute_query("SELECT * FROM users WHERE role = 'admin' LIMIT 1", fetchone=True)['data']
    return user

def get_user_by_id(user_id):
    return execute_query("SELECT * FROM users WHERE id = %s", (user_id,), fetchone=True)['data']

def create_user(full_name, email, student_id, phone, password_hash, role='student', department='General'):
    res = execute_query(
        """INSERT INTO users (full_name, email, student_id, phone, password_hash, role, department)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (full_name, email.strip().lower(), student_id.strip(), phone.strip(), password_hash, role, department),
        commit=True
    )
    return res['last_id']

# -------------------------------------------------------------
# Category Data Access Functions
# -------------------------------------------------------------
def get_categories():
    return execute_query("SELECT * FROM categories ORDER BY name ASC", fetchall=True)['data']

def get_category_by_id(category_id):
    return execute_query("SELECT * FROM categories WHERE id = %s", (category_id,), fetchone=True)['data']

# -------------------------------------------------------------
# Items Data Access Functions
# -------------------------------------------------------------
def create_item(user_id, item_type, title, category_id, description, location, event_date, primary_color, brand, image_filename, storage_location=None, secret_details=None):
    res = execute_query(
        """INSERT INTO items (user_id, item_type, title, category_id, description, location, event_date, primary_color, brand, image_filename, storage_location, secret_details, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'open')""",
        (user_id, item_type, title, category_id, description, location, event_date, primary_color, brand, image_filename, storage_location, secret_details),
        commit=True
    )
    return res['last_id']

def get_item_by_id(item_id):
    sql = """
    SELECT i.*, c.name as category_name, c.icon as category_icon, 
           u.full_name as reporter_name, u.email as reporter_email, u.phone as reporter_phone, 
           u.student_id as reporter_student_id, u.department as reporter_department
    FROM items i
    JOIN categories c ON i.category_id = c.id
    JOIN users u ON i.user_id = u.id
    WHERE i.id = %s
    """
    return execute_query(sql, (item_id,), fetchone=True)['data']

def get_items(item_type=None, category_id=None, status=None, search_query=None, limit=50):
    sql = """
    SELECT i.*, c.name as category_name, c.icon as category_icon, u.full_name as reporter_name
    FROM items i
    JOIN categories c ON i.category_id = c.id
    JOIN users u ON i.user_id = u.id
    WHERE 1=1
    """
    params = []
    
    if item_type:
        sql += " AND i.item_type = %s"
        params.append(item_type)
    if category_id:
        sql += " AND i.category_id = %s"
        params.append(int(category_id))
    if status:
        sql += " AND i.status = %s"
        params.append(status)
    if search_query:
        sql += " AND (i.title LIKE %s OR i.description LIKE %s OR i.location LIKE %s OR i.brand LIKE %s)"
        pattern = f"%{search_query.strip()}%"
        params.extend([pattern, pattern, pattern, pattern])

    sql += " ORDER BY i.created_at DESC LIMIT %s"
    params.append(max(1, min(int(limit), 200)))

    return execute_query(sql, tuple(params), fetchall=True)['data']

def get_items_by_user(user_id):
    sql = """
    SELECT i.*, c.name as category_name, c.icon as category_icon
    FROM items i
    JOIN categories c ON i.category_id = c.id
    WHERE i.user_id = %s
    ORDER BY i.created_at DESC
    """
    return execute_query(sql, (user_id,), fetchall=True)['data']

def update_item_status(item_id, status, is_resolved=False):
    execute_query(
        "UPDATE items SET status = %s, is_resolved = %s WHERE id = %s",
        (status, 1 if is_resolved else 0, item_id),
        commit=True
    )

def delete_item(item_id):
    execute_query("DELETE FROM items WHERE id = %s", (item_id,), commit=True)

# -------------------------------------------------------------
# Claims Data Access Functions
# -------------------------------------------------------------
def create_claim(item_id, claimant_id, proof_description, proof_image, contact_number, secret_answer=None, claim_match_score=0.0, ai_recommendation=None, risk_flags=None, evidence_type='Feature Description'):
    res = execute_query(
        """INSERT INTO claims (item_id, claimant_id, proof_description, proof_image, contact_number, secret_answer, claim_match_score, ai_recommendation, risk_flags, evidence_type, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')""",
        (item_id, claimant_id, proof_description, proof_image, contact_number, secret_answer, claim_match_score, ai_recommendation, risk_flags, evidence_type),
        commit=True
    )
    return res['last_id']

def get_claim_by_id(claim_id):
    sql = """
    SELECT cl.*, 
           i.title as item_title, i.item_type, i.storage_location, i.status as item_status,
           i.secret_details as item_secret_details, i.description as item_desc,
           i.brand as item_brand, i.primary_color as item_color, i.location as item_location,
           i.event_date as item_event_date, i.image_filename as item_image,
           u.full_name as claimant_name, u.email as claimant_email, u.student_id as claimant_student_id, u.phone as claimant_phone, u.department as claimant_dept,
           admin.full_name as reviewer_name
    FROM claims cl
    JOIN items i ON cl.item_id = i.id
    JOIN users u ON cl.claimant_id = u.id
    LEFT JOIN users admin ON cl.reviewed_by = admin.id
    WHERE cl.id = %s
    """
    return execute_query(sql, (claim_id,), fetchone=True)['data']

def get_claims_for_item(item_id):
    sql = """
    SELECT cl.*, 
           u.full_name as claimant_name, u.student_id as claimant_student_id, 
           u.email as claimant_email, u.phone as claimant_phone, u.department as claimant_dept
    FROM claims cl
    JOIN users u ON cl.claimant_id = u.id
    WHERE cl.item_id = %s
    ORDER BY cl.created_at DESC
    """
    return execute_query(sql, (item_id,), fetchall=True)['data']

def get_claims_by_user(user_id):
    sql = """
    SELECT cl.*, i.title as item_title, i.image_filename as item_image, i.location as item_location, i.status as item_status
    FROM claims cl
    JOIN items i ON cl.item_id = i.id
    WHERE cl.claimant_id = %s
    ORDER BY cl.created_at DESC
    """
    return execute_query(sql, (user_id,), fetchall=True)['data']

def get_all_claims(status=None):
    sql = """
    SELECT cl.*, 
           i.title as item_title, i.image_filename, i.storage_location, i.location,
           u.full_name as claimant_name, u.student_id as claimant_student_id, u.department as claimant_dept
    FROM claims cl
    JOIN items i ON cl.item_id = i.id
    JOIN users u ON cl.claimant_id = u.id
    """
    params = []
    if status:
        sql += " WHERE cl.status = %s"
        params.append(status)
    sql += " ORDER BY cl.created_at DESC"
    return execute_query(sql, tuple(params), fetchall=True)['data']

def update_claim_status(claim_id, status, admin_notes, reviewed_by):
    from datetime import datetime
    execute_query(
        """UPDATE claims 
           SET status = %s, admin_notes = %s, reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP 
           WHERE id = %s""",
        (status, admin_notes, reviewed_by, claim_id),
        commit=True
    )

# -------------------------------------------------------------
# Item Return & Receipt Tracking Functions
# -------------------------------------------------------------
def create_item_return(item_id, claim_id, owner_id, handed_over_by, receipt_token, verification_method, remarks):
    res = execute_query(
        """INSERT INTO item_returns (item_id, claim_id, owner_id, handed_over_by, receipt_token, verification_method, remarks)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (item_id, claim_id, owner_id, handed_over_by, receipt_token, verification_method, remarks),
        commit=True
    )
    # Update item status to 'returned' and resolved to 1
    update_item_status(item_id, 'returned', is_resolved=True)
    return res['last_id']

def get_return_by_token(token):
    sql = """
    SELECT r.*, 
           i.title as item_title, i.description as item_desc, i.event_date, i.location as item_location,
           owner.full_name as owner_name, owner.student_id as owner_student_id, owner.email as owner_email, owner.phone as owner_phone, owner.department as owner_dept,
           finder.full_name as finder_name, finder.student_id as finder_student_id, finder.phone as finder_phone, finder.email as finder_email,
           admin.full_name as admin_name, admin.email as admin_email,
           cl.proof_description
    FROM item_returns r
    JOIN items i ON r.item_id = i.id
    JOIN users owner ON r.owner_id = owner.id
    JOIN users finder ON i.user_id = finder.id
    JOIN users admin ON r.handed_over_by = admin.id
    JOIN claims cl ON r.claim_id = cl.id
    WHERE r.receipt_token = %s
    """
    return execute_query(sql, (token,), fetchone=True)['data']

def get_return_for_item(item_id):
    sql = """
    SELECT r.*, 
           owner.full_name as owner_name, owner.student_id as owner_student_id, 
           owner.email as owner_email, owner.phone as owner_phone, owner.department as owner_dept,
           admin.full_name as admin_name
    FROM item_returns r
    JOIN users owner ON r.owner_id = owner.id
    JOIN users admin ON r.handed_over_by = admin.id
    WHERE r.item_id = %s
    """
    return execute_query(sql, (item_id,), fetchone=True)['data']

def get_all_returns():
    sql = """
    SELECT r.*, i.title as item_title, owner.full_name as owner_name, admin.full_name as admin_name
    FROM item_returns r
    JOIN items i ON r.item_id = i.id
    JOIN users owner ON r.owner_id = owner.id
    JOIN users admin ON r.handed_over_by = admin.id
    ORDER BY r.returned_date DESC
    """
    return execute_query(sql, fetchall=True)['data']

# -------------------------------------------------------------
# Notifications Functions
# -------------------------------------------------------------
def add_notification(user_id, title, message, link='#'):
    res = execute_query(
        """INSERT INTO notifications (user_id, title, message, link, is_read)
           VALUES (%s, %s, %s, %s, 0)""",
        (user_id, title, message, link),
        commit=True
    )
    return res['last_id']

def get_user_notifications(user_id, limit=20):
    return execute_query(
        """SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT %s""",
        (user_id, limit),
        fetchall=True
    )['data']

def get_unread_count(user_id):
    res = execute_query(
        """SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = 0""",
        (user_id,),
        fetchone=True
    )['data']
    return res['count'] if res else 0

def mark_notification_as_read(notif_id, user_id):
    execute_query(
        "UPDATE notifications SET is_read = 1 WHERE id = %s AND user_id = %s",
        (notif_id, user_id),
        commit=True
    )

def mark_all_notifications_read(user_id):
    execute_query(
        "UPDATE notifications SET is_read = 1 WHERE user_id = %s",
        (user_id,),
        commit=True
    )

# -------------------------------------------------------------
# -------------------------------------------------------------
# Smart Matching Persistence & Alerts
# -------------------------------------------------------------
def save_smart_match(lost_item_id, found_item_id, similarity_score, match_breakdown=None):
    import json
    breakdown_str = json.dumps(match_breakdown) if isinstance(match_breakdown, dict) else (match_breakdown or '')
    
    # Check if this pair is already saved
    existing = execute_query(
        "SELECT id FROM smart_matches WHERE (lost_item_id = %s AND found_item_id = %s) OR (lost_item_id = %s AND found_item_id = %s)",
        (lost_item_id, found_item_id, found_item_id, lost_item_id),
        fetchone=True
    )['data']
    
    if existing:
        execute_query(
            "UPDATE smart_matches SET similarity_score = %s, match_breakdown = %s WHERE id = %s",
            (similarity_score, breakdown_str, existing['id']),
            commit=True
        )
        return existing['id']
    else:
        res = execute_query(
            "INSERT INTO smart_matches (lost_item_id, found_item_id, similarity_score, match_breakdown) VALUES (%s, %s, %s, %s)",
            (lost_item_id, found_item_id, similarity_score, breakdown_str),
            commit=True
        )
        return res['last_id']

def get_smart_matches_for_item(item_id):
    sql = """
    SELECT sm.*,
           lost.title as lost_title, lost.location as lost_location, lost.event_date as lost_date, lost.image_filename as lost_image,
           found.title as found_title, found.location as found_location, found.event_date as found_date, found.image_filename as found_image,
           found.status as found_status, lost.status as lost_status
    FROM smart_matches sm
    JOIN items lost ON sm.lost_item_id = lost.id
    JOIN items found ON sm.found_item_id = found.id
    WHERE sm.lost_item_id = %s OR sm.found_item_id = %s
    ORDER BY sm.similarity_score DESC
    """
    return execute_query(sql, (item_id, item_id), fetchall=True)['data']

def get_smart_matches_for_user(user_id):
    sql = """
    SELECT sm.*,
           lost.id as lost_id, lost.title as lost_title, lost.location as lost_location, lost.user_id as lost_user_id,
           found.id as found_id, found.title as found_title, found.location as found_location, found.user_id as found_user_id,
           found.image_filename as found_image, lost.image_filename as lost_image,
           found.status as found_status, lost.status as lost_status
    FROM smart_matches sm
    JOIN items lost ON sm.lost_item_id = lost.id
    JOIN items found ON sm.found_item_id = found.id
    WHERE (lost.user_id = %s OR found.user_id = %s)
      AND (lost.status = 'open' OR found.status = 'open')
    ORDER BY sm.similarity_score DESC
    """
    return execute_query(sql, (user_id, user_id), fetchall=True)['data']

def get_suspicious_claim_alerts():
    """
    Scans claim patterns for administrator security review:
    1. Users with multiple rejected claims (>= 2).
    2. Users who submitted high volume of claims across different items (>= 3).
    """
    alerts = []

    # 1. High rejection rate
    rejected_users = execute_query("""
        SELECT u.id, u.full_name, u.email, u.student_id, COUNT(cl.id) as rejected_count
        FROM claims cl
        JOIN users u ON cl.claimant_id = u.id
        WHERE cl.status = 'rejected'
        GROUP BY u.id, u.full_name, u.email, u.student_id
        HAVING rejected_count >= 2
    """, fetchall=True)['data']

    for u in rejected_users:
        alerts.append({
            'user_id': u['id'],
            'full_name': u['full_name'],
            'student_id': u['student_id'],
            'email': u['email'],
            'risk_level': 'High' if u['rejected_count'] >= 3 else 'Moderate',
            'alert_type': 'Multiple Rejected Claims',
            'description': f"Student has {u['rejected_count']} previously rejected claim(s). Indicates potential guesswork or fraudulent claiming attempts."
        })

    # 2. High frequency claiming (>= 3 claims)
    frequent_claimers = execute_query("""
        SELECT u.id, u.full_name, u.email, u.student_id, COUNT(cl.id) as total_claims,
               COUNT(DISTINCT cl.item_id) as distinct_items
        FROM claims cl
        JOIN users u ON cl.claimant_id = u.id
        GROUP BY u.id, u.full_name, u.email, u.student_id
        HAVING total_claims >= 3
    """, fetchall=True)['data']

    for u in frequent_claimers:
        if not any(a['user_id'] == u['id'] for a in alerts):
            alerts.append({
                'user_id': u['id'],
                'full_name': u['full_name'],
                'student_id': u['student_id'],
                'email': u['email'],
                'risk_level': 'Moderate',
                'alert_type': 'High Frequency Claiming Activity',
                'description': f"Student submitted claims for {u['distinct_items']} different items ({u['total_claims']} total claims). Exercise thorough proof verification."
            })

    return alerts

# -------------------------------------------------------------
# Dashboard Statistics & Analytics
# -------------------------------------------------------------
def get_dashboard_stats():
    total_items = execute_query("SELECT COUNT(*) as c FROM items", fetchone=True)['data']['c']
    lost_items = execute_query("SELECT COUNT(*) as c FROM items WHERE item_type = 'lost'", fetchone=True)['data']['c']
    found_items = execute_query("SELECT COUNT(*) as c FROM items WHERE item_type = 'found'", fetchone=True)['data']['c']
    total_claims = execute_query("SELECT COUNT(*) as c FROM claims", fetchone=True)['data']['c']
    pending_claims = execute_query("SELECT COUNT(*) as c FROM claims WHERE status = 'pending'", fetchone=True)['data']['c']
    returned_items = execute_query("SELECT COUNT(*) as c FROM items WHERE status = 'returned'", fetchone=True)['data']['c']
    total_users = execute_query("SELECT COUNT(*) as c FROM users WHERE role = 'student'", fetchone=True)['data']['c']
    
    # Category distribution for chart
    cat_counts = execute_query("""
        SELECT c.name, COUNT(i.id) as count
        FROM categories c
        LEFT JOIN items i ON c.id = i.category_id
        GROUP BY c.id, c.name
        ORDER BY count DESC
    """, fetchall=True)['data']

    # Most frequently lost item categories
    frequent_lost_cats = execute_query("""
        SELECT c.name, COUNT(i.id) as lost_count
        FROM categories c
        JOIN items i ON c.id = i.category_id
        WHERE i.item_type = 'lost'
        GROUP BY c.id, c.name
        ORDER BY lost_count DESC
    """, fetchall=True)['data']

    # Monthly recovery statistics
    from collections import defaultdict
    from datetime import datetime
    monthly_recoveries = defaultdict(int)
    returns_list = execute_query("SELECT returned_date FROM item_returns", fetchall=True)['data']
    for r in returns_list:
        rd = r.get('returned_date')
        if rd:
            month_str = str(rd)[:7]
            monthly_recoveries[month_str] += 1

    # Ensure current and past 3 months have keys for clean graphing
    now = datetime.now()
    month_labels = []
    month_values = []
    for i in range(5, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        y = now.year if now.month - i > 0 else now.year - 1
        m_key = f"{y:04d}-{m:02d}"
        m_label = datetime(y, m, 1).strftime('%b %Y')
        month_labels.append(m_label)
        month_values.append(monthly_recoveries.get(m_key, 0))

    # Resolution rate
    resolution_rate = round((returned_items / total_items * 100), 1) if total_items > 0 else 0.0

    return {
        'total_items': total_items,
        'lost_items': lost_items,
        'found_items': found_items,
        'total_claims': total_claims,
        'pending_claims': pending_claims,
        'returned_items': returned_items,
        'total_users': total_users,
        'resolution_rate': resolution_rate,
        'frequent_lost_cats': frequent_lost_cats,
        'monthly_labels': month_labels,
        'monthly_data': month_values,
        'category_chart_labels': [row['name'] for row in cat_counts],
        'category_chart_data': [row['count'] for row in cat_counts]
    }

# -------------------------------------------------------------
# Security Audit Logs & Claim Rate Limiting
# -------------------------------------------------------------
def add_audit_log(user_id, action, item_id=None, claim_id=None, details=None, ip_address=None):
    res = execute_query(
        """INSERT INTO audit_logs (user_id, action, item_id, claim_id, details, ip_address)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (user_id, action, item_id, claim_id, details, ip_address),
        commit=True
    )
    return res['last_id']

def get_audit_logs(limit=25):
    sql = """
    SELECT a.*, u.full_name as user_name, u.email as user_email, u.student_id as user_student_id, u.role as user_role
    FROM audit_logs a
    LEFT JOIN users u ON a.user_id = u.id
    ORDER BY a.created_at DESC
    LIMIT %s
    """
    return execute_query(sql, (limit,), fetchall=True)['data']

def get_user_recent_claims_count(user_id, hours=24):
    """Counts claims submitted by this user within the last X hours to enforce velocity rate limits."""
    conn, engine = get_db_connection()
    try:
        if engine == 'sqlite':
            sql = "SELECT COUNT(*) as c FROM claims WHERE claimant_id = ? AND datetime(created_at) >= datetime('now', ?)"
            param = f"-{hours} hours"
            row = execute_query(sql, (user_id, param), fetchone=True)['data']
        else:
            sql = "SELECT COUNT(*) as c FROM claims WHERE claimant_id = %s AND created_at >= NOW() - INTERVAL %s HOUR"
            row = execute_query(sql, (user_id, hours), fetchone=True)['data']
        return row['c'] if row else 0
    except Exception:
        row = execute_query("SELECT COUNT(*) as c FROM claims WHERE claimant_id = %s", (user_id,), fetchone=True)['data']
        return row['c'] if row else 0

def get_user_claim_history(user_id):
    """Returns total, rejected, approved, and recent 24h claims count for a user."""
    total_res = execute_query("SELECT COUNT(*) as c FROM claims WHERE claimant_id = %s", (user_id,), fetchone=True)['data']
    rej_res = execute_query("SELECT COUNT(*) as c FROM claims WHERE claimant_id = %s AND status = 'rejected'", (user_id,), fetchone=True)['data']
    app_res = execute_query("SELECT COUNT(*) as c FROM claims WHERE claimant_id = %s AND status = 'approved'", (user_id,), fetchone=True)['data']
    recent_24h = get_user_recent_claims_count(user_id, hours=24)
    return {
        'total': total_res['c'] if total_res else 0,
        'rejected': rej_res['c'] if rej_res else 0,
        'approved': app_res['c'] if app_res else 0,
        'recent_24h': recent_24h
    }

