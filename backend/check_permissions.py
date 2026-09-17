#!/usr/bin/env python3
from app.core.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Check if role_templates resource exists
    result = db.execute(text('SELECT id, name FROM resource WHERE name = \'role_templates\' LIMIT 1')).first()
    print(f'role_templates resource exists: {result}')

    # Check if admin user has role_template_id
    result = db.execute(text('SELECT UserID, UserEmail, role_template_id FROM users WHERE UserEmail = \'admin@blitzenx.com\' LIMIT 1')).first()
    print(f'Admin user: {result}')

    # Check permissions for role_templates
    result = db.execute(text('''
        SELECT rt.name, r.name, rtp.can_view, rtp.can_edit
        FROM role_template_permission rtp
        JOIN role_template rt ON rtp.role_template_id = rt.id
        JOIN resource r ON rtp.resource_id = r.id
        WHERE r.name = 'role_templates'
    ''')).fetchall()
    print(f'Role_templates permissions:')
    for row in result:
        print(f'  {row}')
finally:
    db.close()
