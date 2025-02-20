import json
import torch
import asyncio
import base64
import io
from PIL import Image
from channels.generic.websocket import AsyncWebsocketConsumer
from transformers import AutoProcessor, MllamaForConditionalGeneration
from peft import PeftModel


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Handles WebSocket connection and loads the model asynchronously."""
        try:
            self.MODEL_ID = "meta-llama/Llama-3.2-11B-Vision-Instruct"
            # Load processor and model asynchronously
            self.processor = AutoProcessor.from_pretrained(self.MODEL_ID)
            self.base_model = MllamaForConditionalGeneration.from_pretrained(
                self.MODEL_ID,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            self.model = PeftModel.from_pretrained(self.base_model, "/home/ajai/Documents/poc_websocket/poc_backend/poc_backend/lora_math_finetuned_adapter")
            # Initialize stored image and chat history
            self.stored_image = None
            self.chat_history = []
            # Define system prompt
            self.system_prompt = """
                You're an interactive teacher who helps students learn problem-solving skills. Your goal is to guide students through problems while encouraging their own thinking.

CRITICAL RULE: NEVER provide complete solutions in your first response. Instead, ALWAYS frame the problem and ask the student to try solving it.

Follow these strict guidelines:

1. FIRST RESPONSE MUST ONLY:
   - Briefly acknowledge the problem
   - Frame the problem clearly (e.g., "the problem statement for the given problem")
   - For math problems, state the equation format (e.g., "x + y = ? , or x -y = ? where x and y could be problem dependent")
   - provide the problem in mathematical expression and ask the student to try solve it : "so can you try what's x + y?" or "what pattern do you think comes?" like a follow up question that engages the student to give a guess for the problem statement we explained .
   - STOP after this question (DO NOT PROCEED TO SOLUTION)

2. Follow-up responses:
   - If student gives correct answer: Praise them and confirm why it's correct
   - If student gives incorrect answer: Gently point out where they went wrong without revealing answer !important
   - If student says "I don't know" or asks for the answer: Encourage with "Let's try together" and give a hint
   - Only after 2 failed attempts: Provide the solution with clear explanation

3. General principles:
   - Stay focused on the specific problem shown
   - Respond with "I can only help with the problem shown" for off-topic questions
   - Make sure explanations are age-appropriate and encouraging
   - For successful solutions, offer similar practice problems if requested

Example of CORRECT first response:
" so we need to add the given two numbers in order to find the solution. Can you try to add the numbers { number1 } and { number 2} ." like that breifly recollecing problem and engaing student.

Example of INCORRECT first response (never do this):
"Let's solve this step by step. Nick bought 10 crayons and 6 markers. Adding these: 10 + 6 = 16 items. The answer is 16."

CRITICAL: Always verify mathematical calculations before responding! 
    - For addition problems: Add the numbers and check the result exactly
    - NEVER praise incorrect answers
    - If student says 30 + 6 = 15, you MUST point out this is incorrect (as 30 + 6 = 36)

Remember: Your goal is to support student learning while respecting that they've come to you for specific help.


            """
            
            await self.accept()
        except Exception as e:
            print(f"Error in connect: {e}")
            await self.close()

    async def disconnect(self, code):
        """Handles WebSocket disconnection."""
        print(f'Closing WebSocket with code {code}')
        await self.close()

    async def receive(self, text_data):
        """Handles incoming messages, extracts image & text, and manages chat history."""
        if text_data:
            try:
                data = json.loads(text_data)
                question = data.get('question', '')
                image_base64 = data.get('image', '')

                # If an image is received, store it and reset chat history
                if image_base64:
                    image_bytes = base64.b64decode(image_base64)
                    self.stored_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                    self.chat_history = []  # Reset chat history for new image
                    await self.send(json.dumps({"status": "Image stored and chat history reset"}))
                    return

                # If a question is received, process with chat history
                if question and self.stored_image:
                    asyncio.create_task(self.process_and_respond(question))
                elif question and not self.stored_image:
                    await self.send(json.dumps({"error": "No image available for processing"}))
            except Exception as e:
                print(f"Error in receive: {e}")
                await self.send(json.dumps({"error": "Invalid request"}))

    async def process_and_respond(self, question):
        """Processes the question with chat history and generates a response."""
        try:
            # Start with system message
            messages = [{"role": "system", "content": self.system_prompt}]
            
            # Add chat history (text-only) if it exists
            for entry in self.chat_history:
                messages.append(entry)
            
            # Add current question with image only for the current turn
            current_message = {
                "role": "user",
                "content": [{"type": "image"}, {"type": "text", "text": question}]
            }
            messages.append(current_message)

            input_text = self.processor.apply_chat_template(messages, add_generation_prompt=True)
            # Prepare model inputs
            inputs = self.processor(
                images=[self.stored_image],
                text=input_text,
                return_tensors="pt"
            ).to(self.model.device)

            # Run model inference in a separate thread
            with torch.no_grad():
                outputs = await asyncio.to_thread(self.model.generate, **inputs, max_new_tokens=512, temperature = 0.5)

            # Decode and clean the output
            answer = self.processor.decode(outputs[0], skip_special_tokens=True)
            answer = answer.split('assistant')[-1] if 'assistant' in answer else answer

            # Store only text in chat history
            self.chat_history.append({"role": "student", "content": question})
            self.chat_history.append({"role": "model", "content": answer})

            # Send response back to client
            await self.send(json.dumps({"answer": answer}))

        except Exception as e:
            print(f"Error in process_and_respond: {e}")
            await self.send(json.dumps({"error": "Processing failed"}))