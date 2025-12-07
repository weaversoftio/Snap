#!/usr/bin/env python3
"""
SCRIPT 1: Setup Active Directory-Style Structure (OpenLDAP Compatible)
Creates groups and users that work like AD but using standard LDAP attributes
"""

from ldap3 import Server, Connection, SUBTREE, MODIFY_ADD
from ldap3.core.exceptions import LDAPException

LDAP_SERVER = '192.168.33.209'
LDAP_PORT = 1389
LDAP_BASE_DN = 'dc=mycompany,dc=local'
LDAP_ADMIN_DN = 'cn=admin,dc=mycompany,dc=local'
LDAP_ADMIN_PASSWORD = 'Admin123!'


def create_ad_style_structure():
    """Create Active Directory-style structure with standard LDAP schema"""
    
    print("\n" + "="*70)
    print("CREATING ACTIVE DIRECTORY-STYLE STRUCTURE")
    print("="*70)
    print("Using standard LDAP attributes (compatible with OpenLDAP)")
    
    try:
        server = Server(LDAP_SERVER, port=LDAP_PORT)
        conn = Connection(server, user=LDAP_ADMIN_DN, password=LDAP_ADMIN_PASSWORD, auto_bind=True)
        
        # Step 1: Create Users container (using ou instead of cn for containers)
        print("\n[1] Creating Users container...")
        try:
            conn.add(
                'ou=ADUsers,dc=mycompany,dc=local',
                ['organizationalUnit'],
                {'ou': 'ADUsers', 'description': 'Active Directory Style Users'}
            )
            if conn.result['result'] == 0:
                print("    ✓ Users container created (ou=ADUsers)")
            elif conn.result['result'] == 68:
                print("    ℹ Users container already exists")
            else:
                print(f"    ✗ Failed: {conn.result['description']}")
        except Exception as e:
            print(f"    ℹ Container might already exist")
        
        # Step 2: Create Groups container
        print("\n[2] Creating Groups container...")
        try:
            conn.add(
                'ou=ADGroups,dc=mycompany,dc=local',
                ['organizationalUnit'],
                {'ou': 'ADGroups', 'description': 'Active Directory Style Groups'}
            )
            if conn.result['result'] == 0:
                print("    ✓ Groups container created (ou=ADGroups)")
            elif conn.result['result'] == 68:
                print("    ℹ Groups container already exists")
            else:
                print(f"    ✗ Failed: {conn.result['description']}")
        except Exception as e:
            print(f"    ℹ Container might already exist")
        
        # Step 3: Create Groups (AD-style with groupOfNames)
        print("\n[3] Creating groups (AD-style with groupOfNames)...")
        
        groups = [
            {
                'dn': 'cn=Admins,ou=ADGroups,dc=mycompany,dc=local',
                'cn': 'Admins',
                'description': 'System Administrators'
            },
            {
                'dn': 'cn=QA,ou=ADGroups,dc=mycompany,dc=local',
                'cn': 'QA',
                'description': 'Quality Assurance Team'
            },
            {
                'dn': 'cn=Developers,ou=ADGroups,dc=mycompany,dc=local',
                'cn': 'Developers',
                'description': 'Software Development Team'
            },
            {
                'dn': 'cn=Domain Users,ou=ADGroups,dc=mycompany,dc=local',
                'cn': 'Domain Users',
                'description': 'All Domain Users'
            }
        ]
        
        for group in groups:
            try:
                conn.add(
                    group['dn'],
                    ['groupOfNames', 'top'],
                    {
                        'cn': group['cn'],
                        'description': group['description'],
                        'member': LDAP_ADMIN_DN  # Initial member required
                    }
                )
                if conn.result['result'] == 0:
                    print(f"    ✓ Group '{group['cn']}' created")
                elif conn.result['result'] == 68:
                    print(f"    ℹ Group '{group['cn']}' already exists")
                else:
                    print(f"    ✗ Failed to create '{group['cn']}': {conn.result['description']}")
            except Exception as e:
                print(f"    ℹ Group '{group['cn']}' might already exist")
        
        # Step 4: Create Users
        print("\n[4] Creating users...")
        
        users = [
            {
                'dn': 'cn=Tal Sasson,ou=ADUsers,dc=mycompany,dc=local',
                'cn': 'Tal Sasson',
                'sn': 'Sasson',
                'givenName': 'Tal',
                'uid': 'tal.sasson',  # Using uid instead of sAMAccountName
                'mail': 'tal.sasson@mycompany.local',
                'userPassword': 'Tal@2025!',
                'description': 'Admin User'
            },
            {
                'dn': 'cn=Assaf Shaikevich,ou=ADUsers,dc=mycompany,dc=local',
                'cn': 'Assaf Shaikevich',
                'sn': 'Shaikevich',
                'givenName': 'Assaf',
                'uid': 'assaf.shaikevich',  # Using uid instead of sAMAccountName
                'mail': 'assaf.shaikevich@mycompany.local',
                'userPassword': 'Assaf@2025!',
                'description': 'QA User'
            }
        ]
        
        for user in users:
            try:
                user_dn = user.pop('dn')
                conn.add(
                    user_dn,
                    ['inetOrgPerson', 'organizationalPerson', 'person', 'top'],
                    user
                )
                if conn.result['result'] == 0:
                    print(f"    ✓ User '{user['cn']}' created")
                elif conn.result['result'] == 68:
                    print(f"    ℹ User '{user['cn']}' already exists")
                else:
                    print(f"    ✗ Failed to create '{user['cn']}': {conn.result['description']}")
            except Exception as e:
                print(f"    ℹ User '{user['cn']}' might already exist: {e}")
        
        # Step 5: Add users to groups
        print("\n[5] Adding users to groups (using member with full DN)...")
        
        group_assignments = [
            ('Admins', 'cn=Tal Sasson,ou=ADUsers,dc=mycompany,dc=local', 'Tal Sasson'),
            ('Domain Users', 'cn=Tal Sasson,ou=ADUsers,dc=mycompany,dc=local', 'Tal Sasson'),
            ('QA', 'cn=Assaf Shaikevich,ou=ADUsers,dc=mycompany,dc=local', 'Assaf Shaikevich'),
            ('Domain Users', 'cn=Assaf Shaikevich,ou=ADUsers,dc=mycompany,dc=local', 'Assaf Shaikevich')
        ]
        
        for group_name, user_dn, user_name in group_assignments:
            group_dn = f'cn={group_name},ou=ADGroups,dc=mycompany,dc=local'
            try:
                conn.modify(
                    group_dn,
                    {'member': [(MODIFY_ADD, [user_dn])]}
                )
                if conn.result['result'] == 0:
                    print(f"    ✓ Added {user_name} to {group_name}")
                elif conn.result['result'] == 20:  # Already a member
                    print(f"    ℹ {user_name} already in {group_name}")
                else:
                    print(f"    ✗ Failed to add {user_name} to {group_name}: {conn.result['description']}")
            except Exception as e:
                print(f"    ℹ Error adding {user_name} to {group_name}: {e}")
        
        conn.unbind()
        
        # Verification
        print("\n" + "="*70)
        print("VERIFICATION")
        print("="*70)
        
        conn = Connection(server, user=LDAP_ADMIN_DN, password=LDAP_ADMIN_PASSWORD, auto_bind=True)
        
        print("\nGroups created:")
        conn.search(
            search_base='ou=ADGroups,dc=mycompany,dc=local',
            search_filter='(objectClass=groupOfNames)',
            search_scope=SUBTREE,
            attributes=['cn', 'member', 'description']
        )
        
        for entry in conn.entries:
            print(f"\n  • {entry.cn}")
            if hasattr(entry, 'description'):
                print(f"    Description: {entry.description}")
            if hasattr(entry, 'member') and entry.member:
                print(f"    Members: {len(entry.member)}")
                for member in entry.member:
                    member_cn = member.split(',')[0].replace('cn=', '')
                    print(f"      - {member_cn}")
        
        print("\nUsers created:")
        conn.search(
            search_base='ou=ADUsers,dc=mycompany,dc=local',
            search_filter='(objectClass=inetOrgPerson)',
            search_scope=SUBTREE,
            attributes=['cn', 'uid', 'mail', 'description']
        )
        
        for entry in conn.entries:
            print(f"\n  • {entry.cn}")
            if hasattr(entry, 'uid'):
                print(f"    Username (uid): {entry.uid}")
            if hasattr(entry, 'mail'):
                print(f"    Email: {entry.mail}")
            if hasattr(entry, 'description'):
                print(f"    Description: {entry.description}")
        
        conn.unbind()
        
        print("\n" + "="*70)
        print("✓ SETUP COMPLETE!")
        print("="*70)
        print("\nActive Directory-style structure created:")
        print("  • Location: ou=ADUsers and ou=ADGroups")
        print("  • Groups: Admins, QA, Developers, Domain Users (groupOfNames)")
        print("  • Users: Tal Sasson, Assaf Shaikevich")
        print("  • Tal is in: Admins, Domain Users")
        print("  • Assaf is in: QA, Domain Users")
        print("\nCredentials:")
        print("  • tal.sasson / Tal@2025!")
        print("  • assaf.shaikevich / Assaf@2025!")
        print("\nNow run: python3 /home/claude/test_ad_style_fixed.py")
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    create_ad_style_structure()