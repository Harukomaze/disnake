from __future__ import annotations
from typing import List, Optional, TYPE_CHECKING

from .base import Interaction

from ..components import ActionRow, Component
from ..utils import cached_slot_property
from ..message import Message

__all__ = (
    'MessageInteraction',
    'MessageInteractionData'
)

if TYPE_CHECKING:
    from ..types.interactions import (
        Interaction as InteractionPayload,
        ComponentInteractionData as ComponentInteractionDataPayload,
        ComponentType
    )
    from ..state import ConnectionState


class MessageInteraction(Interaction):
    """Represents an interaction with a message component.

    Current examples are buttons and dropdowns.

    .. versionadded:: 2.1

    Attributes
    -----------
    id: :class:`int`
        The interaction's ID.
    type: :class:`InteractionType`
        The interaction type.
    guild_id: Optional[:class:`int`]
        The guild ID the interaction was sent from.
    channel_id: Optional[:class:`int`]
        The channel ID the interaction was sent from.
    application_id: :class:`int`
        The application ID that the interaction was for.
    author: Optional[Union[:class:`User`, :class:`Member`]]
        The user or member that sent the interaction.
    message: Optional[:class:`Message`]
        The message that sent this interaction.
    component: :class:`Component`
        The component the user interacted with
    values: Optional[List[:class:`str`]]
        The values the user selected
    token: :class:`str`
        The token to continue the interaction. These are valid
        for 15 minutes.
    data: :class:`MessageInteractionData`
        The wrapped interaction data.
    """

    def __init__(self, *, data: InteractionPayload, state: ConnectionState):
        super().__init__(data=data, state=state)
        self.data = MessageInteractionData(data=data.get('data'))
        self.message = Message(state=self._state, channel=self.channel, data=data['message'])
    
    @property
    def values(self) -> Optional[List[str]]:
        return self.data.values

    @cached_slot_property('_cs_component')
    def component(self) -> Component:
        for action_row in self.message.components:
            if not isinstance(action_row, ActionRow):
                continue
            for component in action_row.children:
                if component.custom_id == self.data.custom_id:
                    return component


class MessageInteractionData:
    """Represents the data of an interaction with a message component.

    .. versionadded:: 2.1

    Attributes
    ----------
    id: :class:`int`
        The application command ID.
    name: :class:`str`
        The application command name.
    type: :class:`ApplicationCommandType`
        The application command type.
    custom_id: :class:`str`
        The custom ID of the component.
    component_type: :class:`ComponentType`
        The type of the component.
    values: Optional[List[:class:`str`]]
        The values the user selected
    """

    __slots__ = (
        'custom_id',
        'component_type',
        'values'
    )

    def __init__(self, *, data: ComponentInteractionDataPayload):
        data = {} if data is None else data
        self.custom_id: str = data.get('custom_id')
        self.component_type: ComponentType = data.get('component_type')
        self.values: Optional[List[str]] = data.get('values')
