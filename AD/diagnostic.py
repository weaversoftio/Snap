#!/usr/bin/env python3
"""
Diagnostic - Check what attributes users have
"""

from ldap3 import Server, Connection, SUBTREE

LDAP_SERVER = '192.168.33.209'
LDAP_PORT = 1389
LDAP_BASE_DN = 'dc=mycompany,dc=local'
LDAP_ADMIN_DN = 'cn=admin,dc=mycompany,dc=local'
LDAP_ADMIN_PASSWORD = 'Admin123!'

print("\n" + "="*70)
print("DIAGNOSTIC: Checking user attributes in LDAP")
print("="*70)

try:
    server = Server(LDAP_SERVER, port=LDAP_PORT)
    conn = Connection(server, user=LDAP_ADMIN_DN, password=LDAP_ADMIN_PASSWORD, auto_bind=True)
    
    # Search for all users
    conn.search(
        search_base=LDAP_BASE_DN,
        search_filter='(objectClass=inetOrgPerson)',
        search_scope=SUBTREE,
        attributes=['*']  # Get ALL attributes
    )
    
    print(f"\nFound {len(conn.entries)} users:\n")
    
    for entry in conn.entries:
        print("="*70)
        print(f"User: {entry.cn}")
        print("="*70)
        print(f"DN: {entry.entry_dn}")
        print("\nAll attributes:")
        
        # Print all attributes
        for attr in entry.entry_attributes:
            value = getattr(entry, attr)
            print(f"  {attr}: {value}")
        
        print()
    
    conn.unbind()
    
except Exception as e:
    print(f"Error: {str(e)}")
    import traceback
    traceback.print_exc()