import os
import google.generativeai as genai
import logging
import json

logger = logging.getLogger("TrafficAI-Chat")

class ChatService:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found. Chatbot will return mocked responses.")
            self.model = None
        else:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-flash-latest')
                logger.info("Gemini API configured successfully.")
            except Exception as e:
                logger.error(f"Failed to configure Gemini API: {e}")
                self.model = None

    def get_response(self, user_query, traffic_context):
        """
        Generates a response using Gemini based on the user query and traffic context.
        """
        if not self.model:
            return "I'm sorry, but I can't connect to my brain right now (Gemini API Key missing). Please check the server logs."

        try:
            # Construct System Prompt
            system_prompt = self._construct_prompt(traffic_context)
            
            # Full Prompt
            full_prompt = f"{system_prompt}\n\nUser Question: {user_query}\nAnswer:"
            
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I encountered an error while processing your request. Please try again later."

    def _construct_prompt(self, data):
        """
        Creates a context-rich prompt from the traffic data.
        """
        total = data.get('total_vehicles', 0)
        locations = data.get('locations', [])
        
        loc_summaries = []
        for loc in locations:
            name = loc.get('name', 'Unknown')
            count = loc.get('total', 0)
            intensity = loc.get('intensity', 'unknown').upper()
            loc_summaries.append(f"- {name}: {count} vehicles ({intensity})")
            
        loc_text = "\n".join(loc_summaries)
        
        prompt = f"""
You are TrafficAI, an intelligent assistant for specific smart city traffic traffic monitoring system.
Here is the real-time traffic data for Kochi, India:

Global Status:
- Total Vehicles Detected across all sensors: {total}

Location Specifics:
{loc_text}

Instructions:
1. Answer the user's question concisely based strictly on the above data.
2. If the user asks about traffic conditions, cite specific numbers and locations.
3. If a location is 'CONGESTION' or 'HIGH', warn the user.
4. Keep the tone professional, helpful, and futuristic.
5. If the answer is not in the data, say you don't have that information.
"""
        return prompt
