import requests
from bs4 import BeautifulSoup
import time

class ProductAIPrompter:
    """A class to interact with the Product AI service.

    Attributes:
        url (str): The URL of the Product AI service.
        headers (dict): The headers to include in the HTTP requests.
    """

    def __init__(self, cookie):
        """
        Args:
            cookie (str): The cookie to use for authentication. Obtained by logging in on the website for ProductAI. Then sending a prompt and inspecting the response headers.
        """
        self.url = "https://app-validation-services-dev.azurewebsites.net/chat"
        self.headers = {
            "Content-Type": "application/json",
            "Cookie": cookie
        }

    def prompt_productai(self, question):
        """Sends a question to the Product AI service and returns the response.

        Args:
            question (str): The question to send to the Product AI service.

        Returns:
            str: The text response from the Product AI service.
        """
        payload = {"message": question, "history": "[{}]", "last_chunks": ""}
        
        # Implemented to avoid rate limiting and catch HTTP errors.
        while True:
            time_start = time.time()
            response = requests.post(self.url, headers=self.headers, json=payload)
            response_time = time.time() - time_start
            if response.status_code == 200:
                response_json = response.json()
                soup = BeautifulSoup(response_json["message"]["html_answer"], "html.parser")
                return soup.get_text(), response_time
            elif response.status_code == 429:
                print("HTTP Error:", response.status_code, "\nRetrying in 20 seconds")
                time.sleep(20)
            elif response.status_code == 500:
                print("HTTP Error:", response.status_code, "\nRetrying in 20 seconds")
                time.sleep(20)
            else:
                response.raise_for_status()
        
        
        