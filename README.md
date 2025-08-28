# Gmail Cleanup Tool

A fast Python script to automatically delete unnecessary emails from Gmail. Can process 1000+ emails in under 5 minutes.

## What it does

Identifies and deletes:
- Promotional emails (sales, discounts, offers)
- Newsletters and marketing emails
- Social media notifications
- Automated system messages
- Spam and no-reply emails

Only processes emails older than June 1, 2025.

## Requirements

- Python 3.6+
- Gmail App Password

## Setup

1. **Enable App Password in Gmail:**
   - Go to Google Account Settings → Security → 2-Step Verification
   - Generate an App Password under "App passwords"
   - Save the password

2. **Update email address in script** (if not using gabrielbarita@gmail.com):
   ```python
   cleanup = FastGmailCleanup('your-email@gmail.com')
   ```

## Usage

**Preview mode (recommended first run):**
```bash
python3 emailcleanup.py
# Change last line to: main(dry_run_mode=True)
```

**Full cleanup:**
```bash
python3 emailcleanup.py
```

Press Ctrl+C to stop at any time.

## Sample output

```
Found 1247 unread emails
Processing batch 1/13 (100 emails)...
❌ [1] Weekly Newsletter... (Contains pattern: newsletter)
❌ [2] 50% OFF Summer Sale... (Promotional keyword: sale)

⚡ Processed: 100/1247 | Speed: 45.2 emails/sec | ETA: 4.2m

ANALYSIS COMPLETE
🗑️ Identified for deletion: 892
✅ To keep: 355

Proceed with deletion? (yes/no):
```

## Configuration

Change the date cutoff:
```python
self.cutoff_date = datetime.datetime(2025, 6, 1)
```

Add custom patterns to delete:
```python
UNNECESSARY_PATTERNS = [
    r'your-custom-pattern',
    # add more...
]
```

## Troubleshooting

- **Connection failed**: Check App Password and internet connection
- **SSL errors**: Script includes macOS SSL fix
- **Slow processing**: Check internet speed, Gmail may throttle requests

## Important Notes

- Always test with preview mode first
- This permanently deletes emails
- Keep important emails in separate folders
- Script only processes unread emails
