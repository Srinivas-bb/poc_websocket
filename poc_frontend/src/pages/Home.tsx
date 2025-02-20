import { useState, useEffect, useRef } from 'react'
const url = 'ws://127.0.0.1:8000/ask/'
import q1 from '../assets/images/q1.jpg'
import q2 from '../assets/images/q2.jpg'
import q3 from '../assets/images/q3.jpg'
import q4 from '../assets/images/q4.jpg'
import q5 from '../assets/images/q5.jpg'

interface Message {
  text: string;
  isUser: boolean;
  timestamp: Date;
}

const images = [q1,q2,q3,q4,q5]

export default function Home() {
  const [activeSlide, setactiveSlide] = useState(0)
  const socketRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [isConnected, setisConnected] = useState(false)

  useEffect(() => {
    const socket = new WebSocket(url);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('Connected to WebSocket');
    };

    socket.onmessage = (event: MessageEvent) => {
      const response = JSON.parse(event.data);
      setMessages(prev => [...prev, {
        text: response.answer || response.message || JSON.stringify(response),
        isUser: false,
        timestamp: new Date()
      }]);
    };

    socket.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    socket.onclose = () => {
      console.log('WebSocket connection closed');
    };

    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, []);

  useEffect(() => {
    // Scroll to bottom when new messages arrive
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSendMessage = (question: string) => {
    if (question.trim()) {
      // Add user message to chat
      setMessages(prev => [...prev, {
        text: question,
        isUser: true,
        timestamp: new Date()
      }]);

      // Send message through WebSocket
      socketRef.current?.send(JSON.stringify({ question }));
    }
  };

  const handleClick = (direction: 'left' | 'right') => {
    if (direction === 'left') {
      setisConnected(false)
      setMessages([])
      setactiveSlide(activeSlide > 0 ? activeSlide - 1 : 4)
    } else {
      setisConnected(false)
      setMessages([])
      setactiveSlide(activeSlide < 4 ? activeSlide + 1 : 0)
    }
  }
  const getBase64FromUrl = async (imageUrl: string): Promise<string> => {
    try {
      // Fetch the image
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      
      // Convert blob to base64
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => {
          if (typeof reader.result === 'string') {
            // Remove the data:image/jpeg;base64, prefix if needed
            const base64 = reader.result.split(',')[1];
            resolve(base64);
          }
        };
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
    } catch (error) {
      console.error('Error converting image to base64:', error);
      throw error;
    }
  };
  const handleRequest = async () => {
    try {
        const imageBase64 = await getBase64FromUrl(images[activeSlide]);
        
        socketRef.current?.send(JSON.stringify({ 
          question: 'Help the student answer the questions in the image', 
          image: imageBase64
        }));
        
        setisConnected(true);
      } catch (error) {
        console.error('Error sending image:', error);
      }
  
  }
  return (
    <div className="w-[100vw] h-[100vh] bg-blue-200 grid grid-cols-12">
      <div className="col-span-3 bg-slate-400 relative flex flex-col">
        {/* Chat Cover */}
        { !isConnected && 
        <div>
            <button className='absolute bottom-10 left-1/2 -translate-x-1/2 bg-blue-500 px-10 py-2 text-white text-[20px] text-nowrap rounded-md' onClick={handleRequest}>Request Support</button>
        </div>
        }
        {
            isConnected &&
            <>
            <div 
          ref={chatContainerRef}
          className="flex-1 overflow-y-auto p-4 space-y-4"
          style={{ maxHeight: 'calc(100vh - 60px)' }}
        >
          {messages.map((message, index) => (
            <div 
              key={index} 
              className={`flex ${message.isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div 
                className={`max-w-[80%] p-3 rounded-lg ${
                  message.isUser 
                    ? 'bg-blue-500 text-white rounded-br-none' 
                    : 'bg-white rounded-bl-none'
                }`}
              >
                <p className="text-sm">{message.text}</p>
                <p className="text-xs opacity-70 mt-1">
                  {message.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))}
        </div>
        <div className="h-[60px] border-t border-gray-300">
        <input 
          ref={inputRef}
          type="text" 
          className='w-full h-full bg-white/50 text-[16px] focus:outline-none px-5'
          placeholder='Type your message...'
          onKeyUp={(e) => {
            if (e.key === 'Enter') {
              const input = e.target as HTMLInputElement;
              handleSendMessage(input.value);
              input.value = '';
            }
          }}
        />
      </div>
      </>
        }
      </div>

      <div className="col-span-9 relative flex items-center justify-center">
        <img src={images[activeSlide]} className='absolute h-[100%]' alt="activeSlide" />
        <div 
          onClick={() => handleClick('left')} 
          className='absolute w-[15%] h-[100%] hover:bg-black/10 duration-500 cursor-pointer left-0'
        />
        <div 
          onClick={() => handleClick('right')} 
          className='absolute w-[15%] h-[100%] hover:bg-black/10 duration-500 cursor-pointer right-0'
        />
      </div>
    </div>
  )
}