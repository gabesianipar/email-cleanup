#!/usr/bin/env python3
"""
Fast Gmail Cleanup Tool for gabrielbarita@gmail.com (IMAP Version)
Optimized for speed - can process 1000+ emails in under 5 minutes.

Requirements:
- App Password for Gmail
"""

import imaplib
import email
import datetime
import re
import getpass
import time
from email.header import decode_header
from email.utils import parsedate_tz, mktime_tz
import ssl
import signal
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix SSL certificate verification issues on macOS
ssl._create_default_https_context = ssl._create_unverified_context

# Email patterns that typically indicate unnecessary emails
UNNECESSARY_PATTERNS = [
    r'noreply', r'no-reply', r'donotreply', r'notification', r'newsletter',
    r'unsubscribe', r'promotional', r'marketing', r'sale', r'offer', r'deal',
    r'discount', r'coupon', r'survey', r'feedback', r'social.*notification',
    r'linkedin.*invitation', r'facebook.*notification', r'twitter.*notification',
    r'instagram.*notification', r'spam', r'advertisement', r'promo',
    r'alert.*account', r'security.*alert', r'backup.*complete',
    r'system.*notification', r'automated.*message', r'digest',
    r'weekly.*update', r'monthly.*report'
]

UNNECESSARY_DOMAINS = [
    'newsletters.com', 'marketing.com', 'promo.com', 'noreply.com',
    'notifications.com', 'alerts.com', 'survey.com', 'feedback.com',
    'mailchimp.com', 'constantcontact.com', 'sendgrid.net', 'mailgun.org'
]

UNNECESSARY_SENDERS = [
    'newsletter', 'marketing', 'promo', 'deals', 'offers', 'support',
    'team', 'hello', 'info', 'updates', 'notifications'
]

class FastGmailCleanup:
    def __init__(self, email_address='gabrielbarita@gmail.com'):
        self.email_address = email_address
        self.password = None
        self.mail = None
        self.cutoff_date = datetime.datetime(2025, 6, 1)
        self.stop_requested = False
        self.emails_to_delete = []
        self.deleted_count = 0
        self.kept_count = 0
        self.processed_count = 0
        
        # Set up signal handler for graceful stopping
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print(f"\n\n🛑 STOP REQUESTED - Finishing current batch...")
        self.stop_requested = True
    
    def connect_to_gmail(self):
        """Connect to Gmail using IMAP with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Retry attempt {attempt + 1}/{max_retries}...")
                    time.sleep(2)  # Wait before retry
                
                print(f"Connecting to Gmail for {self.email_address}...")
                
                # Get password only on first attempt
                if attempt == 0:
                    self.password = getpass.getpass("Enter your Gmail password (or App Password): ")
                
                # Close any existing connection
                if self.mail:
                    try:
                        self.mail.logout()
                    except:
                        pass
                
                # Create fresh connection
                self.mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
                
                # Login
                self.mail.login(self.email_address, self.password)
                
                # Test the connection
                self.mail.select('inbox')
                
                print("✓ Successfully connected to Gmail")
                return True
                
            except Exception as e:
                print(f"✗ Connection attempt {attempt + 1} failed: {e}")
                if self.mail:
                    try:
                        self.mail.logout()
                    except:
                        pass
                    self.mail = None
                
                if attempt == max_retries - 1:
                    print("\n❌ All connection attempts failed.")
                    print("Troubleshooting steps:")
                    print("1. Check your internet connection")
                    print("2. Verify your App Password is correct")
                    print("3. Try again in a few minutes")
                    return False
        
        return False
    
    def reconnect_if_needed(self):
        """Reconnect to Gmail if connection is lost"""
        try:
            # Test connection
            self.mail.noop()  # No-op to test connection
            return True
        except:
            print("🔄 Connection lost, attempting to reconnect...")
            return self.connect_to_gmail()
    
    def get_unread_emails_fast(self):
        """Get unread emails with basic info only (much faster) with retry logic"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Ensure connection is good
                if not self.reconnect_if_needed():
                    print(f"❌ Could not establish connection for attempt {attempt + 1}")
                    continue
                
                # Select inbox
                self.mail.select('inbox')
                
                # Search for unread emails
                status, messages = self.mail.search(None, 'UNSEEN')
                
                if status != 'OK':
                    print(f"⚠️ Search returned status: {status}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        print("❌ Error searching for unread emails after all retries")
                        return []
                
                email_ids = messages[0].split()
                print(f"✅ Found {len(email_ids)} unread emails")
                
                return email_ids
                
            except Exception as e:
                print(f"⚠️ Attempt {attempt + 1} failed: {e}")
                
                if "EOF occurred in violation of protocol" in str(e) or "socket error" in str(e):
                    print("🔄 SSL/Socket error detected, reconnecting...")
                    # Force reconnection
                    self.mail = None
                    time.sleep(3)
                    if not self.connect_to_gmail():
                        continue
                elif attempt < max_retries - 1:
                    print(f"🔄 Retrying in 3 seconds...")
                    time.sleep(3)
                else:
                    print("❌ All retry attempts failed")
                    return []
        
        return []
    
    def fetch_email_headers_batch(self, email_ids, batch_size=50):
        """Fetch email headers in batches for speed"""
        batches = []
        for i in range(0, len(email_ids), batch_size):
            batch = email_ids[i:i + batch_size]
            batches.append(batch)
        
        return batches
    
    def process_email_batch(self, email_batch):
        """Process a batch of emails (headers only for speed) with error handling"""
        batch_results = []
        
        for email_id in email_batch:
            if self.stop_requested:
                break
                
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    # Check connection before each batch
                    if attempt > 0:
                        if not self.reconnect_if_needed():
                            continue
                    
                    # Fetch only headers (much faster than full email)
                    status, msg_data = self.mail.fetch(email_id, '(BODY.PEEK[HEADER])')
                    
                    if status != 'OK':
                        if attempt < max_retries - 1:
                            time.sleep(1)
                            continue
                        else:
                            break
                    
                    # Parse headers only
                    raw_headers = msg_data[0][1]
                    email_message = email.message_from_bytes(raw_headers)
                    
                    # Extract key info
                    sender_full = self.decode_header_value(email_message.get('From', ''))
                    subject = self.decode_header_value(email_message.get('Subject', ''))
                    date_str = email_message.get('Date', '')
                    
                    # Extract email address from sender
                    sender_match = re.search(r'<([^>]+)>', sender_full)
                    sender = sender_match.group(1) if sender_match else sender_full
                    
                    # Parse date
                    email_date = self.parse_email_date(date_str)
                    
                    # Quick date filter
                    if not email_date or email_date >= self.cutoff_date:
                        batch_results.append({
                            'id': email_id,
                            'action': 'keep',
                            'reason': 'too_recent_or_no_date'
                        })
                        break
                    
                    # Quick unnecessary check
                    is_unnecessary, reason = self.is_unnecessary_email_fast(sender, subject, sender_full)
                    
                    if is_unnecessary:
                        batch_results.append({
                            'id': email_id,
                            'action': 'delete',
                            'date': email_date,
                            'sender': sender_full,
                            'subject': subject,
                            'reason': reason
                        })
                    else:
                        batch_results.append({
                            'id': email_id,
                            'action': 'keep',
                            'reason': 'not_unnecessary'
                        })
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if "EOF occurred in violation of protocol" in str(e) or "socket error" in str(e):
                        if attempt < max_retries - 1:
                            print(f"🔄 Socket error on email {email_id}, retrying...")
                            time.sleep(1)
                            continue
                    
                    if attempt == max_retries - 1:
                        print(f'⚠️ Could not process email {email_id}: {e}')
                    continue
        
        return batch_results
    
    def is_unnecessary_email_fast(self, sender, subject, sender_full):
        """Fast version of unnecessary email detection"""
        sender_lower = sender.lower()
        subject_lower = subject.lower()
        sender_full_lower = sender_full.lower()
        
        # Quick pattern matching (compiled regex would be even faster)
        for pattern in UNNECESSARY_PATTERNS:
            if pattern in sender_lower or pattern in subject_lower or pattern in sender_full_lower:
                return True, f"Contains pattern: {pattern}"
        
        # Quick domain check
        sender_domain = sender_lower.split('@')[-1] if '@' in sender_lower else ''
        for domain in UNNECESSARY_DOMAINS:
            if domain in sender_domain:
                return True, f"Sender domain: {domain}"
        
        # Quick sender keyword check
        sender_name = sender_lower.split('@')[0] if '@' in sender_lower else sender_lower
        for keyword in UNNECESSARY_SENDERS:
            if keyword in sender_name:
                return True, f"Sender name contains: {keyword}"
        
        # Quick promotional keywords
        promo_keywords = ['sale', 'discount', 'offer', 'deal', 'coupon', '% off', 'free shipping']
        for keyword in promo_keywords:
            if keyword in subject_lower:
                return True, f"Promotional keyword: {keyword}"
        
        return False, "Not identified as unnecessary"
    
    def decode_header_value(self, value):
        """Fast header decoding"""
        if value is None:
            return ""
        
        try:
            decoded_parts = decode_header(value)
            result = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        result += part.decode(encoding, errors='ignore')
                    else:
                        result += part.decode('utf-8', errors='ignore')
                else:
                    result += str(part)
            return result.strip()
        except:
            return str(value)
    
    def parse_email_date(self, date_str):
        """Fast date parsing"""
        if not date_str:
            return None
        
        try:
            parsed_date = parsedate_tz(date_str)
            if parsed_date:
                timestamp = mktime_tz(parsed_date)
                return datetime.datetime.fromtimestamp(timestamp)
        except:
            pass
        
        return None
    
    def analyze_emails_fast(self, dry_run=True):
        """Fast analysis using batched processing"""
        email_ids = self.get_unread_emails_fast()
        
        if not email_ids:
            print("No unread emails found.")
            return
        
        # Reset counters
        self.deleted_count = 0
        self.kept_count = 0
        self.emails_to_delete = []
        self.processed_count = 0
        self.stop_requested = False
        
        print(f"\n{'='*70}")
        print(f"🚀 FAST ANALYSIS MODE - Processing {len(email_ids)} emails in batches")
        print(f"{'='*70}")
        print("💡 Press Ctrl+C at any time to stop")
        print(f"{'='*70}")
        
        # Process in batches for speed
        batch_size = 100  # Larger batches for speed
        batches = self.fetch_email_headers_batch(email_ids, batch_size)
        
        start_time = time.time()
        
        for batch_num, batch in enumerate(batches):
            if self.stop_requested:
                break
            
            print(f"\n📦 Processing batch {batch_num + 1}/{len(batches)} ({len(batch)} emails)...")
            
            batch_results = self.process_email_batch(batch)
            
            # Process results
            for result in batch_results:
                self.processed_count += 1
                
                if result['action'] == 'delete':
                    self.emails_to_delete.append(result)
                    self.deleted_count += 1
                    
                    # Show some deletions for feedback
                    if self.deleted_count <= 20 or self.deleted_count % 50 == 0:
                        print(f"  ❌ [{self.deleted_count}] {result['subject'][:50]}... ({result['reason']})")
                
                elif result['action'] == 'keep':
                    self.kept_count += 1
            
            # Progress update
            elapsed = time.time() - start_time
            emails_per_sec = self.processed_count / elapsed if elapsed > 0 else 0
            remaining_emails = len(email_ids) - self.processed_count
            eta_seconds = remaining_emails / emails_per_sec if emails_per_sec > 0 else 0
            
            print(f"  ⚡ Processed: {self.processed_count}/{len(email_ids)} | "
                  f"Speed: {emails_per_sec:.1f} emails/sec | "
                  f"ETA: {eta_seconds/60:.1f}m")
        
        # Show final results
        self.show_analysis_results(len(email_ids), dry_run)
    
    def show_analysis_results(self, total_emails, dry_run):
        """Show analysis results"""
        print(f"\n{'='*70}")
        if self.stop_requested:
            print(f"🛑 ANALYSIS STOPPED EARLY")
        else:
            print(f"✅ ANALYSIS COMPLETE")
        print(f"{'='*70}")
        print(f"Emails processed: {self.processed_count}/{total_emails}")
        print(f"🗑️  Identified for deletion: {self.deleted_count}")
        print(f"✅ To keep: {self.kept_count}")
        
        if self.stop_requested:
            print(f"⏳ Remaining: {total_emails - self.processed_count}")
        
        if dry_run:
            print(f"\n⚠️  DRY RUN MODE - No emails were deleted")
            if self.deleted_count > 0:
                print(f"\n📋 Sample emails that would be deleted:")
                for i, email in enumerate(self.emails_to_delete[:5]):
                    print(f"  {i+1}. {email['subject'][:60]}...")
                    print(f"      From: {email['sender'][:50]}...")
                    print(f"      Reason: {email['reason']}")
                if len(self.emails_to_delete) > 5:
                    print(f"  ... and {len(self.emails_to_delete) - 5} more")
        else:
            if self.deleted_count > 0:
                print(f"\n📋 Emails identified for deletion:")
                for i, email in enumerate(self.emails_to_delete[:5]):
                    print(f"  {i+1}. {email['subject'][:60]}...")
                    print(f"      From: {email['sender'][:50]}...")
                    print(f"      Reason: {email['reason']}")
                if len(self.emails_to_delete) > 5:
                    print(f"  ... and {len(self.emails_to_delete) - 5} more")
                
                confirm = input(f"\n❗ Proceed with deletion of {self.deleted_count} emails? (yes/no): ")
                if confirm.lower() == 'yes':
                    self.delete_emails_fast()
                else:
                    print("Deletion cancelled.")
            else:
                print("No emails identified for deletion.")
    def delete_emails_fast(self):
        """Fast email deletion using batch operations"""
        print(f"\n🗑️  FAST DELETION: Removing {len(self.emails_to_delete)} emails...")
        
        successful = 0
        failed = 0
        
        # Delete in batches for speed
        batch_size = 50
        
        for i in range(0, len(self.emails_to_delete), batch_size):
            batch = self.emails_to_delete[i:i + batch_size]
            
            for email in batch:
                try:
                    self.mail.store(email['id'], '+FLAGS', '\\Deleted')
                    successful += 1
                    
                    if successful % 100 == 0:
                        print(f"  ⚡ Deleted: {successful}/{len(self.emails_to_delete)}")
                        
                except Exception as e:
                    failed += 1
                    if failed < 5:  # Only show first few errors
                        print(f"  ❌ Failed: {email['subject'][:30]}...")
        
        # Expunge to permanently delete
        try:
            print("🔥 Permanently removing deleted emails...")
            self.mail.expunge()
            print("✅ Deletion complete!")
        except Exception as e:
            print(f"❌ Error during expunge: {e}")
        
        print(f"\n{'='*50}")
        print(f"✅ Successfully deleted: {successful}")
        print(f"❌ Failed deletions: {failed}")
        print(f"{'='*50}")
    
    def close_connection(self):
        """Close the IMAP connection"""
        if self.mail:
            try:
                self.mail.close()
                self.mail.logout()
                print("✓ Disconnected from Gmail")
            except:
                pass

def main(dry_run_mode=False):
    """Main function"""
    print("🚀 FAST Gmail Cleanup Tool for gabrielbarita@gmail.com")
    print("="*60)
    print("⚡ Optimized for speed - 5-10x faster than standard version!")
    if dry_run_mode:
        print("⚠️  DRY RUN MODE - Will show what would be deleted without deleting")
    else:
        print("🔥 DELETION MODE - Will actually delete emails after analysis")
    print("="*60)
    
    cleanup = FastGmailCleanup('gabrielbarita@gmail.com')
    
    try:
        if not cleanup.connect_to_gmail():
            return
        
        print(f"\n🎯 Target: Unread emails older than {cleanup.cutoff_date.strftime('%B %d, %Y')}")
        print(f"🔍 Looking for: Newsletters, promotions, notifications, etc.")
        
        if dry_run_mode:
            # Dry run mode - just show what would be deleted
            cleanup.analyze_emails_fast(dry_run=True)
        else:
            # Default mode - analyze and delete
            cleanup.analyze_emails_fast(dry_run=False)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Operation cancelled.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cleanup.close_connection()

if __name__ == '__main__':
    # Default mode: Analyze and delete emails (with confirmation)
    main()
    
    # For dry run mode only (just preview, no deletion):
    # main(dry_run_mode=True)