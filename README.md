# 🏫 Campus Smart Lost & Found System

A secure, web-based Lost and Found management system designed for universities and colleges. Built with **Python Flask**, **MySQL**, **Bootstrap 5**, and a **Python-based Smart Similarity Matching Engine**.

---

## 🌟 Key Features

1. **Student & Admin Authentication**:
   - Secure registration and login with `scrypt` cryptographic password hashing.
   - Role-Based Access Control (Student vs Campus Security Administrator).

2. **Report Lost & Found Items**:
   - Categorized reporting (Electronics, ID Cards, Bags, Keys, Books, Accessories, etc.).
   - Campus location tracking (e.g. *Central Library 2nd Floor*, *Cafeteria*, *Science Block*).
   - Image upload support with live client-side preview.
   - Found item custody tracking (e.g. *Deposited at Security Desk Gate 1*).

3. **Python Smart Similarity Matching Engine**:
   - Multi-factor algorithmic scoring (0–100%):
     - **Category Match**: 30%
     - **Title Token & Sequence Similarity**: 30%
     - **Description & Keyword Overlap**: 20%
     - **Campus Location Proximity**: 10%
     - **Event Date Proximity**: 10%
   - Automatically recommends candidate matches and triggers instant notifications.

4. **Ownership Claims & Anti-Fraud Verification**:
   - Students submit secret identifying proof (e.g. unique scratches, serial numbers, wallpapers, internal contents) and optional receipts/photos.
   - Campus Security reviews proof side-by-side with physical found items.

5. **Item Return Tracking & Digital Handover Receipts**:
   - Generates tamper-evident cryptographic receipt tokens (`REC-YYYYMMDD-XXXXXXXX`).
   - Official printable handover certificate with signatures, timestamps, and custody audit logs.

6. **Campus Notification Center**:
   - In-app notification bell with unread badge counter for match alerts, claim approvals, and return confirmations.

7. **Admin Command Dashboard**:
   - Real-time KPI statistics and interactive **Chart.js** category distribution charts.
   - Verification queue for claim approvals and custody management.

8. **Dual Database Architecture (MySQL + Auto-Fallback)**:
   - Primary: **MySQL** (via PyMySQL).
   - Auto-Fallback: **SQLite** (`campus_lost_found.db`), ensuring zero downtime if the MySQL service is stopped.

---

## 💻 Tech Stack

- **Backend**: Python 3.13, Flask 3.1
- **Database**: MySQL Community Server / MariaDB (with PyMySQL) + SQLite auto-fallback
- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons
- **Visual Analytics**: Chart.js
- **Security**: Werkzeug Security (`generate_password_hash`, `check_password_hash`)

---

## 🚀 Windows Setup & Installation (Step-by-Step)

### Step 1: Open Terminal in Project Directory
Navigate to the project directory:
```powershell
cd campus_lost_and_found
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: MySQL Configuration & Database Initialization

#### Option A: Using MySQL Server (Recommended)
1. **Start the MySQL Service**:
   - Press `Win + R`, type `services.msc`, and press **Enter**.
   - Locate **MySQL267** (or **MySQL** / **MySQL80**), right-click and select **Start**.
   - *Alternatively, open PowerShell as Administrator and run:*
     ```powershell
     net start MySQL267
     ```
2. **Configure Database Credentials**:
   - By default, `config.py` connects to `127.0.0.1:3306` with user `root` and password `""` (empty).
   - If your MySQL root account has a password, set environment variables:
     ```powershell
     $env:MYSQL_PASSWORD="YourPasswordHere"
     ```
     *(Or create a `.env` file in the project folder with `MYSQL_PASSWORD=YourPasswordHere`)*.
3. **Run the Database Setup Script**:
   ```powershell
   python setup_database.py --engine mysql --password YourPasswordHere
   ```
   *This automatically creates the `campus_lost_found` database, executes `schema.sql`, and seeds initial demo categories and accounts.*

#### Option B: Immediate Zero-Configuration Mode (SQLite)
If MySQL is not currently running on your PC, you can start using the application immediately! The application automatically initializes a local database file (`campus_lost_found.db`) with zero setup required:
```powershell
python setup_database.py --engine sqlite
```

---

### Step 4: Run the Application
Start the Flask web development server:
```powershell
python app.py
```

Open your browser and navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔑 Default Accounts

| Role | Username / Identifier | Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Campus Admin** | `admin` (or `admin@campus.edu`) | `ADMIN@123` | Security Dashboard, Verify Claims, Issue Receipts |
| **Student 1** | `rahul@campus.edu` | `Student@123` | Report Items, Submit Claims, View Receipts |
| **Student 2** | `priya@campus.edu` | `Student@123` | Report Items, Submit Claims |

---

## 🧪 Running Automated Tests
Run the comprehensive test suite verifying database queries, authentication, smart matching scoring, and receipt generation:
```powershell
python tests\test_app.py
```

---

## 📂 Project Structure

```
campus_lost_and_found/
├── app.py                     # Main Flask routes, controllers, and REST APIs
├── config.py                  # Database & upload configurations
├── database.py                # Database connection manager (MySQL & SQLite abstraction)
├── matcher.py                 # Python Smart Matching similarity algorithm
├── schema.sql                 # MySQL schema DDL & initial seed dataset
├── setup_database.py          # Database initializer script
├── requirements.txt           # Python dependencies
├── static/
│   ├── css/
│   │   └── style.css          # Custom styling, badges, animations, print CSS
│   ├── js/
│   │   └── main.js            # Image preview, dynamic form toggles, copy tokens
│   └── uploads/               # Uploaded item images & default placeholder
├── templates/
│   ├── base.html              # Core layout, sticky navbar, footer, flash alerts
│   ├── index.html             # Landing page with search bar, stats, category grid
│   ├── login.html             # Login with 1-click demo fillers
│   ├── register.html          # Student registration form
│   ├── report_item.html       # Report lost/found items with live image preview
│   ├── browse.html            # Browse items with multi-parameter filter toolbar
│   ├── item_detail.html       # Item details with Smart Match score cards & claim modal
│   ├── my_items.html          # User's reported items & claims history
│   ├── notifications.html     # Notification center with unread badges
│   ├── admin_dashboard.html   # Admin portal with KPI cards and Chart.js chart
│   ├── admin_claims.html      # Filterable claims management table
│   ├── admin_claim_review.html# Side-by-side claim proof vs found item comparison
│   ├── admin_return_form.html # Verification & return handover protocol
│   ├── receipt.html           # Official printable digital return receipt
│   ├── 404.html               # Custom 404 error page
│   └── 500.html               # Custom 500 error page
├── tests/
│   └── test_app.py            # Automated unit & integration tests
├── README.md                  # Windows setup & execution guide
├── PROJECT_REPORT.md          # Comprehensive academic project report
├── PRESENTATION_OUTLINE.md    # 10-slide presentation outline with speaker notes
└── VIVA_QUESTIONS.md          # 25 Viva voce examination questions & answers
```

---

## 🛠️ Troubleshooting Guide

- **Error: `Port 5000 is already in use`**:
  - Run `netstat -ano | findstr :5000` to find the PID, and kill it with `taskkill /PID <PID> /F`, or modify `port=5001` in `app.py`.
- **MySQL Connection Refused**:
  - Check if the Windows service `MySQL267` is running (`services.msc`).
  - If stopped and you don't have Admin privileges to start it, the application will automatically fall back to SQLite without crashing.
