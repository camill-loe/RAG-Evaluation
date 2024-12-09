"""
In this class, we define the Chunk class. The chunk is part of a MarkdownDocument object, which is also defined in this module.
"""
import os
import re
import json
import logging as log
import copy
import string
from objects.utils import utils

class MarkdownDocument:

    def __init__(self, file_path):
        self.file_path = file_path
        self.file_name= os.path.basename(file_path)
        # split file name from extension
        self.file_name, self.file_extension = os.path.splitext(self.file_name)
        self.folder = os.path.dirname(file_path)

        # init title with name of the file
        self.title = self.file_name

        # read the text from specified path (supports markdown and json files)
        # set the text, source metadata, lenght and num_pages of the document
        self._read_file()

        # generate document context
        self._generate_document_context()
        
        # used for compatibility because the chunk class is derived from the document class
        self.page_number = 1
        self.is_merged_chunk = False
        # the document is the level 0 chunk in our chunk hierarchy
        self.chunk_level = 0
        # will be populated later
        self.chunks = None
        self.atom_chunks = None
        

    def _read_file(self):
        """Read the content of the file and set the text, source metadata, length and number of pages of the document."""
        # read markdown files
        if self.file_extension == ".md":
            with open(self.file_path, "r", encoding="utf-8") as file:
                md_content = file.read()
                self.text = md_content
                self.source_metadata = {}
        # read json files
        elif self.file_extension == ".json":
            with open(self.file_path, 'r', encoding="utf-8") as f:
                json_content = json.load(f)
                self.text = json_content['source_content']
                self.title = json_content['source_title']
                self.source_metadata = json_content
        else:
            raise AttributeError(f"Trying to read content from unexpected file type: {self.file_path}")
        
        self._get_page_count()
        self.len = len(self.text)
        

    def _generate_document_context(self):
        """
        The context provides the info about the document.
        It is a list of strings where each string marks a hierarchy level. It could be a product group, type of document, doc title, paragraph etc.. 
        In case of a document, the context in the moment is its title and might be extended by other metadata in the future."""
        self.context = [f'Document: {self.title}']


    def print_chunk_tree(self, text_instead_of_context=False):
        start_of_text = self.text[:100].replace('\n', ' |-> ')
        context = str(self.context).replace('\n', ' --> ')
        print('\t'* self.chunk_level, self.chunk_level, f'(p.{self.page_number}, l.{self.len})', 
              context if not text_instead_of_context else start_of_text)
        if self.chunks is not None:
            for chunk in self.chunks:
                chunk.print_chunk_tree(text_instead_of_context)
     

    def get_atom_chunks(self):
        """Get the chunks that cannot be splitted further as they are already too small to be splitted
        or they do not meet any split criteria. This means, that for a long chunk, we get the sub-chunks instead of the chunk itself!
        But, if the document itself doesn't have any chunks, it should be returned."""
        # if a document does not have chunks, it can be considered itself a chunk
        if self is None:
            stop = True
        if type(self) is MarkdownDocument and len(self.chunks) == 0:
            return [Chunk(self.text, self, self.chunk_level, 0, self.page_number)]

        # Only include chunks that do not have sub-chunks
        # as those with sub-chunks would otherwise repeat
        atom_chunks = [chunk for chunk in self.chunks if len(chunk.chunks) == 0]

        non_atomic_chunks = [chunk for chunk in self.chunks if len(chunk.chunks) > 0]

        # Recursively retrieve sub-chunks
        for sub_chunk in non_atomic_chunks:
            atom_chunks.extend(sub_chunk.get_atom_chunks()) 

        # Sort the atom chunks by page number
        atom_chunks = sorted(atom_chunks, key=lambda x: x.page_number)
            
        return atom_chunks
    

    def get_chunks_of_level(self, level: int, debug=False):
        """Iterate over all chunks and sub-chunks and retrieve a list of all chunks at a specific level."""
        chunks_at_level = []
    
        if self.chunk_level > level:
            if debug: log.warning(f"The current level {self.chunk_level} is already above the requested level {level}. Returning an empty list.")
            return []
        elif self.chunk_level == level:
            if debug: log.warning(f"The current level {self.chunk_level} is equal to the requested level {level}. Returning the current chunk.")
            return [self]
        else:
            for chunk in self.chunks:
                chunks_at_level.extend(chunk.get_chunks_of_level(level))
            return chunks_at_level
        

    def calculate_number_of_chunks_for_each_level(self):
        """Calculate the number of chunks for each level in the chunk hierarchy.
           We start with the document and check if it has chunks. These would be level 1 chunks. 
           Then, we iterate over all level 1 chunks and check if they have sub-chunks. These are level 2 chunks and so on."""
        # TODO: think if recursive approach would be easy to implement and understand
        chunk_counts = {0: 1}
        for level in range(1, 10):
            chunks_at_level = self.get_chunks_of_level(level)
            chunk_counts[level] = len(chunks_at_level)
        return chunk_counts

            
    def _get_page_count(self):
        """Get the number of pages in the document and check if each page is included."""
        # first, get all page markers in the whole markdown document
        page_numbers = re.findall(r'\[PAGE (\d+)\]', self.text)
        # get the page_count as the max page_number identified in the document
        page_count = max([int(page) for page in page_numbers]) if len(page_numbers) > 0 else 1
        # check if all pages are included in the document, from page 1 to page_count
        missing_pages = [page for page in range(1, page_count+1) if f'[PAGE {page}]' not in self.text]
        # log warning if some pages are missing
        if len(missing_pages) > 0:
            log.warning(f"Markdown Document '{self.title}' is missing pages: {missing_pages}")
        self.num_pages = page_count
    
    
    def __str__(self) -> str:
        if type(self) is MarkdownDocument:
            return f"MarkdownDocument: ({self.num_pages} pages, {self.len} chars) {self.title}"
        else:
            return f"Chunk: ({self.len} chars) {self.title}"

    def __repr__(self) -> str:
        return self.__str__()
    
    def display(self):
        print(self.__repr__(), '\n', self.text)



class Chunk(MarkdownDocument):
    def __init__(self, chunk_text:str, parent:MarkdownDocument, level:int, chunk_pos:int, 
                 page_number:int, merged_titles:list=[], title:str=None):
        """
        @param chunk_text: the textual context of the chunk
        @param parent: the parent document the chunk was extracted from
        @param level:  We have a hierarchy of strings to split by defined in split_criteria. 
                       If the doc cannot be splitted by the string of one level, the level is increased until the chunk gets splitted or reaches max level
        @param chunk_pos: specifies the position of the chunk in the parent document (position of the split)
        """
        self.text = chunk_text.strip()
        self.parent = parent
        self.page_number = page_number
        self.chunk_level = level
        self.chunk_pos = chunk_pos
        self.source_metadata = parent.source_metadata
        
        # handle merged chunks
        self.merged_titles = merged_titles
        self.is_merged_chunk = len(merged_titles) > 0

        self.len = len(self.text)
        self.title = title or self._generate_chunk_title_from_first_line()
        self.file_name = parent.file_name
        self.folder = parent.folder

        # self.context = None
        # generate context for the new chunk
        self._generate_chunk_context()
        
        self.chunks = None
        self.json_dict = None
        self.json_string = None


    def __clean_filename(self, filename):
        """
        Replace special characters with "-" or an empty string "".
        """
        special_chars_map = {
            '?': '',
            '\\': '',
            '/': '-',
            '’': '',
            '"': '',
            "'": '',
            '‘': '',
            '”': '',
            '“': '',
            '–': '-',
            '—': '-',
            '(': '- ',
            '*': '',
            '”': '',
            '&': 'and',
            '–': '-',
            ',': ' -',
            ')': ' -',
            '®': '',
            '“': '',
            ':': '-',
            '#': '',
            '/':' or ',
            '®':'',
            '|':'-',
            '[':"",
            ']':""           
        }
        
        mapping = str.maketrans(special_chars_map)
        filename = filename.translate(mapping)

        # replace multiple spaces with a single one
        filename = re.sub(' +', ' ', filename)

        # replace "- -" with "-"
        filename = filename.replace("- -", "-")
        
        return filename
    

    def _generate_chunk_title_from_first_line(self):
        try:
            # replace page markers first
            cleaned_text = re.sub(r'\n*\[PAGE (\d+)\]\n*', '', self.text).strip()
            
            # check if the chunks starts with bold text or one of the hashes indicating titles
            # and in this case, use the first line of the text as title
            if cleaned_text.startswith('#') or cleaned_text.startswith('*'):
                chunk_title = cleaned_text.split('\n', maxsplit=1)[0] if '\n' in cleaned_text else self.parent.title
            else:
                # no title detected in first line, so just use a the title of the parent
                chunk_title = self.parent.title
                rest_of_text = self.text

            # remove the title from the original text 
            # do not use the cleaned text as we would loose the page information
            rest_of_text = self.text.replace(chunk_title, '', 1)
        
        except Exception as ex:
            log.warning(f"Error while extracting chunk title from the chunk text:\n{ex}")
            # some chunks seem to be too short
            chunk_title = self.parent.title
            rest_of_text = self.text

        # TODO: check if a chunk starts with a removed image and in this case use the next line as title
        # # replace special characters
        # chunk_title = chunk_title.replace('#', '')
        # # remove all punctuations
        # chunk_title = ''.join(char for char in chunk_title if char not in string.punctuation)
            
        # do not shorten title. It was only necessary for using it as file name, but we can shorten during path creation
        # if len(chunk_title) > 50: chunk_title = chunk_title[:50]
        self.text = rest_of_text.strip()
        return chunk_title.strip()
    
    
    def _generate_chunk_context(self, include_title=True, include_page_number=True):
        """The context provides the info about the location of the chunk in a given text corpus."""
        # construct the context from the titles of the parent documents and the title of the chunk
        self.context = copy.copy(self.parent.context)

        # only if the title of the chunk contains a hash (is a heading), we add  it to the context together with the page number
        if (self.title.startswith('#') or self.title.startswith('*')) and self.title not in ''.join(self.context):
            title_with_page_nr = self.title + f" (Page Nr. {self.page_number})"
            self.context += [title_with_page_nr]
        
        # # add the title only if it is not yet included in the context
        # # as some chunks do not have a title and use the title of their parent
        # if include_title and self.title.contains('#') and self.title not in ''.join(self.context): 
        #     self.context += [self.title]

        # # add page number to the first context item
        # if include_page_number:
        #     self.context[0] += f" (Page Nr. {self.page_number})"

        
    def generate_json_chunk_with_metadata(self):
        # build the context string from the extended context list
        extended_context = copy.deepcopy(self.context)
        # add page info to first line specifying the document
        # extended_context[0] += f" (Page Nr. {self.page_number})"
        # do not include the last item in the context as its equal to the first line of the chunk
        if len(extended_context) >= 2 : extended_context = extended_context[:-1] 
        context_string = '\n'.join(extended_context)

        metadata = {
            "chunk_title": self.title,
            "chunk_file_name": self.file_name,
            "chunk_page": self.page_number,
            "chunk_length": self.len,
            "chunk_context": context_string,
            "chunk_date_created": utils.get_current_datetime_as_str(str_format="%Y-%m-%d"),
            "chunk_text": self.text,
            "chunk_text_with_context": context_string + '\n\n' + self.title + '\n\n' + self.text 
        }

        # add parent metadata without the content of the whole document
        parent_metadata = copy.deepcopy(self.parent.source_metadata)
        parent_metadata.pop('source_content', None) 
        metadata = {**parent_metadata, **metadata}
        
        self.json_dict = metadata
        self.json_string = json.dumps(metadata, indent=4) 


    def save_chunk(self, dest_folder, as_json, chunk_index, debug=False):
        """Save the chunk to the passed destination folder as json file and as markdown."""

        # if the json chunk has not yet been created so far, do it now
        if as_json and self.json_dict is None:
            log.warning("JSON chunk has not yet been generated so far! Generating now...")
            self.generate_json_chunk_with_metadata()

        # extend the destination folder with a subfolder for the document
        dest_folder = os.path.join(dest_folder, self.file_name)

        # first, create the folder is not yet existing
        os.makedirs(dest_folder, exist_ok=True)

        # generate file_path and create if not existing
        chunk_file_name = f"Chunk{chunk_index}-{self.title[:30].strip()}" + (".md" if not as_json else ".json")
        chunk_file_name = self.__clean_filename(chunk_file_name)
        chunk_save_path = os.path.join(dest_folder, chunk_file_name)

        if debug:
            print('Saving chunk to:\n', chunk_save_path)       

        # generate the chunk content with context ignoring the last context item as it is the title of the chunk
        chunk_with_context = '\n'.join(self.context[:-1])  + '\n\n' + self.text

        with open(chunk_save_path, "w", encoding="utf-8") as file:
            if not as_json:
                file.write(chunk_with_context)
            else:
                json.dump(self.json_dict, file, indent=4)

        # save once again but not as json this time
        if as_json: self.save_chunk(os.path.dirname(dest_folder), as_json=False, chunk_index=chunk_index, debug=debug)


    def print(self, print_whole_text=False, num_chars=500) -> str:
        """Print the chunk context, title and a part of the text."""
        print(self)
        if print_whole_text:
            num_chars = len(self.text)
        print('---', '\n'.join(self.context), '---', sep='\n')
        if num_chars < len(self.text) and not print_whole_text:
            print(f"[NOTE! Printing only the first {num_chars} characters of the text.]")
        print(self.text[:num_chars])
        # print(text)


    def __str__(self) -> str:
        if self.is_merged_chunk:
            return 'Merged Chunk ' + f"(page {self.page_number}, len {self.len}) " + ' + '.join(self.merged_titles)
        return 'Chunk ' + f"(page {self.page_number}, len {self.len}) " + self.title
    


class WebpageChunk(Chunk):
    def __init__(self, chunk_text:str, parent:MarkdownDocument, level:int, chunk_pos:int, page_number):
        super().__init__()
        self.title = self.generate_chunk_title_for_webpage()
        self.context = self.generate_chunk_context_for_webpage()


    def generate_chunk_title_for_webpage(self):
        return self.parent.title
    
    def generate_chunk_context_for_webpage(self):
        return self.parent.context

    