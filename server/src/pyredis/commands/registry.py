"""Command Registry with declarative metadata, complexity annotations, and RBAC."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Union
from pyredis.core.exceptions import AuthError, CommandError, WrongTypeError
from pyredis.core.types import Role
from pyredis.storage.store import DataStore

# Hierarchy levels for RBAC: higher number = greater privilege
ROLE_HIERARCHY: Dict[Role, int] = {
    Role.READONLY: 1,
    Role.DEVELOPER: 2,
    Role.OPERATOR: 3,
    Role.ADMIN: 4,
}


@dataclass
class CommandContext:
    """Execution context provided to every command handler."""
    store: DataStore
    role: Role = Role.ADMIN
    client_id: Optional[str] = None
    authenticated: bool = True
    session_user: Optional[str] = None
    aof: Optional[Any] = None
    snapshot: Optional[Any] = None


@dataclass
class CommandDefinition:
    """Metadata and execution specification for a command."""
    name: str
    handler: Callable[..., Any]
    min_args: int
    max_args: Optional[int]  # None means unlimited
    required_role: Role
    complexity: str
    is_mutation: bool
    description: str


class CommandRegistry:
    """Central registry and dispatcher for all PyRedis commands."""

    def __init__(self) -> None:
        self._commands: Dict[str, CommandDefinition] = {}

    def register(
        self,
        name: str,
        min_args: int = 0,
        max_args: Optional[int] = None,
        role: Role = Role.DEVELOPER,
        complexity: str = "O(1)",
        is_mutation: bool = False,
        description: str = "",
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register a command handler."""
        cmd_name = name.upper()

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            definition = CommandDefinition(
                name=cmd_name,
                handler=func,
                min_args=min_args,
                max_args=max_args,
                required_role=role,
                complexity=complexity,
                is_mutation=is_mutation,
                description=description,
            )
            self._commands[cmd_name] = definition
            return func

        return decorator

    def get_definition(self, name: str) -> Optional[CommandDefinition]:
        """Retrieve command definition by name."""
        return self._commands.get(name.upper())

    def list_commands(self) -> List[CommandDefinition]:
        """List all registered command definitions."""
        return list(self._commands.values())

    def execute(
        self,
        name: str,
        args: List[Union[bytes, str]],
        context: CommandContext,
    ) -> Any:
        """Validate arity, verify caller role, and execute command."""
        cmd_name = name.upper()
        definition = self._commands.get(cmd_name)

        if not definition:
            raise CommandError(f"unknown command '{name}'")

        # 1. Check Role Permissions
        user_privilege = ROLE_HIERARCHY.get(context.role, 1)
        required_privilege = ROLE_HIERARCHY.get(definition.required_role, 2)
        if user_privilege < required_privilege:
            raise AuthError(
                f"NOPERM this user has no permissions to run the '{name.lower()}' command"
            )

        # 2. Validate Argument Count (Arity)
        arg_count = len(args)
        if arg_count < definition.min_args:
            raise CommandError(
                f"wrong number of arguments for '{name.lower()}' command"
            )
        if definition.max_args is not None and arg_count > definition.max_args:
            raise CommandError(
                f"wrong number of arguments for '{name.lower()}' command"
            )

        # 3. Execute Handler
        try:
            return definition.handler(args, context)
        except (WrongTypeError, CommandError, AuthError):
            raise
        except Exception as e:
            raise CommandError(f"ERR {str(e)}") from e


# Global command registry instance
registry = CommandRegistry()
command = registry.register
