from __future__ import annotations
from typing import Any, Dict, List, Tuple, Union, TYPE_CHECKING, Callable

from .base_core import InvokableApplicationCommand, _get_overridden_method
from .errors import *

from disnake.app_commands import SlashCommand, Option
from disnake.enums import OptionType

import asyncio

if TYPE_CHECKING:
    from disnake.interactions import ApplicationCommandInteraction

__all__ = (
    'InvokableSlashCommand',
    'SubCommandGroup',
    'SubCommand',
    'slash_command'
)


def options_as_route(options: Dict[str, Any]) -> Tuple[Tuple[str, ...], Dict[str, Any]]:
    if not options:
        return (), {}
    name, value = next(iter(options.items()))
    if isinstance(value, dict):
        chain, kwargs = options_as_route(value)
        return (name,) + chain, kwargs
    return (), options


class SubCommandGroup(InvokableApplicationCommand):
    def __init__(self, func, *, name: str = None, **kwargs):
        super().__init__(func, name=name, **kwargs)
        self.children: Dict[str, SubCommand] = {}
        self.option = Option(
            name=self.name,
            description='-',
            type=OptionType.sub_command_group,
            options=[]
        )
        self.qualified_name: str = None

    def sub_command(
        self,
        name: str = None,
        description: str = None,
        options: list = None,
        connectors: dict = None,
        **kwargs
    ) -> Callable:
        """
        A decorator that creates a subcommand in the
        subcommand group.
        Parameters are the same as in :class:`InvokableSlashCommand.sub_command`

        Returns
        --------
        Callable[..., :class:`SubCommand`]
            A decorator that converts the provided method into a SubCommand, adds it to the bot, then returns it.
        """

        def decorator(func) -> SubCommand:
            new_func = SubCommand(
                func,
                name=name,
                description=description,
                options=options,
                connectors=connectors,
                **kwargs
            )
            qualified_name = self.qualified_name or self.name
            new_func.qualified_name = f'{qualified_name} {new_func.name}'
            self.children[new_func.name] = new_func
            self.option.options.append(new_func.option)
            return new_func
        return decorator


class SubCommand(InvokableApplicationCommand):
    def __init__(
        self,
        func,
        *,
        name: str = None,
        description: str = None,
        options: list = None,
        connectors: Dict[str, str] = None,
        **kwargs
    ):
        super().__init__(func, name=name, **kwargs)
        self.connectors: Dict[str, str] = connectors
        self.option = Option(
            name=self.name,
            description=description or '-',
            type=OptionType.sub_command,
            options=options
        )
        self.qualified_name = None


class InvokableSlashCommand(InvokableApplicationCommand):
    def __init__(
        self,
        func,
        *,
        name: str = None,
        description: str = None,
        options: List[Option] = None,
        default_permission: bool = True,
        guild_ids: List[int] = None,
        connectors: Dict[str, str] = None,
        auto_sync: bool = True,
        **kwargs
    ):
        super().__init__(func, name=name, **kwargs)
        self.connectors: Dict[str, str] = connectors
        self.children: Dict[str, Union[SubCommand, SubCommandGroup]] = {}
        self.auto_sync: bool = auto_sync
        self.guild_ids: List[int] = guild_ids
        self.body = SlashCommand(
            name=self.name,
            description=description or '-',
            options=options or [],
            default_permission=default_permission,
        )
    
    def sub_command(
        self,
        name: str = None,
        description: str = None,
        options: list = None,
        connectors: dict = None,
        **kwargs
    ) -> Callable:
        """
        A decorator that creates a subcommand under the base command.

        Parameters
        ----------
        name: :class:`str`
            the name of the subcommand. Defaults to the function name
        description: :class:`str`
            the description of the subcommand
        options: List[:class:`Option`]
            the options of the subcommand for registration in API
        connectors: Dict[:class:`str`, :class:`str`]
            which function param states for each option. If the name
            of an option already matches the corresponding function param,
            you don't have to specify the connectors. Connectors template:
            ``{"option-name": "param_name", ...}``
        
        Returns
        --------
        Callable[..., :class:`SubCommand`]
            A decorator that converts the provided method into a SubCommand, adds it to the bot, then returns it.
        """
        def decorator(func) -> SubCommand:
            if len(self.children) == 0:
                if len(self.body.options) > 0:
                    self.body.options = []
            new_func = SubCommand(
                func,
                name=name,
                description=description,
                options=options,
                connectors=connectors,
                **kwargs
            )
            new_func.qualified_name = f'{self.qualified_name} {new_func.name}'
            self.children[new_func.name] = new_func
            self.body.options.append(new_func.option)
            return new_func
        return decorator

    def sub_command_group(
        self,
        name: str = None,
        **kwargs
    ) -> Callable:
        """
        A decorator that creates a subcommand group under the base command.

        Parameters
        ----------
        name : :class:`str`
            the name of the subcommand group. Defaults to the function name
        
        Returns
        --------
        Callable[..., :class:`SubCommandGroup`]
            A decorator that converts the provided method into a SubCommandGroup, adds it to the bot, then returns it.
        """
        def decorator(func) -> SubCommandGroup:
            if len(self.children) == 0:
                if len(self.body.options) > 0:
                    self.body.options = []
            new_func = SubCommandGroup(func, name=name, **kwargs)
            new_func.qualified_name = f'{self.qualified_name} {new_func.name}'
            self.children[new_func.name] = new_func
            self.body.options.append(new_func.option)
            return new_func
        return decorator

    async def _call_external_error_handlers(self, inter: ApplicationCommandInteraction, error: CommandError) -> None:
        cog = self.cog
        try:
            if cog is not None:
                local = _get_overridden_method(cog.cog_slash_command_error)
                if local is not None:
                    await local(inter, error)
        finally:
            inter.bot.dispatch('slash_command_error', inter, error)

    async def invoke_children(self, inter: ApplicationCommandInteraction):
        chain, kwargs = options_as_route(inter.options)
        
        if len(chain) == 0:
            group = None
            subcmd = None
        elif len(chain) == 1:
            group = None
            subcmd = self.children.get(chain[0])
        elif len(chain) == 2:
            group = self.children.get(chain[0])
            subcmd = group.children.get(chain[1]) if group is not None else None

        if group is not None:
            try:
                await group.invoke(inter)
            except Exception as exc:
                await group._call_local_error_handler(inter, exc)
                raise
        
        if subcmd is not None:
            try:
                await subcmd.invoke(inter, **kwargs)
            except Exception as exc:
                await subcmd._call_local_error_handler(inter, exc)
                raise

    async def invoke(self, inter: ApplicationCommandInteraction):
        await self.prepare(inter)

        try:
            if len(self.children) > 0:
                await self(inter)
                await self.invoke_children(inter)
            else:
                await self(inter, **inter.options)
        except CommandError:
            inter.command_failed = True
            raise
        except asyncio.CancelledError:
            inter.command_failed = True
            return
        except Exception as exc:
            inter.command_failed = True
            raise CommandInvokeError(exc) from exc
        finally:
            if self._max_concurrency is not None:
                await self._max_concurrency.release(inter)

            await self.call_after_hooks(inter)


def slash_command(
    *,
    name: str = None,
    description: str = None,
    options: List[Option] = None,
    default_permission: bool = True,
    guild_ids: List[int] = None,
    connectors: Dict[str, str] = None,
    auto_sync: bool = True,
    **kwargs
) -> Callable:
    """
    A decorator that builds a slash command.

    Parameters
    ----------
    auto_sync: :class:`bool`
        whether to automatically register the command or not. Defaults to ``True``
    name: :class:`str`
        name of the slash command you want to respond to (equals to function name by default).
    description: :class:`str`
        the description of the slash command. It will be visible in Discord.
    options: List[:class:`Option`]
        the list of slash command options. The options will be visible in Discord.
    default_permission: :class:`bool`
        whether the command is enabled by default when the app is added to a guild.
    guild_ids: List[:class:`int`]
        if specified, the client will register a command in these guilds.
        Otherwise this command will be registered globally.
    connectors: Dict[:class:`str`, :class:`str`]
        binds function names to option names. If the name
        of an option already matches the corresponding function param,
        you don't have to specify the connectors. Connectors template:
        ``{"option-name": "param_name", ...}``
    """

    def decorator(func) -> InvokableSlashCommand:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f'<{func.__qualname__}> must be a coroutine function')
        if hasattr(func, '__command_flag__'):
            raise TypeError('Callback is already a command.')
        new_func = InvokableSlashCommand(
            func,
            name=name,
            description=description,
            options=options,
            default_permission=default_permission,
            guild_ids=guild_ids,
            connectors=connectors,
            auto_sync=auto_sync,
            **kwargs
        )
        return new_func
    return decorator
