import imaplib
import email
from bs4 import BeautifulSoup
import logging
from datetime import datetime
import re
import json
import os
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("email_check.log"),
        logging.StreamHandler()
    ]
)

# Email server and credentials
IMAP_SERVER = "imap.hostinger.com"
IMAP_PORT = 993
EMAIL_ACCOUNT = "vipin@agentflow.in"
PASSWORD = "P2mw0bdod#1Q2mw0bdod#1"

# Pattern to match subjects like "[Urban Threads] Order #1021 placed by user name"
TARGET_SUBJECT_PATTERN = r"\[Urban Threads\] Order #\d+ placed by .+"

# Store emails in memory as a list of dictionaries
emails_in_memory = []
all_orders = []

def decode_email_content(payload):
    """Attempt to decode email content with multiple encodings."""
    for encoding in ["utf-8", "ISO-8859-1", "latin1"]:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            logging.warning(f"Decoding failed with {encoding}, trying next...")
            continue
    logging.warning("All decoding attempts failed, ignoring errors.")
    return payload.decode("utf-8", errors="ignore")

def process_email(subject, from_email, body):
    """Process and store the email in memory if it matches the subject pattern."""
    if re.match(TARGET_SUBJECT_PATTERN, subject.strip()):
        email_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from": from_email,
            "subject": subject,
            "body": body
        }
        #emails_in_memory.append(email_data)
        order_details = {
                "customer_name": None,
                "order_id": None,
                "timestamp": None,
                "customer_address": None,
                "customer_email": None
                }


        order_pattern = r"(\w+\s+\w+)\s+placed\s+order\s+#(\d+)\s+on\s+(\w+\s+\d+\s+at\s+\d+:\d+\s+[ap]m)"
        order_match = re.search(order_pattern, body)
        if order_match:
            order_details["customer_name"] = order_match.group(1)
            order_details["order_id"] = order_match.group(2)
            order_details["timestamp"] = order_match.group(3)
        
        # Pattern for shipping address
        address_pattern = r"Shipping address\s*\n\s*(.*?)(?=Customer Email)"
        address_match = re.search(address_pattern, body, re.DOTALL)
        if address_match:
            # Clean up the address by removing extra whitespace and empty lines
            address = address_match.group(1)
            address_lines = [line.strip() for line in address.split('\n') if line.strip()]
            order_details["customer_address"] = '\n'.join(address_lines)
        
        # Pattern for customer email
        email_pattern = r"Customer Email\s*\n\s*(\S+@\S+\.\S+)"
        email_match = re.search(email_pattern, body)
        if email_match:
            order_details["customer_email"] = email_match.group(1)

        return order_details

        logging.info(f"Email added to memory: {subject}")
    else:
        logging.info(f"Skipping email with subject: {subject}")

def check_hostinger_email():
    logging.info("Starting email check process...")

    try:
        # Connect to Hostinger mail server with SSL encryption
        logging.info("Connecting to Hostinger mail server...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL_ACCOUNT, PASSWORD)
        logging.info("Successfully logged in to email account.")

        # Select the inbox folder
        mail.select("inbox")
        logging.info("Inbox selected.")

        # Search for all emails (read and unread)
        logging.info("Searching for all emails...")
        status, messages = mail.search(None, "UNSEEN")

        if status != "OK":
            logging.warning("No emails found.")
            return

        mail_ids = messages[0].split()
        logging.info(f"Found {len(mail_ids)} emails.")

        for mail_id in mail_ids:
            # Fetch each email by ID
            logging.info(f"Fetching email ID: {mail_id.decode()}")
            status, msg_data = mail.fetch(mail_id, "(RFC822)")

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    logging.info("Parsing email content...")
                    msg = email.message_from_bytes(response_part[1])

                    # Get email details
                    subject = msg["subject"] or "No Subject"
                    from_email = msg["from"]

                    # Get email content
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                body = decode_email_content(part.get_payload(decode=True))
                                break
                            elif content_type == "text/html":
                                html = decode_email_content(part.get_payload(decode=True))
                                body = BeautifulSoup(html, "html.parser").get_text()
                                break
                    else:
                        body = decode_email_content(msg.get_payload(decode=True))

                    order_details = process_email(subject, from_email, body)
                    if order_details:
                        all_orders.append(order_details)

                    mail.store(mail_id, "+FLAGS", "\\Seen")

#        with open('shopify_orders.json', 'a', encoding='utf-8') as json_file:
#            json.dump(all_orders, json_file, indent=4, ensure_ascii=False)

        json_filename = 'shopify_orders.json'

        if os.path.exists(json_filename) and os.path.getsize(json_filename) > 0:
            with open(json_filename, 'r', encoding='utf-8') as json_file:
                try:
                    existing_orders = json.load(json_file)  # Load existing JSON data
                    if not isinstance(existing_orders, list):  # Ensure it's a list
                        existing_orders = []
                except json.JSONDecodeError:
                    existing_orders = []  # If file is corrupted, reset to empty list
        else:
            existing_orders = []  # No file -> Start with an empty list
        
        existing_orders.extend(all_orders)  # Merge lists
        
        if all_orders:
            with open(json_filename, 'w', encoding='utf-8') as json_file:
                json.dump(existing_orders, json_file, indent=4, ensure_ascii=False)
            all_orders.clear()





        logging.info("Email check and process completed successfully.")
        logging.info(f"Total emails in memory: {len(emails_in_memory)}")
        mail.close()
        mail.logout()

    except imaplib.IMAP4.error as e:
        logging.error(f"IMAP error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

# Run the email check function
while True:
    check_hostinger_email()
    time.sleep(60)
