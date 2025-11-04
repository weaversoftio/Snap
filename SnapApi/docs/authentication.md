# Authentication

Authentication methods and security configuration for SNAP.

## Authentication Methods

### Token-based Authentication
SNAP uses JWT (JSON Web Tokens) for API authentication.

#### Getting a Token
```bash
curl -X POST http://localhost:8000/config/user/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "securepassword"
  }'
```

#### Using the Token
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/checkpoint/list
```

### Session-based Authentication
For web interface access:
1. Login via web interface
2. Session cookie is automatically managed
3. No manual token handling required

## User Management

### Creating Users
```bash
curl -X POST http://localhost:8000/config/user/create \
  -H "Content-Type: application/json" \
  -d '{
    "username": "operator",
    "password": "securepassword",
    "email": "operator@company.com",
    "role": "operator"
  }'
```

### User Roles
- **Administrator**: Full system access
- **Operator**: Checkpoint operations
- **Viewer**: Read-only access

### Updating Users
```bash
curl -X PUT http://localhost:8000/config/user/update \
  -H "Content-Type: application/json" \
  -d '{
    "username": "operator",
    "email": "newemail@company.com",
    "role": "administrator"
  }'
```

## Security Configuration

### Password Requirements
- Minimum 8 characters
- Must contain uppercase and lowercase letters
- Must contain numbers
- Must contain special characters

### Token Configuration
```json
{
  "token_expiry": 3600,
  "refresh_token_expiry": 86400,
  "max_login_attempts": 5,
  "lockout_duration": 900
}
```

### Session Configuration
```json
{
  "session_timeout": 1800,
  "session_secure": true,
  "session_httponly": true,
  "session_samesite": "strict"
}
```

## Enterprise Authentication

### LDAP Integration
```json
{
  "ldap_server": "ldap://ldap.company.com:389",
  "ldap_base_dn": "ou=users,dc=company,dc=com",
  "ldap_bind_dn": "cn=admin,dc=company,dc=com",
  "ldap_bind_password": "password"
}
```

### Active Directory Integration
```json
{
  "ad_server": "ldap://ad.company.com:389",
  "ad_domain": "company.com",
  "ad_base_dn": "dc=company,dc=com"
}
```

### OAuth Integration
```json
{
  "oauth_provider": "github",
  "oauth_client_id": "your_client_id",
  "oauth_client_secret": "your_client_secret",
  "oauth_redirect_uri": "http://localhost:3000/auth/callback"
}
```

## API Security

### HTTPS Configuration
```yaml
environment:
  - SSL_CERT_PATH=/app/cert.pem
  - SSL_KEY_PATH=/app/key.pem
  - FORCE_HTTPS=true
```

### CORS Configuration
```json
{
  "allowed_origins": ["http://localhost:3000", "https://app.company.com"],
  "allowed_methods": ["GET", "POST", "PUT", "DELETE"],
  "allowed_headers": ["Content-Type", "Authorization"],
  "allow_credentials": true
}
```

## Audit Logging

### Authentication Events
- Login attempts (success/failure)
- Token generation and refresh
- Password changes
- User creation and deletion

### API Access Events
- API endpoint access
- Request parameters
- Response status codes
- User identification

### Security Events
- Failed login attempts
- Suspicious activity
- Permission violations
- System access attempts

## Best Practices

### Token Management
- Use short-lived tokens
- Implement token refresh
- Store tokens securely
- Monitor token usage

### Password Security
- Enforce strong passwords
- Implement password rotation
- Use password hashing
- Monitor password changes

### Access Control
- Principle of least privilege
- Regular access reviews
- Role-based permissions
- Audit trail maintenance
