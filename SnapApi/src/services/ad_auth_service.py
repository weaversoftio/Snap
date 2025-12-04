"""
Active Directory Authentication Service
Supports both OpenLDAP and real Active Directory authentication
"""

import logging
from typing import Dict, List, Optional
from ldap3 import Server, Connection, SUBTREE
from ldap3.core.exceptions import LDAPException
import os
import json

logger = logging.getLogger("automation_api")


class ADAuthService:
    """
    Active Directory Authentication Service
    Supports both OpenLDAP (uid, groupOfNames) and real AD (sAMAccountName, objectClass=group)
    """
    
    
    AD_CONFIG_PATH = "config/security/ad_config.json"
    
    @staticmethod
    def get_ad_config() -> Optional[Dict]:
        """Get app-level AD configuration"""
        try:
            if not os.path.exists(ADAuthService.AD_CONFIG_PATH):
                return None
            
            with open(ADAuthService.AD_CONFIG_PATH, "r") as f:
                ad_config = json.load(f)
            
            if not ad_config.get("ad_enabled", False):
                return None
            
            return {
                "ad_type": ad_config.get("ad_type"),
                "ad_server": ad_config.get("ad_server"),
                "ad_port": ad_config.get("ad_port", 389),
                "ad_base_dn": ad_config.get("ad_base_dn"),
                "ad_service_dn": ad_config.get("ad_service_dn"),
                "ad_service_password": ad_config.get("ad_service_password"),
                "ad_allowed_groups": ad_config.get("ad_allowed_groups", []),
                "ad_use_ssl": ad_config.get("ad_use_ssl", False)
            }
        except Exception as e:
            logger.error(f"Error loading AD config: {e}")
            return None
    
    @staticmethod
    def authenticate_and_authorize(username: str, password: str) -> Dict:
        """
        Authenticate and authorize user against AD
        
        Args:
            username: Username (uid for OpenLDAP, sAMAccountName for real AD)
            password: User's password
            
        Returns:
            dict with authentication result
        """
        ad_config = ADAuthService.get_ad_config()
        if not ad_config:
            return {
                'success': False,
                'access_granted': False,
                'message': 'AD not enabled',
                'fallback_to_local': True
            }
        
        try:
            # Determine port based on SSL setting
            port = ad_config.get("ad_port", 636 if ad_config.get("ad_use_ssl") else 389)
            if ad_config.get("ad_use_ssl") and port == 389:
                port = 636
            
            server = Server(ad_config["ad_server"], port=port, use_ssl=ad_config.get("ad_use_ssl", False))
            
            # STEP 1: Search for user
            logger.info(f"[AD Auth] Searching for user '{username}'")
            search_conn = Connection(
                server,
                user=ad_config["ad_service_dn"],
                password=ad_config["ad_service_password"],
                auto_bind=True
            )
            
            # Determine search filter based on AD type
            if ad_config["ad_type"] == "openldap":
                search_filter = f'(uid={username})'
                username_attr = 'uid'
            else:  # real_ad
                search_filter = f'(sAMAccountName={username})'
                username_attr = 'sAMAccountName'
            
            search_conn.search(
                search_base=ad_config["ad_base_dn"],
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=['cn', username_attr, 'mail', 'givenName', 'sn', 'displayName']
            )
            
            if not search_conn.entries:
                logger.info(f"[AD Auth] User '{username}' not found in AD")
                search_conn.unbind()
                return {
                    'success': False,
                    'access_granted': False,
                    'message': f"User '{username}' does not exist in AD",
                    'fallback_to_local': True
                }
            
            user_entry = search_conn.entries[0]
            user_dn = user_entry.entry_dn
            user_cn = user_entry.cn.value if hasattr(user_entry, 'cn') else username
            
            logger.info(f"[AD Auth] Found user: {user_cn} (DN: {user_dn})")
            
            # STEP 2: Authenticate user (bind with their credentials)
            try:
                user_conn = Connection(
                    server,
                    user=user_dn,
                    password=password,
                    auto_bind=True
                )
                user_conn.unbind()
                logger.info(f"[AD Auth] Password verified for user '{username}'")
            except LDAPException as e:
                logger.warning(f"[AD Auth] Invalid password for user '{username}': {e}")
                search_conn.unbind()
                return {
                    'success': False,
                    'access_granted': False,
                    'message': 'Invalid password',
                    'user_cn': user_cn,
                    'fallback_to_local': False  # Don't fallback on wrong password
                }
            
            # STEP 3: Get user's groups
            allowed_groups = ad_config.get("ad_allowed_groups") or []
            if not allowed_groups:
                logger.warning(f"[AD Auth] No allowed groups configured")
                search_conn.unbind()
                return {
                    'success': False,
                    'access_granted': False,
                    'message': 'No allowed groups configured',
                    'fallback_to_local': True
                }
            
            # Determine group search filter based on AD type
            if ad_config["ad_type"] == "openldap":
                group_filter = f'(&(objectClass=groupOfNames)(member={user_dn}))'
            else:  # real_ad
                group_filter = f'(&(objectClass=group)(member={user_dn}))'
            
            search_conn.search(
                search_base=ad_config["ad_base_dn"],
                search_filter=group_filter,
                search_scope=SUBTREE,
                attributes=['cn']
            )
            
            user_groups = [entry.cn.value for entry in search_conn.entries]
            logger.info(f"[AD Auth] User '{username}' is member of groups: {user_groups}")
            
            search_conn.unbind()
            
            # STEP 4: Check if user is in any allowed group
            has_access = any(group in user_groups for group in allowed_groups)
            
            if has_access:
                matching_groups = [g for g in user_groups if g in allowed_groups]
                logger.info(f"[AD Auth] Access granted to user '{username}' (groups: {matching_groups})")
                
                return {
                    'success': True,
                    'access_granted': True,
                    'user_cn': user_cn,
                    'user_dn': user_dn,
                    'username': username,
                    'groups': user_groups,
                    'matching_groups': matching_groups
                }
            else:
                logger.warning(f"[AD Auth] Access denied to user '{username}' - not in allowed groups")
                return {
                    'success': True,
                    'access_granted': False,
                    'user_cn': user_cn,
                    'user_dn': user_dn,
                    'username': username,
                    'groups': user_groups,
                    'message': 'User not in allowed groups',
                    'fallback_to_local': False  # Don't fallback if user exists but not authorized
                }
                
        except LDAPException as e:
            logger.error(f"[AD Auth] LDAP error for user '{username}': {e}")
            return {
                'success': False,
                'access_granted': False,
                'message': f'LDAP connection error: {str(e)}',
                'fallback_to_local': True
            }
        except Exception as e:
            logger.error(f"[AD Auth] Error authenticating user '{username}': {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'access_granted': False,
                'message': str(e),
                'fallback_to_local': True
            }
    
    @staticmethod
    def test_connection(ad_config: Optional[Dict] = None) -> Dict:
        """
        Test AD connection
        
        Args:
            ad_config: Optional AD config dict (if not provided, loads from app config)
            
        Returns:
            dict with connection test result
        """
        if not ad_config:
            ad_config = ADAuthService.get_ad_config()
            if not ad_config:
                return {
                    'success': False,
                    'message': 'AD not enabled'
                }
        
        try:
            port = ad_config.get("ad_port", 636 if ad_config.get("ad_use_ssl") else 389)
            if ad_config.get("ad_use_ssl") and port == 389:
                port = 636
            
            server = Server(ad_config["ad_server"], port=port, use_ssl=ad_config.get("ad_use_ssl", False))
            conn = Connection(
                server,
                user=ad_config["ad_service_dn"],
                password=ad_config["ad_service_password"],
                auto_bind=True
            )
            
            # Try a simple search to verify connection
            conn.search(
                search_base=ad_config["ad_base_dn"],
                search_filter='(objectClass=*)',
                search_scope=SUBTREE,
                size_limit=1
            )
            
            conn.unbind()
            
            return {
                'success': True,
                'message': 'Connection successful'
            }
        except LDAPException as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    @staticmethod
    def get_available_groups() -> Dict:
        """
        Get all available groups from AD for selection UI
        
        Returns:
            dict with list of groups
        """
        ad_config = ADAuthService.get_ad_config()
        if not ad_config:
            return {
                'success': False,
                'message': 'AD not enabled',
                'groups': []
            }
        
        try:
            port = ad_config.get("ad_port", 636 if ad_config.get("ad_use_ssl") else 389)
            if ad_config.get("ad_use_ssl") and port == 389:
                port = 636
            
            server = Server(ad_config["ad_server"], port=port, use_ssl=ad_config.get("ad_use_ssl", False))
            conn = Connection(
                server,
                user=ad_config["ad_service_dn"],
                password=ad_config["ad_service_password"],
                auto_bind=True
            )
            
            # Determine group filter based on AD type
            if ad_config["ad_type"] == "openldap":
                group_filter = '(objectClass=groupOfNames)'
            else:  # real_ad
                group_filter = '(objectClass=group)'
            
            logger.info(f"[AD Groups] Searching for groups with filter: {group_filter}")
            logger.info(f"[AD Groups] Search base: {ad_config['ad_base_dn']}")
            
            # Try searching from base DN first
            conn.search(
                search_base=ad_config["ad_base_dn"],
                search_filter=group_filter,
                search_scope=SUBTREE,
                attributes=['cn', 'description']
            )
            
            entries = list(conn.entries)  # Store entries from first search
            logger.info(f"[AD Groups] Found {len(entries)} entries from base DN")
            
            # If no groups found and using OpenLDAP, try searching in ADGroups OU specifically
            if len(entries) == 0 and ad_config["ad_type"] == "openldap":
                # Try to construct ADGroups OU path
                base_dn = ad_config["ad_base_dn"]
                groups_ou = f"ou=ADGroups,{base_dn}"
                logger.info(f"[AD Groups] No groups found, trying specific OU: {groups_ou}")
                try:
                    conn.search(
                        search_base=groups_ou,
                        search_filter=group_filter,
                        search_scope=SUBTREE,
                        attributes=['cn', 'description']
                    )
                    entries = list(conn.entries)  # Use entries from ADGroups OU search
                    logger.info(f"[AD Groups] Found {len(entries)} entries from ADGroups OU")
                except Exception as e:
                    logger.warning(f"[AD Groups] Error searching in ADGroups OU: {e}")
            
            groups = []
            for entry in entries:
                try:
                    # Handle different ways cn might be stored
                    if hasattr(entry, 'cn'):
                        if hasattr(entry.cn, 'value'):
                            group_name = entry.cn.value
                        elif isinstance(entry.cn, list) and len(entry.cn) > 0:
                            group_name = entry.cn[0] if isinstance(entry.cn[0], str) else str(entry.cn[0])
                        else:
                            group_name = str(entry.cn)
                    else:
                        # Try to get cn from entry_dn
                        dn_parts = entry.entry_dn.split(',')
                        for part in dn_parts:
                            if part.startswith('cn='):
                                group_name = part.replace('cn=', '')
                                break
                        else:
                            group_name = None
                    
                    if group_name:
                        # Handle description similarly
                        description = ''
                        if hasattr(entry, 'description'):
                            if hasattr(entry.description, 'value'):
                                description = entry.description.value
                            elif isinstance(entry.description, list) and len(entry.description) > 0:
                                description = entry.description[0] if isinstance(entry.description[0], str) else str(entry.description[0])
                            else:
                                description = str(entry.description) if entry.description else ''
                        
                        groups.append({
                            'name': group_name,
                            'description': description
                        })
                        logger.info(f"[AD Groups] Added group: {group_name}")
                except Exception as e:
                    logger.warning(f"[AD Groups] Error processing entry {entry.entry_dn}: {e}")
                    continue
            
            conn.unbind()
            
            logger.info(f"[AD Groups] Returning {len(groups)} groups")
            
            if len(groups) == 0:
                logger.warning(f"[AD Groups] No groups found. Search filter: {group_filter}, Base DN: {ad_config['ad_base_dn']}")
                return {
                    'success': True,
                    'groups': [],
                    'message': f'No groups found. Searched with filter "{group_filter}" from base "{ad_config["ad_base_dn"]}". Make sure groups exist and are accessible.'
                }
            
            return {
                'success': True,
                'groups': groups
            }
        except LDAPException as e:
            return {
                'success': False,
                'message': f'LDAP error: {str(e)}',
                'groups': []
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'groups': []
            }

