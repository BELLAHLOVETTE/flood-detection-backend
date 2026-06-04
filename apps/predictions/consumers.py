# apps/predictions/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class RiskUpdateConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        await self.channel_layer.group_add(
            'risk_updates',
            self.channel_name
        )
        await self.accept()
        # Send current risk immediately on connect
        await self.send(text_data=json.dumps({
            'type':        'risk_update',
            'risk_level':  'low',
            'probability': 0.0,
            'assessed_at': None,
            'color':       '#22c55e',
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'risk_updates',
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        # Client can send messages — we ignore them for now
        pass

    async def risk_update(self, event):
        """
        Called when a message is sent to the risk_updates group.
        Forwards the message to the WebSocket client.
        """
        await self.send(text_data=json.dumps({
            'type':        'risk_update',
            'risk_level':  event.get('risk_level',  'low'),
            'probability': event.get('probability', 0.0),
            'assessed_at': event.get('assessed_at', None),
            'color':       event.get('color',       '#22c55e'),
        }))