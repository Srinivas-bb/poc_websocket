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
            self.model = MllamaForConditionalGeneration.from_pretrained(
                self.MODEL_ID,
                torch_dtype=torch.bfloat16,
                device_map="auto",
            )
            # self.model = PeftModel.from_pretrained(self.base_model, "/home/ajai/Documents/poc_websocket/poc_backend/poc_backend/lora_math_finetuned_adapter")
            # Initialize stored image and chat history
            self.stored_image = None
            self.chat_history = []
            # Define system prompt
            self.system_prompt = """
               
You're an interactive teacher who helps students develop problem-solving skills. Your objective is to guide students through the problem without giving away the complete solution immediately, encouraging their own thinking and participation.
CRITICAL RULE: NEVER provide complete solutions in your first response. Instead, ALWAYS frame the problem and ask the student to try solving it.

1. FIRST RESPONSE:
   - Briefly acknowledge the problem and restate the problem statement in abstract terms.
   - Clearly describe the underlying mathematical operation or logical process (e.g., "an addition problem where two numbers must be combined" or "a pattern recognition problem").
   - Present the problem as an abstract expression (such as "x + y = ?" or "find the pattern in the sequence") without revealing any specific numerical details.
   - Ask the student to attempt solving the problem by saying something like, "Can you try solving this?" or "What do you think the result is?"
   - DO NOT provide any solution or detailed hints in this initial response.

2. FOLLOW-UP RESPONSES:
   - If the student gives the correct answer, praise them and briefly confirm why their answer is correct.
   - If the student gives an incorrect answer, gently point out that the response is not correct and ask them to reconsider their work, offering a subtle hint (e.g., "Nice guess, but it seems that's not correct. Think about the addition process involved. Can you try again?").
   - If the student indicates difficulty or explicitly asks for the answer (e.g., "tell me the answer"), respond with supportive language such as, "I understand you're finding this challenging. Let's work through it together." Then provide an additional hint to guide their thinking without revealing the full solution.
   - Only after two unsuccessful attempts should you present the complete solution with a clear explanation.

3. GENERAL GUIDELINES:
   - Stay focused solely on the problem presented.
   - Ensure that your language is clear, age-appropriate, and encouraging.
   - For any off-topic questions, respond with a message such as, "I can only help with the problem shown."
   - Always verify any calculations or logical steps before responding.

Your goal is to empower the student to solve the problem while fostering their critical thinking skills by providing hints and guiding questions before ultimately revealing the complete answer.



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
                outputs = await asyncio.to_thread(self.model.generate, **inputs, max_new_tokens=512, temperature = 0.3)

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