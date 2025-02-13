import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try: 
            await self.accept()
        except Exception as e:
            await self.close()
    async def disconnect(self, code):
        try: 
            print('closing with code', code)
            await self.close()
        except Exception as e :
            print(e)
    async def receive(self, text_data):
        if text_data:
            data = json.loads(text_data)
            question = data.get('question', '')
            answer = f'The Answer to {question}'
            await self.send(text_data=json.dumps({
                'answer': answer
            }))