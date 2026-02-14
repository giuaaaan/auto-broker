"""
AUTO-BROKER RBAC Matrix
Role-Based Access Control with resource-level permissions
Zero Trust - P0 Critical
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Set, Optional, Any
from functools import wraps
import logging

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class Resource(str, Enum):
    """Protected resources in AUTO-BROKER."""
    LEADS = "leads"
    PRICING = "pricing"
    SHIPMENTS = "shipments"
    CONTRACTS = "contracts"
    PAYMENTS = "payments"
    AGENTS = "agents"
    CONFIG = "config"
    USERS = "users"
    AUDIT = "audit"
    SECRETS = "secrets"


class Action(str, Enum):
    """CRUD actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"  # For actions like override, block


class PermissionLevel(Enum):
    """Permission granularity."""
    NONE = 0
    OWN = 1      # Only resources owned by user
    ORG = 2      # All resources in organization
    GLOBAL = 3   # All resources (admin only)


@dataclass(frozen=True)
class Permission:
    """Permission tuple (resource, action, level)."""
    resource: Resource
    action: Action
    level: PermissionLevel


class Role(str, Enum):
    """Enterprise roles."""
    BROKER = "broker"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


class RBACMatrix:
    """
    Programmatic RBAC matrix for AUTO-BROKER.
    
    Broker: Own leads only, read-only pricing, no system config
    Supervisor: Org-wide read, override AI, escalation management
    Admin: Full access, secret rotation, chaos testing
    """
    
    # Role definitions with permissions
    _MATRIX: Dict[Role, Set[Permission]] = {
        Role.BROKER: {
            # Leads: CRUD only own
            Permission(Resource.LEADS, Action.CREATE, PermissionLevel.OWN),
            Permission(Resource.LEADS, Action.READ, PermissionLevel.OWN),
            Permission(Resource.LEADS, Action.UPDATE, PermissionLevel.OWN),
            Permission(Resource.LEADS, Action.DELETE, PermissionLevel.OWN),
            
            # Pricing: Read-only
            Permission(Resource.PRICING, Action.READ, PermissionLevel.ORG),
            
            # Shipments: Own only
            Permission(Resource.SHIPMENTS, Action.CREATE, PermissionLevel.OWN),
            Permission(Resource.SHIPMENTS, Action.READ, PermissionLevel.OWN),
            Permission(Resource.SHIPMENTS, Action.UPDATE, PermissionLevel.OWN),
            
            # Contracts: Read own
            Permission(Resource.CONTRACTS, Action.READ, PermissionLevel.OWN),
            Permission(Resource.CONTRACTS, Action.CREATE, PermissionLevel.OWN),
            
            # Payments: Read own
            Permission(Resource.PAYMENTS, Action.READ, PermissionLevel.OWN),
            
            # Agents: Read (status only)
            Permission(Resource.AGENTS, Action.READ, PermissionLevel.ORG),
        },
        
        Role.SUPERVISOR: {
            # Leads: Org-wide access
            Permission(Resource.LEADS, Action.CREATE, PermissionLevel.ORG),
            Permission(Resource.LEADS, Action.READ, PermissionLevel.ORG),
            Permission(Resource.LEADS, Action.UPDATE, PermissionLevel.ORG),
            Permission(Resource.LEADS, Action.DELETE, PermissionLevel.ORG),
            
            # Pricing: Full access
            Permission(Resource.PRICING, Action.CREATE, PermissionLevel.ORG),
            Permission(Resource.PRICING, Action.READ, PermissionLevel.ORG),
            Permission(Resource.PRICING, Action.UPDATE, PermissionLevel.ORG),
            Permission(Resource.PRICING, Action.EXECUTE, PermissionLevel.ORG),  # Override
            
            # Shipments: Org-wide
            Permission(Resource.SHIPMENTS, Action.CREATE, PermissionLevel.ORG),
            Permission(Resource.SHIPMENTS, Action.READ, PermissionLevel.ORG),
            Permission(Resource.SHIPMENTS, Action.UPDATE, PermissionLevel.ORG),
            Permission(Resource.SHIPMENTS, Action.EXECUTE, PermissionLevel.ORG),  # Block
            
            # Contracts: Org-wide
            Permission(Resource.CONTRACTS, Action.READ, PermissionLevel.ORG),
            
            # Payments: Read org
            Permission(Resource.PAYMENTS, Action.READ, PermissionLevel.ORG),
            
            # Agents: Read org
            Permission(Resource.AGENTS, Action.READ, PermissionLevel.ORG),
            Permission(Resource.AGENTS, Action.EXECUTE, PermissionLevel.ORG),  # Override
            
            # Users: Read org
            Permission(Resource.USERS, Action.READ, PermissionLevel.ORG),
            
            # Audit: Read org
            Permission(Resource.AUDIT, Action.READ, PermissionLevel.ORG),
        },
        
        Role.ADMIN: {
            # All resources, all actions, global level
            Permission(Resource.LEADS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.LEADS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.LEADS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.LEADS, Action.DELETE, PermissionLevel.GLOBAL),
            
            Permission(Resource.PRICING, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.PRICING, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.PRICING, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.PRICING, Action.DELETE, PermissionLevel.GLOBAL),
            Permission(Resource.PRICING, Action.EXECUTE, PermissionLevel.GLOBAL),
            
            Permission(Resource.SHIPMENTS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.SHIPMENTS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.SHIPMENTS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.SHIPMENTS, Action.DELETE, PermissionLevel.GLOBAL),
            Permission(Resource.SHIPMENTS, Action.EXECUTE, PermissionLevel.GLOBAL),
            
            Permission(Resource.CONTRACTS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.CONTRACTS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.CONTRACTS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.CONTRACTS, Action.DELETE, PermissionLevel.GLOBAL),
            
            Permission(Resource.PAYMENTS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.PAYMENTS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.PAYMENTS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.PAYMENTS, Action.DELETE, PermissionLevel.GLOBAL),
            
            Permission(Resource.AGENTS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.AGENTS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.AGENTS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.AGENTS, Action.DELETE, PermissionLevel.GLOBAL),
            Permission(Resource.AGENTS, Action.EXECUTE, PermissionLevel.GLOBAL),
            
            # Config: Only admin
            Permission(Resource.CONFIG, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.CONFIG, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.CONFIG, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.CONFIG, Action.DELETE, PermissionLevel.GLOBAL),
            
            # Users: Only admin
            Permission(Resource.USERS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.USERS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.USERS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.USERS, Action.DELETE, PermissionLevel.GLOBAL),
            
            # Audit: Only admin
            Permission(Resource.AUDIT, Action.READ, PermissionLevel.GLOBAL),
            
            # Secrets: Only admin
            Permission(Resource.SECRETS, Action.CREATE, PermissionLevel.GLOBAL),
            Permission(Resource.SECRETS, Action.READ, PermissionLevel.GLOBAL),
            Permission(Resource.SECRETS, Action.UPDATE, PermissionLevel.GLOBAL),
            Permission(Resource.SECRETS, Action.DELETE, PermissionLevel.GLOBAL),
            Permission(Resource.SECRETS, Action.EXECUTE, PermissionLevel.GLOBAL),  # Rotate
        }
    }
    
    @classmethod
    def has_permission(
        cls,
        role: Role,
        resource: Resource,
        action: Action,
        required_level: PermissionLevel = PermissionLevel.OWN
    ) -> bool:
        """Check if role has permission for resource/action at required level."""
        role_perms = cls._MATRIX.get(role, set())
        
        for perm in role_perms:
            if perm.resource == resource and perm.action == action:
                if perm.level.value >= required_level.value:
                    return True
        
        return False
    
    @classmethod
    def check_permission(
        cls,
        role: Role,
        resource: Resource,
        action: Action,
        user_org_id: Optional[str] = None,
        resource_org_id: Optional[str] = None,
        user_id: Optional[str] = None,
        resource_owner_id: Optional[str] = None
    ):
        """
        Check permission with ownership validation.
        
        Raises HTTPException if access denied.
        """
        # Get permission level for role
        role_perms = cls._MATRIX.get(role, set())
        perm_level = PermissionLevel.NONE
        
        for perm in role_perms:
            if perm.resource == resource and perm.action == action:
                perm_level = perm.level
                break
        
        if perm_level == PermissionLevel.NONE:
            logger.warning(
                f"Access denied: {role} has no {action} permission on {resource}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions for {action} on {resource}"
            )
        
        # Check ownership/org constraints
        if perm_level == PermissionLevel.OWN:
            if user_id != resource_owner_id:
                logger.warning(
                    f"Access denied: {role} can only access own {resource}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access limited to own resources only"
                )
        
        elif perm_level == PermissionLevel.ORG:
            if user_org_id != resource_org_id:
                logger.warning(
                    f"Access denied: {role} can only access org {resource}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access limited to organization resources only"
                )
        
        # GLOBAL: No additional checks
        return True
    
    @classmethod
    def get_role_permissions(cls, role: Role) -> Dict[str, Any]:
        """Get human-readable permission matrix for role."""
        perms = cls._MATRIX.get(role, set())
        result = {}
        
        for perm in perms:
            if perm.resource not in result:
                result[perm.resource] = {}
            result[perm.resource][perm.action] = perm.level.name
        
        return result


# API Gateway Enforcement Decorators
def enforce_rbac(resource: Resource, action: Action):
    """Decorator to enforce RBAC at API endpoint level."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user from kwargs (injected by FastAPI)
            user = kwargs.get("current_user")
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            from security.identity_provider import Role
            role = Role(user.role)
            
            # Check permission
            RBACMatrix.check_permission(
                role=role,
                resource=resource,
                action=action,
                user_org_id=getattr(user, "organization_id", None),
                resource_org_id=kwargs.get("org_id"),
                user_id=user.sub,
                resource_owner_id=kwargs.get("owner_id")
            )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Kong/AWS API Gateway Policy Export
class PolicyExporter:
    """Export RBAC policies for API Gateway configuration."""
    
    @staticmethod
    def generate_kong_policies() -> List[Dict]:
        """Generate Kong Gateway ACL policies."""
        policies = []
        
        for role in Role:
            role_perms = RBACMatrix._MATRIX.get(role, set())
            paths = set()
            
            # Map resources to API paths
            resource_paths = {
                Resource.LEADS: ["/api/v1/leads", "/api/v1/leads/*"],
                Resource.PRICING: ["/api/v1/pricing", "/api/v1/pricing/*"],
                Resource.SHIPMENTS: ["/api/v1/shipments", "/api/v1/shipments/*"],
                Resource.CONTRACTS: ["/api/v1/contracts", "/api/v1/contracts/*"],
                Resource.PAYMENTS: ["/api/v1/payments", "/api/v1/payments/*"],
                Resource.AGENTS: ["/api/v1/agents", "/api/v1/agents/*"],
                Resource.CONFIG: ["/api/v1/config", "/api/v1/config/*"],
                Resource.USERS: ["/api/v1/users", "/api/v1/users/*"],
                Resource.AUDIT: ["/api/v1/audit", "/api/v1/audit/*"],
                Resource.SECRETS: ["/api/v1/secrets", "/api/v1/secrets/*"],
            }
            
            for perm in role_perms:
                paths.update(resource_paths.get(perm.resource, []))
            
            policies.append({
                "role": role.value,
                "allowed_paths": list(paths),
                "description": f"Policy for {role.value}"
            })
        
        return policies
    
    @staticmethod
    def generate_aws_iam_policy(role: Role) -> Dict:
        """Generate AWS IAM policy JSON for role."""
        role_perms = RBACMatrix._MATRIX.get(role, set())
        
        statements = []
        resource_actions = {
            Resource.LEADS: "auto-broker:leads",
            Resource.PRICING: "auto-broker:pricing",
            Resource.SHIPMENTS: "auto-broker:shipments",
            Resource.CONTRACTS: "auto-broker:contracts",
            Resource.PAYMENTS: "auto-broker:payments",
            Resource.AGENTS: "auto-broker:agents",
            Resource.CONFIG: "auto-broker:config",
            Resource.USERS: "auto-broker:users",
            Resource.AUDIT: "auto-broker:audit",
            Resource.SECRETS: "auto-broker:secrets",
        }
        
        actions = set()
        for perm in role_perms:
            aws_action = f"{resource_actions.get(perm.resource)}:{perm.action}"
            actions.add(aws_action)
        
        return {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": list(actions),
                "Resource": "*"
            }]
        }
