import re
import json
from objects.agentic_generator import AgenticGenerator, SimpleGenerator
from objects.chunk_objects.chunk import Chunk, MarkdownDocument
from objects.chunk_objects.chunk_handler import ChunkHandler

class QAPairGenerator:
    """Generates question-answer pairs from a markdown document.

    Attributes:
        doc_twin (MarkdownDocument): The markdown document to generate QA pairs from.
        chunks (list): List of chunks from the document.
        qa_pairs (list): List of generated QA pairs.
        model (str): The model name for the QA generation.
        api_key (str): The API key for the QA generation.
        llm_config (dict): Configuration for the language model.
    """

    def __init__(self, path_to_document_twin, model_name, api_key):
        """
        Args:
            path_to_document_twin (str): Path to the markdown document.
            model_name (str): The model name for the QA generation.
            api_key (str): The API key for the QA generation.
        """
        self.doc_twin = MarkdownDocument(path_to_document_twin)
        self.chunks = self._chunk_document()
        self.qa_pairs = []
        self.model = model_name
        self.api_key = api_key
        self.llm_config = {"config_list": [{
            "model": model_name,
            "api_key": api_key,
            "base_url": "https://appprodsagopenaigpt4weu.openai.azure.com",
            "api_type": "azure",
            "api_version": "2024-02-15-preview"
        }]}

    def _chunk_document(self):
        """Chunks the document into smaller parts based on predefined criteria.

        Returns:
            list: List of chunks from the document.
        """
        MAX_CHUNK_SIZE = ChunkHandler.RECOMMENDED_MAX_CHUNK_SIZE
        SPLIT_CRITERIA = [
            *ChunkHandler.MARKDOWN_HEADINGS,
            '''
            ChunkHandler.split_by_bold_headers, 
            ChunkHandler.split_by_short_lines_that_might_be_headers, 
            ChunkHandler.hard_split_by_character_number
            '''
        ]
        self.doc_twin.chunks = ChunkHandler.split_document_into_chunks(self.doc_twin, max_chunk_size=MAX_CHUNK_SIZE, split_criteria=SPLIT_CRITERIA, recursive=False)
        return self.doc_twin.chunks

    def generate_qa_pairs(self, number_questions):
        """Generates QA pairs for each chunk in the document.

        Args:
            number_questions (int): Number of questions to generate per chunk.

        Returns:
            list: List of generated QA pairs.
        """
        self.qa_pairs = []
        for i in range(1, len(self.chunks)):
            qa_pairs = self._generate_qa_pair(self.chunks[i].text, number_questions)
            for qa_pair in qa_pairs:
                qa_pair['chunk'] = self.chunks[i].text
                qa_pair['document'] = self.doc_twin.file_name
                qa_pair['path_to_document'] = self.doc_twin.file_path
                self.qa_pairs.append(qa_pair)
        return self.qa_pairs
    
    def _generate_qa_pair(self, section, number_questions):
        """Generates QA pairs for a given section of the document.

        Args:
            section (str): The text section to generate QA pairs from.
            number_questions (int): Number of questions to generate.

        Returns:
            list: List of generated QA pairs.
        """
        simple_generator = SimpleGenerator(self.model, self.api_key, number_questions)
        qa_pair = simple_generator.generate_question_answer_pair(section)
        return qa_pair