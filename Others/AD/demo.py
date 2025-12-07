#!/usr/bin/env python3
"""
SCRIPT 2: Test Active Directory-Style Authentication (OpenLDAP Compatible)
Uses uid instead of sAMAccountName, but behaves exactly like AD
"""

from ldap3 import Server, Connection, SUBTREE
from ldap3.core.exceptions import LDAPException

LDAP_SERVER = '192.168.33.209'
LDAP_PORT = 1389
LDAP_BASE_DN = 'dc=mycompany,dc=local'
LDAP_ADMIN_DN = 'cn=admin,dc=mycompany,dc=local'
LDAP_ADMIN_PASSWORD = 'Admin123!'

# Application requires Admins group
REQUIRED_GROUP = 'Admins'


class ADStyleAuthManager:
    """
    Active Directory-Style Authentication Manager
    Uses groupOfNames with member (full DN) - exactly like AD
    Uses uid for username (standard LDAP, AD uses sAMAccountName)
    """
    
    def __init__(self, server, port, base_dn, service_dn, service_password):
        self.server = server
        self.port = port
        self.base_dn = base_dn
        self.service_dn = service_dn
        self.service_password = service_password
    
    def authenticate_and_authorize(self, username, password, required_groups):
        """
        Authenticate and authorize user (AD-style)
        
        Args:
            username: uid (like 'tal.sasson') - in real AD this would be sAMAccountName
            password: User's password
            required_groups: List of group names (user needs to be in at least one)
            
        Returns:
            dict with authentication result
        """
        print(f"\n{'='*70}")
        print(f"LOGIN ATTEMPT (AD-Style)")
        print('='*70)
        print(f"Username: {username}")
        print(f"Required groups: {', '.join(required_groups)}")
        print('='*70)
        
        try:
            server = Server(self.server, port=self.port)
            
            # STEP 1: Search for user by uid (in real AD: sAMAccountName)
            print(f"\n[Step 1] Searching for user by uid (AD uses sAMAccountName)...")
            search_conn = Connection(
                server,
                user=self.service_dn,
                password=self.service_password,
                auto_bind=True
            )
            
            search_conn.search(
                search_base=self.base_dn,
                search_filter=f'(uid={username})',  # Real AD: sAMAccountName
                search_scope=SUBTREE,
                attributes=['cn', 'uid', 'mail', 'givenName', 'sn']
            )
            
            if not search_conn.entries:
                print(f"    ✗ User '{username}' not found")
                search_conn.unbind()
                return {
                    'success': False,
                    'access_granted': False,
                    'message': f"User '{username}' does not exist"
                }
            
            user_entry = search_conn.entries[0]
            user_dn = user_entry.entry_dn
            user_cn = user_entry.cn.value
            
            print(f"    ✓ Found user: {user_cn}")
            print(f"      DN: {user_dn}")
            print(f"      Username: {user_entry.uid.value}")
            
            # STEP 2: Authenticate user (bind with their credentials)
            print(f"\n[Step 2] Verifying password...")
            try:
                user_conn = Connection(
                    server,
                    user=user_dn,
                    password=password,
                    auto_bind=True
                )
                user_conn.unbind()
                print(f"    ✓ Password is correct - User authenticated")
            except LDAPException:
                print(f"    ✗ Password is incorrect")
                search_conn.unbind()
                return {
                    'success': False,
                    'access_granted': False,
                    'message': 'Invalid password',
                    'user_cn': user_cn
                }
            
            # STEP 3: Get user's groups (AD-style: groupOfNames with member=DN)
            print(f"\n[Step 3] Checking group memberships (AD-style)...")
            print(f"    Searching: (&(objectClass=groupOfNames)(member={user_dn}))")
            print(f"    This is EXACTLY how Active Directory works!")
            
            search_conn.search(
                search_base=self.base_dn,
                search_filter=f'(&(objectClass=groupOfNames)(member={user_dn}))',
                search_scope=SUBTREE,
                attributes=['cn']
            )
            
            user_groups = [entry.cn.value for entry in search_conn.entries]
            
            if user_groups:
                print(f"    User is member of {len(user_groups)} group(s):")
                for group in user_groups:
                    print(f"      • {group}")
            else:
                print(f"    User is not a member of any groups")
            
            search_conn.unbind()
            
            # STEP 4: Check if user is in any required group
            print(f"\n[Step 4] Authorization check...")
            has_access = any(group in user_groups for group in required_groups)
            
            if has_access:
                matching_groups = [g for g in user_groups if g in required_groups]
                print(f"    ✓ User IS in required group(s): {', '.join(matching_groups)}")
                print(f"\n{'='*70}")
                print(f"✓✓✓ ACCESS GRANTED ✓✓✓")
                print(f"{'='*70}")
                print(f"Welcome, {user_cn}!")
                print(f"You have been authenticated and authorized.")
                print('='*70)
                
                return {
                    'success': True,
                    'access_granted': True,
                    'user_cn': user_cn,
                    'user_dn': user_dn,
                    'username': username,
                    'groups': user_groups
                }
            else:
                print(f"    ✗ User is NOT in any required group")
                print(f"\n{'='*70}")
                print(f"✗✗✗ ACCESS DENIED ✗✗✗")
                print(f"{'='*70}")
                print(f"Sorry, {user_cn}.")
                print(f"Required groups: {', '.join(required_groups)}")
                print(f"Your groups: {', '.join(user_groups) if user_groups else '(none)'}")
                print('='*70)
                
                return {
                    'success': True,
                    'access_granted': False,
                    'user_cn': user_cn,
                    'user_dn': user_dn,
                    'username': username,
                    'groups': user_groups,
                    'message': 'User not in required groups'
                }
                
        except Exception as e:
            print(f"\n✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'access_granted': False,
                'message': str(e)
            }


def run_tests():
    """Run comprehensive tests"""
    
    print("\n" + "#"*70)
    print("# TESTING ACTIVE DIRECTORY-STYLE AUTHENTICATION")
    print("#"*70)
    print(f"\nLDAP Server: {LDAP_SERVER}:{LDAP_PORT}")
    print(f"Required Group: {REQUIRED_GROUP}")
    print("\nThis behaves EXACTLY like Active Directory:")
    print("  • Uses groupOfNames (like AD's 'group' objectClass)")
    print("  • Uses member attribute with full DN (exactly like AD)")
    print("  • Searches: (&(objectClass=groupOfNames)(member=USER_DN))")
    
    # Initialize manager
    auth_manager = ADStyleAuthManager(
        server=LDAP_SERVER,
        port=LDAP_PORT,
        base_dn=LDAP_BASE_DN,
        service_dn=LDAP_ADMIN_DN,
        service_password=LDAP_ADMIN_PASSWORD
    )
    
    # Test scenarios
    print("\n\n" + "#"*70)
    print("# AUTOMATED TESTS")
    print("#"*70)
    
    # TEST 1: Tal Sasson with correct password (should PASS - he's in Admins)
    print("\n\n" + "="*70)
    print("TEST 1: Tal Sasson (Admins member) - Expected: GRANTED")
    print("="*70)
    result1 = auth_manager.authenticate_and_authorize(
        username='tal.sasson',
        password='Tal@2025!',
        required_groups=[REQUIRED_GROUP]
    )
    
    # TEST 2: Assaf with correct password (should FAIL - he's in QA, not Admins)
    print("\n\n" + "="*70)
    print("TEST 2: Assaf Shaikevich (QA member) - Expected: DENIED")
    print("="*70)
    result2 = auth_manager.authenticate_and_authorize(
        username='assaf.shaikevich',
        password='Assaf@2025!',
        required_groups=[REQUIRED_GROUP]
    )
    
    # TEST 3: Tal with wrong password (should FAIL)
    print("\n\n" + "="*70)
    print("TEST 3: Tal Sasson - Wrong password - Expected: DENIED")
    print("="*70)
    result3 = auth_manager.authenticate_and_authorize(
        username='tal.sasson',
        password='WrongPassword',
        required_groups=[REQUIRED_GROUP]
    )
    
    # TEST 4: Non-existent user (should FAIL)
    print("\n\n" + "="*70)
    print("TEST 4: Non-existent user - Expected: DENIED")
    print("="*70)
    result4 = auth_manager.authenticate_and_authorize(
        username='nonexistent',
        password='Password123',
        required_groups=[REQUIRED_GROUP]
    )
    
    # TEST 5: Check with multiple allowed groups
    print("\n\n" + "="*70)
    print("TEST 5: Assaf with multiple allowed groups (QA or Admins)")
    print("="*70)
    result5 = auth_manager.authenticate_and_authorize(
        username='assaf.shaikevich',
        password='Assaf@2025!',
        required_groups=['Admins', 'QA']  # Allow either group
    )
    
    # Summary
    print("\n\n" + "#"*70)
    print("# TEST SUMMARY")
    print("#"*70)
    
    tests = [
        ("Tal with correct password (Admins)", result1.get('access_granted', False), True),
        ("Assaf with correct password (QA only)", result2.get('access_granted', False), False),
        ("Tal with wrong password", result3.get('access_granted', False), False),
        ("Non-existent user", result4.get('access_granted', False), False),
        ("Assaf with QA allowed", result5.get('access_granted', False), True),
    ]
    
    passed = 0
    for test_name, actual, expected in tests:
        test_passed = (actual == expected)
        if test_passed:
            passed += 1
        status = "✓ PASS" if passed else "✗ FAIL"
        result = "GRANTED" if actual else "DENIED"
        print(f"{status} - {test_name}: {result}")
    
    print(f"\nTotal: {passed}/{len(tests)} tests passed")
    
    # Usage example
    print("\n\n" + "#"*70)
    print("# PRODUCTION CODE FOR REAL ACTIVE DIRECTORY")
    print("#"*70)
    print("""
When deploying with customer's REAL Active Directory, the ONLY change is:

Search filter changes from:
    (uid={username})              # OpenLDAP
to:
    (sAMAccountName={username})   # Real Active Directory

Everything else is IDENTICAL:
    • Group search: (&(objectClass=group)(member={user_dn}))
    • Member attribute: full DN
    • Authentication: bind with user DN and password

Example for real AD:

class RealADAuthManager(ADStyleAuthManager):
    def authenticate_and_authorize(self, username, password, required_groups):
        # Only this search filter changes:
        search_filter = f'(sAMAccountName={username})'  # Instead of uid
        
        # And group objectClass:
        group_filter = f'(&(objectClass=group)(member={user_dn}))'  # Instead of groupOfNames
        
        # Everything else is THE SAME

Connection parameters for customer's AD:
    server='ad.customer.com'
    port=389  # or 636 for LDAPS
    base_dn='DC=customer,DC=com'
    service_dn='CN=ServiceAccount,CN=Users,DC=customer,DC=com'
    service_password='password from customer'
    """)
    
    print("\n" + "#"*70)
    print("# CREDENTIALS FOR TESTING")
    print("#"*70)
    print("""
Tal Sasson (Admin):
  Username: tal.sasson
  Password: Tal@2025!
  Groups: Admins, Domain Users
  Expected: ACCESS GRANTED
  
Assaf Shaikevich (QA):
  Username: assaf.shaikevich
  Password: Assaf@2025!
  Groups: QA, Domain Users
  Expected: ACCESS DENIED (not in Admins group)
    """)


if __name__ == "__main__":
    try:
        run_tests()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()