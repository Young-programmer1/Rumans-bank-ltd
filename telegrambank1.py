import threading
import time
import json
import os
import random
import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import getpass
from datetime import datetime, timedelta
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
# --- TELEGRAM BOT IMPORTS ---
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, filters
)

# ---------------- CONFIG ----------------
# !!! REPLACE '8441110948:AAE1nP1yP3J_ijVPfQaVJyqozkaK5_fOCwI' WITH YOUR ACTUAL BOT TOKEN !!!
BOT_TOKEN = os.environ.get("TOKEN_BOT") 
# --- CONVERSATION STATES ---
(
    START, MAIN_MENU, LOGIN_EMAIL, LOGIN_PIN, ADMIN_PIN_INPUT,
    USER_MENU, TRANSFER_MENU, TRANSFER_INTERNAL_ACCT, TRANSFER_INTERNAL_AMT,
    TRANSFER_EXTERNAL_BANK, TRANSFER_EXTERNAL_ACCT, TRANSFER_EXTERNAL_NAME,
    TRANSFER_EXTERNAL_AMT, TRANSFER_EXTERNAL_EMAIL, TRANSFER_EXTERNAL_NARR,
    OTP_ENTRY, TOPUP_MENU, TOPUP_NETWORK, TOPUP_AIRTIME_PHONE, TOPUP_AIRTIME_AMT,
    TOPUP_DATA_PHONE, TOPUP_DATA_BUNDLE, DEPOSIT_CODE_INPUT,
    REGISTER_FIRST_NAME, REGISTER_LAST_NAME, REGISTER_AGE, REGISTER_EMAIL, REGISTER_PIN,
    ADMIN_GEN_CODE_INPUT
) = range(29)

DATA_FILE = "romans_banks_data.json"
SENDER_EMAIL = "rumansbankltd@gmail.com"          # Replace with your Gmail
# Replace with Gmail App Password
APP_PASSWORD = os.environ.get("APP_PASSWORD")
SENDER_NAME = "ROMANS BANK LTD"

# ---------------- UTILITY ----------------
BANK_LIST = ["Romans Bank Ltd"]
ADMIN_EMAIL = "admin@romansbank.com"
ADMIN_PIN = "350184"
# code -> {"amount": float, "used": False, "redeemed_by": None, "redeemed_at": None}
DEPOSIT_CODE_FILE = "deposit_codes.json"


def load_deposit_codes():
    if os.path.exists(DEPOSIT_CODE_FILE):
        with open(DEPOSIT_CODE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_deposit_codes():
    with open(DEPOSIT_CODE_FILE, "w") as f:
        json.dump(DEPOSIT_CODES, f, indent=2)


# Load deposit codes at startup
DEPOSIT_CODES = load_deposit_codes()
# ---------------- TOP-UP / AIRTIME CONFIG ----------------
NETWORKS = {
    "mtn": {
        "display": "MTN",
        "data_bundles": [
            ("100MB", 100.0),
            ("500MB", 250.0),
            ("1GB", 500.0),
            ("2GB", 900.0),
        ]
    },
    "glo": {
        "display": "GLO",
        "data_bundles": [
            ("150MB", 120.0),
            ("500MB", 300.0),
            ("1.5GB", 700.0),
        ]
    },
    "airtel": {
        "display": "AIRTEL",
        "data_bundles": [
            ("200MB", 150.0),
            ("750MB", 350.0),
            ("1.5GB", 650.0),
        ]
    },
    "9mobile": {
        "display": "9MOBILE",
        "data_bundles": [
            ("100MB", 110.0),
            ("500MB", 260.0),
            ("1GB", 480.0),
        ]
    }
}

# fee rules for external transfers: percentage or flat min (example)
EXTERNAL_TRANSFER_FEE_PERCENT = 0.01   # 1%
EXTERNAL_TRANSFER_FEE_MIN = 50.0      # min ₦50


def send_email(to_email, subject, html_body, plain_body=""):
    """Sends an email using the configured SMTP server."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(plain_body or html_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    try:
        # Note: The actual email sending logic is dependent on a valid
        # SENDER_EMAIL and APP_PASSWORD for the Gmail account.
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        print(f"✅ Email sent to: {to_email}")
    except Exception as e:
        print("❌ Failed to send email (Check SENDER_EMAIL/APP_PASSWORD):", e)
        print(
            f"SIMULATION: Would have sent email to {to_email} with subject: {subject}")


def now_iso():
    """Returns current UTC time in ISO format."""
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")


def format_transaction_email(sender_name, sender_balance, tx_type, dest_name, dest_bank, dest_acct, amount, tx_ref, tx_date):
    """Generates a generic HTML email body for transactions (Not used for alerts, which have specific templates)."""
    html = f"""
<html>
<body style="font-family: Arial, sans-serif; background-color:#f4f7fb; color:#333; margin:0; padding:20px;">
    <div style="max-width:600px; margin:auto; background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden;">
        
        <div style="background:#0047AB; color:#fff; text-align:center; padding:18px 0;">
            <h2 style="margin:0;">Romans Bank Ltd</h2>
            <p style="margin:0; font-size:13px;">Transaction Notification</p>
        </div>

        <div style="padding:25px;">
            <p>Dear <b>{sender_name}</b>,</p>
            
            <p style="font-size:16px;"> <b>{tx_type.capitalize()} Successful!</b></p>
            
            <p>Your transaction of <b>₦{amount:,.2f}</b> has been successfully processed.</p>
            <p>Your new available balance is <b>₦{sender_balance:,.2f}</b>.</p>

            <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:10px;">
                <tr><td style="padding:6px 0;"><b>Recipient Name:</b></td><td>{dest_name}</td></tr>
                <tr><td style="padding:6px 0;"><b>Recipient Bank:</b></td><td>{dest_bank}</td></tr>
                <tr><td style="padding:6px 0;"><b>Account Number:</b></td><td>{dest_acct}</td></tr>
                <tr><td style="padding:6px 0;"><b>Amount:</b></td><td>₦{amount:,.2f}</td></tr>
                <tr><td style="padding:6px 0;"><b>Transaction Reference:</b></td><td>{tx_ref}</td></tr>
                <tr><td style="padding:6px 0;"><b>Date:</b></td><td>{tx_date}</td></tr>
            </table>

            <div style="margin-top:25px; background:#f1f4f9; border-radius:8px; padding:15px;">
                <p style="font-size:13px; color:#555;">
                    This is an automated transaction confirmation message.  
                    Please verify this transaction in your Romans Bank dashboard for details.
                </p>
            </div>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                For enquiries, contact our customer support:<br>
                <b>Email:</b> customerservice@romansbank.com<br>
                <b>Phone:</b> 01-182-9829
            </p>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                Thank you for choosing <b>Romans Bank Ltd</b>.<br>
                <b>The Romans Bank Team</b>
            </p>
        </div>

        <div style="background:#0047AB; color:#fff; text-align:center; padding:10px; font-size:12px;">
            &copy; {datetime.utcnow().year} Romans Bank Ltd. All rights reserved.
        </div>
    </div>
</body>
</html>
"""
    return html


def generate_account_number():
    """Generates a unique 10-digit account number."""
    prefix = "23"
    used_path = "used_accounts.json"

    if os.path.exists(used_path):
        with open(used_path, "r") as f:
            used = json.load(f)
    else:
        used = []

    while True:
        acct_no = prefix + ''.join(random.choices("0123456789", k=8))
        if acct_no not in used:
            used.append(acct_no)
            with open(used_path, "w") as f:
                json.dump(used, f)
            return acct_no


def tx_reference(prefix="TXN"):
    """Generates a unique transaction reference."""
    timestamp = datetime.utcnow().strftime("%d%m%y%H%M%S")
    random_part = random.randint(1000, 9999)
    return f"{prefix}{timestamp}{random_part}"
# ---------------- PERSISTENCE ----------------


def load_data():
    """Loads all banking data from the JSON file safely."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Warning: Data file corrupted. Recreating new database.")
            return {"accounts": {}, "by_account_number": {}, "otps": {}}

    return {"account": {}, "by_account_number": {}, "otps": {}}
# --- AUTO-SAVE SYSTEM (keeps all data safe even after crash/restart) ---


def autosave_loop():
    """Runs forever in the background to automatically save user data and deposit codes."""
    while True:
        try:
            # Save accounts & transactions
            save_data(db)
            # Save deposit codes
            save_deposit_codes()
            print(f"[💾 Autosave] Data and deposit codes saved at {now_iso()}")
        except Exception as e:
            print(f"[⚠️ Autosave Error] {e}")
        time.sleep(60)  # wait 30 seconds before next save


def start_autosave_thread():
    """Start the background autosave thread."""
    t = threading.Thread(target=autosave_loop, daemon=True)
    t.start()
    print("✅ Autosave system started (every 30 seconds).")


def save_data(data):
    """Saves all banking data to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# Load data once at the start
db = load_data()

# ---------------- ACCOUNT HELPERS ----------------


def create_account(first_name, last_name, age, email, pin):
    """Creates a new user account and sends a welcome email."""
    email = email.lower().strip()
    if email in db["accounts"]:
        raise ValueError("Email already registered")

    acct_no = generate_account_number()
    bank = random.choice(BANK_LIST)
    full_name = f"{first_name} {last_name}"

    account = {
        "first_name": first_name,
        "last_name": last_name,
        "age": age,
        "name": full_name,
        "email": email,
        "pin": pin,
        "account_number": acct_no,
        "bank": bank,
        "balance": 0.0,
        "transactions": [],
        "beneficiaries": {}
    }

    db["accounts"][email] = account
    db["by_account_number"][acct_no] = email
    save_data(db)

    html = f"""
<html>
<body style="font-family: Arial, sans-serif; background-color:#f4f7fb; color:#333; margin:0; padding:20px;">
    <div style="max-width:600px; margin:auto; background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden;">
        
        <div style="background:#0047AB; color:#fff; text-align:center; padding:18px 0;">
            <h2 style="margin:0;">Romans Bank Ltd</h2>
            <p style="margin:0; font-size:13px;">Welcome to a Better Way to Bank</p>
        </div>

        <div style="padding:25px;">
            <p>Dear <b>{full_name}</b>,</p>
            
            <p style="font-size:16px;"> <b>Welcome to Romans Bank Ltd!</b></p>
            
            <p>Your account has been successfully created. Below are your account details:</p>

            <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:10px;">
                <tr><td style="padding:6px 0;"><b>Full Name:</b></td><td>{full_name}</td></tr>
                <tr><td style="padding:6px 0;"><b>Age:</b></td><td>{age}</td></tr>
                <tr><td style="padding:6px 0;"><b>Account Number:</b></td><td><b>{acct_no}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Bank:</b></td><td>{bank}</td></tr>
                <tr><td style="padding:6px 0;"><b>PIN:</b></td><td><b>{pin}</b></td></tr>
            </table>

            <div style="margin-top:25px; background:#f1f4f9; border-radius:8px; padding:15px;">
                <p style="font-size:13px; color:#555;">
                    Please <b>keep your PIN confidential</b> and never share it with anyone.  
                    You can now log in to your Romans Bank account to view balance, transfer funds, and manage beneficiaries.
                </p>
            </div>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                For assistance, contact our customer support:<br>
                <b>Email:</b> customerservice@romansbank.com<br>
                <b>Phone:</b> 01-182-9829
            </p>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                Thank you for choosing <b>Romans Bank Ltd</b>.<br>
                <b>The Romans Bank Team</b>
            </p>
        </div>

        <div style="background:#0047AB; color:#fff; text-align:center; padding:10px; font-size:12px;">
            &copy; {datetime.utcnow().year} Romans Bank Ltd. All rights reserved.
        </div>
    </div>
</body>
</html>
"""
    send_email(email, "Welcome to Romans Bank Ltd - Your Account Details", html)
    return account


def find_by_email(email):
    """Retrieves an account by email address."""
    return db["accounts"].get(email.lower().strip())


def find_by_account_number(acct_no):
    """Retrieves an account by account number."""
    email = db["by_account_number"].get(acct_no)
    if email:
        return db["accounts"].get(email)
    return None

# ---------------- TRANSACTIONS ----------------


def record_tx(account, tx_type, amount, metadata=None):
    """Records a transaction into the account's transaction history."""
    tx = {
        "ref": tx_reference(),
        "type": tx_type,
        "amount": round(float(amount), 2),
        "timestamp": now_iso(),
        "balance_after": round(account["balance"], 2),
        "metadata": metadata or {}
    }
    account["transactions"].append(tx)
    save_data(db)
    return tx


def internal_transfer(sender_acc, receiver_acct_no, amount, narration=""):
    """Handles transfers between two Romans Bank accounts."""
    amount = float(amount)
    receiver = find_by_account_number(receiver_acct_no)

    if receiver is None:
        raise ValueError("Destination account not found")
    if sender_acc["account_number"] == receiver_acct_no:
        raise ValueError("Cannot transfer to same account")
    if amount > sender_acc["balance"]:
        raise ValueError("Insufficient funds")

    # Update balances
    sender_acc["balance"] -= amount
    receiver["balance"] += amount

    # Record transactions
    tx_out = record_tx(sender_acc, "transfer_out_internal", amount, {
        "to": receiver_acct_no,
        "narration": narration
    })
    tx_in = record_tx(receiver, "transfer_in_internal", amount, {
        "from": sender_acc["account_number"],
        "narration": narration
    })

    # --- HTML Email Templates ---
    html_sender = f"""
<html>
<body style="font-family: Arial, sans-serif; background-color:#f4f7fb; color:#333; margin:0; padding:20px;">
    <div style="max-width:600px; margin:auto; background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden;">
        
        <div style="background:#C62828; color:#fff; text-align:center; padding:18px 0;">
            <h2 style="margin:0;">Debit Alert</h2>
            <p style="margin:0; font-size:13px;">Romans Bank Ltd</p>
        </div>

        <div style="padding:25px;">
            <p>Dear <b>{sender_acc['name']}</b>,</p>
            
            <p style="font-size:16px; color:#C62828;"><b>₦{amount:,.2f}</b> has been debited from your account.</p>

            <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:15px;">
                <tr><td style="padding:6px 0;"><b>Recipient Name:</td><td><b>{receiver['name']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Bank:</td><td><b>{receiver['bank']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Account Number:</td><td><b>{receiver['account_number']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Reference:</td><td><b>{tx_out['ref']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Date:</td><td><b>{tx_out['timestamp']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Narration:</td><td><b>{narration if narration else "N/A"}</b></td></tr>
            </table>

            <p style="margin-top:20px; font-size:14px;">
                <b>New Balance:</b>  ₦{sender_acc['balance']:,.2f}
            </p>

            <div style="margin-top:25px; background:#fff8e1; border-left:4px solid #FFA000; padding:10px 15px; border-radius:6px;">
                <p style="font-size:13px; color:#555; margin:0;">
                    ⚠️ If you did not authorize this transaction, please contact our support team immediately.
                </p>
            </div>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                Thank you for banking with <b>Romans Bank Ltd</b>.<br>
                <b>Customer Support:</b> 01-182-9829 | support@romansbank.com
            </p>
        </div>

        <div style="background:#C62828; color:#fff; text-align:center; padding:10px; font-size:12px;">
            &copy; {datetime.utcnow().year} Romans Bank Ltd. All rights reserved.
        </div>
    </div>
</body>
</html>
"""

    html_receiver = f"""
<html>
<body style="font-family: Arial, sans-serif; background-color:#f4f7fb; color:#333; margin:0; padding:20px;">
    <div style="max-width:600px; margin:auto; background:#fff; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,0.08); overflow:hidden;">
        
        <div style="background:#2E7D32; color:#fff; text-align:center; padding:18px 0;">
            <h2 style="margin:0;">Credit Alert</h2>
            <p style="margin:0; font-size:13px;">Romans Bank Ltd</p>
        </div>

        <div style="padding:25px;">
            <p>Dear <b>{receiver['name']}</b>,</p>
            
            <p style="font-size:16px; color:#2E7D32;"><b>₦{amount:,.2f}</b> has been credited to your account.</p>

            <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:15px;">
                <tr><td style="padding:6px 0;"><b>Sender Name:</td><td><b>{sender_acc['name']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Bank:</b></td><td>{sender_acc['bank']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Account Number:</td><td><b>{sender_acc['account_number']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Reference:</td><td><b>{tx_in['ref']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Date:</td><td><b>{tx_in['timestamp']}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Narration:</td><td><b>{narration if narration else "N/A"}</b></td></tr>
            </table>

            <p style="margin-top:20px; font-size:14px;">
                <b>New Balance:</b>  ₦{receiver['balance']:,.2f}
            </p>

            <div style="margin-top:25px; background:#e8f5e9; border-left:4px solid #43A047; padding:10px 15px; border-radius:6px;">
                <p style="font-size:13px; color:#2E7D32; margin:0;">
                    💡 You can now use your new balance to make transfers, payments, or withdrawals.
                </p>
            </div>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                Thank you for banking with <b>Romans Bank Ltd</b>.<br>
                <b>Customer Support:</b> 01-182-9829 | support@romansbank.com
            </p>
        </div>

        <div style="background:#2E7D32; color:#fff; text-align:center; padding:10px; font-size:12px;">
            &copy; {datetime.utcnow().year} Romans Bank Ltd. All rights reserved.
        </div>
    </div>
</body>
</html>
"""

    # --- Send the emails ---
    send_email(sender_acc["email"],
               f"Debit Alert - {tx_out['ref']}", html_sender)
    send_email(receiver["email"],
               f"Credit Alert - {tx_in['ref']}", html_receiver)

    return tx_out, tx_in

# ---------------- TOP-UP / AIRTIME & DATA ----------------


def format_tel_number(n):
    """Normalize Nigerian phone numbers to +234 format."""
    n = n.strip()
    if n.startswith("+234"):
        return n
    if n.startswith("0"):
        return "+234" + n[1:]
    if len(n) == 10 and n.isdigit():
        return "+234" + n
    return n


def find_by_phone(phone):
    """Find user by phone number in db (if you store it)."""
    # Simplified: Romans Bank doesn't store phone numbers by default, so this is just for simulation purposes.
    return None


def send_topup_email(purchaser, recipient_phone, recipient_name, network_display, product_name, amount, tx_ref):
    """Send professional top-up email to purchaser and optionally to recipient."""

    # Set primary brand color for Romans Bank
    PRIMARY_COLOR = "#0047AB"
    ACCENT_COLOR = "#4CAF50"  # Green for successful purchase

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Top-up Receipt - Romans Bank</title>
        <style>
            .receipt-table td {{padding: 8px 0; border-bottom: 1px solid #eee;}}
            .receipt-table .label {{width: 40%; color: #555;}}
            .receipt-table .value {{text-align: right; font-weight: bold; color: #222;}}
        </style>
    </head>
    <body style="font-family: Arial, sans-serif; background-color:#F4F7FB; margin:0; padding:0;">
      <div style="max-width:600px; margin:20px auto; background:#fff; border:1px solid #e0e0e0; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        
        <div style="background:{PRIMARY_COLOR}; color:#fff; padding:20px 25px; text-align:left;">
          <h1 style="margin:0; font-size:20px; font-weight:bold;">Romans Bank Ltd</h1>
          <p style="margin:5px 0 0 0; font-size:14px; opacity:0.8;">Electronic Transaction Receipt</p>
        </div>

        <div style="padding:25px 25px 15px 25px;">
            <p style="color:#555; margin-top:0;">Dear <b>{purchaser['name']}</b>,</p>
            
            <div style="background:#E8F5E9; border-left:4px solid {ACCENT_COLOR}; padding:15px; margin-bottom:20px;">
                <p style="font-size:16px; color:#388E3C; font-weight:bold; margin:0;">
                    PURCHASE SUCCESSFUL
                </p>
            </div>
            
            <h3 style="font-size:24px; color:{ACCENT_COLOR}; margin:0 0 10px 0;">
                ₦{amount:,.2f}
            </h3>
            <p style="font-size:16px; color:#333; margin:0 0 20px 0;">
                Your request to purchase **{product_name}** has been successfully completed.
            </p>

            <table class="receipt-table" style="width:100%; border-collapse:collapse; font-size:14px; color:#333;">
                <tr>
                    <td class="label"><b>Transaction Date:</b></td>
                    <td class="value">{now_iso()}</td>
                </tr>
                <tr>
                    <td class="label"><b>Service Type:</b></td>
                    <td class="value">{product_name}</td>
                </tr>
                <tr>
                    <td class="label"><b>Network Provider:</b></td>
                    <td class="value">{network_display}</td>
                </tr>
                <tr>
                    <td class="label"><b>Recipient Phone:</b></td>
                    <td class="value">{recipient_phone}</td>
                </tr>
                <tr>
                    <td class="label"><b>Recipient Name:</b></td>
                    <td class="value">{recipient_name or purchaser['name']}</td>
                </tr>
                <tr>
                    <td class="label"><b>Amount Paid:</b></td>
                    <td class="value">₦{amount:,.2f}</td>
                </tr>
                <tr>
                    <td class="label"><b>Transaction Ref:</b></td>
                    <td class="value">{tx_ref}</td>
                </tr>
                <tr>
                    <td class="label" style="border-bottom:none;"><b>Debited Account:</b></td>
                    <td class="value" style="border-bottom:none;">{purchaser['account_number']}</td>
                </tr>
            </table>
            
            <p style="margin-top:25px; font-size:13px; color:#D32F2F; font-weight:bold;">
                SECURITY ALERT: Do not reply to this email. If you did not authorize this purchase, please contact us immediately.
            </p>
        </div>

        <div style="background:{PRIMARY_COLOR}; color:#fff; text-align:center; padding:15px; font-size:11px; border-top:5px solid {ACCENT_COLOR};">
          <p style="margin:0;">This is an automated receipt.</p>
          <p style="margin:5px 0 0 0;">&copy; {datetime.utcnow().year} Romans Bank Ltd. All rights reserved.</p>
        </div>

      </div>
    </body>
    </html>
    """
    send_email(purchaser['email'], f"Top-up Receipt - {tx_ref}", html)
    return html


# --- CONSOLE I/O FUNCTIONS REMOVED/REPLACED ---

# ---------------- EXTERNAL TRANSFER (to other banks) ----------------

def external_transfer(sender_acc, dest_bank, dest_acct_no, dest_name, amount, dest_email=None, narration=""):
    """Simulate external transfer with transaction fee and send custom bank-branded emails."""
    amount = float(amount)
    fee = max(round(amount * EXTERNAL_TRANSFER_FEE_PERCENT, 2),
              EXTERNAL_TRANSFER_FEE_MIN)
    total = amount + fee

    if total > sender_acc["balance"]:
        raise ValueError(f"Insufficient funds (including ₦{fee:,.2f} fee).")

    # Deduct funds
    sender_acc["balance"] -= total
    tx = record_tx(sender_acc, "transfer_out_external", amount, {
        "to_bank": dest_bank,
        "to_account": dest_acct_no,
        "to_name": dest_name,
        "fee": fee,
        "narration": narration
    })
    tx_ref = tx["ref"]
    tx_date = now_iso()

    # --- Email for sender ---
    html_sender = f"""
<html>
<body style="font-family:Arial, sans-serif; background-color:#f9f9f9; margin:0; padding:0;">
<div style="max-width:600px; margin:40px auto; background-color:#ffffff; border-radius:10px; box-shadow:0 2px 8px rgba(0,0,0,0.05); overflow:hidden;">
<div style="background-color:#002b5c; color:#fff; padding:18px 25px; border-bottom:3px solid #f2c94c;">
<h2 style="margin:0; font-size:20px;">Romans Bank Ltd</h2>
<p style="margin:5px 0 0 0; font-size:13px;">Transaction Notification</p>
</div>
<div style="padding:25px;">
<p>Dear <b>{sender_acc['name']}</b>,</p>
<p>Your transfer of <b>₦{amount:,.2f}</b> to <b>{dest_name}</b> (<b>{dest_acct_no}</b> - {dest_bank}) has been <span style="color:green;"><b>successfully completed</b></span>.</p>
<table style="width:100%; border-collapse:collapse; margin:20px 0; font-size:14px;">
<tr><td style="padding:6px 0; color:#555;">Transaction Reference:</td><td style="padding:6px 0; text-align:right;"><b>{tx_ref}</b></td></tr>
<tr><td style="padding:6px 0; color:#555;">Date:</td><td style="padding:6px 0; text-align:right;">{tx_date}</td></tr>
<tr><td style="padding:6px 0; color:#555;">Transfer Amount:</td><td style="padding:6px 0; text-align:right;">₦{amount:,.2f}</td></tr>
<tr><td style="padding:6px 0; color:#555;">Transfer Fee:</td><td style="padding:6px 0; text-align:right;">₦{fee:,.2f}</td></tr>
<tr><td style="padding:6px 0; color:#555;">Total Debited:</td><td style="padding:6px 0; text-align:right; color:#c0392b;"><b>₦{total:,.2f}</b></td></tr>
<tr><td style="padding:6px 0; color:#555;">Available Balance:</td><td style="padding:6px 0; text-align:right; color:#2c7a7b;"><b>₦{sender_acc['balance']:,.2f}</b></td></tr>
</table>
<p style="font-size:13px; line-height:1.6; color:#555;">Kindly note that this debit alert confirms your transfer. If you did not authorize this transaction, please contact our support team immediately.</p>
<div style="margin-top:20px; background:#f4f4f4; padding:12px; border-radius:6px; font-size:12px; color:#666;">
<p style="margin:0;">Romans Bank Ltd — <b>support@romansbank.com</b> | 01-182-9829</p>
</div>
</div>
</div>
<p style="text-align:center; font-size:11px; color:#999; margin-top:20px;">© {tx_date[:4]} Romans Bank Ltd. All rights reserved.</p>
</body>
</html>
"""

    # --- Send email to sender ---
    try:
        send_email(sender_acc["email"], f"Debit Alert - {tx_ref}", html_sender)
        print(f"✔ Sender email sent to {sender_acc['email']}")
    except Exception as e:
        print("⚠️ Failed to send sender email:", e)

    # --- Email for receiver (Bank-Specific Header) ---
    if dest_email:
        # Dynamic color schemes per bank (add more as needed)
        bank_styles = {
            "Access Bank": ("#002663", "#E0E6F1"),
            "GTBank": ("#FF5B00", "#FFF3E0"),
            "UBA": ("#CE0E2D", "#FCE4EC"),
            "First Bank": ("#00205B", "#E3F2FD"),
            "Zenith Bank": ("#000000", "#ECEFF1"),
            "FCMB": ("#4B0082", "#EDE7F6"),
            "Kuda Bank": ("#40196D", "#F3E5F5"),
            "Opay": ("#00A884", "#E0F2F1"),
            "Moniepoint": ("#002878", "#E8EAF6"),
            "PalmPay": ("#8E24AA", "#F3E5F5"),
        }

        header_color, bg_color = bank_styles.get(
            dest_bank, ("#0047AB", "#F4F7FB"))

        html_receiver = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:{bg_color}; margin:0; padding:0;">
          <div style="max-width:600px; margin:40px auto; background:#fff; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            <div style="background:{header_color}; color:#fff; padding:18px 25px;">
              <h2 style="margin:0;">{dest_bank} Plc</h2>
              <p style="margin:5px 0;">Credit Alert Notification</p>
            </div>
            <div style="padding:25px;">
              <p>Dear <b>{dest_name}</b>,</p>
              <p>Your account has been credited with <b>₦{amount:,.2f}</b>.</p>
              <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tr><td><b>Sender Name:</b></td><td>{sender_acc['name']}</td></tr>
                <tr><td><b>Sender Bank:</b></td><td>Romans Bank Ltd</td></tr>
                <tr><td><b>Sender Account:</b></td><td>{sender_acc['account_number']}</td></tr>
                <tr><td><b>Amount:</b></td><td>₦{amount:,.2f}</td></tr>
                <tr><td><b>Reference:</b></td><td>{tx_ref}</td></tr>
                <tr><td><b>Date:</b></td><td>{tx_date}</td></tr>
              </table>
              <p style="margin-top:15px; color:#555;">Thank you for banking with <b>{dest_bank}</b>.</p>
            </div>
            <div style="background:{header_color}; color:#fff; text-align:center; padding:10px; font-size:12px;">
              © {datetime.utcnow().year} {dest_bank}. All rights reserved.
            </div>
          </div>
        </body>
        </html>
        """

        # Email subject & sender branding
        subject = f"Credit Alert - ₦{amount:,.2f}"
        send_email(dest_email, subject, html_receiver)

    return tx_ref, fee


def simulate_otp(sender_acc, action="transfer", amount=0):
    """Generate a 6-digit OTP, store it, and send a professional email notification."""
    otp = random.randint(100000, 999999)
    otp_ref = tx_reference("OTP")

    # Record OTP details (including expiry time)
    created_at = datetime.utcnow()
    expires_at = created_at + timedelta(minutes=5)

    db["otps"][otp_ref] = {
        "otp": str(otp),
        "email": sender_acc["email"],
        "action": action,
        "amount": amount,
        "used": False,
        "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "expires_at": expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    save_data(db)

    # --- Professional HTML Email ---
    PRIMARY_COLOR = "#0047AB"
    SECURITY_RED = "#D32F2F"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>OTP - One-Time Password</title>
        <style>
            .detail-table td {{padding: 8px 0; border-bottom: 1px dashed #e0e0e0;}}
            .detail-table .label {{width: 40%; color: #555;}}
            .detail-table .value {{text-align: right; font-weight: bold; color: #222;}}
        </style>
    </head>
    <body style="font-family: Arial, sans-serif; background-color:#F4F7FB; margin:0; padding:0;">
        <div style="max-width:600px; margin:20px auto; background-color:#fff; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
            
            <div style="background:{PRIMARY_COLOR}; color:#fff; padding:20px 25px; text-align:left;">
                <h1 style="margin:0; font-size:20px; font-weight:bold;">Romans Bank Ltd</h1>
                <p style="margin:5px 0 0 0; font-size:14px; opacity:0.8;">One-Time Password Service</p>
            </div>

            <div style="padding:25px;">
                <p style="color:#333; margin-top:0;">Dear <b>{sender_acc['name']}</b>,</p>
                <p style="font-size:16px; color:#333;">
                    Please use the following code to authorize your **{action.title()}** transaction.
                </p>

                <div style="text-align:center; margin:30px 0; padding:20px; background:#e0f7fa; border:1px solid #00BCD4; border-radius:8px;">
                    <p style="font-size:14px; color:#0047AB; margin:0 0 10px 0;">Your Secure One-Time Password is:</p>
                    <h1 style="font-size:38px; letter-spacing:8px; color:#0047AB; margin:0; font-weight:bold;">{otp}</h1>
                    <p style="font-size:14px; color:{SECURITY_RED}; margin-top:10px;">
                        ⚠️ **EXPIRES IN 5 MINUTES**
                    </p>
                </div>
                
                <h3 style="margin:25px 0 10px 0; font-size:16px; border-bottom:1px solid #eee; padding-bottom:5px;">Transaction Summary</h3>
                <table class="detail-table" style="width:100%; border-collapse:collapse; font-size:14px;">
                    <tr>
                        <td class="label"><b>Transaction Type:</b></td>
                        <td class="value">{action.title()}</td>
                    </tr>
                    <tr>
                        <td class="label"><b>Amount (Approx.):</b></td>
                        <td class="value">₦{amount:,.2f}</td>
                    </tr>
                    <tr>
                        <td class="label"><b>OTP Reference:</b></td>
                        <td class="value">{otp_ref}</td>
                    </tr>
                    <tr>
                        <td class="label" style="border-bottom:none;"><b>Time Generated:</b></td>
                        <td class="value" style="border-bottom:none;">{created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}</td>
                    </tr>
                </table>

                <div style="margin-top:25px; background:#fff3e0; border-left:4px solid #f90; padding:15px; border-radius:4px;">
                    <p style="font-size:13px; color:#c0392b; font-weight:bold; margin:0;">
                        IMPORTANT SECURITY NOTICE: Never share this OTP with anyone, including bank staff. We will *never* call or email you to ask for this code. If you did not request this OTP, contact us immediately.
                    </p>
                </div>
            </div>

            <div style="background:{PRIMARY_COLOR}; color:#fff; text-align:center; padding:15px; font-size:11px;">
                <p style="margin:0;">This is an automated security message. Do not reply.</p>
                <p style="margin:5px 0 0 0;">&copy; {datetime.utcnow().year} Romans Bank Ltd. Member of the NDIC.</p>
            </div>
        </div>
    </body>
    </html>
    """

    send_email(sender_acc["email"],
               f"Your OTP for {action.title()} - {otp_ref}", html)
    print(
        f"✅ OTP sent to {sender_acc['email']} (expires in 5 minutes). Ref: {otp_ref}")
    return otp_ref


def confirm_otp(otp_ref, otp_code):
    """Validates an OTP against its reference and expiry."""
    rec = db["otps"].get(otp_ref)
    if not rec:
        raise ValueError("OTP reference invalid")
    if rec["used"]:
        raise ValueError("OTP already used")

    # Check for expiry
    expires_at = datetime.strptime(rec["expires_at"], "%Y-%m-%d %H:%M:%S UTC")
    if datetime.utcnow() > expires_at:
        raise ValueError("OTP expired")

    if rec["otp"] != str(otp_code):
        raise ValueError("Incorrect OTP")

    # OTP is valid
    rec["used"] = True
    save_data(db)
    return True


# ---------------- DEPOSIT CODES (PERSISTENT) ----------------
DEPOSIT_CODE_FILE = "deposit_codes.json"


def load_deposit_codes():
    """Loads all deposit codes from JSON file."""
    if os.path.exists(DEPOSIT_CODE_FILE):
        with open(DEPOSIT_CODE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_deposit_codes():
    """Saves all deposit codes to JSON file."""
    with open(DEPOSIT_CODE_FILE, "w", encoding="utf-8") as f:
        json.dump(DEPOSIT_CODES, f, indent=2)


# Load deposit codes when bot starts
DEPOSIT_CODES = load_deposit_codes()


def admin_generate_code(amount):
    """Generates a unique, one-time use deposit code."""
    code = f"DEP{random.randint(1000000,9999999)}"
    DEPOSIT_CODES[code] = {
        "amount": amount,
        "used": False,
        "redeemed_by": None,
        "redeemed_at": None
    }
    save_deposit_codes()  # ✅ Save immediately so it doesn’t vanish
    return code


def user_deposit_with_code(account, code):
    """Allows a user to redeem an admin-generated deposit code."""
    if code not in DEPOSIT_CODES:
        raise ValueError("Invalid deposit code.")

    deposit = DEPOSIT_CODES[code]
    if deposit["used"]:
        raise ValueError(
            f"Deposit code {code} has already been redeemed by {deposit['redeemed_by']} on {deposit['redeemed_at']}.")

    amount = deposit["amount"]

    # Update account balance
    account["balance"] += amount

    # Mark code as used
    deposit["used"] = True
    deposit["redeemed_by"] = account["name"]
    deposit["redeemed_at"] = now_iso()
    save_deposit_codes()  # ✅ Save usage update

    # Record transaction
    tx = record_tx(account, "deposit_code_in", amount, {
        "code": code,
        "admin_note": "Deposit via admin-generated code"
    })

    # Notify by email
    html_email = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color:#e0f7fa; padding:20px; color:#333;">
        <div style="max-width:600px; margin:auto; background-color:#fff; border-radius:10px; padding:25px; box-shadow:0 4px 15px rgba(0,0,0,0.1);">
            <h2 style="text-align:center; color:#006064;">Romans Bank - Deposit Confirmation</h2>
            <hr style="border:none; border-top:2px solid #006064;">
            <p>Dear <b>{account['name']}</b>,</p>
            
            <p style="font-size:16px; color:#2e7d32;">
                🎉 <b>Success! ₦{amount:,.2f}</b> has been credited to your account.
            </p>

            <table style="width:100%; border-collapse:collapse; font-size:14px; margin-top:15px;">
                <tr><td style="padding:6px 0;"><b>Transaction Type:</b></td><td>Deposit (via Code)</td></tr>
                <tr><td style="padding:6px 0;"><b>Deposit Code:</b></td><td><b>{code}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Amount Credited:</b></td><td><b>₦{amount:,.2f}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>New Balance:</b></td><td><b>₦{account['balance']:,.2f}</b></td></tr>
                <tr><td style="padding:6px 0;"><b>Transaction Ref:</b></td><td>{tx['ref']}</td></tr>
                <tr><td style="padding:6px 0;"><b>Date:</b></td><td>{tx['timestamp']}</td></tr>
            </table>

            <p style="margin-top:25px; font-size:13px; color:#555;">
                Thank you for using Romans Bank. Your financial security is our priority.
            </p>

            <p style="text-align:center; margin-top:30px;">
                <b>Romans Bank Team</b>
            </p>
        </div>
    </body>
    </html>
    """
    send_email(account["email"],
               f"Deposit Successful - ₦{amount:,.2f}", html_email)
    return amount

# ---------------- TELEGRAM HANDLERS (New I/O) ----------------

# --- Global Handlers ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the initial main menu using ReplyKeyboardMarkup."""
    
    # Use ReplyKeyboardMarkup for persistent buttons at the bottom
    keyboard = [
        ["Login to Account", "Create New Account (Sign Up)"],
        ["Admin Login"],
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, one_time_keyboard=False, resize_keyboard=True)

    text = "Welcome to Romans Bank Ltd – The Future of Banking.\n\nPlease choose an option from the keyboard below:"

    # CRITICAL FIX: Only check for update.message, which is guaranteed when using CommandHandler.
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    context.user_data.clear() # Clear state when restarting
    return START


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ends the conversation and removes the keyboard."""
    if update.callback_query:
        await update.callback_query.answer()
        text = "Thank you for using Romans Bank. Goodbye! /start"
        await update.callback_query.edit_message_text(text, reply_markup=ReplyKeyboardRemove())
    else:
        text = "Thank you for using Romans Bank. Goodbye! /start"
        await update.message.reply_text(text, reply_markup=ReplyKeyboardRemove())

    context.user_data.clear()
    return ConversationHandler.END

# --- Registration Handlers (No change, as they rely on direct text input) ---


async def register_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Remove the Reply Keyboard before asking for input
    await update.message.reply_text("--- NEW ACCOUNT REGISTRATION ---\nEnter your **First Name**:", reply_markup=ReplyKeyboardRemove())
    return REGISTER_FIRST_NAME


async def register_first_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['reg_first_name'] = update.message.text.strip().title()
    await update.message.reply_text("Enter your **Last Name**:")
    return REGISTER_LAST_NAME


async def register_last_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['reg_last_name'] = update.message.text.strip().title()
    await update.message.reply_text("Enter your **Age** (number):")
    return REGISTER_AGE


async def register_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        age = int(update.message.text.strip())
        if age < 18:
            await update.message.reply_text("You must be 18 or older to register. Please enter a valid age:")
            return REGISTER_AGE
        context.user_data['reg_age'] = age
        await update.message.reply_text("Enter your **Email** address:")
        return REGISTER_EMAIL
    except ValueError:
        await update.message.reply_text("Invalid age format. Please enter a number:")
        return REGISTER_AGE


async def register_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip().lower()
    if not email or "@" not in email:
        await update.message.reply_text("❌ Invalid email format. Please try again:")
        return REGISTER_EMAIL
    if find_by_email(email):
        await update.message.reply_text("❌ Email already registered. Please try another or /start to log in.")
        return REGISTER_EMAIL
    context.user_data['reg_email'] = email
    await update.message.reply_text("Choose a **4-digit PIN** (sent as plain text, enter carefully!):")
    return REGISTER_PIN


async def register_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pin = update.message.text.strip()
    if not pin.isdigit() or len(pin) != 4:
        await update.message.reply_text("❌ PIN must be 4 digits. Please try again:")
        return REGISTER_PIN

    try:
        create_account(
            context.user_data['reg_first_name'],
            context.user_data['reg_last_name'],
            context.user_data['reg_age'],
            context.user_data['reg_email'],
            pin
        )
        # Send a final message and use /start to re-display the main menu.
        await update.message.reply_text(
            "✅ Account created successfully! Check your email for details.\n\nNow, please /start to return to the main menu.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END  # End conversation to require /start
    except Exception as e:
        await update.message.reply_text(f"❌ Error during registration: {e}. Please /start again.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


# --- Login Handlers (Modified for Reply Keyboard) ---

async def login_route(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This handler now gets the button text from a MessageHandler
    button_text = update.message.text.strip()

    # Remove the Reply Keyboard before asking for input
    await update.message.reply_text("Starting login...", reply_markup=ReplyKeyboardRemove())

    if button_text == "Admin Login":
        context.user_data['is_admin'] = True
        await update.message.reply_text("ADMIN LOGIN: Enter **Admin PIN**:")
        return ADMIN_PIN_INPUT
    elif button_text == "Login to Account":
        context.user_data['is_admin'] = False
        await update.message.reply_text("USER LOGIN: Enter your **Email** address:")
        return LOGIN_EMAIL
    elif button_text == "Create New Account (Sign Up)":
        return await register_start(update, context)
    else:
        # Fallback for unexpected text
        await update.message.reply_text("❌ Invalid option. Please use the buttons or /start.")
        return START  # Or START, depending on preference


async def login_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email = update.message.text.strip()
    context.user_data['temp_email'] = email

    # Check if email exists to avoid error on next step
    if not find_by_email(email):
        await update.message.reply_text("❌ Invalid email. Please enter a valid email or /start.")
        return LOGIN_EMAIL  # Stay in this state

    await update.message.reply_text("Email received. Enter your **4-digit PIN**:")
    return LOGIN_PIN


async def login_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pin = update.message.text.strip()
    email = context.user_data.get('temp_email')

    # --- Original login_user logic ---
    account = find_by_email(email)

    if account and account["pin"] == pin:
        context.user_data['account'] = account
        # user_menu_display now handles the ReplyKeyboardMarkup
        return await user_menu_display(update, context, f"✅ Welcome back, {account['first_name']}.")
    else:
        # Remove keyboard on login failure
        await update.message.reply_text("❌ Invalid email or PIN. Please /start and try again.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


async def admin_pin_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pin = update.message.text.strip()

    if pin == ADMIN_PIN:
        # Mock admin acc, as per original code
        admin_acc = {"name": "Admin User", "email": ADMIN_EMAIL}
        context.user_data['admin_acc'] = admin_acc
        # admin_menu_display now handles the ReplyKeyboardMarkup
        return await admin_menu_display(update, context, "✅ Admin login successful.")
    else:
        # Remove keyboard on login failure
        await update.message.reply_text("❌ Invalid Admin PIN. Please /start to retry.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

# --- Menus (Modified for Reply Keyboard) ---


async def user_menu_display(update: Update, context: ContextTypes.DEFAULT_TYPE, message=""):
    """Displays the user main menu using ReplyKeyboardMarkup."""
    account = context.user_data['account']

    text = f"💰 **Welcome, {account['first_name']}**\n\n"
    text += f"Acct No: `{account['account_number']}`\n"
    text += f"Current Balance: **₦{account['balance']:,.2f}**\n\n"
    text += "What would you like to do?"

    # Use ReplyKeyboardMarkup
    keyboard = [
        ["Transfer Funds", "Buy Airtime / Data"],
        ["Deposit via Code", "View Transaction History"],
        ["Logout"],
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, one_time_keyboard=False, resize_keyboard=True)

    if update.callback_query:
        # If coming from a callback query (e.g. back button in a nested inline menu)
        await update.callback_query.answer()
        # Cannot use ReplyKeyboardMarkup with edit_message_text, so send a new message and remove the old inline menu
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=f"{message}\n\n{text}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # If coming from a message (e.g. successful login or another menu item)
        await update.message.reply_text(f"{message}\n\n{text}", reply_markup=reply_markup, parse_mode='Markdown')

    return USER_MENU


async def admin_menu_display(update: Update, context: ContextTypes.DEFAULT_TYPE, message=""):
    """Displays the admin menu using ReplyKeyboardMarkup."""
    admin_acc = context.user_data['admin_acc']

    text = f"👑 **ADMIN PORTAL**\nWelcome, {admin_acc['name']}\n\n"
    text += "Select a management task:"

    # Use ReplyKeyboardMarkup
    keyboard = [
        ["Generate Deposit Code", "View All User Accounts"],
        ["View All Deposit Codes", "Logout"],
    ]
    reply_markup = ReplyKeyboardMarkup(
        keyboard, one_time_keyboard=False, resize_keyboard=True)

    if update.callback_query:
        # Same logic as user_menu_display for handling callback_query from an inline menu
        await update.callback_query.answer()
        await update.callback_query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=f"{message}\n\n{text}",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"{message}\n\n{text}", reply_markup=reply_markup, parse_mode='Markdown')

    return USER_MENU  # Reusing USER_MENU state for admin actions

# --- User Menu Handlers (Modified to use MessageHandler(filters.TEXT) with Reply Keyboard options) ---

# ✅ FIXED user_menu_route FUNCTION


async def user_menu_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles all user and admin menu options (buttons and text replies).
    Automatically detects if the user is an admin or a regular user.
    """
    text = update.message.text.strip()

    # Always remove the reply keyboard before next step
    await update.message.reply_text(
        f"Processing: {text}...", reply_markup=ReplyKeyboardRemove()
    )

    # ✅ 1. Regular User Menu Actions
    if text == "Transfer Funds":
        return await transfer_menu_display(update, context)

    elif text == "Buy Airtime / Data":
        return await topup_menu_display(update, context)

    elif text == "Deposit via Code":
        await update.message.reply_text("Please enter the **Deposit Code**:")
        return DEPOSIT_CODE_INPUT

    elif text == "View Transaction History":
        return await user_tx_history(update, context)

    # ✅ 2. Logout (works for both User & Admin)
    elif text.lower() == "logout":
        # Safely get user name
        name = (
            context.user_data.get("account", {}).get("first_name")
            or context.user_data.get("admin", {}).get("first_name")
            or "User"
        )

        await update.message.reply_text(
            f"Goodbye, {name} 👋 \nThank you for choosing {SENDER_NAME}.\n/start to fresh begin.",
            reply_markup=ReplyKeyboardRemove()
        )

        # Clear session data and end conversation
        context.user_data.clear()
        return ConversationHandler.END

    # ✅ 3. Admin Menu Options
    elif text == "Generate Deposit Code":
        await update.message.reply_text(
            "ADMIN: Enter **amount** for the new deposit code (e.g. 5000):"
        )
        return ADMIN_GEN_CODE_INPUT

    elif text == "View All User Accounts":
        return await admin_view_accounts(update, context)

    elif text == "View All Deposit Codes":
        return await admin_view_codes(update, context)

    # ✅ 4. Fallback for invalid choices
    else:
        await update.message.reply_text(
            "❌ Invalid choice. Please use the menu buttons or /start.",
            reply_markup=ReplyKeyboardRemove()
        )
        return USER_MENU
# --- Admin Handlers (Modified to use ReplyKeyboardMarkup for back button) ---


async def admin_gen_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError

        code = admin_generate_code(amount)

        message = f"✅ Deposit code generated successfully!\n\n**Code:** `{code}`\n**Amount:** ₦{amount:,.2f}"
        return await admin_menu_display(update, context, message)
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a positive number:")
        return ADMIN_GEN_CODE_INPUT


async def admin_view_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    output = "--- ALL USER ACCOUNTS ---\n"
    if not db["accounts"]:
        output += "No user accounts registered."
    else:
        for acc in db["accounts"].values():
            output += f"**Name:** {acc['name']}\n"
            output += f"**Account No:** `{acc['account_number']}`\n"
            output += f"**Email:** {acc['email']}\n"
            output += f"**Balance:** ₦{acc['balance']:,.2f}\n"
            output += f"**Transactions:** {len(acc['transactions'])}\n"
            output += "-" * 20 + "\n"

    # Send message and then return to main menu, which will display the ReplyKeyboardMarkup
    await update.message.reply_text(output, parse_mode='Markdown')
    # Re-display admin menu with ReplyKeyboardMarkup
    return await admin_menu_display(update, context)


async def admin_view_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    output = "--- ALL DEPOSIT CODES STATUS ---\n"
    if not DEPOSIT_CODES:
        output += "No deposit codes generated."
    else:
        for code, data in DEPOSIT_CODES.items():
            status = "✅ USED" if data['used'] else "⏳ ACTIVE"
            redeemed = f"By {data['redeemed_by']} on {data['redeemed_at']}" if data['used'] else "N/A"
            output += f"**Code:** `{code}` | {status}\n"
            output += f"**Amount:** ₦{data['amount']:,.2f}\n"
            output += f"**Redeemed:** {redeemed}\n"
            output += "-" * 20 + "\n"

    # Send message and then return to main menu, which will display the ReplyKeyboardMarkup
    await update.message.reply_text(output, parse_mode='Markdown')
    # Re-display admin menu with ReplyKeyboardMarkup
    return await admin_menu_display(update, context)


# --- Deposit Code Handlers ---

async def deposit_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip()
    account = context.user_data['account']

    try:
        amount = user_deposit_with_code(account, code)
        message = f"🎉 Deposit of **₦{amount:,.2f}** successful!\n"
        message += f"Your new balance is **₦{account['balance']:,.2f}**."
        return await user_menu_display(update, context, message)
    except ValueError as e:
        # Re-ask for input, keeping ReplyKeyboardRemove in place
        await update.message.reply_text(f"❌ Deposit failed: {e}\n\nPlease enter a valid code or /start.")
        return DEPOSIT_CODE_INPUT  # Stay in deposit input state

# --- Transaction History Handler ---


async def user_tx_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    account = context.user_data['account']
    output = "--- TRANSACTION HISTORY ---\n"
    if not account["transactions"]:
        output += "No transactions found."
    else:
        # Display the last 10 transactions (most recent first)
        last_transactions = account["transactions"][-10:][::-1]

        for tx in last_transactions:
            amount_display = f"₦{tx['amount']:,.2f}"
            if tx["type"].startswith("transfer_out") or tx["type"] in ["airtime_purchase", "data_purchase"]:
                amount_display = f"🔻 {amount_display}"
            else:
                amount_display = f"🟢 {amount_display}"

            output += f"**{tx['type'].replace('_', ' ').title()}**\n"
            output += f"  Amount: {amount_display}\n"
            output += f"  Balance After: ₦{tx['balance_after']:,.2f}\n"
            output += f"  Ref: `{tx['ref']}`\n"
            output += f"  Date: {tx['timestamp'][:19]}\n"
            output += "-" * 20 + "\n"

    # Send message and then return to main menu, which will display the ReplyKeyboardMarkup
    await update.message.reply_text(output, parse_mode='Markdown')
    return await user_menu_display(update, context)

# --- Transfer Handlers (using Inline Keyboard for nested menus) ---


async def transfer_menu_display(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = "--- TRANSFER FUNDS ---\nSelect transfer type:"
    keyboard = [
        [InlineKeyboardButton("Internal Transfer (Romans Bank)",
                              callback_data="transfer_internal")],
        [InlineKeyboardButton("External Transfer (Other Bank)",
                              callback_data="transfer_external")],
        # Use a specific callback to go back
        [InlineKeyboardButton(
            "⬅️ Back to Menu", callback_data="back_to_main_menu_inline")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # This must be a new message as the previous one hid the ReplyKeyboardMarkup
    await update.message.reply_text(text, reply_markup=reply_markup)
    return TRANSFER_MENU

# Internal Transfer Flow


async def transfer_internal_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Edit the inline menu message
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("INTERNAL TRANSFER: Enter **Recipient Romans Bank Account Number**:")
    return TRANSFER_INTERNAL_ACCT


async def transfer_internal_acct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    acct_no = update.message.text.strip()
    if not acct_no.isdigit():
        await update.message.reply_text("❌ Invalid account number. Must be digits only. Please re-enter:")
        return TRANSFER_INTERNAL_ACCT

    receiver = find_by_account_number(acct_no)
    if not receiver:
        await update.message.reply_text("❌ Destination account not found. Please re-enter:")
        return TRANSFER_INTERNAL_ACCT

    context.user_data['temp_dest_acct'] = acct_no
    context.user_data['temp_dest_name'] = receiver['name']
    await update.message.reply_text(f"Recipient: **{receiver['name']}**. Enter **Amount (₦)** to transfer:")
    return TRANSFER_INTERNAL_AMT


async def transfer_internal_amt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    account = context.user_data['account']
    acct_no = context.user_data['temp_dest_acct']

    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive.")
        if amount > account["balance"]:
            raise ValueError("Insufficient funds.")

        context.user_data['temp_amount'] = amount

        # Internal transfer success and notification
        tx_out, tx_in = internal_transfer(
            account, acct_no, amount, narration="Internal Transfer via Telegram")

        message = f"✅ Internal transfer of **₦{amount:,.2f}** to **{context.user_data['temp_dest_name']}** successful.\n"
        message += f"Reference: `{tx_out['ref']}`. New balance: **₦{account['balance']:,.2f}**."

        context.user_data.pop('temp_dest_acct', None)
        context.user_data.pop('temp_dest_name', None)
        context.user_data.pop('temp_amount', None)

        # Return to main menu, which displays the ReplyKeyboardMarkup
        return await user_menu_display(update, context, message)

    except ValueError as e:
        await update.message.reply_text(f"❌ Transfer failed: {e}. Please re-enter amount:")
        return TRANSFER_INTERNAL_AMT

# External Transfer Flow


async def transfer_external_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: Show bank list as InlineKeyboard for external transfer."""
    await update.callback_query.answer()

    # List of available banks (add or remove as you like)
    bank_list = [
        "Access Bank", "GTBank", "UBA", "First Bank", "Zenith Bank",
        "FCMB", "Kuda Bank", "Opay", "Moniepoint", "PalmPay"
    ]

    keyboard = [
        [InlineKeyboardButton(bank, callback_data=f"bank_{bank}")]
        for bank in bank_list
    ]
    keyboard.append([InlineKeyboardButton("⬅️ Back to Menu",
                    callback_data="back_to_main_menu_inline")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("🏦 Select Recipient Bank:", reply_markup=reply_markup)
    return TRANSFER_EXTERNAL_BANK


async def transfer_external_bank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Store chosen bank and ask for recipient account number."""
    query = update.callback_query
    await query.answer()

    # Extract bank name from callback data (e.g. 'bank_UBA' → 'UBA')
    bank_name = query.data.replace("bank_", "")
    context.user_data['temp_dest_bank'] = bank_name

    await query.edit_message_text(f"✅ Bank selected: <b>{bank_name}</b>\n\nEnter <b>Recipient Account Number</b>:", parse_mode="HTML")
    return TRANSFER_EXTERNAL_ACCT


async def transfer_external_acct(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['temp_dest_acct'] = update.message.text.strip()
    await update.message.reply_text("Enter **Recipient Name**:")
    return TRANSFER_EXTERNAL_NAME


async def transfer_external_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['temp_dest_name'] = update.message.text.strip().title()
    await update.message.reply_text("Enter **Amount (₦)** to transfer:")
    return TRANSFER_EXTERNAL_AMT


async def transfer_external_amt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    account = context.user_data['account']
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Amount must be positive.")

        fee = max(round(amount * EXTERNAL_TRANSFER_FEE_PERCENT, 2),
                  EXTERNAL_TRANSFER_FEE_MIN)
        total = amount + fee

        if total > account["balance"]:
            await update.message.reply_text(f"❌ Insufficient funds. Total required (incl. ₦{fee:,.2f} fee) is ₦{total:,.2f}. Please re-enter amount:")
            return TRANSFER_EXTERNAL_AMT

        context.user_data['temp_amount'] = amount
        context.user_data['temp_total'] = total

        text = f"Fee calculation: ₦{amount:,.2f} + ₦{fee:,.2f} fee = ₦{total:,.2f} total\n"
        text += "Enter **Recipient Email** (optional for alert, type 'none' if not available):"
        await update.message.reply_text(text)
        return TRANSFER_EXTERNAL_EMAIL
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a valid number:")
        return TRANSFER_EXTERNAL_AMT


async def transfer_external_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    email_input = update.message.text.strip()
    context.user_data['temp_dest_email'] = email_input if email_input.lower(
    ) != 'none' else None
    await update.message.reply_text("Enter **Narration** (optional, type 'none' if none):")
    return TRANSFER_EXTERNAL_NARR


async def transfer_external_narr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    narration_input = update.message.text.strip()
    narration = narration_input if narration_input.lower() != 'none' else ""
    context.user_data['temp_narration'] = narration

    # Trigger OTP
    account = context.user_data['account']
    total = context.user_data['temp_total']

    try:
        otp_ref = simulate_otp(account, "External Transfer", total)
        context.user_data['otp_ref'] = otp_ref

        text = f"An OTP has been sent to your email ({account['email']}).\n"
        text += f"Enter the **6-digit OTP** to confirm the external transfer of ₦{total:,.2f}:"
        await update.message.reply_text(text)
        return OTP_ENTRY
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to generate OTP: {e}. Please try again or /start.")
        return ConversationHandler.END


async def otp_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    otp_code = update.message.text.strip()
    account = context.user_data['account']
    otp_ref = context.user_data.get('otp_ref')

    if not otp_ref:
        await update.message.reply_text("❌ Error: OTP reference missing. Please /start again.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    try:
        confirm_otp(otp_ref, otp_code)

        # Execute transfer (Final step)
        tx_ref, fee_charged = external_transfer(
            account,
            context.user_data['temp_dest_bank'],
            context.user_data['temp_dest_acct'],
            context.user_data['temp_dest_name'],
            context.user_data['temp_amount'],
            context.user_data['temp_dest_email'],
            context.user_data['temp_narration']
        )

        message = f"✅ External transfer of **₦{context.user_data['temp_amount']:,.2f}** successful (Fee: ₦{fee_charged:,.2f}).\n"
        message += f"Reference: `{tx_ref}`. New balance: **₦{account['balance']:,.2f}**."

        context.user_data.pop('temp_total', None)
        context.user_data.pop('otp_ref', None)

        # Return to main menu, which displays the ReplyKeyboardMarkup
        return await user_menu_display(update, context, message)

    except ValueError as e:
        await update.message.reply_text(f"❌ OTP/Transfer failed: {e}. Please check your email and re-enter OTP or /start.")
        return OTP_ENTRY  # Allow retry of OTP
    except Exception as e:
        await update.message.reply_text(f"❌ An unexpected error occurred: {e}. Please /start again.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


# --- Top-up Handlers (using Inline Keyboard for nested menus) ---

async def topup_menu_display(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = "--- BUY AIRTIME / DATA ---\nSelect product type:"
    keyboard = [
        [InlineKeyboardButton("Buy Airtime", callback_data="buy_airtime")],
        [InlineKeyboardButton("Buy Data Bundle", callback_data="buy_data")],
        [InlineKeyboardButton(
            "⬅️ Back to Menu", callback_data="back_to_main_menu_inline")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    # This must be a new message as the previous one hid the ReplyKeyboardMarkup
    await update.message.reply_text(text, reply_markup=reply_markup)
    return TOPUP_MENU


async def topup_network_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    # query.data can be 'buy_airtime' or 'buy_data'
    product_type = query.data.split('_')[1]
    context.user_data['product_type'] = product_type

    text = f"Select network for {product_type}:"
    keyboard = []
    for k, v in NETWORKS.items():
        keyboard.append([InlineKeyboardButton(
            v['display'], callback_data=f"net_{k}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Top-up Menu",
                    callback_data="user_topup_inline")])  # Back to topup_menu_display

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)
    return TOPUP_NETWORK


async def topup_network_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    net_key = query.data.split('_')[1]
    network = NETWORKS[net_key]
    context.user_data['net_key'] = net_key
    context.user_data['network_display'] = network['display']

    product_type = context.user_data['product_type']

    # ✅ SAFER: Use context.bot.send_message instead of edit_message_text for text input stage
    chat_id = query.message.chat_id

    if product_type == 'airtime':
        await query.delete_message()  # remove inline keyboard message safely
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"You chose *{network['display']} Airtime*.\n\nEnter recipient phone number (e.g. 0803xxxxxxx):",
            parse_mode="Markdown"
        )
        return TOPUP_AIRTIME_PHONE

    elif product_type == 'data':
        context.user_data['network_data_bundles'] = network['data_bundles']
        text = f"You chose *{network['display']} Data*.\nSelect a bundle:"
        keyboard = []
        for i, (name, price) in enumerate(network['data_bundles']):
            keyboard.append([InlineKeyboardButton(
                f"{name} — ₦{price:,.2f}", callback_data=f"bundle_{i}")])
        keyboard.append([InlineKeyboardButton(
            "⬅️ Back", callback_data="buy_data")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return TOPUP_DATA_BUNDLE

# Airtime Flow


async def topup_airtime_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    phone_fmt = format_tel_number(phone)
    # ✅ Validate number
    if not phone_fmt.startswith("+234") or len(phone_fmt) < 10:
        await update.message.reply_text("❌ Invalid phone number format. Please enter again (e.g. 0803xxxxxxx):")
        return TOPUP_AIRTIME_PHONE

    # ✅ Save and ask for amount
    context.user_data['recipient_phone'] = phone_fmt
    await update.message.reply_text("Enter **Airtime Amount (₦)**:")
    return TOPUP_AIRTIME_AMT  # <- return the next state properly


async def topup_airtime_amt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    account = context.user_data['account']
    phone_fmt = context.user_data['recipient_phone']
    network_display = context.user_data['network_display']

    try:
        amt = float(update.message.text.strip())
        if amt <= 0:
            raise ValueError("Amount must be positive.")
        if amt > account["balance"]:
            raise ValueError("Insufficient balance.")

        # --- Core Airtime Logic ---
        account["balance"] -= amt
        tx = record_tx(account, "airtime_purchase", amt, {
            "phone": phone_fmt,
            "network": network_display,
            "product": f"Airtime ₦{amt:,.2f}"
        })
        tx_ref = tx["ref"]
        send_topup_email(
            account, phone_fmt, account['name'], network_display, f"Airtime ₦{amt:,.2f}", amt, tx_ref)

        message = f"✅ Airtime purchase successful! **₦{amt:,.2f}** sent to `{phone_fmt}`.\n"
        message += f"Reference: `{tx_ref}`. New balance: **₦{account['balance']:,.2f}**."

        # Return to main menu, which displays the ReplyKeyboardMarkup
        return await user_menu_display(update, context, message)

    except ValueError as e:
        await update.message.reply_text(f"❌ Purchase failed: {e}. Please re-enter amount:")
        return TOPUP_AIRTIME_AMT

# Data Flow


async def topup_data_bundle_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    bundle_index = int(query.data.split('_')[1])
    network_bundles = context.user_data['network_data_bundles']
    bundle_name, bundle_price = network_bundles[bundle_index]

    context.user_data['bundle_name'] = bundle_name
    context.user_data['bundle_price'] = bundle_price

    account = context.user_data['account']
    if bundle_price > account["balance"]:
        text = f"❌ Insufficient balance to purchase *{bundle_name}* (₦{bundle_price:,.2f}).\n"
        text += f"Your balance: ₦{account['balance']:,.2f}."
        keyboard = [[InlineKeyboardButton(
            "⬅️ Back", callback_data="buy_data")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return TOPUP_DATA_BUNDLE

    # ✅ SAFER: delete inline message and send a fresh message for phone number
    chat_id = query.message.chat_id
    await query.delete_message()
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"You chose *{bundle_name}* (₦{bundle_price:,.2f}).\nEnter recipient phone number (e.g. 0803xxxxxxx):",
        parse_mode="Markdown"
    )
    return TOPUP_DATA_PHONE


async def topup_data_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    account = context.user_data['account']
    phone = update.message.text.strip()
    phone_fmt = format_tel_number(phone)
    if not phone_fmt.startswith("+234") or len(phone_fmt) < 10:
        await update.message.reply_text("❌ Invalid phone number format. Please enter again (e.g. 0803xxxxxxx):")
        return TOPUP_DATA_PHONE

    bundle_name = context.user_data['bundle_name']
    bundle_price = context.user_data['bundle_price']
    network_display = context.user_data['network_display']

    try:
        # Deduct balance and record
        account["balance"] -= bundle_price
        tx = record_tx(account, "data_purchase", bundle_price, {
            "phone": phone_fmt,
            "network": network_display,
            "product": bundle_name
        })
        tx_ref = tx["ref"]
        send_topup_email(
            account, phone_fmt, account['name'], network_display, f"{bundle_name} (Data)", bundle_price, tx_ref)

        message = f"✅ Data purchase successful! **{bundle_name}** (₦{bundle_price:,.2f}) sent to `{phone_fmt}`.\n"
        message += f"Reference: `{tx_ref}`. New balance: **₦{account['balance']:,.2f}**."

        return await user_menu_display(update, context, message)

    except Exception as e:
        await update.message.reply_text(f"❌ Data purchase failed: {e}. Please /start again.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END


# (Assuming your existing imports like os, Application, etc., are here)
import os 
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

# ... (ALL YOUR EXISTING CONSTANTS, HANDLER FUNCTIONS, AND HELPER FUNCTIONS GO HERE) ...

# -------------------------------------------------------------
# --- NEW CODE ADDED FOR RENDER FREE WEB SERVICE WORKAROUND ---
# -------------------------------------------------------------

# This server is just a dummy to satisfy Render's Web Service requirements.
class HealthCheckHandler(BaseHTTPRequestHandler):
    """A minimal HTTP handler for health checks."""
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running.')

def start_http_server():
    """Starts a simple server on the port Render requires (PORT environment variable)."""
    # Render sets the PORT environment variable for Web Services
    # We use 8080 as a local fallback, but Render always uses its own port.
    PORT = int(os.environ.get("PORT", 8080)) 
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, HealthCheckHandler)
    print(f"Starting dummy HTTP server on port {PORT}...")
    # This call blocks the main thread, keeping the Render service alive.
    httpd.serve_forever()

# -------------------------------------------------------------
# --- REPLACED MAIN FUNCTION ---
# -------------------------------------------------------------

def main():
    """Entry point and main loop for the Telegram application."""
    
    # NOTE: BOT_TOKEN must be loaded from os.environ previously or here. 
    # Assuming it's defined via os.environ.get('TELEGRAM_BOT_TOKEN') at the top.
    if BOT_TOKEN in ("", None, "YOUR_TELEGRAM_BOT_TOKEN_HERE"):
        print("ERROR: Please set BOT_TOKEN to your actual Telegram bot token.")
        return

    # 1. Initialize Threading and Application
    start_autosave_thread()
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Define Reply Keyboard options that trigger actions in the START state
    start_options = filters.Text(
        ["Login to Account", "Create New Account (Sign Up)", "Admin Login"])

    # Define Reply Keyboard options that trigger actions in the USER_MENU state
    user_menu_options = filters.Text(["Transfer Funds", "Buy Airtime / Data", "Deposit via Code", "View Transaction History",
                                    "Logout", "Generate Deposit Code", "View All User Accounts", "View All Deposit Codes"])

    # Main Conversation Handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START: [
                # Use MessageHandler for ReplyKeyboard buttons
                MessageHandler(start_options, login_route),
            ],
            # Registration flow
            REGISTER_FIRST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_first_name)],
            REGISTER_LAST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_last_name)],
            REGISTER_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_age)],
            REGISTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_email)],
            REGISTER_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_pin)],
            # Login flow
            LOGIN_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_email)],
            LOGIN_PIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_pin)],
            ADMIN_PIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_pin_input)],
            # User & Admin Main Menu (now uses MessageHandler for ReplyKeyboardMarkup)
            USER_MENU: [
                MessageHandler(user_menu_options, user_menu_route),
            ],
            # Admin Specific
            ADMIN_GEN_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_gen_code_input)],
            # Deposit Code Input
            DEPOSIT_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_code_input)],
            # Transfer flow (back to main menu via inline button needs a specific pattern and to handle state transition back to USER_MENU)
            TRANSFER_MENU: [
                CallbackQueryHandler(
                    transfer_internal_start, pattern="^transfer_internal$"),
                CallbackQueryHandler(
                    transfer_external_start, pattern="^transfer_external$"),
                # This callback is used to return from a nested INLINE menu to the main REPLY menu
                CallbackQueryHandler(
                    user_menu_display, pattern="^back_to_main_menu_inline$"),
            ],
            # Internal Transfer
            TRANSFER_INTERNAL_ACCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_internal_acct)],
            TRANSFER_INTERNAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_internal_amt)],
            # External Transfer
            TRANSFER_EXTERNAL_BANK: [CallbackQueryHandler(transfer_external_bank, pattern="^bank_")],
            TRANSFER_EXTERNAL_ACCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_external_acct)],
            TRANSFER_EXTERNAL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_external_name)],
            TRANSFER_EXTERNAL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_external_amt)],
            TRANSFER_EXTERNAL_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_external_email)],
            TRANSFER_EXTERNAL_NARR: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_external_narr)],
            # OTP Confirmation
            OTP_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, otp_confirmation)],
            # Top-up flow (back to main menu via inline button needs a specific pattern and to handle state transition back to USER_MENU)
            TOPUP_MENU: [
                CallbackQueryHandler(topup_network_select,
                                        pattern="^buy_(airtime|data)$"),
                # This callback is used to return from a nested INLINE menu to the main REPLY menu
                CallbackQueryHandler(
                    user_menu_display, pattern="^back_to_main_menu_inline$"),
                # From network select back to top-up menu
                CallbackQueryHandler(topup_menu_display,
                                        pattern="^user_topup_inline$"),
            ],
            TOPUP_NETWORK: [CallbackQueryHandler(topup_network_chosen, pattern="^net_")],
            # Airtime Specific
            TOPUP_AIRTIME_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_airtime_phone)],
            TOPUP_AIRTIME_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_airtime_amt)],
            # Data Specific
            TOPUP_DATA_BUNDLE: [
                CallbackQueryHandler(
                    topup_data_bundle_chosen, pattern="^bundle_"),
                # Back button from insufficient balance
                CallbackQueryHandler(topup_network_select,
                                        pattern="^buy_data$"),
            ],
            TOPUP_DATA_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, topup_data_phone)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="romans_bank_conversation",
        persistent=False
    )

    application.add_handler(conv_handler)
    
    # 2. Start Telegram Polling in a background thread
    bot_thread = threading.Thread(
        target=lambda: application.run_polling(allowed_updates=Update.ALL_TYPES), 
        daemon=True # Daemon thread allows the main process to exit if the main thread (HTTP server) stops
    )
    bot_thread.start()
    
    print("🤖 Romans Bank Bot is running in a thread...")

    # 3. Start the dummy HTTP server in the main thread (this is the process Render monitors)
    start_http_server()


if __name__ == "__main__":
    main()

