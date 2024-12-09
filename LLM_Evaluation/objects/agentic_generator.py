from autogen import ConversableAgent
import ast
import requests
import json
import time

class SimpleGenerator:
    """A class to generate question-answer pairs using a specified model and API key.

    Attributes:
        model (str): The model to be used for generating questions and answers.
        api_key (str): The API key for authentication.
        number_questions (int): The number of questions to generate.
        format (str): The format the generator should return the question-answer pairs in.
        instruction (str): The instruction for generating questions and answers.
    """
    def __init__(self, model, api_key, number_questions=2):
        """
        Args:
            model (str): The model to be used for generating questions and answers.
            api_key (str): The API key for authentication.
            number_questions (int, optional): The number of questions to generate. Defaults to 2.
        """
        self.model = model
        self.api_key = api_key
        self.number_questions = number_questions
        self.format = "{'question': 'the question', 'answer': 'the answer'}, "
        self.instruction = f"""
        Background:
        In the pharmaceutical industry, process validation is a critical procedure that ensures the safety, quality, and efficacy of drugs. Manufacturers must prove that their production process, including equipment and material used, does not interact with or alter the final drug. Sartorius has been offering corresponding services for more than 30 years. The Validation Services team performs validation testing and provides reports for customers to ensure regulatory compliance.

        Your role:
        You are an expert in the Validation Services division of the pharmaceutical company Sartorius. You hold a PhD in medicine, pharmacy, and biochemistry and possess extensive knowledge of regulatory compliance and quality assurance in the pharmaceutical industry. You are adept at analyzing and interpreting regulatory documents, extractable guides, and scientific research papers in biotech, biology, and pharmacy. Your expertise spans regulatory compliance, quality assurance, and scientific research methodologies in the pharmaceutical industry. 
        
        Instructions:
        !!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        
        Imagine you held a course, where you taught students about your field of expertise.

        !!!!!!!!!!!!!!!!!!!!!!!!!!!!
        You are given a text extract and should generate {self.number_questions} different questions from that text, which relate to a product in the text. The questions don't have to be related to the same product. You should also generate the answers to the questions.

        Your answer is always of exactly the format: "[{self.format * self.number_questions}]"
        """
    
    def generate_question_answer_pair(self, context):
        """Generates question-answer pairs from the given context.

        Args:
            context (str): The text extract from which to generate questions and answers.

        Returns:
            list: A list of dictionaries containing question-answer pairs.

        Raises:
            KeyError: If the 'choices' key is missing or empty in the response.
            HTTPError: If the request to the API fails.
        """
        headers = {"Content-Type": "application/json", 
                   "api-key": self.api_key}
        payload = {
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": "Here is the text:\n" + context}]},
                {"role": "user", "content": [{"type": "text", "text": self.instruction}]}
            ],
            "temperature": 0.7, "top_p": 0.95, "max_tokens": 4096
        }
        GPT4V_ENDPOINT = f"https://appprodsagopenaigpt4weu.openai.azure.com/openai/deployments/{self.model}/chat/completions?api-version=2024-02-15-preview"
        
        # Implemented to handle rate limiting by waiting before retrying and catching HTTP errors.
        while True:
            response = requests.post(GPT4V_ENDPOINT, headers=headers, json=payload)
            if response.status_code == 200:
                response_json = response.json()
                if "choices" in response_json and len(response_json["choices"]) > 0:
                    qa_pair = response_json["choices"][0]["message"]["content"]
                    return ast.literal_eval(qa_pair)
                else:
                    raise KeyError("The 'choices' key is missing or empty in the response.")
            elif response.status_code == 429:
                print("HTTP Error:", response.status_code, "\nRetrying in 60 seconds")
                time.sleep(60)
            else:
                response.raise_for_status()


class AgenticGenerator:
    """A class to generate question-answer pairs using a conversational agent.

    Attributes:
        max_turns (int): The maximum number of turns in the conversation.
        agent_config (dict): The LLM configuration for the conversational agent.
        student_agent (ConversableAgent): The student agent for generating questions and answers.
        teacher_agent (ConversableAgent): The teacher agent for evaluating the student agent.
    """

    def __init__(self, llm_config, max_turns=2):
        """
        Args:
            llm_config (dict): The configuration for the conversational agent.
            max_turns (int, optional): The maximum number of turns in the conversation. Defaults to 2.
        """
        self.max_turns = max_turns
        self.agent_config = llm_config
        self.student_agent = ConversableAgent(
            name="Student_Agent",
            system_message="""
            You are an examiner for text comprehension. You are given a chunk of text and you have to generate a question and answer from the text. Your teacher will rate your reply and you need to (potentially) improve it.
            
            Your answer is always of exactly the format: "{'question': 'the question', 'answer': 'the answer'}"
            """,
            llm_config=self.agent_config,
        )
        self.teacher_agent = ConversableAgent(
            name="Teacher_Agent",
            system_message="""
            You are a teacher for examiners for text comprehension. You will give your student a text and your student should generate a question and answer from the text. Then you rate the reply from 1 to 10 and give advice what to do better in the next iteration.
            """,
            llm_config=self.agent_config,
        )

    def start_chat(self, context):
        """Starts a chat between the teacher and student agents to generate a question-answer pair.

        Args:
            context (str): The text extract from which to generate questions and answers.

        Returns:
            dict: A dictionary containing the question and answer.
        """
        self.chat = self.teacher_agent.initiate_chat(
            self.student_agent,
            message="Here is the text:\n" + context,
            summary_method="last_msg",
            max_turns=self.max_turns,
        )
        return ast.literal_eval(self.chat.chat_history[-1]["content"])