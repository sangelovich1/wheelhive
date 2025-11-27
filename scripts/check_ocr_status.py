#!/usr/bin/env python3
"""
Check OCR extraction status after reboot

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import sys
sys.path.insert(0, 'src')

from db import Db
from messages import Messages

def main():
    db = Db(in_memory=False)  # Use persistent trades.db
    messages = Messages(db)  # Initialize to create tables

    print('📊 OCR Status Check After Reboot')
    print('=' * 60)

    # Check message statistics
    try:
        result = db.query('''
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN has_attachments = 1 THEN 1 ELSE 0 END) as with_attachments,
                SUM(CASE WHEN image_text IS NOT NULL AND LENGTH(image_text) > 0 THEN 1 ELSE 0 END) as with_ocr
            FROM harvested_messages
        ''', None)

        if result:
            total, with_attach, with_ocr = result[0]
            # Handle None values from SUM() when no rows match
            total = total or 0
            with_attach = with_attach or 0
            with_ocr = with_ocr or 0

            print(f'\n📈 Statistics:')
            print(f'  • Total messages:            {total:,}')
            print(f'  • Messages with attachments: {with_attach:,}')
            print(f'  • Messages with OCR text:    {with_ocr:,}')

            if with_attach > 0:
                ocr_rate = (with_ocr / with_attach) * 100
                print(f'  • OCR extraction rate:       {ocr_rate:.1f}%')

        # Show recent messages with attachments
        print(f'\n📷 Recent Messages with Attachments:')
        print('-' * 60)
        result = db.query('''
            SELECT
                message_id,
                channel_name,
                username,
                LENGTH(image_text) as ocr_len,
                harvested_at,
                attachment_urls
            FROM harvested_messages
            WHERE has_attachments = 1
            ORDER BY harvested_at DESC
            LIMIT 15
        ''', None)

        if result:
            for row in result:
                msg_id = row[0]
                channel = row[1][:20]
                user = row[2][:12]
                ocr_len = row[3] if row[3] else 0
                date = row[4][:10] if row[4] else 'unknown'

                ocr_status = '✅ OCR' if ocr_len > 0 else '❌ NO OCR'
                print(f'  {date} | {channel:<20} | {user:<12} | {ocr_status} ({ocr_len} chars)')
        else:
            print('  No messages with attachments found')

        # Show OCR configuration
        print(f'\n⚙️  OCR Configuration:')
        print('-' * 60)
        # Note: OCR constants have been removed from constants.py
        # OCR functionality may have been migrated to system_settings or deprecated
        print(f'  • OCR configuration moved to system_settings or deprecated')

        # Check if EasyOCR is available
        print(f'\n🔧 OCR Library Status:')
        print('-' * 60)
        try:
            import easyocr
            print(f'  • EasyOCR version:      {easyocr.__version__}')
            print(f'  • Status:               ✅ Installed')
        except ImportError as e:
            print(f'  • Status:               ❌ NOT INSTALLED')
            print(f'  • Error:                {e}')

        # Check if bot is running
        print(f'\n🤖 Bot Status:')
        print('-' * 60)
        import subprocess
        proc_result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        bot_processes = [line for line in proc_result.stdout.split('\n') if 'bot.py' in line and 'grep' not in line]

        if bot_processes:
            print(f'  • Bot running:          ✅ YES')
            for proc in bot_processes:
                parts = proc.split()
                if len(parts) > 10:
                    print(f'    PID {parts[1]}: {" ".join(parts[10:])}')
        else:
            print(f'  • Bot running:          ❌ NO')
            print(f'  • Action needed:        Start bot with: python src/bot.py')

    except Exception as e:
        print(f'\n❌ Error: {e}')
        import traceback
        traceback.print_exc()

    print('\n' + '=' * 60)

if __name__ == '__main__':
    main()
